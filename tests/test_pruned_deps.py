"""The image strips packages the segmentation path never imports; prove it still runs.

TotalSegmentator declares its preview, reporting and DICOM-rendering dependencies as
hard requirements, so they cannot be resolved away — the container image uninstalls
them after the fact. That is safe only for as long as nothing on the segmentation path
imports them, and an upstream release could change that at any time.

Rather than trusting that, this blocks the pruned modules from importing and then
imports the chain the tools actually use. It fails here, in CI, instead of in an image
nobody can build.
"""

import importlib
import re
import sys
from collections.abc import Iterator
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

DOCKERFILE = Path(__file__).resolve().parent.parent / "Dockerfile"

# Distribution name -> the top-level module(s) it installs, where they differ.
_EXTRA_MODULES: dict[str, tuple[str, ...]] = {"vtk": ("vtkmodules",)}

# The chain that must keep importing. nnunet is where every removal that mattered
# broke: it imports dicom_io at module scope, which is why the DICOM packages stayed.
_REQUIRED_IMPORTS: tuple[str, ...] = (
    "totalsegmentator.python_api",
    "totalsegmentator.nnunet",
)


def _pruned_distributions() -> list[str]:
    """Read the pruned package list out of the Dockerfile, so the two cannot drift."""
    match = re.search(r"^# PRUNED-PACKAGES:(.*)$", DOCKERFILE.read_text(), re.MULTILINE)
    assert match, "no '# PRUNED-PACKAGES:' marker in the Dockerfile"
    return match.group(1).split()


def _blocked_modules() -> set[str]:
    """Top-level module names the pruned distributions provide."""
    blocked: set[str] = set()
    for dist in _pruned_distributions():
        blocked.add(dist.replace("-", "_"))
        blocked.update(_EXTRA_MODULES.get(dist, ()))
    return blocked


class _Blocker:
    """A meta-path finder that makes the pruned modules look uninstalled."""

    def __init__(self, blocked: set[str]) -> None:
        self._blocked = blocked

    def find_spec(self, name: str, path: Any = None, target: Any = None) -> None:
        if name.split(".")[0] in self._blocked:
            raise ImportError(f"{name} is pruned from the container image")
        return None


@pytest.fixture
def without_pruned_packages() -> Iterator[set[str]]:
    """Make the pruned packages unimportable for the duration of a test."""
    blocked = _blocked_modules()
    saved: dict[str, ModuleType] = {
        name: module for name, module in sys.modules.items() if name.split(".")[0] in blocked
    }
    for name in saved:
        del sys.modules[name]
    blocker = _Blocker(blocked)
    sys.meta_path.insert(0, blocker)
    try:
        yield blocked
    finally:
        sys.meta_path.remove(blocker)
        sys.modules.update(saved)


def test_pruned_list_is_not_empty() -> None:
    """The Dockerfile marker parses and names something."""
    assert _pruned_distributions(), "pruned package list is empty"


def test_segmentation_chain_imports_without_the_pruned_packages(
    without_pruned_packages: set[str],
) -> None:
    """The import chain the tools rely on must not touch anything the image removes."""
    for module in _REQUIRED_IMPORTS:
        sys.modules.pop(module, None)
        try:
            importlib.import_module(module)
        except ImportError as exc:  # pragma: no cover - the failure we want to see
            pytest.fail(
                f"{module} imports a package the image prunes ({exc}). Either drop it "
                f"from the '# PRUNED-PACKAGES:' list in the Dockerfile, or stop the "
                f"segmentation path from importing it."
            )


def test_our_own_modules_import_without_the_pruned_packages(
    without_pruned_packages: set[str],
) -> None:
    """Our tools must not reach for a pruned package either."""
    for module in (
        "medmcp_totalsegmentator.server",
        "medmcp_totalsegmentator.tools.segmentation",
        "medmcp_totalsegmentator.tools.catalog",
        "medmcp_totalsegmentator.tools._run_totalseg",
    ):
        sys.modules.pop(module, None)
        importlib.import_module(module)
