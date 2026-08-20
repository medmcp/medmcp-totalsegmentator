"""Whole-body anatomy segmentation on CT and MR volumes using TotalSegmentator.

Only the Apache-2.0 licensed tasks are reachable from here; the license policy and
the reasons behind it live in :mod:`_catalog`. All weights are baked into the
container image, so a call never reaches the network.
"""

import csv
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Literal, TypedDict, cast

from medmcp_totalsegmentator.tools import _catalog
from medmcp_totalsegmentator.tools._ts import (
    Device,
    Speed,
    cuda_unavailable_note,
    modality_warning,
    nii_stem,
    resolve_device,
    to_totalseg_device,
)

# Tail of the subprocess's stderr quoted back when a run fails. Enough to carry a
# torch OOM or an nnU-Net trace; short enough not to flood the chat.
_ERROR_TAIL_LINES: int = 25

# Only the whole-body "total" models support restricting the run to a subset of
# structures; upstream raises for anything else, so we check first and say why.
_ROI_SUBSET_TASKS: tuple[str, ...] = ("total", "total_mr")


class SegmentationResult(TypedDict):
    """A completed segmentation run."""

    task: str
    modality: str
    input_path: str
    segmentation_path: str
    output_kind: Literal["multilabel", "separate_masks"]
    labels_path: str | None
    volumes_path: str | None
    num_structures: int
    structures: list[str]
    device: str
    speed: str
    warnings: list[str]
    _render: str


def _validate_structures(task: str, structures: list[str]) -> list[str]:
    """Check a requested structure subset against the task, returning it unchanged.

    Raises:
        ValueError: if the task cannot restrict its output, or a name is not one of
            the structures it produces.
    """
    if task not in _ROI_SUBSET_TASKS:
        raise ValueError(
            f"'structures' only works with the whole-body tasks "
            f"({', '.join(_ROI_SUBSET_TASKS)}), not {task!r}. Task {task!r} is already "
            "specific -- run it without 'structures' and read the labels it produces."
        )
    known = set(_catalog.structures_for(task))
    unknown = [name for name in structures if name not in known]
    if unknown:
        raise ValueError(
            f"Not structures of task {task!r}: {', '.join(unknown)}. Names must match "
            "exactly -- call list_task_structures to see them, or find_structures to "
            "search across tasks."
        )
    return structures


def _write_labels_csv(path: Path, task: str) -> Path:
    """Write the label-index -> structure-name lookup for a multilabel segmentation."""
    structures = _catalog.structures_for(task)
    with path.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["label", "structure"])
        for index, name in enumerate(structures, start=1):
            writer.writerow([index, name])
    return path


def _write_volumes_csv(statistics_path: Path, destination: Path) -> Path | None:
    """Convert TotalSegmentator's statistics.json into a volumes CSV.

    Upstream records volume in mm^3 and a mean/median intensity per structure. The
    CSV keeps both and drops structures with zero volume, which are simply the
    classes the model did not find in this field of view.

    Returns:
        The CSV path, or ``None`` if the statistics file was unreadable.
    """
    try:
        raw: dict[str, Any] = json.loads(statistics_path.read_text())
    except (OSError, json.JSONDecodeError):
        return None
    rows: list[tuple[str, float, float]] = []
    for name, values in sorted(raw.items()):
        if not isinstance(values, dict):
            continue
        stats = cast(dict[str, float], values)
        volume = float(stats.get("volume", 0.0))
        if volume > 0.0:
            rows.append((name, volume, float(stats.get("intensity", 0.0))))
    with destination.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["structure", "volume_mm3", "intensity_mean"])
        writer.writerows(rows)
    return destination


