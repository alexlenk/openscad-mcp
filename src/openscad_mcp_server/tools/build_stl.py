"""Build-stl tool — compiles OpenSCAD code into an STL file via a containerized OpenSCAD."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from openscad_mcp_server.services.container import ContainerError, ContainerManager
from openscad_mcp_server.services.file_manager import FileManager

BUILD_IMAGE = "openscad-mcp-build"
CONTAINER_WORK_DIR = "/work"
CONTAINER_LIB_DIR = "/work/libraries"


@dataclass
class BuildStlResult:
    """Successful build result."""

    stl_path: str


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
    return BuildStlResult(stl_path=str(stl_path.resolve()))
