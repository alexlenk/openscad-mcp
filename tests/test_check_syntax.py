"""Tests for check-syntax tool (issue #6)."""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import patch

from openscad_mcp_server.models import ContainerResult
from openscad_mcp_server.services.container import ContainerError, ContainerManager
from openscad_mcp_server.services.file_manager import FileManager
from openscad_mcp_server.tools.check_syntax import run_check_syntax


def test_valid_syntax(tmp_path: Path) -> None:
    """A successful syntax check should return valid=True."""
    fm = FileManager(tmp_path)
    (fm.working_dir / "model.scad").write_text("cube([10,10,10]);")
    mgr = ContainerManager("docker", "docker")

    async def _ok(image, command, mounts=None, timeout=300):
        return ContainerResult(exit_code=0, stdout="", stderr="")

    with patch.object(mgr, "run", side_effect=_ok):
        result = asyncio.run(run_check_syntax("model.scad", mgr, fm))

    assert result.valid is True
    assert result.errors == []


def test_syntax_error(tmp_path: Path) -> None:
    """A syntax error should return valid=False with error details."""
    fm = FileManager(tmp_path)
    (fm.working_dir / "bad.scad").write_text("cube(")
    mgr = ContainerManager("docker", "docker")

    async def _fail(image, command, mounts=None, timeout=300):
        return ContainerResult(
            exit_code=1,
            stdout="",
            stderr="ERROR: Parser error in line 1: syntax error",
        )

    with patch.object(mgr, "run", side_effect=_fail):
        result = asyncio.run(run_check_syntax("bad.scad", mgr, fm))

    assert result.valid is False
    assert len(result.errors) > 0
    assert "error" in result.errors[0].lower()


def test_warnings_reported(tmp_path: Path) -> None:
    """Warnings should be captured even when the check succeeds."""
    fm = FileManager(tmp_path)
    (fm.working_dir / "warn.scad").write_text("cube(10);")
    mgr = ContainerManager("docker", "docker")

    async def _warn(image, command, mounts=None, timeout=300):
        return ContainerResult(
            exit_code=0,
            stdout="",
            stderr="WARNING: Object may not be a valid 2-manifold at line 45",
        )

    with patch.object(mgr, "run", side_effect=_warn):
        result = asyncio.run(run_check_syntax("warn.scad", mgr, fm))

    assert result.valid is True
    assert len(result.warnings) == 1
    assert "manifold" in result.warnings[0].lower()


def test_container_error(tmp_path: Path) -> None:
    """A container error should return valid=False."""
    fm = FileManager(tmp_path)
    (fm.working_dir / "model.scad").write_text("cube(10);")
    mgr = ContainerManager("docker", "docker")

    async def _err(image, command, mounts=None, timeout=300):
        raise ContainerError("Runtime unavailable", image=image)

    with patch.object(mgr, "run", side_effect=_err):
        result = asyncio.run(run_check_syntax("model.scad", mgr, fm))

    assert result.valid is False
    assert len(result.errors) > 0
