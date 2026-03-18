"""Finalize tool — copy working area artifacts to final output."""

from __future__ import annotations

from dataclasses import dataclass

from openscad_mcp_server.services.file_manager import FileManager


@dataclass
class FinalizeResult:
    """Result from the finalize tool."""

    final_dir: str
    files: list[str]


def run_finalize(file_manager: FileManager) -> FinalizeResult:
    """Copy the latest artifacts from the working area to the final output directory.

    Delegates to :meth:`FileManager.finalize` and then lists all files in the
    output directory.

    Returns
    -------
    FinalizeResult
        The output directory path and a list of relative file paths within it.
    """
    output_dir = file_manager.finalize()

    files: list[str] = []
    for path in sorted(output_dir.rglob("*")):
        if path.is_file():
            files.append(str(path.relative_to(output_dir)))

    return FinalizeResult(
        final_dir=str(output_dir),
        files=files,
    )
