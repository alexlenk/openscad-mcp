"""Property tests for render-images tool (Properties 7–10)."""

from __future__ import annotations

import asyncio
import base64
import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

from hypothesis import given, settings, strategies as st

from openscad_mcp_server.models import CAMERA_ANGLES, CameraAngle, ContainerResult
from openscad_mcp_server.services.container import ContainerError, ContainerManager
from openscad_mcp_server.services.file_manager import FileManager
from openscad_mcp_server.tools.render_images import (
    RenderResult,
    build_render_command,
    run_render_images,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

ANGLE_LABELS = [a.label for a in CAMERA_ANGLES]

# Minimal valid PNG (1x1 pixel, transparent)
_MINIMAL_PNG = (
    b"\x89PNG\r\n\x1a\n"
    b"\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
    b"\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01"
    b"\r\n\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
)


def _make_file_manager(tmp_path: Path) -> FileManager:
    return FileManager(tmp_path)


def _successful_container_run(file_manager: FileManager):
    """Return an AsyncMock for ContainerManager.run that writes fake PNGs."""

    async def _mock_run(image, command, mounts=None, timeout=300):
        # Extract the output filename from the bash -c command string
        # Command is ["bash", "-c", "... -o /work/renders/front.png ..."]
        if len(command) >= 3 and command[0] == "bash" and command[1] == "-c":
            cmd_str = command[2]
            # Find "-o <path>" in the command string
            import re
            m = re.search(r"-o\s+(\S+)", cmd_str)
            if m:
                container_out = m.group(1)
                png_name = Path(container_out).name
                local_path = file_manager.renders_dir / png_name
                local_path.parent.mkdir(parents=True, exist_ok=True)
                local_path.write_bytes(_MINIMAL_PNG)
        else:
            # Fallback for non-bash-wrapped commands
            for i, arg in enumerate(command):
                if arg == "-o" and i + 1 < len(command):
                    container_out = command[i + 1]
                    png_name = Path(container_out).name
                    local_path = file_manager.renders_dir / png_name
                    local_path.parent.mkdir(parents=True, exist_ok=True)
                    local_path.write_bytes(_MINIMAL_PNG)
                    break
        return ContainerResult(exit_code=0, stdout="", stderr="")

    return _mock_run


# ---------------------------------------------------------------------------
# Property 7: Render produces exactly 8 images with correct angles
# ---------------------------------------------------------------------------


# Feature: openscad-mcp-server, Property 7: Render produces exactly 8 images with correct angles
def test_render_produces_8_images_with_correct_angles(tmp_path: Path) -> None:
    """For any successful render invocation, the output should contain exactly
    8 images, one for each predefined camera angle, with no duplicates."""
    fm = _make_file_manager(tmp_path)
    # Write a dummy STL so the path exists
    (fm.working_dir / "model.stl").write_bytes(b"solid dummy")

    mgr = ContainerManager("docker", "docker")

    with patch.object(mgr, "run", side_effect=_successful_container_run(fm)):
        result: RenderResult = asyncio.run(
            run_render_images("model.stl", mgr, fm)
        )

    assert len(result.failures) == 0
    assert len(result.image_contents) == 8

    rendered_labels = [label for label, _ in result.image_contents]
    assert sorted(rendered_labels) == sorted(ANGLE_LABELS)
    # No duplicates
    assert len(set(rendered_labels)) == 8


# Feature: openscad-mcp-server, Property 7: Metadata contains all 8 angles
def test_render_metadata_contains_all_angles(tmp_path: Path) -> None:
    """The text_content metadata block should list all 8 camera angles."""
    fm = _make_file_manager(tmp_path)
    (fm.working_dir / "model.stl").write_bytes(b"solid dummy")
    mgr = ContainerManager("docker", "docker")

    with patch.object(mgr, "run", side_effect=_successful_container_run(fm)):
        result = asyncio.run(run_render_images("model.stl", mgr, fm))

    metadata = json.loads(result.text_content)
    assert len(metadata["angles"]) == 8
    meta_labels = [a["label"] for a in metadata["angles"]]
    assert sorted(meta_labels) == sorted(ANGLE_LABELS)


# ---------------------------------------------------------------------------
# Property 8: Render command specifies PNG at 1024x1024
# ---------------------------------------------------------------------------


# Feature: openscad-mcp-server, Property 8: Render command specifies PNG at 1024x1024
@given(
    pos=st.tuples(
        st.floats(allow_nan=False, allow_infinity=False, min_value=-1000, max_value=1000),
        st.floats(allow_nan=False, allow_infinity=False, min_value=-1000, max_value=1000),
        st.floats(allow_nan=False, allow_infinity=False, min_value=-1000, max_value=1000),
    ),
    rot=st.tuples(
        st.floats(allow_nan=False, allow_infinity=False, min_value=-360, max_value=360),
        st.floats(allow_nan=False, allow_infinity=False, min_value=-360, max_value=360),
        st.floats(allow_nan=False, allow_infinity=False, min_value=-360, max_value=360),
    ),
)
@settings(max_examples=100)
def test_render_command_specifies_png_1024(
    pos: tuple[float, float, float],
    rot: tuple[float, float, float],
) -> None:
    """For any camera angle, the render command must include --imgsize=1024,1024
    and produce PNG output (via -o .png), wrapped in xvfb-run."""
    angle = CameraAngle(label="test", position=pos, rotation=rot)
    cmd = build_render_command(angle, "/work/model.scad", "/work/renders/test.png")

    # Command is ["bash", "-c", "..."]
    assert cmd[0] == "bash"
    assert cmd[1] == "-c"
    cmd_str = cmd[2]
    assert "--imgsize=1024,1024" in cmd_str
    assert "-o /work/renders/test.png" in cmd_str
    assert "xvfb-run" in cmd_str


# Feature: openscad-mcp-server, Property 8: All predefined angles produce correct commands
def test_all_predefined_angles_specify_png_1024() -> None:
    """Every predefined CAMERA_ANGLES entry should produce a command with
    --imgsize=1024,1024, PNG output, and xvfb-run wrapper."""
    for angle in CAMERA_ANGLES:
        cmd = build_render_command(angle, "/work/m.scad", f"/work/renders/{angle.label}.png")
        assert cmd[0] == "bash"
        cmd_str = cmd[2]
        assert "--imgsize=1024,1024" in cmd_str
        assert f"-o /work/renders/{angle.label}.png" in cmd_str
        assert "xvfb-run" in cmd_str


# ---------------------------------------------------------------------------
# Property 9: Partial render failure reports failed angles
# ---------------------------------------------------------------------------


# Feature: openscad-mcp-server, Property 9: Partial render failure reports failed angles
@given(
    fail_indices=st.sets(
        st.integers(min_value=0, max_value=len(CAMERA_ANGLES) - 1),
        min_size=1,
        max_size=len(CAMERA_ANGLES) - 1,
    )
)
@settings(max_examples=100)
def test_partial_render_failure_reports_failed_angles(
    tmp_path_factory, fail_indices: set[int]
) -> None:
    """When a subset of angles fail, the error response should list exactly
    the labels of the failed angles while still returning successful images."""
    tmp_path = tmp_path_factory.mktemp("render")
    fm = _make_file_manager(tmp_path)
    (fm.working_dir / "model.stl").write_bytes(b"solid dummy")

    fail_labels = {CAMERA_ANGLES[i].label for i in fail_indices}
    call_count = 0

    async def _partial_fail_run(image, command, mounts=None, timeout=300):
        nonlocal call_count
        # Determine which angle this call is for based on call order
        angle = CAMERA_ANGLES[call_count]
        call_count += 1

        if angle.label in fail_labels:
            return ContainerResult(exit_code=1, stdout="", stderr=f"Failed: {angle.label}")

        # Write the PNG for successful angles
        png_name = f"{angle.label}.png"
        local_path = fm.renders_dir / png_name
        local_path.parent.mkdir(parents=True, exist_ok=True)
        local_path.write_bytes(_MINIMAL_PNG)
        return ContainerResult(exit_code=0, stdout="", stderr="")

    mgr = ContainerManager("docker", "docker")
    with patch.object(mgr, "run", side_effect=_partial_fail_run):
        result = asyncio.run(run_render_images("model.stl", mgr, fm))

    # Failed angles should be reported
    reported_fail_labels = {f.label for f in result.failures}
    assert reported_fail_labels == fail_labels

    # Successful angles should still have images
    success_labels = {label for label, _ in result.image_contents}
    expected_success = {a.label for a in CAMERA_ANGLES} - fail_labels
    assert success_labels == expected_success

    # Each failure should include error text
    for failure in result.failures:
        assert failure.error


# Feature: openscad-mcp-server, Property 9: All angles fail
def test_all_angles_fail(tmp_path: Path) -> None:
    """When all angles fail, failures should list all 8 labels and no images returned."""
    fm = _make_file_manager(tmp_path)
    (fm.working_dir / "model.stl").write_bytes(b"solid dummy")

    async def _all_fail(image, command, mounts=None, timeout=300):
        return ContainerResult(exit_code=1, stdout="", stderr="render error")

    mgr = ContainerManager("docker", "docker")
    with patch.object(mgr, "run", side_effect=_all_fail):
        result = asyncio.run(run_render_images("model.stl", mgr, fm))

    assert len(result.failures) == 8
    assert len(result.image_contents) == 0
    assert {f.label for f in result.failures} == set(ANGLE_LABELS)


# ---------------------------------------------------------------------------
# Property 10: Render tool returns MCP ImageContent blocks
# ---------------------------------------------------------------------------


# Feature: openscad-mcp-server, Property 10: Render tool returns MCP ImageContent blocks
def test_render_returns_valid_base64_image_data(tmp_path: Path) -> None:
    """For any successful render, each image should be valid base64-encoded PNG
    data, and the text block should contain camera position and rotation for all angles."""
    fm = _make_file_manager(tmp_path)
    (fm.working_dir / "model.stl").write_bytes(b"solid dummy")
    mgr = ContainerManager("docker", "docker")

    with patch.object(mgr, "run", side_effect=_successful_container_run(fm)):
        result = asyncio.run(run_render_images("model.stl", mgr, fm))

    # Each image_content entry should have valid base64 data
    for label, b64_data in result.image_contents:
        assert b64_data  # non-empty
        decoded = base64.b64decode(b64_data)
        # Should start with PNG magic bytes
        assert decoded[:4] == b"\x89PNG"

    # Text content should have camera params for all angles
    metadata = json.loads(result.text_content)
    for angle_meta in metadata["angles"]:
        assert "label" in angle_meta
        assert "camera_position" in angle_meta
        assert "camera_rotation" in angle_meta
        assert len(angle_meta["camera_position"]) == 3
        assert len(angle_meta["camera_rotation"]) == 3


# Feature: openscad-mcp-server, Property 10: Image data matches written PNGs
@given(
    png_payload=st.binary(min_size=8, max_size=200).map(
        lambda b: b"\x89PNG\r\n\x1a\n" + b
    )
)
@settings(max_examples=50)
def test_render_image_data_matches_written_png(
    tmp_path_factory, png_payload: bytes
) -> None:
    """The base64 data returned for each angle should decode to exactly the
    bytes that were written to disk by the container."""
    tmp_path = tmp_path_factory.mktemp("render")
    fm = _make_file_manager(tmp_path)
    (fm.working_dir / "model.stl").write_bytes(b"solid dummy")

    async def _write_custom_png(image, command, mounts=None, timeout=300):
        if len(command) >= 3 and command[0] == "bash" and command[1] == "-c":
            import re
            m = re.search(r"-o\s+(\S+)", command[2])
            if m:
                png_name = Path(m.group(1)).name
                local_path = fm.renders_dir / png_name
                local_path.parent.mkdir(parents=True, exist_ok=True)
                local_path.write_bytes(png_payload)
        else:
            for i, arg in enumerate(command):
                if arg == "-o" and i + 1 < len(command):
                    png_name = Path(command[i + 1]).name
                    local_path = fm.renders_dir / png_name
                    local_path.parent.mkdir(parents=True, exist_ok=True)
                    local_path.write_bytes(png_payload)
                    break
        return ContainerResult(exit_code=0, stdout="", stderr="")

    mgr = ContainerManager("docker", "docker")
    with patch.object(mgr, "run", side_effect=_write_custom_png):
        result = asyncio.run(run_render_images("model.stl", mgr, fm))

    for _, b64_data in result.image_contents:
        assert base64.b64decode(b64_data) == png_payload
