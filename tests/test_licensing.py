"""The license policy is the reason this stack can be redistributed — so it is tested.

Every weight baked into the published image has to be Apache-2.0. That property is
easy to break by accident: upstream adds tasks in most releases, and the obvious
filter (upstream's own ``requires_license()``) is not sufficient on its own.
"""

from collections.abc import Callable
from typing import cast

from totalsegmentator.map_to_binary import commercial_models
from totalsegmentator.registry import TASKS
from totalsegmentator.registry import (
    requires_license as _raw_requires_license,  # pyright: ignore[reportUnknownVariableType]
)

from medmcp_totalsegmentator.tools import _catalog

# Upstream is untyped; bind an explicit signature so the assertions are checked.
requires_license = cast(Callable[[str], bool], _raw_requires_license)

_PUBLIC_WEIGHTS_PREFIX = "https://github.com/wasserth/TotalSegmentator/releases/download/"


def test_no_bundled_task_requires_a_license() -> None:
    """No exposed task may be one of upstream's license-gated models."""
    gated = [task for task in _catalog.BUNDLED_TASKS if requires_license(task)]
    assert gated == [], f"license-gated tasks leaked into the catalogue: {gated}"


def test_every_commercial_model_is_excluded() -> None:
    """Every task upstream flags as commercial is excluded, with a reason."""
    for task in commercial_models:
        assert task in _catalog.EXCLUDED_TASKS, f"{task} is license-gated but exposed"
        assert _catalog.EXCLUDED_TASKS[task], f"{task} is excluded without a reason"


def test_brain_aneurysm_is_excluded_despite_not_being_flagged_commercial() -> None:
    """The CC BY-NC model must be excluded even though ``requires_license`` is False.

    ``brain_aneurysm`` is CC BY-NC 4.0 with no commercial license available, yet it is
    absent from ``commercial_models``. Filtering on ``requires_license()`` alone would
    pull a non-commercial model into an Apache-2.0 image — this test is here so that
    stays impossible rather than merely currently-true.
    """
    assert not requires_license("brain_aneurysm"), (
        "upstream now flags brain_aneurysm as commercial; the explicit exclusion in "
        "_catalog may be redundant, but verify before removing it"
    )
    assert "brain_aneurysm" in _catalog.EXCLUDED_TASKS
    assert "CC BY-NC" in _catalog.EXCLUDED_TASKS["brain_aneurysm"]


def test_every_task_is_either_bundled_or_excluded_with_a_reason() -> None:
    """A task upstream adds must land in exactly one bucket, never silently vanish."""
    for task in TASKS:
        bundled = task in _catalog.BUNDLED_TASKS
        excluded = task in _catalog.EXCLUDED_TASKS
        assert bundled != excluded, f"{task} is neither bundled nor excluded (or both)"
        if excluded:
            assert _catalog.EXCLUDED_TASKS[task].strip(), f"{task} excluded without a reason"


def test_all_weights_come_from_the_public_release_not_the_license_backend() -> None:
    """Every baked archive is a public GitHub release asset.

    License-gated weights are served from the TotalSegmentator license backend
    instead, so a URL pointing anywhere else is the signal that a gated model has
    crept into the build.
    """
    urls = _catalog.weight_urls()
    assert urls, "no weights resolved"
    for url in urls:
        assert url.startswith(_PUBLIC_WEIGHTS_PREFIX), f"non-public weights URL: {url}"


def test_auxiliary_crop_models_are_baked() -> None:
    """The coarse models used for cropping must be present or offline runs break.

    These never appear in the task list, so nothing else would catch their loss —
    but without them, most focused tasks fail on their first call with the network
    disabled.
    """
    ids = set(_catalog.weight_dataset_ids())
    for dataset_id in (297, 298, 300, 305, 852):
        assert dataset_id in ids, f"auxiliary crop model {dataset_id} is not baked"


def test_bundled_tasks_all_resolve_to_weights() -> None:
    """Every bundled task maps to at least one downloadable dataset id."""
    ids = set(_catalog.weight_dataset_ids())
    assert len(ids) >= len(_catalog.BUNDLED_TASKS), "fewer weight datasets than tasks"
    for task in _catalog.BUNDLED_TASKS:
        assert _catalog.structures_for(task), f"{task} produces no structures"
