"""Measure-stl tool — dimensional verification from STL file without rendering."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from openscad_mcp_server.services.file_manager import FileManager
from openscad_mcp_server.services.stl_parser import parse_stl


@dataclass
class MeasureStlResult:
    """Dimensional and geometric metadata from an STL file."""

    bounding_box: dict
    dimensions: dict
    volume_cm3: float
    surface_area_cm2: float
    facet_count: int
    vertex_count: int
    is_manifold: bool
    file_size_bytes: int


def run_measure_stl(stl_file: str, file_manager: FileManager) -> MeasureStlResult:
    """Parse an STL file and return geometry metadata.

    Parameters
    ----------
    stl_file:
        Filename (relative to the working area) of the ``.stl`` file.
    file_manager:
        File manager providing working-area paths.
    """
    stl_path = file_manager.working_dir / Path(stl_file).name
    if not stl_path.exists():
        raise FileNotFoundError(f"STL file not found: {stl_path}")

    meta = parse_stl(stl_path)
    bb = meta.bounding_box
    dims = bb.dimensions

    return MeasureStlResult(
        bounding_box={
            "min": [round(bb.min_x, 3), round(bb.min_y, 3), round(bb.min_z, 3)],
            "max": [round(bb.max_x, 3), round(bb.max_y, 3), round(bb.max_z, 3)],
        },
        dimensions={"x": round(dims[0], 3), "y": round(dims[1], 3), "z": round(dims[2], 3)},
        volume_cm3=meta.volume_cm3,
        surface_area_cm2=meta.surface_area_cm2,
        facet_count=meta.facet_count,
        vertex_count=meta.vertex_count,
        is_manifold=meta.is_manifold,
        file_size_bytes=meta.file_size_bytes,
    )
