"""Property tests for init tool (Property 15: Init tool runtime detection)."""

from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from hypothesis import given, settings, strategies as st

from openscad_mcp_server.services.session import SessionState
from openscad_mcp_server.tools.init_tool import (
    SUPPORTED_RUNTIMES_MSG,
    WORKSPACE_ENV_VAR,
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
    persist it in session state, and produce valid persistence content."""
    session = SessionState()

    with tempfile.TemporaryDirectory() as td:
        with patch(
            "openscad_mcp_server.tools.init_tool.ContainerManager.detect",
            new_callable=AsyncMock,
            return_value=(runtime, executable),
        ):
            result: InitResult = asyncio.run(run_init(session, workspace_dir=td))

    assert result.runtime == runtime
    assert result.executable_path == executable
    assert result.working_dir  # non-empty
    assert runtime in result.persistence_content
    assert executable in result.persistence_content

    # Session state must be updated
    assert session.container_runtime == runtime
    assert session.container_executable == executable
    assert session.working_dir is not None


# Feature: openscad-mcp-server, Property 15: workspace_dir is used
@given(runtime=_runtimes, executable=_executables)
@settings(max_examples=10)
def test_init_uses_provided_workspace_dir(runtime: str, executable: str) -> None:
    """Init should use the provided workspace_dir, not cwd or a temp dir."""
    session = SessionState()

    with tempfile.TemporaryDirectory() as td:
        with patch(
            "openscad_mcp_server.tools.init_tool.ContainerManager.detect",
            new_callable=AsyncMock,
            return_value=(runtime, executable),
        ):
            result: InitResult = asyncio.run(run_init(session, workspace_dir=td))

    expected = str(Path(td).resolve())
    assert result.working_dir == expected
    assert str(session.working_dir) == expected


# Feature: openscad-mcp-server, Property 15: fallback to cwd
def test_init_falls_back_to_cwd_when_no_workspace_dir() -> None:
    """When workspace_dir is not provided, init should fall back to cwd."""
    session = SessionState()

    with patch(
        "openscad_mcp_server.tools.init_tool.ContainerManager.detect",
        new_callable=AsyncMock,
        return_value=("docker", "/usr/bin/docker"),
    ):
        result = asyncio.run(run_init(session))

    expected = str(Path.cwd().resolve())
    assert result.working_dir == expected


# Feature: openscad-mcp-server, Property 15: non-existent workspace_dir rejected
def test_init_rejects_nonexistent_workspace_dir() -> None:
    """Init should raise ValueError when workspace_dir does not exist,
    and the error should suggest the server's cwd."""
    session = SessionState()

    with patch(
        "openscad_mcp_server.tools.init_tool.ContainerManager.detect",
        new_callable=AsyncMock,
        return_value=("docker", "/usr/bin/docker"),
    ):
        with pytest.raises(ValueError, match="does not exist"):
            asyncio.run(run_init(session, workspace_dir="/nonexistent/fake/path"))

    # Session state should remain unset
    assert session.working_dir is None


def test_init_error_suggests_cwd() -> None:
    """The ValueError for a bad workspace_dir should include the server's cwd
    so the agent can self-correct."""
    session = SessionState()
    cwd = str(Path.cwd().resolve())

    with patch(
        "openscad_mcp_server.tools.init_tool.ContainerManager.detect",
        new_callable=AsyncMock,
        return_value=("docker", "/usr/bin/docker"),
    ):
        try:
            asyncio.run(run_init(session, workspace_dir="/nonexistent/path"))
            raise AssertionError("Expected ValueError")
        except ValueError as exc:
            assert cwd in str(exc)
            assert "Do not invent paths" in str(exc)


# Feature: openscad-mcp-server, Property 15: OPENSCAD_WORKSPACE env var
def test_init_uses_env_var_workspace() -> None:
    """When OPENSCAD_WORKSPACE is set, init should use it regardless of
    workspace_dir param or cwd."""
    session = SessionState()

    with tempfile.TemporaryDirectory() as td:
        with patch.dict("os.environ", {WORKSPACE_ENV_VAR: td}):
            with patch(
                "openscad_mcp_server.tools.init_tool.ContainerManager.detect",
                new_callable=AsyncMock,
                return_value=("docker", "/usr/bin/docker"),
            ):
                result = asyncio.run(run_init(session))

    expected = str(Path(td).resolve())
    assert result.working_dir == expected


def test_init_env_var_takes_priority_over_param() -> None:
    """OPENSCAD_WORKSPACE env var should take priority over workspace_dir param."""
    session = SessionState()

    with tempfile.TemporaryDirectory() as env_dir:
        with tempfile.TemporaryDirectory() as param_dir:
            with patch.dict("os.environ", {WORKSPACE_ENV_VAR: env_dir}):
                with patch(
                    "openscad_mcp_server.tools.init_tool.ContainerManager.detect",
                    new_callable=AsyncMock,
                    return_value=("docker", "/usr/bin/docker"),
                ):
                    result = asyncio.run(run_init(session, workspace_dir=param_dir))

    expected = str(Path(env_dir).resolve())
    assert result.working_dir == expected


def test_init_env_var_nonexistent_raises() -> None:
    """When OPENSCAD_WORKSPACE points to a non-existent dir, raise ValueError."""
    session = SessionState()

    with patch.dict("os.environ", {WORKSPACE_ENV_VAR: "/nonexistent/env/path"}):
        with patch(
            "openscad_mcp_server.tools.init_tool.ContainerManager.detect",
            new_callable=AsyncMock,
            return_value=("docker", "/usr/bin/docker"),
        ):
            with pytest.raises(ValueError, match="OPENSCAD_WORKSPACE"):
                asyncio.run(run_init(session))


# Feature: openscad-mcp-server, Property 15: Docker preferred over Finch
def test_init_prefers_docker_when_both_available() -> None:
    """When both Docker and Finch are available, Docker should be preferred."""
    session = SessionState()

    with tempfile.TemporaryDirectory() as td:
        with patch(
            "openscad_mcp_server.tools.init_tool.ContainerManager.detect",
            new_callable=AsyncMock,
            return_value=("docker", "/usr/bin/docker"),
        ):
            result = asyncio.run(run_init(session, workspace_dir=td))

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
            asyncio.run(run_init(session, workspace_dir="/tmp/test"))

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
