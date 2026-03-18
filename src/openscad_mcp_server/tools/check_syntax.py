"""Check-syntax tool — fast OpenSCAD code validation without full CGAL build."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from openscad_mcp_server.services.container import ContainerError, ContainerManager
from openscad_mcp_server.services.file_manager import FileManager

BUILD_IMAGE = "openscad/openscad:latest"
CONTAINER_WORK_DIR = "/work"
CONTAINER_LIB_DIR = "/work/libraries"


@dataclass
class SyntaxCheckResult:
    """Result of a syntax check."""

    valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


async def run_check_syntax(
    scad_file: str,
    container_manager: ContainerManager,
    file_manager: FileManager,
    timeout: int = 30,
) -> SyntaxCheckResult:
    """Run a fast syntax check on an OpenSCAD file without full geometry computation.

    Uses ``openscad -o /dev/null`` with the file to parse it and catch syntax
    errors, undefined modules, and other issues quickly.
    """
    mounts: dict[str, str] = {
        str(file_manager.working_dir): CONTAINER_WORK_DIR,
    }
    if file_manager.libraries_dir.exists():
        mounts[str(file_manager.libraries_dir)] = CONTAINER_LIB_DIR

    scad_name = Path(scad_file).name
    command = [
        "openscad",
        "-o", "/dev/null",
        "--export-format", "echo",
        f"{CONTAINER_WORK_DIR}/{scad_name}",
    ]

    try:
        result = await container_manager.run(
            image=BUILD_IMAGE,
            command=command,
            mounts=mounts,
            timeout=timeout,
        )
    except ContainerError as exc:
        return SyntaxCheckResult(valid=False, errors=[str(exc)])

    output = (result.stderr + "\n" + result.stdout).strip()
    errors: list[str] = []
    warnings: list[str] = []

    for line in output.splitlines():
        line = line.strip()
        if not line:
            continue
        lower = line.lower()
        if "error" in lower or "unknown" in lower:
            errors.append(line)
        elif "warning" in lower or "deprecated" in lower:
            warnings.append(line)

    valid = result.exit_code == 0 and len(errors) == 0
    return SyntaxCheckResult(valid=valid, errors=errors, warnings=warnings)
