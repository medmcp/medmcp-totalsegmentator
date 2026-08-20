"""Smoke tests — the template must pass CI out of the box."""

import pytest

from medmcp_template import __version__
from medmcp_template.server import mcp


def test_version_is_string() -> None:
    """The package exposes a ``__version__`` string."""
    assert isinstance(__version__, str)
    assert __version__


@pytest.mark.asyncio
async def test_server_has_tools() -> None:
    """The MCP server exposes at least one registered tool."""
    tools = await mcp.list_tools()
    assert len(tools) > 0, "No tools registered on the MCP server"


def test_server_config_satisfies_autodiscovery() -> None:
    """`server_config()` is the contract with the medmcp core's discovery.

    The core reads these keys to build the stack's entry in the agent's config;
    a missing or misspelled one means the stack is silently not discovered, with
    no error anywhere. Cheap to assert, expensive to debug.
    """
    from pathlib import Path

    from medmcp_template.server import server_config

    cfg = server_config()

    assert isinstance(cfg.get("name"), str) and cfg["name"], "name is required"
    assert isinstance(cfg.get("command"), str) and cfg["command"], "command is required"

    skills = cfg.get("skills_path")
    assert isinstance(skills, str) and Path(skills).is_dir(), (
        "skills_path must point at a directory that ships with the package"
    )

    for key in ("tool_timeout_sec", "startup_timeout_sec"):
        value = cfg.get(key)
        if value is not None:
            assert isinstance(value, (int, float)), f"{key} must be a number"
            assert value > 0, f"{key} must be positive"
