"""MCP server entrypoint for medmcp-totalsegmentator."""

from importlib.resources import files as _pkg_files

from mcp.server.fastmcp import FastMCP

from medmcp_totalsegmentator.tools.catalog import (
    find_structures,
    list_segmentation_tasks,
    list_task_structures,
)
from medmcp_totalsegmentator.tools.segmentation import segment_anatomy

mcp = FastMCP("medmcp-totalsegmentator")

mcp.add_tool(segment_anatomy)
mcp.add_tool(list_segmentation_tasks)
mcp.add_tool(list_task_structures)
mcp.add_tool(find_structures)


def server_config() -> dict[str, object]:
    """Return MCP server metadata for autodiscovery by the local agent."""
    return {
        "name": "medmcp-totalsegmentator",
        "command": "medmcp-totalsegmentator",
        # A whole-body CT at full resolution is about a minute on a GPU but can run
        # into the tens of minutes on CPU, and a batch replay runs many in a row.
        "tool_timeout_sec": 7200.0,
        "skills_path": str(_pkg_files("medmcp_totalsegmentator") / "skills"),
    }


def main() -> None:
    """Launch the MCP server over stdio (JSON-RPC)."""
    mcp.run(transport="stdio")
