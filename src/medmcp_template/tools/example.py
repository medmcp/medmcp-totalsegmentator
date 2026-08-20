"""Example tool — replace with real domain tools after scaffolding.

Each function in this module that is registered in server.py becomes an
LLM-invokable MCP tool. FastMCP derives the tool name, description, and
JSON-schema inputSchema from the function signature and docstring, so:

  - Keep docstrings focused on what the tool does and what it returns.
    Do not embed workflow or output-format instructions in docstrings.
  - Type-annotate every parameter and the return type.
  - For tools with specific output format requirements, include a ``_render``
    key (str) in the return dict. The model treats its value as mandatory
    display instructions for that specific result — use it for any tool whose
    output has non-obvious formatting rules or a required next action.
  - Confine all filesystem writes to the ``output_dir`` argument.
"""

from pathlib import Path


def add_numbers(a: float, b: float) -> dict[str, float]:
    """Add two numbers and return the result.

    Placeholder tool demonstrating the minimal tool signature. Replace with
    a real domain operation (e.g. skull stripping, registration, segmentation).

    Args:
        a: First operand.
        b: Second operand.

    Returns:
        A dict with key ``result`` containing the sum.
    """
    return {"result": a + b}


def process_image(input_path: Path, output_dir: Path) -> dict[str, str]:
    r"""Skeleton for a real image-processing tool.

    Args:
        input_path: Absolute path to the input file (NIfTI or DICOM).
        output_dir: Workspace directory where all outputs must be written.
            Writing outside this directory is not permitted.

    Returns:
        A dict with ``output_path`` (absolute path to the result file) and
        ``_render`` (display instructions for this result). Example::

            {
                "output_path": "/path/to/result.nii.gz",
                "_render": (
                    "DISPLAY RULES:\n"
                    "Report: output_path, and whether the file exists.\n"
                    "NEXT ACTION: Confirm success with the user, then stop."
                ),
            }

    Raises:
        NotImplementedError: Until implemented by a real downstream package.
    """
    raise NotImplementedError
