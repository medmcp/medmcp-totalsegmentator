"""The README's task table must match what the stack actually offers.

The table is the first thing a reader uses to decide whether this stack does what
they need, and it is hand-written prose next to machine-generated truth. Upstream
adds tasks in most releases, so without this the table silently drifts into
advertising models that are not installed, or omitting ones that are.
"""

import re
from pathlib import Path

from medmcp_totalsegmentator.tools import _catalog

README = Path(__file__).resolve().parent.parent / "README.md"

# Rows look like: | `task_name` | CT | 117 | description |
# Task names are not all lowercase -- e.g. lung_vessels_LEGACY.
_ROW = re.compile(r"^\|\s*`([A-Za-z0-9_]+)`\s*\|\s*(CT|MR)\s*\|\s*(\d+)\s*\|", re.MULTILINE)


def _table_rows() -> dict[str, tuple[str, int]]:
    """Parse the Available tasks table into {task: (modality, num_structures)}."""
    text = README.read_text()
    start = text.index("## Available tasks")
    end = text.index("## Skill inventory", start)
    return {m[1]: (m[2], int(m[3])) for m in _ROW.finditer(text[start:end])}


def test_readme_lists_every_available_task() -> None:
    """No task the stack offers is missing from the table."""
    missing = sorted(set(_catalog.BUNDLED_TASKS) - _table_rows().keys())
    assert missing == [], f"tasks missing from the README table: {missing}"


def test_readme_lists_no_unavailable_task() -> None:
    """The table never advertises a task this stack cannot run."""
    extra = sorted(_table_rows().keys() - set(_catalog.BUNDLED_TASKS))
    assert extra == [], f"README table lists tasks that are not installed: {extra}"


def test_readme_modalities_and_counts_are_accurate() -> None:
    """Modality and structure counts match the catalogue, not a stale hand edit."""
    for task, (modality, count) in sorted(_table_rows().items()):
        info = _catalog.task_info(task)
        assert modality == info["modality"], f"{task}: README says {modality}"
        assert count == info["num_structures"], (
            f"{task}: README says {count} structures, catalogue says {info['num_structures']}"
        )
