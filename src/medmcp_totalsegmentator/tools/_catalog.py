"""Which TotalSegmentator tasks this stack exposes, and why the rest are not.

TotalSegmentator ships ~53 segmentation tasks under three different licenses. This
module is the single choke point where that policy is applied: **only tasks whose
pretrained weights are Apache-2.0 are reachable**, and their weights are baked into
the container image so segmentation runs with ``--network none``.

Three groups are deliberately excluded:

* **License-gated tasks** (``tissue_types``, ``brain_structures``, ``face``, …).
  Upstream flags these in ``map_to_binary.commercial_models``; their weights are
  served from a license backend rather than GitHub, and a license number is free
  for non-commercial use but paid for commercial use. Bundling them would put
  weights we may not redistribute into the image.
* **``brain_aneurysm``** — CC BY-NC 4.0 with *no* commercial license available.
  This one is a trap: it is **not** in ``commercial_models``, so upstream's
  ``requires_license()`` returns ``False`` for it. Filtering on that predicate alone
  would quietly pull a non-commercial model into an otherwise Apache-2.0 image, so
  it is named explicitly here.
* **Tasks whose weights are not published** — ``total_v3`` is listed in the registry
  but its ``v3.0.0-weights`` release does not exist yet (every asset URL 404s), and
  the internal ``test`` tasks have no usable weights either.

The task list, class maps and dataset ids all come from upstream's own pure-data
modules (``registry``, ``map_to_binary``, ``map_tasks_config``), which import neither
torch nor any model weights — so this module stays cheap enough to import at MCP
server start-up, keeping tool discovery inside the agent's start-up budget.
"""

from collections.abc import Callable
from typing import Any, Literal, TypedDict, cast

from totalsegmentator.map_tasks_config import TASK_CONFIGS as _RAW_TASK_CONFIGS
from totalsegmentator.map_tasks_config import TASK_ID_WEIGHTS_CONFIGS as _RAW_WEIGHTS
from totalsegmentator.registry import TASKS as _RAW_TASKS
from totalsegmentator.registry import (
    get_task_classes as _raw_get_task_classes,  # pyright: ignore[reportUnknownVariableType]
)
from totalsegmentator.registry import (
    requires_license as _raw_requires_license,  # pyright: ignore[reportUnknownVariableType]
)
from totalsegmentator.registry import (
    task_modality as _raw_task_modality,  # pyright: ignore[reportUnknownVariableType]
)

Modality = Literal["CT", "MR"]

# Upstream's helpers are untyped (their parameters infer as Unknown). Bind them to
# explicit signatures once, here, so every call site downstream is checked against a
# real contract; the ignores are the cost of that, confined to these three lines.
_get_task_classes = cast(Callable[[str], dict[int, str]], _raw_get_task_classes)
_requires_license = cast(Callable[[str], bool], _raw_requires_license)
_task_modality = cast(Callable[[str], Modality], _raw_task_modality)

# Upstream ships no type stubs; narrow its pure-data maps once, here, rather than
# casting at every read site.
_TASKS: tuple[str, ...] = tuple(_RAW_TASKS)
_TASK_CONFIGS: dict[str, dict[str, Any]] = cast(dict[str, dict[str, Any]], _RAW_TASK_CONFIGS)
_WEIGHTS_CONFIGS: dict[int, dict[str, Any]] = cast(dict[int, dict[str, Any]], _RAW_WEIGHTS)

# --- exclusion policy ----------------------------------------------------------
# Reason strings are user-facing: they are what the agent relays when someone asks
# for a structure only an excluded task can produce, so each says what to do next.

_NON_COMMERCIAL: dict[str, str] = {
    "brain_aneurysm": (
        "weights are CC BY-NC 4.0 with no commercial license available, so they are "
        "not bundled in this Apache-2.0 image"
    ),
}

_WEIGHTS_UNPUBLISHED: dict[str, str] = {
    "total_v3": (
        "upstream has not published the v3.0.0 weights release yet; use 'total', "
        "which segments the same 117 classes"
    ),
    "test": "internal upstream test task, not a real model",
    "total_highres_test": "internal upstream test task, not a real model",
}

_LICENSED_REASON = (
    "requires a TotalSegmentator license number (free for non-commercial use, paid "
    "for commercial use); its weights are not Apache-2.0 and are not bundled here"
)

# The GitHub release that serves every Apache-2.0 weights archive.
_WEIGHTS_BASE_URL = "https://github.com/wasserth/TotalSegmentator/releases/download"

# Models TotalSegmentator fetches at *run* time on top of the requested task's own
# weights, so they have to be baked in too or the first call fails with the network
# disabled. Most tasks first run a coarse "total" pass to crop the field of view
# (298 at 6 mm for CT, 852 at 3 mm for MR, 297 when robust cropping is asked for),
# a body model when cropping to body_trunc/body_extremities (300), and
# vertebrae_pp_refined additionally pulls the vertebrae_body model (305).
# Each of these currently also belongs to a bundled task, so the set below is
# usually a no-op -- it is here so that stops being a coincidence: dropping 'body'
# from the catalogue would otherwise silently break cropping for a dozen tasks.
_AUXILIARY_DATASET_IDS: frozenset[int] = frozenset({297, 298, 300, 305, 852})


