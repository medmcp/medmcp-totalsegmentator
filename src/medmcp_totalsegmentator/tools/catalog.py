"""Discovery tools: which tasks exist, what they segment, and where a structure lives.

TotalSegmentator offers ~800 distinct structure names spread over dozens of tasks, and
picking the wrong task is the single easiest way to get a confident, meaningless
answer. These tools let the agent resolve "segment the liver" to a concrete task
before running anything, and they are cheap -- everything here is read from
upstream's pure-data registry, with no model load and no file access.
"""

from typing import TypedDict

from medmcp_totalsegmentator.tools import _catalog

# A structure search that matches half the catalogue is not an answer. Above this
# many hits we report the count and ask for a narrower query instead.
_MAX_MATCHES: int = 40


class TaskSummary(TypedDict):
    """One row of the task listing."""

    task: str
    modality: str
    num_structures: int


class TaskListing(TypedDict):
    """Every segmentation task this stack can run."""

    tasks: list[TaskSummary]
    num_tasks: int
    _render: str


class TaskStructures(TypedDict):
    """The structures one task produces, in label order."""

    task: str
    modality: str
    num_structures: int
    structures: list[str]
    _render: str


class StructureMatch(TypedDict):
    """One structure name and the tasks that produce it."""

    structure: str
    tasks: list[str]


class StructureSearch(TypedDict):
    """Result of searching the catalogue for a structure."""

    query: str
    matches: list[StructureMatch]
    num_matches: int
    unavailable: list[str]
    _render: str


def list_segmentation_tasks() -> TaskListing:
    """List every segmentation task available in this stack, with its modality.

    Use this to choose a task before calling ``segment_anatomy``. ``total`` (CT) and
    ``total_mr`` (MR) are the general whole-body models; the rest are focused models
    that either cover anatomy the whole-body models omit, or segment it more
    accurately. Every task listed here runs fully offline.

    Returns:
        One entry per task with its name, imaging modality and structure count.
    """
    tasks: list[TaskSummary] = []
    for name in _catalog.BUNDLED_TASKS:
        info = _catalog.task_info(name)
        tasks.append(
            {
                "task": name,
                "modality": info["modality"],
                "num_structures": info["num_structures"],
            }
        )
    return {
        "tasks": tasks,
        "num_tasks": len(tasks),
        "_render": (
            "DISPLAY RULES -- follow exactly:\n"
            "Render 'tasks' as a markdown table with columns Task | Modality | "
            "Structures. Keep upstream ordering.\n"
            "NEXT ACTION: Ask which task to run, or -- if the user named an anatomical "
            "structure rather than a task -- call find_structures with that name "
            "instead of guessing a task from this table."
        ),
    }


def list_task_structures(task: str) -> TaskStructures:
    """List the exact structure names a segmentation task produces, in label order.

    The names are also the label ordering of a multilabel segmentation (label 1 is
    the first name, and so on) and the exact spellings ``segment_anatomy`` accepts in
    its ``structures`` argument, so match them verbatim -- ``kidney_left``, not
    "left kidney".

    Args:
        task: A task name from ``list_segmentation_tasks``.

    Returns:
        The task's modality and its structures in label order.

    Raises:
        ValueError: if the task is unknown or is not available in this stack.
    """
    info = _catalog.task_info(task)
    return {
        "task": task,
        "modality": info["modality"],
        "num_structures": info["num_structures"],
        "structures": info["structures"],
        "_render": (
            "DISPLAY RULES -- follow exactly:\n"
            "If the user asked for specific structures, report only those. Otherwise "
            "summarise by group rather than listing all <num_structures> names.\n"
            "NEXT ACTION: Offer to run segment_anatomy on this task. These are the "
            "exact spellings its 'structures' argument requires."
        ),
    }


def find_structures(query: str) -> StructureSearch:
    """Find which segmentation tasks produce a given anatomical structure.

    Matches any structure whose name contains *query* (case-insensitive, and ``_`` and
    ``-`` and spaces are interchangeable), so "left kidney", "kidney_left" and "kidney"
    all work. This is the tool to reach for when the user names anatomy rather than a
    task -- several tasks segment the same structure at different scope and quality,
    and this shows all of them.

    Structures that only a license-gated or non-commercial model can produce are
    reported separately under ``unavailable``, with the reason, rather than silently
    omitted.

    Args:
        query: All or part of a structure name.

    Returns:
        Matching structures with the tasks producing them, plus any matches this stack
        cannot run.
    """
    needle = query.strip().lower().replace("-", "_").replace(" ", "_")
    index = _catalog.structure_index()

    matches: list[StructureMatch] = [
        {"structure": structure, "tasks": tasks}
        for structure, tasks in sorted(index.items())
        if needle in structure.lower()
    ]

    unavailable: list[str] = []
    for excluded, reason in sorted(_catalog.EXCLUDED_TASKS.items()):
        try:
            structures = _catalog.structures_for(excluded)
        except KeyError:  # pragma: no cover - registry and task list agree
            continue
        hits = [name for name in structures if needle in name.lower()]
        if hits:
            shown = ", ".join(hits[:5]) + (" ..." if len(hits) > 5 else "")
            unavailable.append(f"{excluded} ({shown}) -- {reason}")

    truncated = matches[:_MAX_MATCHES]
    return {
        "query": query,
        "matches": truncated,
        "num_matches": len(matches),
        "unavailable": unavailable,
        "_render": (
            "DISPLAY RULES -- follow exactly:\n"
            "If 'matches' is empty and 'unavailable' is empty, say no structure matches "
            "and suggest a broader query (e.g. 'kidney' rather than 'left renal cortex').\n"
            "Otherwise list each match as '<structure> -- available from: <tasks>'. If "
            "num_matches exceeds the number shown, say so and suggest a narrower query.\n"
            "Always relay 'unavailable' entries verbatim when present: those structures "
            "exist upstream but this stack cannot produce them, and the user needs the "
            "reason to decide what to do.\n"
            "NEXT ACTION: Recommend one task and offer to run segment_anatomy with it. "
            "Prefer 'total'/'total_mr' for a general request, and a focused task when "
            "the user asked specifically about the anatomy it specialises in."
        ),
    }
