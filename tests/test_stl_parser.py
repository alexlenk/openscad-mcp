"""Tests for STL parser and measure-stl tool."""

from __future__ import annotations

import struct
from pathlib import Path

import pytest
from hypothesis import given, settings, strategies as st

from openscad_mcp_server.services.stl_parser import (
    BoundingBox,
    StlMetadata,
    parse_stl,
)
from openscad_mcp_server.services.file_manager import FileManager
from openscad_mcp_server.tools.measure_stl import run_measure_stl


# ---------------------------------------------------------------------------
# Helpers: generate minimal binary STL
# ---------------------------------------------------------------------------

def _make_binary_stl(triangles: list[tuple[tuple, tuple, tuple]]) -> bytes:
    """Build a minimal binary STL from a list of (v1, v2, v3) triangles."""
    header = b"\x00" * 80
    count = struct.pack("<I", len(triangles))
    facets = b""
    for v1, v2, v3 in triangles:
        normal = (0.0, 0.0, 0.0)
        facets += struct.pack("<3f", *normal)
        facets += struct.pack("<3f", *v1)
        facets += struct.pack("<3f", *v2)
        facets += struct.pack("<3f", *v3)
        facets += struct.pack("<H", 0)  # attribute byte count
    return header + count + facets


# A unit cube as 12 triangles (2 per face)
_CUBE_TRIS = [
    # front face (z=1)
    ((0, 0, 1), (1, 0, 1), (1, 1, 1)),
    ((0, 0, 1), (1, 1, 1), (0, 1, 1)),
    # back face (z=0)
    ((0, 0, 0), (0, 1, 0), (1, 1, 0)),
    ((0, 0, 0), (1, 1, 0), (1, 0, 0)),
    # top face (y=1)
    ((0, 1, 0), (0, 1, 1), (1, 1, 1)),
    ((0, 1, 0), (1, 1, 1), (1, 1, 0)),
    # bottom face (y=0)
    ((0, 0, 0), (1, 0, 0), (1, 0, 1)),
    ((0, 0, 0), (1, 0, 1), (0, 0, 1)),
    # right face (x=1)
    ((1, 0, 0), (1, 1, 0), (1, 1, 1)),
    ((1, 0, 0), (1, 1, 1), (1, 0, 1)),
    # left face (x=0)
    ((0, 0, 0), (0, 0, 1), (0, 1, 1)),
    ((0, 0, 0), (0, 1, 1), (0, 1, 0)),
]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_parse_binary_stl_cube(tmp_path: Path) -> None:
    """A unit cube STL should have 12 facets, 8 vertices, and correct bounding box."""
    stl_data = _make_binary_stl(_CUBE_TRIS)
    stl_file = tmp_path / "cube.stl"
    stl_file.write_bytes(stl_data)

    meta = parse_stl(stl_file)

    assert meta.facet_count == 12
    assert meta.vertex_count == 8
    assert meta.is_manifold is True
    bb = meta.bounding_box
    assert bb.min_x == pytest.approx(0.0)
    assert bb.min_y == pytest.approx(0.0)
    assert bb.min_z == pytest.approx(0.0)
    assert bb.max_x == pytest.approx(1.0)
    assert bb.max_y == pytest.approx(1.0)
    assert bb.max_z == pytest.approx(1.0)
    dims = bb.dimensions
    assert dims == pytest.approx((1.0, 1.0, 1.0))
    assert meta.volume_cm3 > 0
    assert meta.surface_area_cm2 > 0


def test_parse_ascii_stl(tmp_path: Path) -> None:
    """An ASCII STL with a single triangle should parse correctly."""
    ascii_stl = """\
solid test
  facet normal 0 0 1
    outer loop
      vertex 0 0 0
      vertex 1 0 0
      vertex 0 1 0
    endloop
  endfacet
endsolid test
"""
    stl_file = tmp_path / "tri.stl"
    stl_file.write_text(ascii_stl)

    meta = parse_stl(stl_file)

    assert meta.facet_count == 1
    assert meta.vertex_count == 3
    bb = meta.bounding_box
    assert bb.min_x == pytest.approx(0.0)
    assert bb.max_x == pytest.approx(1.0)
    assert bb.max_y == pytest.approx(1.0)


def test_empty_stl(tmp_path: Path) -> None:
    """An empty binary STL should return zero counts."""
    stl_data = _make_binary_stl([])
    stl_file = tmp_path / "empty.stl"
    stl_file.write_bytes(stl_data)

    meta = parse_stl(stl_file)
    assert meta.facet_count == 0
    assert meta.vertex_count == 0


def test_bounding_box_dimensions() -> None:
    """BoundingBox.dimensions should return correct deltas."""
    bb = BoundingBox(min_x=-5, min_y=0, min_z=10, max_x=5, max_y=20, max_z=30)
    assert bb.dimensions == (10.0, 20.0, 20.0)


def test_measure_stl_tool(tmp_path: Path) -> None:
    """measure-stl tool should return structured metadata from an STL file."""
    stl_data = _make_binary_stl(_CUBE_TRIS)
    fm = FileManager(tmp_path)
    (fm.working_dir / "model.stl").write_bytes(stl_data)

    result = run_measure_stl("model.stl", fm)

    assert result.facet_count == 12
    assert result.vertex_count == 8
    assert result.is_manifold is True
    assert result.dimensions["x"] == pytest.approx(1.0, abs=0.01)
    assert result.dimensions["y"] == pytest.approx(1.0, abs=0.01)
    assert result.dimensions["z"] == pytest.approx(1.0, abs=0.01)
    assert result.volume_cm3 > 0
    assert result.file_size_bytes > 0


def test_measure_stl_file_not_found(tmp_path: Path) -> None:
    """measure-stl should raise FileNotFoundError for missing files."""
    fm = FileManager(tmp_path)
    with pytest.raises(FileNotFoundError):
        run_measure_stl("nonexistent.stl", fm)


@given(
    x=st.floats(min_value=1, max_value=100, allow_nan=False),
    y=st.floats(min_value=1, max_value=100, allow_nan=False),
    z=st.floats(min_value=1, max_value=100, allow_nan=False),
)
@settings(max_examples=50)
def test_bounding_box_dimensions_property(x: float, y: float, z: float) -> None:
    """For any bounding box, dimensions should equal max - min for each axis."""
    bb = BoundingBox(min_x=0, min_y=0, min_z=0, max_x=x, max_y=y, max_z=z)
    dx, dy, dz = bb.dimensions
    assert dx == pytest.approx(x)
    assert dy == pytest.approx(y)
    assert dz == pytest.approx(z)
