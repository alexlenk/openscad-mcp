"""Init tool — probes container runtime and returns persistence content."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from openscad_mcp_server.services.container import ContainerManager
from openscad_mcp_server.services.session import SessionState


@dataclass
class InitResult:
    """Structured result from the init tool."""

    runtime: str
    executable_path: str
    working_dir: str
    persistence_content: str
    next_step: str


PERSISTENCE_TEMPLATE = """\
# OpenSCAD MCP Server Settings
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
    "IMPORTANT: Before writing any code, call browse-library-catalog to check "
    "for existing libraries. For enclosures use YAPP_Box, for mechanical parts "
    "use BOSL2. Then fetch-library + read-library-source to understand the API. "
    "Only then write code with save-code using library modules where possible."
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
        The user's project directory. When provided, all files (code, STL,
        renders, libraries) are stored here so they're visible in the IDE
        and tracked by git. When omitted, falls back to the process's
        current working directory.

    Raises
    ------
    RuntimeError
        If no supported container runtime is detected.
    """
    detection = await ContainerManager.detect()
    if detection is None:
        raise RuntimeError(SUPPORTED_RUNTIMES_MSG)

    runtime, executable = detection

    if workspace_dir:
        working_dir = Path(workspace_dir).resolve()
    else:
        working_dir = Path.cwd().resolve()

    working_dir.mkdir(parents=True, exist_ok=True)

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
