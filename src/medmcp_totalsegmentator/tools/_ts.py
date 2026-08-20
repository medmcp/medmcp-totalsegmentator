"""Shared helpers for the TotalSegmentator tools.

Deliberately free of heavy imports at module scope: the MCP server imports this at
start-up, and the agent gives a stack only a few seconds to answer "what tools do you
have" before dropping it for the whole session. torch and TotalSegmentator are
imported lazily inside the functions that need them (and, for inference itself, only
ever inside the :mod:`_run_totalseg` subprocess).
"""

from collections.abc import Callable
from pathlib import Path
from typing import Any, Literal, cast

Device = Literal["auto", "cuda", "mps", "cpu"]
Speed = Literal["standard", "fast", "fastest"]
Modality = Literal["CT", "MR"]

# 1st-percentile intensity at or below this means the volume carries Hounsfield
# units (air is about -1000 HU), which only a CT does. Chosen well clear of 0 so a
# background-subtracted MR cannot reach it, and well above -1000 so an already
# cropped or partially masked CT still trips it.
_CT_HU_THRESHOLD: float = -300.0

# Slices sampled along the through-plane axis when sniffing modality. Enough to be
# representative, few enough that a whole-body CT is not fully decompressed just to
# answer "is this a CT?".
_MODALITY_SAMPLE_SLICES: int = 16


def nii_stem(path: Path) -> str:
    """Return a NIfTI filename stem with both ``.nii`` and ``.nii.gz`` removed.

    Args:
        path: Path to a NIfTI file.

    Returns:
        The bare filename stem (e.g. ``sub-01_ct.nii.gz`` -> ``sub-01_ct``).
    """
    stem = path.name
    for suffix in (".nii.gz", ".nii"):
        if stem.endswith(suffix):
            return stem[: -len(suffix)]
    return path.stem


def detect_devices() -> list[str]:
    """Return the compute devices torch reports as usable, best first.

    Returns:
        Some subset of ``["cuda", "mps", "cpu"]``; ``"cpu"`` is always present.
    """
    devices: list[str] = []
    try:
        import torch
    except ImportError:  # pragma: no cover - torch is a hard dependency
        return ["cpu"]
    if torch.cuda.is_available():
        devices.append("cuda")
    mps = getattr(getattr(torch, "backends", None), "mps", None)
    if mps is not None and bool(mps.is_available()):
        devices.append("mps")
    devices.append("cpu")
    return devices


def resolve_device(device: Device) -> str:
    """Resolve a requested compute device to a concrete one (the shared device convention).

    ``"auto"`` selects the best available accelerator -- CUDA, then MPS, then CPU;
    an explicit device is returned unchanged. Tools run on, and report, the
    *resolved* device so an ``"auto"`` -> CPU fallback is never silent.

    Args:
        device: ``"auto"``, or an explicit ``"cuda"`` / ``"mps"`` / ``"cpu"``.

    Returns:
        A concrete device string (``"cuda"``, ``"mps"``, or ``"cpu"``).
    """
    if device != "auto":
        return device
    available = detect_devices()
    if "cuda" in available:
        return "cuda"
    if "mps" in available:
        return "mps"
    return "cpu"


def to_totalseg_device(resolved: str) -> str:
    """Translate our device convention into TotalSegmentator's.

    TotalSegmentator spells the CUDA device ``"gpu"``; ``"cpu"`` and ``"mps"`` match.

    Args:
        resolved: A concrete device from :func:`resolve_device`.

    Returns:
        The device string TotalSegmentator's python API expects.
    """
    return "gpu" if resolved == "cuda" else resolved


def cuda_unavailable_note() -> str:
    """Return an actionable note if a CUDA-capable torch is installed but CUDA is unavailable.

    Returns:
        Human-readable note, or an empty string when CUDA works or is absent by design.
    """
    try:
        import torch
    except ImportError:  # pragma: no cover - torch is a hard dependency
        return ""
    if torch.cuda.is_available():
        return ""
    # torch.version isn't in torch's type stubs; reach it via getattr so strict
    # pyright stays happy (the attribute is the documented way to read the build).
    cuda_ver: str | None = getattr(getattr(torch, "version", None), "cuda", None)
    if cuda_ver is None:
        return "CPU-only torch is installed, so GPU inference is not possible."
    return (
        "torch is built for CUDA but no GPU is visible -- the container may be missing "
        "'--device nvidia.com/gpu=all'. Running on CPU instead (much slower)."
    )


def sniff_modality(path: Path) -> Modality | None:
    """Guess whether a NIfTI volume is CT or MR from its intensity distribution.

    CT stores Hounsfield units, so air reads about -1000; MR intensities are
    essentially non-negative. That difference is reliable enough to catch the common
    mistake of pointing a CT task at an MR scan (or the reverse), which otherwise
    produces a plausible-looking but meaningless segmentation.

    Only a subset of slices is read, so this stays cheap on whole-body volumes.
    Returns ``None`` rather than guessing when the distribution fits neither shape --
    the caller warns, and never blocks, on the result.

    Args:
        path: Path to a NIfTI volume.

    Returns:
        ``"CT"``, ``"MR"``, or ``None`` when the evidence is ambiguous.
    """
    try:
        import nibabel as nib
        import numpy as np

        # nib.load is annotated as returning a bare FileBasedImage, which declares
        # neither .shape nor .dataobj.
        load_image = cast(Callable[[str], Any], nib.load)  # pyright: ignore[reportUnknownMemberType]
        img = load_image(str(path))
        shape: tuple[int, ...] = tuple(int(dim) for dim in img.shape)
        if len(shape) < 3:
            return None
        step = max(1, shape[2] // _MODALITY_SAMPLE_SLICES)
        sample: Any = np.asarray(img.dataobj[:, :, ::step], dtype="float32")
    except Exception:
        # Modality sniffing is advisory. An unreadable or unusual volume is the
        # segmentation tool's problem to report, not this helper's.
        return None
    if sample.size == 0:
        return None
    low = float(np.percentile(sample, 1))
    if low <= _CT_HU_THRESHOLD:
        return "CT"
    if low >= -10.0 and float(sample.max()) > 0.0:
        return "MR"
    return None


def modality_warning(input_path: Path, task: str, expected: Modality) -> str | None:
    """Warn when the input's apparent modality contradicts the task's.

    Args:
        input_path: The volume about to be segmented.
        task: The task name, for the message.
        expected: The modality the task was trained on.

    Returns:
        A warning string, or ``None`` when the modality matches or is unclear.
    """
    observed = sniff_modality(input_path)
    if observed is None or observed == expected:
        return None
    return (
        f"Input looks like {observed} (from its intensity range) but task {task!r} is "
        f"trained on {expected} images, so the segmentation is likely meaningless. "
        f"Pass a {expected} volume, or choose a {observed} task -- "
        "list_segmentation_tasks reports the modality of each."
    )
