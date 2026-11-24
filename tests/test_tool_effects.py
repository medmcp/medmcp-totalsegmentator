"""Every tool declares its effect for MedMCP's approval card.

The tools are listed through a real MCP client session (in memory), so the test
sees what the core sees: ``_meta["org.medmcp/effect"]`` and the matching
``readOnlyHint`` / ``destructiveHint``. ``server.py`` registers each effect; a
change of one shows up here as a diff.
"""

import anyio
import pytest
from mcp.shared.memory import create_connected_server_and_client_session
from mcp.types import Tool

from medmcp_totalsegmentator.effects import EFFECT_META_KEY, Effect
from medmcp_totalsegmentator.server import mcp

EXPECTED: dict[str, Effect] = {
    "segment_anatomy": "writes_new",
    "list_segmentation_tasks": "read_only",
    "list_task_structures": "read_only",
    "find_structures": "read_only",
}

# effect: (readOnlyHint, destructiveHint)
_HINTS: dict[str, tuple[bool, bool]] = {
    "read_only": (True, False),
    "writes_new": (False, False),
    "destructive": (False, True),
}


def _listed_tools() -> dict[str, Tool]:
    """The tools as an MCP client lists them (tools/list over a session)."""

    async def run() -> list[Tool]:
        async with create_connected_server_and_client_session(mcp._mcp_server) as client:  # pyright: ignore[reportPrivateUsage]
            return (await client.list_tools()).tools

    return {tool.name: tool for tool in anyio.run(run)}


def test_every_listed_tool_is_pinned() -> None:
    """A new tool must get its effect decided here, not go without one."""
    assert set(_listed_tools()) == set(EXPECTED)


@pytest.mark.parametrize("name", sorted(EXPECTED))
def test_tool_declares_its_effect(name: str) -> None:
    """The effect in ``_meta`` and the two hints that follow from it."""
    tool = _listed_tools()[name]
    effect = EXPECTED[name]
    assert tool.meta == {EFFECT_META_KEY: effect}
    assert tool.annotations is not None
    read_only, destructive = _HINTS[effect]
    assert tool.annotations.readOnlyHint is read_only
    assert tool.annotations.destructiveHint is destructive
