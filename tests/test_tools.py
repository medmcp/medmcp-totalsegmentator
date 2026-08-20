"""Tests for domain tools.

Pattern for testing MCP tools: call the plain Python function directly.
No MCP server or subprocess needed — tools are just annotated functions.
"""

import pytest

from medmcp_template.tools.example import add_numbers, process_image


def test_add_numbers_basic() -> None:
    """Tool returns correct sum for positive inputs."""
    assert add_numbers(1.0, 2.0) == {"result": 3.0}


def test_add_numbers_negative() -> None:
    """Tool handles negative operands."""
    assert add_numbers(-5.0, 3.0) == {"result": -2.0}


def test_add_numbers_zero() -> None:
    """Tool handles zero."""
    assert add_numbers(0.0, 0.0) == {"result": 0.0}


def test_process_image_workspace_confinement(tmp_path: pytest.TempPathFactory) -> None:
    """Output files must not escape the workspace directory.

    Implement this test once process_image is implemented:
    verify that all outputs lie under output_dir.
    """
    with pytest.raises(NotImplementedError):
        process_image(tmp_path / "input.nii.gz", tmp_path / "output")  # type: ignore[arg-type]
