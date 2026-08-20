"""Tests for the discovery tools."""

import pytest

from medmcp_totalsegmentator.tools.catalog import (
    find_structures,
    list_segmentation_tasks,
    list_task_structures,
)


def test_listing_reports_every_bundled_task() -> None:
    """The listing covers the catalogue and carries modality and counts."""
    listing = list_segmentation_tasks()
    names = [row["task"] for row in listing["tasks"]]
    assert listing["num_tasks"] == len(listing["tasks"])
    assert "total" in names and "total_mr" in names
    assert all(row["modality"] in ("CT", "MR") for row in listing["tasks"])
    assert all(row["num_structures"] > 0 for row in listing["tasks"])


def test_listing_hides_licensed_tasks() -> None:
    """Tasks needing a license never appear in the listing."""
    names = {row["task"] for row in list_segmentation_tasks()["tasks"]}
    assert "tissue_types" not in names
    assert "brain_aneurysm" not in names


def test_task_structures_are_in_label_order() -> None:
    """Structure order is the multilabel label order, which callers rely on."""
    result = list_task_structures("total")
    assert result["modality"] == "CT"
    assert result["num_structures"] == len(result["structures"]) == 117
    assert result["structures"][0] == "spleen"


def test_excluded_task_raises_with_the_reason() -> None:
    """Asking for a gated task explains why, rather than failing opaquely."""
    with pytest.raises(ValueError, match="license"):
        list_task_structures("tissue_types")


def test_unknown_task_raises() -> None:
    """An unknown task name is rejected."""
    with pytest.raises(ValueError, match=r"not available|Unknown task"):
        list_task_structures("definitely_not_a_task")


def test_find_structures_maps_anatomy_to_tasks() -> None:
    """A structure search reports every bundled task producing it."""
    found = find_structures("liver")
    matched = {row["structure"] for row in found["matches"]}
    assert "liver" in matched
    liver = next(row for row in found["matches"] if row["structure"] == "liver")
    assert "total" in liver["tasks"]


def test_find_structures_normalises_separators_and_case() -> None:
    """'left kidney', 'kidney-left' and 'kidney_left' are the same query."""
    spellings = ("kidney_left", "kidney-left", "kidney left", "KIDNEY_LEFT")
    results = [{row["structure"] for row in find_structures(q)["matches"]} for q in spellings]
    assert all("kidney_left" in names for names in results)


def test_find_structures_reports_license_gated_matches_separately() -> None:
    """A structure only a gated model produces is surfaced with its reason.

    Silently returning "no match" would be actively misleading: the structure does
    exist upstream, and the user needs to know why it is unavailable here.
    """
    found = find_structures("subcutaneous_fat")
    assert found["matches"] == []
    assert any("tissue_types" in entry for entry in found["unavailable"])
    assert any("license" in entry for entry in found["unavailable"])


def test_find_structures_with_no_match_anywhere() -> None:
    """A nonsense query returns empty results rather than raising."""
    found = find_structures("zzzznotanatomy")
    assert found["matches"] == []
    assert found["unavailable"] == []
    assert found["num_matches"] == 0
