"""Init tool — probes container runtime and returns persistence content."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from openscad_mcp_server.services.container import ContainerManager
from openscad_mcp_server.services.session import SessionState

WORKSPACE_ENV_VAR = "OPENSCAD_WORKSPACE"


@dataclass
class InitResult:
    """Structured result from the init tool."""

    runtime: str
    executable_path: str
    working_dir: str
    persistence_content: str
    next_step: str


PERSISTENCE_TEMPLATE = """# OpenSCAD MCP Server Settings
- Container runtime: {runtime}
- Container executable: {executable}
- Working directory: {working_dir}
"""

SUPPORTED_RUNTIMES_MSG = (
    "No supported container runtime found. "
    "Please install one of the following:\n"
    "  - Docker: https://docs.docker.com/get-docker/\n"
    "  - Finch: https://runfinch.com/\n"
)


NEXT_STEP_GUIDANCE = (
    "IMPORTANT: Before writing any code, check the OpenSCAD library catalog "
    "at https://openscad.org/libraries.html for existing libraries. "
    "For enclosures use YAPP_Box, for mechanical parts use BOSL2. "
    "Download the library, read its source to understand the API, then "
    "write your .scad code using library modules where possible. "
    "Use check-syntax for fast validation, then build-stl to compile."
)


async def run_init(
    session: SessionState,
    workspace_dir: str | None = None,
) -> InitResult:
    """Detect container runtime and configure the working directory.

    Parameters
    ----------
    session
        The current session state.
    workspace_dir
        Optional override for the working directory. Usually not needed
        when OPENSCAD_WORKSPACE is set via the MCP config.

    Raises
    ------
    RuntimeError
        If no supported container runtime is detected.
    ValueError
        If workspace_dir is provided but does not exist on disk.
    """
    detection = await ContainerManager.detect()
    if detection is None:
        raise RuntimeError(SUPPORTED_RUNTIMES_MSG)

    runtime, executable = detection

    # Resolution order:
    # 1. OPENSCAD_WORKSPACE env var (set by IDE via mcp.json config)
    # 2. workspace_dir parameter (explicit agent override)
    # 3. Process cwd fallback
    env_workspace = os.environ.get(WORKSPACE_ENV_VAR)

    if env_workspace:
        working_dir = Path(env_workspace).resolve()
        if not working_dir.is_dir():
            raise ValueError(
                f"{WORKSPACE_ENV_VAR} env var points to '{env_workspace}' "
                f"which does not exist. Check your MCP server config."
            )
    elif workspace_dir:
        working_dir = Path(workspace_dir).resolve()
        if not working_dir.is_dir():
            cwd = str(Path.cwd().resolve())
            raise ValueError(
                f"workspace_dir '{workspace_dir}' does not exist. "
                f"Do not invent paths. The server's current working "
                f"directory is: {cwd}"
            )
    else:
        working_dir = Path.cwd().resolve()

    # Persist into session state
    session.container_runtime = runtime
    session.container_executable = executable
    session.working_dir = working_dir

    persistence_content = PERSISTENCE_TEMPLATE.format(
        runtime=runtime,
        executable=executable,
        working_dir=str(working_dir),
    )

    return InitResult(
        runtime=runtime,
        executable_path=executable,
        working_dir=str(working_dir),
        persistence_content=persistence_content,
        next_step=NEXT_STEP_GUIDANCE,
    )
