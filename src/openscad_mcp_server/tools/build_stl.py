"""Build-stl tool — compiles OpenSCAD code into an STL file via a containerized OpenSCAD."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from openscad_mcp_server.services.container import ContainerError, ContainerManager
from openscad_mcp_server.services.file_manager import FileManager
from openscad_mcp_server.services.stl_parser import parse_stl

BUILD_IMAGE = "openscad/openscad:latest"
CONTAINER_WORK_DIR = "/work"
CONTAINER_LIB_DIR = "/work/libraries"


@dataclass
class BuildStlResult:
    """Successful build result with geometry metadata."""

    stl_path: str
    file_size_bytes: int = 0
    facet_count: int = 0
    vertex_count: int = 0
    bounding_box: dict | None = None
    dimensions: dict | None = None
    volume_cm3: float = 0.0
    surface_area_cm2: float = 0.0
    is_manifold: bool = True


@dataclass
class BuildStlError:
    """Build failure result carrying the full error output."""

    error: str
    details: str


async def run_build_stl(
    scad_file: str,
    container_manager: ContainerManager,
    file_manager: FileManager,
    timeout: int = 300,
) -> BuildStlResult | BuildStlError:
    """Compile an OpenSCAD file into an STL using the build container.

    Parameters
    ----------
    scad_file:
        Filename (relative to the working area) of the ``.scad`` source.
    container_manager:
        Configured container manager for the current runtime.
    file_manager:
        File manager providing working-area and library paths.
    timeout:
        Maximum seconds to wait for the container.

    Returns
    -------
    BuildStlResult on success, BuildStlError on compilation or container failure.
    """
    scad_path = Path(scad_file)
    stl_filename = scad_path.stem + ".stl"

    mounts: dict[str, str] = {
        str(file_manager.working_dir): CONTAINER_WORK_DIR,
    }
    if file_manager.libraries_dir.exists():
        mounts[str(file_manager.libraries_dir)] = CONTAINER_LIB_DIR

    command = [
        "openscad",
        "-o", f"{CONTAINER_WORK_DIR}/{stl_filename}",
        f"{CONTAINER_WORK_DIR}/{scad_path.name}",
    ]

    try:
        result = await container_manager.run(
            image=BUILD_IMAGE,
            command=command,
            mounts=mounts,
            timeout=timeout,
        )
    except ContainerError as exc:
        return BuildStlError(error=str(exc), details="")

    if result.exit_code != 0:
        return BuildStlError(
            error="OpenSCAD compilation failed",
            details=result.stderr or result.stdout,
        )

    stl_path = file_manager.working_dir / stl_filename
    
    # Extract geometry metadata from the STL
    meta = parse_stl(stl_path)
    bb = meta.bounding_box
    dims = bb.dimensions

    return BuildStlResult(
        stl_path=str(stl_path.resolve()),
        file_size_bytes=meta.file_size_bytes,
        facet_count=meta.facet_count,
        vertex_count=meta.vertex_count,
        bounding_box={
            "min": [round(bb.min_x, 3), round(bb.min_y, 3), round(bb.min_z, 3)],
            "max": [round(bb.max_x, 3), round(bb.max_y, 3), round(bb.max_z, 3)],
        },
        dimensions={
            "x": round(dims[0], 3),
            "y": round(dims[1], 3),
            "z": round(dims[2], 3),
        },
        volume_cm3=meta.volume_cm3,
        surface_area_cm2=meta.surface_area_cm2,
        is_manifold=meta.is_manifold,
    )
