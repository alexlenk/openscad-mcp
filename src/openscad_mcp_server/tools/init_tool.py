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


async def run_init(session: SessionState) -> InitResult:
    """Detect container runtime and use the current working directory.

    The working directory is the process's cwd — which is the user's
    project directory when launched by an MCP client like Kiro. All files
    (code, STL, renders, libraries) live here so they're visible in the
    IDE and tracked by git.

    Raises
    ------
    RuntimeError
        If no supported container runtime is detected.
    """
    detection = await ContainerManager.detect()
    if detection is None:
        raise RuntimeError(SUPPORTED_RUNTIMES_MSG)

    runtime, executable = detection

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
    )
