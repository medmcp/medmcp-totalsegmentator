"""MCP server entrypoint for medmcp-template.

Replace this module's tool registrations with your domain tools after
scaffolding a new repo from the template. See README.md for the full workflow.
"""

from importlib.resources import files as _pkg_files

from mcp.server.fastmcp import FastMCP

from medmcp_template.tools.example import add_numbers

mcp = FastMCP("medmcp-template")

# Register tools here — one add_tool call per domain tool.
mcp.add_tool(add_numbers)


def server_config() -> dict[str, object]:
    """Return MCP server metadata for autodiscovery by the local agent."""
    return {
        "name": "medmcp-template",
        "command": "medmcp-template",
        "skills_path": str(_pkg_files("medmcp_template") / "skills"),
        "tool_timeout_sec": 300.0,
        # If this stack is slow to start — importing torch, loading weights — set
        # a startup budget too. The agent gives a server only a few seconds to
        # answer "what tools do you have" before giving up, and a stack that
        # misses that window loads with *no* tools and nothing saying why.
        # "startup_timeout_sec": 120.0,
    }


def main() -> None:
    """Launch the MCP server over stdio (JSON-RPC)."""
    mcp.run(transport="stdio")