def _excluded() -> dict[str, str]:
    """Map every non-exposed task to the reason it is not available."""
    reasons: dict[str, str] = {}
    for task in _TASKS:
        if task in _WEIGHTS_UNPUBLISHED:
            reasons[task] = _WEIGHTS_UNPUBLISHED[task]
        elif task in _NON_COMMERCIAL:
            reasons[task] = _NON_COMMERCIAL[task]
        elif _requires_license(task):
            reasons[task] = _LICENSED_REASON
    return reasons


EXCLUDED_TASKS: dict[str, str] = _excluded()
"""Task name -> why this stack does not offer it (user-facing)."""

BUNDLED_TASKS: tuple[str, ...] = tuple(t for t in _TASKS if t not in EXCLUDED_TASKS)
"""Every task this stack exposes, in upstream's own ordering. All Apache-2.0."""


class TaskInfo(TypedDict):
    """Summary of one bundled segmentation task."""

    task: str
    modality: Modality
    num_structures: int
    structures: list[str]


def is_bundled(task: str) -> bool:
    """Whether *task* is exposed by this stack (Apache-2.0 and weights baked in)."""
    return task in BUNDLED_TASKS


def structures_for(task: str) -> list[str]:
    """Return the anatomical structure names *task* outputs, in label order.

    Raises:
        KeyError: if *task* is unknown to TotalSegmentator.
    """
    classes = _get_task_classes(task)
    return [classes[idx] for idx in sorted(classes)]


def task_info(task: str) -> TaskInfo:
    """Return the full description of a bundled *task*.

    Raises:
        ValueError: if *task* is unknown, or is excluded by the license policy.
    """
    if task in EXCLUDED_TASKS:
        raise ValueError(f"Task {task!r} is not available in this stack: {EXCLUDED_TASKS[task]}.")
    if task not in BUNDLED_TASKS:
        raise ValueError(f"Unknown task {task!r}. Available tasks: {', '.join(BUNDLED_TASKS)}.")
    structures = structures_for(task)
    return {
        "task": task,
        "modality": _task_modality(task),
        "num_structures": len(structures),
        "structures": structures,
    }


def structure_index() -> dict[str, list[str]]:
    """Map every structure name to the bundled tasks that produce it.

    Several tasks segment the same structure at different quality/scope (e.g. the
    kidney cysts inside ``total`` versus the dedicated ``kidney_cysts`` model), so
    the value is a list, ordered as :data:`BUNDLED_TASKS`.
    """
    index: dict[str, list[str]] = {}
    for task in BUNDLED_TASKS:
        for structure in structures_for(task):
            index.setdefault(structure, []).append(task)
    return index


def weight_dataset_ids() -> list[int]:
    """Return every nnU-Net dataset id the bundled tasks need, sorted.

    This is what the container build downloads. A task may map to several ids: the
    default ``total`` model is five part-models plus separate 3 mm and 6 mm models
    for ``speed="fast"`` / ``"fastest"``, and all of them have to be present for the
    stack to work offline.
    """
    ids: set[int] = set(_AUXILIARY_DATASET_IDS)
    pending: list[str] = list(BUNDLED_TASKS)
    seen: set[str] = set()
    while pending:
        task = pending.pop()
        if task in seen:
            continue
        seen.add(task)
        config = _TASK_CONFIGS.get(task, {})
        # A few tasks crop using another task's model (teeth crops with
        # craniofacial_structures); follow that reference so its weights come along.
        crop_model = config.get("crop_model")
        if isinstance(crop_model, str):
            pending.append(crop_model)
        sub_modes = cast(dict[str, dict[str, Any]], config.get("sub_modes", {}))
        sources: list[dict[str, Any]] = list(sub_modes.values()) if sub_modes else [config]
        for source in sources:
            task_id = source.get("task_id", config.get("task_id"))
            if task_id is None:
                continue
            if isinstance(task_id, list):
                ids.update(cast(list[int], task_id))
            else:
                ids.add(cast(int, task_id))
    return sorted(ids)


def weight_urls() -> list[str]:
    """Return the download URL of every bundled weights archive.

    Used by the container build and by the licensing test, which asserts that every
    URL points at the public GitHub release rather than the license backend.

    Raises:
        KeyError: if a required dataset id has no weights configuration upstream.
    """
    urls: list[str] = []
    for dataset_id in weight_dataset_ids():
        config = _WEIGHTS_CONFIGS.get(dataset_id)
        if config is None:
            raise KeyError(f"No weights configuration for dataset id {dataset_id}.")
        urls.append(f"{_WEIGHTS_BASE_URL}/{config['version']}/{config['foldername']}.zip")
    return urls
