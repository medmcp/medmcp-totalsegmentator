"""Subprocess entry point that runs one TotalSegmentator inference.

Segmentation runs out-of-process for three reasons:

1. **The stdio JSON-RPC stream must stay clean.** TotalSegmentator prints to stdout
   unconditionally -- a citation banner, progress lines, and a one-off "sends anonymous
   usage statistics" notice that ignores ``quiet=True``. In-process, any of those would
   be interleaved into the MCP framing and corrupt the session.
2. **Start-up stays fast.** The MCP server never imports torch or nnU-Net, so tool
   discovery answers immediately instead of racing the agent's start-up budget.
3. **A crash or OOM kills one call, not the server.**

Invoked as ``python -m medmcp_totalsegmentator.tools._run_totalseg <request> <result>``,
both JSON files. Diagnostics go to stderr, which the parent relays on failure.

Excluded from pyright: TotalSegmentator, nnU-Net and torch ship no type stubs.
"""

import contextlib
import json
import sys
from pathlib import Path


def _silence_usage_stats() -> None:
    """Turn off TotalSegmentator's telemetry before anything can send it.

    The container build already writes ``send_usage_stats: false`` into the config,
    but this stack also runs host-native during development, where the config is
    whatever the developer's home directory happens to hold. Upstream offers no
    environment-variable kill switch, so the config key is the only lever -- and
    ``statistics_disclaimer_shown`` has to be set too, because the disclaimer is
    printed on first run regardless of ``quiet``.

    Best-effort: a failure here must not stop a segmentation the user asked for.
    Network egress is blocked in the container anyway, so this is the belt to that
    braces rather than the only defence.
    """
    try:
        from totalsegmentator.config import get_config_key, set_config_key, setup_totalseg

        setup_totalseg()
        if get_config_key("send_usage_stats") is not False:
            set_config_key("send_usage_stats", False)
        if not get_config_key("statistics_disclaimer_shown"):
            set_config_key("statistics_disclaimer_shown", True)
    except Exception as exc:  # pragma: no cover - defensive
        print(f"warning: could not disable usage statistics: {exc}", file=sys.stderr)


def _written_structures(output: Path, multilabel: bool) -> list[str]:
    """Report which structure masks landed on disk (separate-mask mode only)."""
    if multilabel or not output.is_dir():
        return []
    names: list[str] = []
    for path in sorted(output.glob("*.nii.gz")):
        names.append(path.name[: -len(".nii.gz")])
    return names


# How far from the edge a structure counts as cut off by the field of view: upstream's
# ``touches_border`` checks the outer three slices on every side.
_BORDER_SLICES = 3


def border_structures(output: Path, multilabel: bool, task: str) -> set[str]:
    """Structures with voxels in the outer slices of the volume, i.e. cut off by it.

    The same rule as upstream's ``touches_border``, but read off the six edge slabs
    at once instead of per structure.
    """
    import nibabel as nib
    import numpy as np

    def edge_values(data: "np.ndarray") -> set[int]:
        n = _BORDER_SLICES
        slabs = (data[:n], data[-n:], data[:, :n], data[:, -n:], data[:, :, :n], data[:, :, -n:])
        return {int(v) for slab in slabs for v in np.unique(slab)} - {0}

    if multilabel:
        from totalsegmentator.map_to_binary import class_map

        names: dict[int, str] = class_map.get(task, {})
        data = np.asarray(nib.load(output).dataobj)
        return {names[i] for i in edge_values(data) if i in names}
    cut: set[str] = set()
    for path in sorted(output.glob("*.nii.gz")):
        if edge_values(np.asarray(nib.load(path).dataobj) > 0):
            cut.add(path.name[: -len(".nii.gz")])
    return cut


def _mark_border_structures(
    statistics_path: Path, output: Path, multilabel: bool, task: str
) -> None:
    """Add ``at_border`` to every structure in the statistics file."""
    stats = json.loads(statistics_path.read_text())
    cut = border_structures(output, multilabel, task)
    for name, values in stats.items():
        if isinstance(values, dict):
            values["at_border"] = name in cut
    statistics_path.write_text(json.dumps(stats))


def main() -> int:
    """Run one segmentation described by the request file. Returns a process exit code."""
    if len(sys.argv) != 3:
        print("usage: _run_totalseg <request.json> <result.json>", file=sys.stderr)
        return 2
    request_path, result_path = Path(sys.argv[1]), Path(sys.argv[2])
    request = json.loads(request_path.read_text())

    _silence_usage_stats()

    from totalsegmentator.python_api import totalsegmentator

    output = Path(request["output"])
    multilabel = bool(request["multilabel"])
    statistics_path = request.get("statistics_path")

    # Everything TotalSegmentator prints goes to stderr, so the parent can surface it
    # in an error message without it ever reaching a stdout the MCP framing owns.
    with contextlib.redirect_stdout(sys.stderr):
        totalsegmentator(
            input=Path(request["input_path"]),
            output=output,
            task=request["task"],
            ml=multilabel,
            fast=bool(request["fast"]),
            fastest=bool(request["fastest"]),
            device=request["device"],
            roi_subset=request.get("roi_subset"),
            statistics=Path(statistics_path) if statistics_path else False,
            # A structure cut off by the field of view keeps its measured volume
            # (upstream reports 0); _mark_border_structures flags it instead.
            statistics_exclude_masks_at_border=False,
            body_seg=bool(request.get("body_seg", False)),
            force_split=bool(request.get("force_split", False)),
            quiet=True,
            skip_saving=False,
        )

    if statistics_path and Path(statistics_path).exists():
        _mark_border_structures(Path(statistics_path), output, multilabel, request["task"])

    result = {
        "output": str(output),
        "structures_written": _written_structures(output, multilabel),
        "statistics_path": statistics_path
        if statistics_path and Path(statistics_path).exists()
        else None,
    }
    result_path.write_text(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
