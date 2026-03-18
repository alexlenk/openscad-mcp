"""Tests for selective angle rendering (issue #10)."""

from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path
from unittest.mock import patch

from openscad_mcp_server.models import CAMERA_ANGLES, ContainerResult
from openscad_mcp_server.services.container import ContainerManager
from openscad_mcp_server.services.file_manager import FileManager
from openscad_mcp_server.tools.render_images import run_render_images

_MINIMAL_PNG = (
    b"\x89PNG\r\n\x1a\n"
    b"\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
    b"\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01"
    b"\r\n\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
)


def _mock_run(file_manager: FileManager):
    async def _run(image, command, mounts=None, timeout=300):
        if len(command) >= 3 and command[0] == "bash":
            m = re.search(r"-o\s+(\S+)", command[2])
            if m:
                png_name = Path(m.group(1)).name
                local = file_manager.renders_dir / png_name
                local.parent.mkdir(parents=True, exist_ok=True)
                local.write_bytes(_MINIMAL_PNG)
        return ContainerResult(exit_code=0, stdout="", stderr="")
    return _run


def test_selective_render_single_angle(tmp_path: Path) -> None:
    """Requesting a single angle should return exactly 1 image."""
    fm = FileManager(tmp_path)
    (fm.working_dir / "model.stl").write_bytes(b"solid dummy")
    mgr = ContainerManager("docker", "docker")

    with patch.object(mgr, "run", side_effect=_mock_run(fm)):
        result = asyncio.run(run_render_images("model.stl", mgr, fm, angles=["top"]))

    assert len(result.image_contents) == 1
    assert result.image_contents[0][0] == "top"
    assert len(result.failures) == 0

    metadata = json.loads(result.text_content)
    assert len(metadata["angles"]) == 1
    assert metadata["angles"][0]["label"] == "top"


def test_selective_render_multiple_angles(tmp_path: Path) -> None:
    """Requesting 3 angles should return exactly 3 images."""
    fm = FileManager(tmp_path)
    (fm.working_dir / "model.stl").write_bytes(b"solid dummy")
    mgr = ContainerManager("docker", "docker")

    requested = ["front", "top", "back-left-top-iso"]
    with patch.object(mgr, "run", side_effect=_mock_run(fm)):
        result = asyncio.run(run_render_images("model.stl", mgr, fm, angles=requested))

    labels = [l for l, _ in result.image_contents]
    assert sorted(labels) == sorted(requested)
    assert len(result.failures) == 0


def test_selective_render_unknown_angle(tmp_path: Path) -> None:
    """Requesting an unknown angle should return an error."""
    fm = FileManager(tmp_path)
    (fm.working_dir / "model.stl").write_bytes(b"solid dummy")
    mgr = ContainerManager("docker", "docker")

    with patch.object(mgr, "run", side_effect=_mock_run(fm)):
        result = asyncio.run(run_render_images("model.stl", mgr, fm, angles=["nonexistent"]))

    assert len(result.failures) == 1
    assert result.failures[0].label == "nonexistent"
    metadata = json.loads(result.text_content)
    assert "error" in metadata


def test_selective_render_none_renders_all(tmp_path: Path) -> None:
    """Omitting angles should render all 8."""
    fm = FileManager(tmp_path)
    (fm.working_dir / "model.stl").write_bytes(b"solid dummy")
    mgr = ContainerManager("docker", "docker")

    with patch.object(mgr, "run", side_effect=_mock_run(fm)):
        result = asyncio.run(run_render_images("model.stl", mgr, fm, angles=None))

    assert len(result.image_contents) == 8


def test_selective_render_case_insensitive(tmp_path: Path) -> None:
    """Angle labels should be matched case-insensitively."""
    fm = FileManager(tmp_path)
    (fm.working_dir / "model.stl").write_bytes(b"solid dummy")
    mgr = ContainerManager("docker", "docker")

    with patch.object(mgr, "run", side_effect=_mock_run(fm)):
        result = asyncio.run(run_render_images("model.stl", mgr, fm, angles=["TOP", "Front"]))

    labels = [l for l, _ in result.image_contents]
    assert sorted(labels) == ["front", "top"]
