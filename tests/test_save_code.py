"""Property tests for save-code tool (Property 24: Library review enforcement on save)."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
from hypothesis import assume, given, settings, strategies as st

from openscad_mcp_server.services.file_manager import FileManager
from openscad_mcp_server.services.session import SessionState
from openscad_mcp_server.tools.save_code import (
    LibraryNotReviewedError,
    SaveCodeResult,
    parse_library_references,
    run_save_code,
)

# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# Library names: alphanumeric with hyphens/underscores, like real OpenSCAD libs
_lib_names = st.from_regex(r"[A-Za-z][A-Za-z0-9_-]{0,20}", fullmatch=True)

# Simple OpenSCAD code without library references
_plain_code = st.just("cube([10, 10, 10]);")

# Filenames (no path separators)
_filenames = st.from_regex(r"[A-Za-z][A-Za-z0-9_-]{0,15}", fullmatch=True)


def _code_with_libs(libs: list[str]) -> str:
    """Generate OpenSCAD code that references the given libraries."""
    lines = []
    for lib in libs:
        lines.append(f"use <{lib}/std.scad>")
    lines.append("cube([10, 10, 10]);")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Property 24: Library review enforcement on save
# ---------------------------------------------------------------------------


# Feature: openscad-mcp-server, Property 24: Library review enforcement on save
@given(libs=st.lists(_lib_names, min_size=1, max_size=5, unique=True))
@settings(max_examples=100)
def test_save_rejected_when_libraries_not_reviewed(libs: list[str]) -> None:
    """For any code referencing libraries, save-code must reject if those
    libraries have not been reviewed via read-library-source."""
    session = SessionState()
    with tempfile.TemporaryDirectory() as tmp:
        fm = FileManager(Path(tmp))
        code = _code_with_libs(libs)

        with pytest.raises(LibraryNotReviewedError) as exc_info:
            run_save_code(code, "model.scad", session, fm)

        # Error must list all unreviewed libraries
        for lib in libs:
            assert lib in exc_info.value.libraries


# Feature: openscad-mcp-server, Property 24: Save succeeds when all libraries reviewed
@given(libs=st.lists(_lib_names, min_size=1, max_size=5, unique=True))
@settings(max_examples=100)
def test_save_succeeds_when_all_libraries_reviewed(libs: list[str]) -> None:
    """When all referenced libraries have been reviewed, save-code should
    succeed and return a valid file path."""
    session = SessionState()
    for lib in libs:
        session.mark_library_reviewed(lib)

    with tempfile.TemporaryDirectory() as tmp:
        fm = FileManager(Path(tmp))
        code = _code_with_libs(libs)

        result = run_save_code(code, "model.scad", session, fm)

        assert isinstance(result, SaveCodeResult)
        saved = Path(result.file_path)
        assert saved.exists()
        assert saved.suffix == ".scad"
        assert saved.read_text() == code


# Feature: openscad-mcp-server, Property 24: Partial review still rejects
@given(
    reviewed=st.lists(_lib_names, min_size=1, max_size=3, unique=True),
    unreviewed=st.lists(_lib_names, min_size=1, max_size=3, unique=True),
)
@settings(max_examples=100)
def test_save_rejected_when_partially_reviewed(
    reviewed: list[str], unreviewed: list[str]
) -> None:
    """If only some referenced libraries are reviewed, save must still reject,
    listing exactly the unreviewed ones."""
    # Ensure no overlap between reviewed and unreviewed sets
    assume(not set(reviewed) & set(unreviewed))

    session = SessionState()
    for lib in reviewed:
        session.mark_library_reviewed(lib)

    all_libs = reviewed + unreviewed

    with tempfile.TemporaryDirectory() as tmp:
        fm = FileManager(Path(tmp))
        code = _code_with_libs(all_libs)

        with pytest.raises(LibraryNotReviewedError) as exc_info:
            run_save_code(code, "model.scad", session, fm)

        # Only the unreviewed libraries should be flagged
        assert exc_info.value.libraries == set(unreviewed)


# Feature: openscad-mcp-server, Property 24: No libraries means no enforcement
@given(filename=_filenames)
@settings(max_examples=50)
def test_save_succeeds_without_library_references(filename: str) -> None:
    """Code without include/use statements should always save successfully,
    regardless of session review state."""
    session = SessionState()

    with tempfile.TemporaryDirectory() as tmp:
        fm = FileManager(Path(tmp))
        result = run_save_code("cube([1,1,1]);", filename, session, fm)

        assert isinstance(result, SaveCodeResult)
        assert Path(result.file_path).exists()


# ---------------------------------------------------------------------------
# parse_library_references unit tests
# ---------------------------------------------------------------------------


def test_parse_include_and_use() -> None:
    """Both include and use statements should be parsed."""
    code = 'include <BOSL2/std.scad>\nuse <NopSCADlib/core.scad>\ncube(10);'
    assert parse_library_references(code) == {"BOSL2", "NopSCADlib"}


def test_parse_no_references() -> None:
    """Code without library references returns empty set."""
    assert parse_library_references("cube([1,1,1]);") == set()


def test_parse_ignores_local_includes() -> None:
    """Local includes (no directory prefix) should not be treated as libraries."""
    code = 'include <utils.scad>\ncube(10);'
    assert parse_library_references(code) == set()
