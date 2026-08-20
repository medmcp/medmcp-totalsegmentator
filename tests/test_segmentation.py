"""Tests for segment_anatomy's validation, output layout and failure reporting.

Inference itself is never run: it needs a GPU, multi-gigabyte weights and minutes per
volume. The subprocess boundary is the seam — faking it exercises everything this
package is actually responsible for (what it asks the model to do, what it writes, and
what it reports back) without touching TotalSegmentator.
"""

import csv
import json
import subprocess
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pytest

from medmcp_totalsegmentator.tools import segmentation
from medmcp_totalsegmentator.tools.segmentation import segment_anatomy


@pytest.fixture
def volume(tmp_path: Path) -> Path:
    """A stand-in NIfTI file. Never parsed — inference is faked."""
    path = tmp_path / "sub-01_ct.nii.gz"
    path.write_bytes(b"not-a-real-nifti")
    return path


def _fake_run(
    captured: dict[str, Any],
    *,
    returncode: int = 0,
    stderr: str = "",
    write_statistics: bool = True,
) -> Any:
    """Build a subprocess.run stand-in that plays back a TotalSegmentator run."""

    def run(cmd: Sequence[str], **_: Any) -> subprocess.CompletedProcess[str]:
        request_file, result_file = Path(cmd[-2]), Path(cmd[-1])
        request = json.loads(request_file.read_text())
        captured["request"] = request
        if returncode == 0:
            output = Path(request["output"])
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_bytes(b"segmentation")
            stats_path = request.get("statistics_path")
            if stats_path and write_statistics:
                Path(stats_path).write_text(
                    json.dumps(
                        {
                            "liver": {"volume": 1500.0, "intensity": 55.2},
                            "spleen": {"volume": 200.0, "intensity": 48.0},
                            "aorta": {"volume": 0.0, "intensity": 0.0},
                        }
                    )
                )
            result_file.write_text(json.dumps({"output": str(output), "structures_written": []}))
        return subprocess.CompletedProcess(list(cmd), returncode, "", stderr)

    return run


def test_missing_input_raises(tmp_path: Path) -> None:
    """A path that does not exist fails before anything is spawned."""
    with pytest.raises(FileNotFoundError):
        segment_anatomy(tmp_path / "nope.nii.gz")


def test_license_gated_task_is_refused(volume: Path) -> None:
    """A gated task is refused with its reason, not attempted."""
    with pytest.raises(ValueError, match="license"):
        segment_anatomy(volume, task="tissue_types")


def test_structures_rejected_on_a_focused_task(volume: Path) -> None:
    """``structures`` is only meaningful for the whole-body tasks."""
    with pytest.raises(ValueError, match="only works with the whole-body tasks"):
        segment_anatomy(volume, task="liver_segments", structures=["liver"])


def test_unknown_structure_names_are_rejected(volume: Path) -> None:
    """A misspelled structure fails fast rather than silently segmenting nothing."""
    with pytest.raises(ValueError, match="left kidney"):
        segment_anatomy(volume, task="total", structures=["left kidney"])


def test_successful_run_writes_multilabel_labels_and_volumes(
    volume: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The default run produces one labelled volume plus its two lookup CSVs."""
    captured: dict[str, Any] = {}
    monkeypatch.setattr(subprocess, "run", _fake_run(captured))
    out = tmp_path / "derivatives"

    result = segment_anatomy(volume, output_dir=out, device="cpu")

    assert result["output_kind"] == "multilabel"
    assert result["segmentation_path"] == str(out / "sub-01_ct_dseg.nii.gz")
    assert Path(result["segmentation_path"]).is_file()
    assert result["num_structures"] == 117
    assert result["device"] == "cpu"

    labels = Path(result["labels_path"] or "")
    rows = list(csv.reader(labels.read_text().splitlines()))
    assert rows[0] == ["label", "structure"]
    assert rows[1] == ["1", "spleen"]
    assert len(rows) == 118  # header + 117 structures

    volumes = Path(result["volumes_path"] or "")
    vrows = list(csv.DictReader(volumes.read_text().splitlines()))
    assert vrows[0].keys() >= {"structure", "volume_mm3", "intensity_mean"}
    names = {row["structure"] for row in vrows}
    assert names == {"liver", "spleen"}, "zero-volume structures should be dropped"


def test_request_payload_matches_the_requested_options(
    volume: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Tool arguments are translated into TotalSegmentator's own vocabulary."""
    captured: dict[str, Any] = {}
    monkeypatch.setattr(subprocess, "run", _fake_run(captured))

    segment_anatomy(volume, task="total", structures=["liver"], speed="fast", device="cpu")

    request = captured["request"]
    assert request["task"] == "total"
    assert request["roi_subset"] == ["liver"]
    assert request["fast"] is True and request["fastest"] is False
    assert request["device"] == "cpu"
    assert request["multilabel"] is True


def test_cuda_device_is_translated_to_totalsegmentator_spelling(
    volume: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Our 'cuda' is upstream's 'gpu'; getting this wrong silently runs on CPU."""
    captured: dict[str, Any] = {}
    monkeypatch.setattr(subprocess, "run", _fake_run(captured))

    result = segment_anatomy(volume, device="cuda")

    assert captured["request"]["device"] == "gpu"
    assert result["device"] == "cuda"


def test_separate_masks_mode_targets_a_directory(
    volume: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Per-structure output goes to a directory and skips the label lookup."""
    captured: dict[str, Any] = {}
    monkeypatch.setattr(subprocess, "run", _fake_run(captured))

    result = segment_anatomy(volume, separate_masks=True, device="cpu")

    assert result["output_kind"] == "separate_masks"
    assert result["segmentation_path"].endswith("sub-01_ct_seg")
    assert captured["request"]["multilabel"] is False
    assert result["labels_path"] is None


def test_cpu_run_warns_about_runtime(volume: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Falling back to CPU is never silent — it changes runtime by an order of magnitude."""
    monkeypatch.setattr(subprocess, "run", _fake_run({}))

    result = segment_anatomy(volume, device="cpu")

    assert any("CPU" in warning for warning in result["warnings"])


def test_failure_surfaces_the_subprocess_stderr(
    volume: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A failed run reports why, quoting the tail of the child's stderr."""
    monkeypatch.setattr(
        subprocess,
        "run",
        _fake_run({}, returncode=1, stderr="torch.OutOfMemoryError: CUDA out of memory"),
    )

    with pytest.raises(RuntimeError, match="CUDA out of memory"):
        segment_anatomy(volume, device="cpu")


def test_volumes_csv_is_skipped_when_not_requested(
    volume: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``compute_volumes=False`` asks for no statistics and writes no CSV."""
    captured: dict[str, Any] = {}
    monkeypatch.setattr(subprocess, "run", _fake_run(captured))

    result = segment_anatomy(volume, compute_volumes=False, device="cpu")

    assert captured["request"]["statistics_path"] is None
    assert result["volumes_path"] is None


def test_render_hint_is_present_and_mentions_warnings() -> None:
    """The _render contract drives how the agent reports the result."""
    assert "_render" in segmentation.SegmentationResult.__annotations__
