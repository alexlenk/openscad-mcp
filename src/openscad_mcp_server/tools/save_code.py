"""Save-code tool — validates, checks library review status, and persists OpenSCAD code."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import PurePosixPath

from openscad_mcp_server.services.file_manager import FileManager
from openscad_mcp_server.services.session import SessionState

# Matches OpenSCAD include/use statements:
#   include <lib/foo.scad>
#   use <BOSL2/std.scad>
_LIBRARY_RE = re.compile(
    r"^\s*(?:include|use)\s*<\s*([^>/]+)/",
    re.MULTILINE,
)


class LibraryNotReviewedError(Exception):
    """Raised when code references a library whose source has not been reviewed."""

    def __init__(self, libraries: set[str]) -> None:
        self.libraries = libraries
        names = ", ".join(sorted(libraries))
        super().__init__(
            f"Cannot save code: the following libraries have not been reviewed "
            f"via read-library-source: {names}. "
            f"Please invoke read-library-source for each library before saving code."
        )


@dataclass
class SaveCodeResult:
    """Result from the save-code tool."""

    file_path: str


def parse_library_references(code: str) -> set[str]:
    """Extract library names from ``include``/``use`` statements in OpenSCAD code.

    Returns the set of top-level directory names referenced, e.g.
    ``use <BOSL2/std.scad>`` yields ``{"BOSL2"}``.
    """
    return set(_LIBRARY_RE.findall(code))


def run_save_code(
    code: str,
    filename: str,
    session: SessionState,
    file_manager: FileManager,
) -> SaveCodeResult:
    """Validate filename, enforce library review, and save code.

    Raises
    ------
    LibraryNotReviewedError
        If the code references libraries not yet reviewed this session.
    """
    # Check library review status
    referenced = parse_library_references(code)
    unreviewed = {lib for lib in referenced if not session.is_library_reviewed(lib)}
    if unreviewed:
        raise LibraryNotReviewedError(unreviewed)

    # Delegate to FileManager (handles extension normalization + write)
    saved_path = file_manager.save_code(code, filename)

    return SaveCodeResult(file_path=str(saved_path))