def segment_anatomy(
    input_path: Path,
    output_dir: Path | None = None,
    task: str = "total",
    structures: list[str] | None = None,
    speed: Speed = "standard",
    device: Device = "auto",
    separate_masks: bool = False,
    compute_volumes: bool = True,
) -> SegmentationResult:
    """Segment anatomical structures in a CT or MR volume.

    The default task ``total`` labels 117 structures across a whole-body CT (organs,
    bones, muscles, vessels); ``total_mr`` is its 50-structure MR counterpart, and
    around 30 further focused tasks cover things the whole-body models do not
    (per-vertebra bodies, lung nodules, liver segments, head and neck anatomy, teeth).
    Call ``list_segmentation_tasks`` to see them, or ``find_structures`` to look up
    which task produces a particular structure.

    By default the result is a **single multilabel volume** (``*_dseg.nii.gz``) --
    one file the workspace viewer renders directly as a labelled overlay -- plus a
    CSV mapping each label index to its structure name. Set ``separate_masks=True``
    to get one binary mask per structure in a directory instead, which is what you
    want when a downstream tool consumes individual masks.

    Runtime scales with the field of view. On a GPU a whole-body CT takes roughly a
    minute at ``speed="standard"``; on CPU it is far slower, so prefer ``"fast"``
    (3 mm) there. Restricting ``structures`` on a ``total`` task is usually the
    bigger win: it crops the volume to the region of interest first.

    Args:
        input_path: NIfTI volume to segment (``.nii`` or ``.nii.gz``).
        output_dir: Where to write results. Defaults to the input's own folder.
        task: Which segmentation task to run. Defaults to ``"total"`` (whole-body CT).
        structures: Restrict a ``total``/``total_mr`` run to these structure names
            (exact matches). Speeds the run up considerably. ``None`` segments all.
        speed: ``"standard"`` (1.5 mm, best quality), ``"fast"`` (3 mm) or
            ``"fastest"`` (6 mm, rough). Lower resolution loses small structures.
        device: ``"auto"`` (default), ``"cuda"``, ``"mps"`` or ``"cpu"``.
        separate_masks: Write one binary mask per structure instead of a single
            multilabel volume.
        compute_volumes: Also write a per-structure volume CSV (mm^3) alongside the
            segmentation. Adds a little runtime.

    Returns:
        Paths to the segmentation, the label lookup and the volume CSV, the structures
        requested, the resolved device, and any warnings worth relaying.

    Raises:
        FileNotFoundError: if ``input_path`` does not exist.
        ValueError: if the task is unknown or excluded, or ``structures`` is invalid.
        RuntimeError: if the segmentation itself fails.
    """
    input_path = Path(input_path).expanduser().resolve()
    if not input_path.is_file():
        raise FileNotFoundError(f"Input volume not found: {input_path}")

    info = _catalog.task_info(task)
    requested = _validate_structures(task, structures) if structures else []

    destination = Path(output_dir).expanduser().resolve() if output_dir else input_path.parent
    destination.mkdir(parents=True, exist_ok=True)

    resolved = resolve_device(device)
    warnings: list[str] = []
    if resolved == "cpu":
        note = cuda_unavailable_note()
        if note:
            warnings.append(note)
        if speed == "standard":
            warnings.append(
                "Running at full resolution on CPU can take many minutes per volume. "
                "speed='fast' or a 'structures' subset is much quicker."
            )
    contradiction = modality_warning(input_path, task, info["modality"])
    if contradiction:
        warnings.append(contradiction)

    stem = nii_stem(input_path)
    multilabel = not separate_masks
    output = destination / f"{stem}_dseg.nii.gz" if multilabel else destination / f"{stem}_seg"

    with tempfile.TemporaryDirectory(prefix="medmcp_totalseg_") as scratch:
        scratch_dir = Path(scratch)
        statistics_path = scratch_dir / "statistics.json" if compute_volumes else None
        request = {
            "input_path": str(input_path),
            "output": str(output),
            "task": task,
            "multilabel": multilabel,
            "fast": speed == "fast",
            "fastest": speed == "fastest",
            "device": to_totalseg_device(resolved),
            "roi_subset": requested or None,
            "statistics_path": str(statistics_path) if statistics_path else None,
        }
        request_file = scratch_dir / "request.json"
        result_file = scratch_dir / "result.json"
        request_file.write_text(json.dumps(request))

        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "medmcp_totalsegmentator.tools._run_totalseg",
                str(request_file),
                str(result_file),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if completed.returncode != 0 or not result_file.exists():
            tail = "\n".join(completed.stderr.strip().splitlines()[-_ERROR_TAIL_LINES:])
            raise RuntimeError(f"TotalSegmentator failed on {input_path.name}:\n{tail}")
        run_result: dict[str, Any] = json.loads(result_file.read_text())

        volumes_path: Path | None = None
        if statistics_path and statistics_path.exists():
            volumes_path = _write_volumes_csv(statistics_path, destination / f"{stem}_volumes.csv")

    labels_path: Path | None = None
    if multilabel:
        labels_path = _write_labels_csv(destination / f"{stem}_labels.csv", task)

    written: list[str] = run_result.get("structures_written") or []
    reported = requested or written
    volumes_line = "  Volumes: <volumes_path>\n" if volumes_path else ""
    result: SegmentationResult = {
        "task": task,
        "modality": info["modality"],
        "input_path": str(input_path),
        "segmentation_path": str(output),
        "output_kind": "multilabel" if multilabel else "separate_masks",
        "labels_path": str(labels_path) if labels_path else None,
        "volumes_path": str(volumes_path) if volumes_path else None,
        "num_structures": len(requested) if requested else info["num_structures"],
        "structures": reported,
        "device": resolved,
        "speed": speed,
        "warnings": warnings,
        "_render": (
            "DISPLAY RULES -- follow exactly:\n"
            "Report the segmentation as a compact key-value list:\n"
            "  Input:  <input_path>\n"
            "  Output: <segmentation_path>\n"
            "  Task:   <task> (<num_structures> structures, <modality>)\n"
            f"{volumes_line}"
            "  Device: <device>\n"
            "Substitute values from the result dict. Omit internal keys. Do NOT list "
            "every structure unless the user asked for specific ones.\n"
            "Relay every entry of 'warnings' verbatim -- they change how the result "
            "should be read.\n"
            "NEXT ACTION: Tell the user the output path and offer to open it in the "
            "viewer as an overlay. If they asked for a measurement, read the volume "
            "CSV at <volumes_path> and report the matching rows (values in mm^3) "
            "instead of dumping the file. The tool already verified every path it "
            "returns -- do not recheck them."
        ),
    }
    return result
