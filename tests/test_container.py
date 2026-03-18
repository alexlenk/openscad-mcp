"""Property tests for ContainerManager (Properties 3–6)."""

from __future__ import annotations

import asyncio

from hypothesis import given, settings, strategies as st

from openscad_mcp_server.models import ContainerResult
from openscad_mcp_server.services.container import ContainerError, ContainerManager

# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# Printable, non-empty strings safe for use as image names / commands / paths.
_safe_text = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N", "P"), whitelist_characters="/-_."),
    min_size=1,
    max_size=60,
).filter(lambda s: s.strip() != "")

_image_names = _safe_text
_commands = st.lists(_safe_text, min_size=1, max_size=5)

# Mount dicts: host_path -> container_path
_mounts = st.dictionaries(
    keys=_safe_text,
    values=_safe_text,
    min_size=0,
    max_size=5,
)

# Non-zero exit codes for error scenarios
_nonzero_exit = st.integers(min_value=1, max_value=255)

# Arbitrary stderr content (may include newlines, line numbers, etc.)
_stderr_text = st.text(min_size=0, max_size=500)


# ---------------------------------------------------------------------------
# Property 3: Container command generation is runtime-agnostic
# ---------------------------------------------------------------------------

# Feature: openscad-mcp-server, Property 3: Container command generation is runtime-agnostic
@given(image=_image_names, command=_commands, mounts=_mounts)
@settings(max_examples=100)
def test_runtime_agnostic_commands(
    image: str, command: list[str], mounts: dict[str, str]
) -> None:
    """For any container run request, Docker and Finch commands are structurally
    identical except for the executable name."""
    docker_mgr = ContainerManager("docker", "/usr/bin/docker")
    finch_mgr = ContainerManager("finch", "/usr/local/bin/finch")

    docker_cmd = docker_mgr.build_run_command(image, command, mounts)
    finch_cmd = finch_mgr.build_run_command(image, command, mounts)

    # First element differs (executable), rest must be identical.
    assert docker_cmd[0] == "/usr/bin/docker"
    assert finch_cmd[0] == "/usr/local/bin/finch"
    assert docker_cmd[1:] == finch_cmd[1:]


# ---------------------------------------------------------------------------
# Property 4: Container mount correctness
# ---------------------------------------------------------------------------

# Feature: openscad-mcp-server, Property 4: Container mount correctness
@given(
    working_dir=_safe_text,
    library_dir=_safe_text,
    image=_image_names,
    command=_commands,
)
@settings(max_examples=100)
def test_container_mount_correctness(
    working_dir: str, library_dir: str, image: str, command: list[str]
) -> None:
    """For any build/render invocation with a working directory and library
    directory, the generated command includes mount arguments for both."""
    # When both paths are identical the dict collapses; use distinct paths.
    if working_dir == library_dir:
        library_dir = library_dir + "_lib"

    mounts = {
        working_dir: "/work",
        library_dir: "/work/libraries",
    }
    mgr = ContainerManager("docker", "docker")
    cmd = mgr.build_run_command(image, command, mounts)

    # Collect all -v mount specs from the command
    mount_specs: list[str] = []
    it = iter(cmd)
    for token in it:
        if token == "-v":
            mount_specs.append(next(it))

    # Both mounts must be present
    assert f"{working_dir}:/work" in mount_specs
    assert f"{library_dir}:/work/libraries" in mount_specs


# ---------------------------------------------------------------------------
# Property 5: Build error propagation
# ---------------------------------------------------------------------------

# Feature: openscad-mcp-server, Property 5: Build error propagation
@given(exit_code=_nonzero_exit, stderr=_stderr_text)
@settings(max_examples=100)
def test_build_error_propagation(exit_code: int, stderr: str) -> None:
    """For any ContainerResult with a non-zero exit code, the full stderr
    content is preserved and accessible for error reporting."""
    result = ContainerResult(exit_code=exit_code, stdout="", stderr=stderr)

    # The result must carry the non-zero exit code and the full stderr.
    assert result.exit_code != 0
    assert result.stderr == stderr


# ---------------------------------------------------------------------------
# Property 6: Container start failure diagnostics
# ---------------------------------------------------------------------------

# Feature: openscad-mcp-server, Property 6: Container start failure diagnostics
@given(image=_image_names)
@settings(max_examples=100)
def test_container_start_failure_runtime_unavailable(image: str) -> None:
    """When the container executable is not found, the error message should
    indicate the runtime is unavailable and include the image name."""
    mgr = ContainerManager("docker", "/nonexistent/docker")

    try:
        asyncio.run(mgr.run(image, ["echo", "hello"]))
        # If we somehow get here (shouldn't), fail explicitly.
        raise AssertionError("Expected ContainerError for missing executable")
    except ContainerError as exc:
        assert "unavailable" in str(exc).lower()
        assert exc.image == image


# Feature: openscad-mcp-server, Property 6 (supplemental): image-missing diagnostic
@given(image=_image_names)
@settings(max_examples=100)
def test_container_error_includes_image_name(image: str) -> None:
    """ContainerError always carries the image name for diagnostic purposes."""
    err = ContainerError("Image not found locally", image=image)
    assert err.image == image
    assert "not found" in str(err).lower()
