"""Declare what a tool does to the user's data, for the approval card in MedMCP.

Pass the result to the tool's registration::

    mcp.add_tool(list_segmentation_tasks, **tool_effect("read_only"))

The level travels in ``tools/list`` twice: as ``_meta["org.medmcp/effect"]``, which
the MedMCP core reads, and as the standard MCP annotations, which other MCP clients
understand. A tool registered without it carries neither.
"""

from typing import Any, Literal, TypedDict, get_args

from mcp.types import ToolAnnotations

Effect = Literal["read_only", "writes_new", "destructive"]
"""``read_only``: reads its inputs, writes nothing.
``writes_new``: writes output files; may re-create its own earlier outputs on a re-run,
never changes the user's files.
``destructive``: deletes, moves or changes files the user brought (inputs, a dataset)."""

EFFECT_META_KEY = "org.medmcp/effect"

_ANNOTATIONS: dict[str, tuple[bool, bool]] = {
    # effect: (readOnlyHint, destructiveHint)
    "read_only": (True, False),
    "writes_new": (False, False),
    "destructive": (False, True),
}


class ToolEffect(TypedDict):
    """Keyword arguments for ``FastMCP.add_tool`` / ``FastMCP.tool``."""

    annotations: ToolAnnotations
    meta: dict[str, Any]


def tool_effect(effect: Effect) -> ToolEffect:
    """Return the registration arguments that declare a tool's effect.

    Args:
        effect: ``"read_only"``, ``"writes_new"`` or ``"destructive"``.

    Returns:
        ``annotations`` and ``meta`` for ``mcp.add_tool(fn, **tool_effect(...))``.

    Raises:
        ValueError: For any other value — at registration, so a typo fails at import.
    """
    if effect not in get_args(Effect):
        allowed = ", ".join(get_args(Effect))
        raise ValueError(f"unknown tool effect {effect!r}; use one of: {allowed}")
    read_only, destructive = _ANNOTATIONS[effect]
    return ToolEffect(
        annotations=ToolAnnotations(readOnlyHint=read_only, destructiveHint=destructive),
        meta={EFFECT_META_KEY: effect},
    )
