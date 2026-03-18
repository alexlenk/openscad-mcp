"""File management for working area, final output, libraries, and feedback directories."""

from __future__ import annotations

import shutil
from pathlib import Path

from openscad_mcp_server.models import InspectionImage


class FileManager:
    """Manages the directory layout and file operations for the OpenSCAD workflow.

    Directory structure under *base_dir*::

        working/          – latest code, STL, and renders (overwritten each iteration)
        output/           – final artifacts copied on finalize
        libraries/        – fetched OpenSCAD libraries
        feedback/         – feedback records and index
    """

    WORKING = "working"
    OUTPUT = "output"
    LIBRARIES = "libraries"
    FEEDBACK = "feedback"
    RENDERS = "renders"

    def __init__(self, base_dir: Path) -> None:
        self.base_dir = base_dir
        self.working_dir = base_dir / self.WORKING
        self.output_dir = base_dir / self.OUTPUT
        self.libraries_dir = base_dir / self.LIBRARIES
        self.feedback_dir = base_dir / self.FEEDBACK
        self.renders_dir = self.working_dir / self.RENDERS
        self.ensure_dirs()

    # ------------------------------------------------------------------
    # Directory helpers
    # ------------------------------------------------------------------

    def ensure_dirs(self) -> None:
        """Create all managed directories if they do not exist."""
        for d in (self.working_dir, self.output_dir, self.libraries_dir,
                  self.feedback_dir, self.renders_dir):
            d.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Code management
    # ------------------------------------------------------------------

    @staticmethod
    def _normalize_scad_filename(filename: str) -> str:
        """Ensure *filename* ends with ``.scad`` without doubling the extension.

        If the filename is exactly ``.scad`` (no stem), the extension is still
        appended so the result is ``.scad.scad`` — preserving the dotfile name
        as the stem.
        """
        from pathlib import PurePosixPath

        p = PurePosixPath(filename)
        # A filename like ".scad" has an empty suffix in Python's pathlib
        # (it's treated as a dotfile), so check suffix rather than endswith.
        if p.suffix == ".scad":
            return filename
        return filename + ".scad"

    def save_code(self, code: str, filename: str) -> Path:
        """Write *code* to the working area, overwriting any previous code file.

        Returns the absolute path of the saved file.
        """
        filename = self._normalize_scad_filename(filename)
        path = self.working_dir / filename
        path.write_bytes(code.encode("utf-8"))
        return path.resolve()

    # ------------------------------------------------------------------
    # STL management
    # ------------------------------------------------------------------

    def save_stl(self, data: bytes, filename: str) -> Path:
        """Write raw STL *data* to the working area, overwriting any previous STL.

        Returns the absolute path of the saved file.
        """
        if not filename.endswith(".stl"):
            filename = filename + ".stl"
        path = self.working_dir / filename
        path.write_bytes(data)
        return path.resolve()

    # ------------------------------------------------------------------
    # Render management
    # ------------------------------------------------------------------

    def clear_renders(self) -> None:
        """Remove all images from the renders directory."""
        if self.renders_dir.exists():
            shutil.rmtree(self.renders_dir)
            self.renders_dir.mkdir(parents=True, exist_ok=True)

    def save_renders(self, images: list[InspectionImage]) -> list[Path]:
        """Clear previous renders and save new *images*.

        Each image is written as ``{angle}.png`` in the renders directory.
        Returns the list of saved file paths.
        """
        self.clear_renders()
        paths: list[Path] = []
        import base64

        for img in images:
            path = self.renders_dir / f"{img.angle}.png"
            path.write_bytes(base64.b64decode(img.base64_png))
            paths.append(path)
        return paths

    # ------------------------------------------------------------------
    # Finalize
    # ------------------------------------------------------------------

    def finalize(self) -> Path:
        """Copy all working area artifacts to the final output directory.

        Returns the path to the output directory.
        """
        # Clear previous output
        if self.output_dir.exists():
            shutil.rmtree(self.output_dir)
        shutil.copytree(self.working_dir, self.output_dir)
        return self.output_dir
