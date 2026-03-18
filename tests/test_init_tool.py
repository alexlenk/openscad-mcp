"""Property tests for init tool (Property 15: Init tool runtime detection)."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import pytest
from hypothesis import given, settings, strategies as st

from openscad_mcp_server.services.session import SessionState
from openscad_mcp_server.tools.init_tool import (
    SUPPORTED_RUNTIMES_MSG,
    InitResult,
    run_init,
)

# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

_runtimes = st.sampled_from(["docker", "finch"])
_executables = st.sampled_from(["/usr/bin/docker", "/usr/local/bin/finch", "/opt/bin/docker"])


# ---------------------------------------------------------------------------
# Property 15: Init tool runtime detection
# ---------------------------------------------------------------------------


# Feature: openscad-mcp-server, Property 15: Init tool runtime detection
@given(runtime=_runtimes, executable=_executables)
@settings(max_examples=50)
def test_init_detects_available_runtime(runtime: str, executable: str) -> None:
    """When exactly one runtime is available, init should detect and return it,
    persist it in session state, and produce valid persistence content.
    Working directory should be the current working directory."""
    session = SessionState()

    with patch(
        "openscad_mcp_server.tools.init_tool.ContainerManager.detect",
        new_callable=AsyncMock,
        return_value=(runtime, executable),
    ):
        result: InitResult = asyncio.run(run_init(session))

    assert result.runtime == runtime
    assert result.executable_path == executable
    assert result.working_dir  # non-empty
    assert runtime in result.persistence_content
    assert executable in result.persistence_content

    # Session state must be updated
    assert session.container_runtime == runtime
    assert session.container_executable == executable
    assert session.working_dir is not None


# Feature: openscad-mcp-server, Property 15: Working dir is cwd
@given(runtime=_runtimes, executable=_executables)
@settings(max_examples=10)
def test_init_uses_cwd_as_working_dir(runtime: str, executable: str) -> None:
    """Init should use the current working directory (the user's project dir),
    not a temp directory."""
    import os
    session = SessionState()

    with patch(
        "openscad_mcp_server.tools.init_tool.ContainerManager.detect",
        new_callable=AsyncMock,
        return_value=(runtime, executable),
    ):
        result: InitResult = asyncio.run(run_init(session))

    from pathlib import Path
    expected = str(Path.cwd().resolve())
    assert result.working_dir == expected
    assert str(session.working_dir) == expected


# Feature: openscad-mcp-server, Property 15: Docker preferred over Finch
def test_init_prefers_docker_when_both_available() -> None:
    """When both Docker and Finch are available, Docker should be preferred.

    ContainerManager.detect() already implements this preference (probes Docker
    first), so we verify the init tool propagates the result correctly.
    """
    session = SessionState()

    with patch(
        "openscad_mcp_server.tools.init_tool.ContainerManager.detect",
        new_callable=AsyncMock,
        return_value=("docker", "/usr/bin/docker"),
    ):
        result = asyncio.run(run_init(session))

    assert result.runtime == "docker"


# Feature: openscad-mcp-server, Property 15: No runtime available
def test_init_raises_when_no_runtime() -> None:
    """When neither Docker nor Finch is available, init should raise with
    installation instructions for both runtimes."""
    session = SessionState()

    with patch(
        "openscad_mcp_server.tools.init_tool.ContainerManager.detect",
        new_callable=AsyncMock,
        return_value=None,
    ):
        with pytest.raises(RuntimeError, match="No supported container runtime"):
            asyncio.run(run_init(session))

    # Session state should remain unset
    assert session.container_runtime is None
    assert session.container_executable is None


# Feature: openscad-mcp-server, Property 15: Error message lists both runtimes
def test_no_runtime_error_lists_both_options() -> None:
    """The error message when no runtime is found should mention both Docker
    and Finch with installation URLs."""
    assert "Docker" in SUPPORTED_RUNTIMES_MSG
    assert "Finch" in SUPPORTED_RUNTIMES_MSG
    assert "https://" in SUPPORTED_RUNTIMES_MSG
