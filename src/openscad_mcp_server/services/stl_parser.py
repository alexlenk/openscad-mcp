"""Lightweight STL binary/ASCII parser for geometry metadata extraction."""

from __future__ import annotations

import re
import struct
from dataclasses import dataclass
from pathlib import Path


@dataclass
class BoundingBox:
    """Axis-aligned bounding box."""

    min_x: float
    min_y: float
    min_z: float
    max_x: float
    max_y: float
    max_z: float

    @property
    def dimensions(self) -> tuple[float, float, float]:
        return (self.max_x - self.min_x, self.max_y - self.min_y, self.max_z - self.min_z)


@dataclass
class StlMetadata:
    """Geometry metadata extracted from an STL file."""

    file_size_bytes: int
    facet_count: int
    vertex_count: int
    bounding_box: BoundingBox
    volume_cm3: float
    surface_area_cm2: float
    is_manifold: bool


def _signed_volume_of_triangle(
    v1: tuple[float, float, float],
    v2: tuple[float, float, float],
    v3: tuple[float, float, float],
) -> float:
    """Signed volume of tetrahedron formed by triangle and origin."""
    return (
        v1[0] * (v2[1] * v3[2] - v2[2] * v3[1])
        - v1[1] * (v2[0] * v3[2] - v2[2] * v3[0])
        + v1[2] * (v2[0] * v3[1] - v2[1] * v3[0])
    ) / 6.0


def _triangle_area(
    v1: tuple[float, float, float],
    v2: tuple[float, float, float],
    v3: tuple[float, float, float],
) -> float:
    """Area of a triangle defined by three vertices."""
    # Cross product of (v2-v1) x (v3-v1)
    ax, ay, az = v2[0] - v1[0], v2[1] - v1[1], v2[2] - v1[2]
    bx, by, bz = v3[0] - v1[0], v3[1] - v1[1], v3[2] - v1[2]
    cx = ay * bz - az * by
    cy = az * bx - ax * bz
    cz = ax * by - ay * bx
    return 0.5 * (cx * cx + cy * cy + cz * cz) ** 0.5


def _check_manifold(edges: dict[tuple[tuple[float, ...], tuple[float, ...]], int]) -> bool:
    """A mesh is manifold if every edge is shared by exactly 2 triangles."""
    return all(count == 2 for count in edges.values())


def _edge_key(
    v1: tuple[float, float, float], v2: tuple[float, float, float]
) -> tuple[tuple[float, ...], tuple[float, ...]]:
    """Canonical edge key (sorted vertex pair)."""
    a = tuple(round(c, 6) for c in v1)
    b = tuple(round(c, 6) for c in v2)
    return (a, b) if a <= b else (b, a)


def parse_stl(path: Path) -> StlMetadata:
    """Parse an STL file and return geometry metadata.

    Handles both binary and ASCII STL formats.
    """
    data = path.read_bytes()
    file_size = len(data)

    # Detect ASCII vs binary: ASCII starts with "solid " and contains "facet"
    is_ascii = data[:6] == b"solid " and b"facet" in data[:1000]

    if is_ascii:
        return _parse_ascii_stl(data, file_size)
    return _parse_binary_stl(data, file_size)


def _parse_binary_stl(data: bytes, file_size: int) -> StlMetadata:
    """Parse a binary STL file."""
    if len(data) < 84:
        return _empty_metadata(file_size)

    facet_count = struct.unpack_from("<I", data, 80)[0]
    if facet_count == 0:
        return _empty_metadata(file_size)

    vertices: set[tuple[float, ...]] = set()
    edges: dict[tuple[tuple[float, ...], tuple[float, ...]], int] = {}
    min_x = min_y = min_z = float("inf")
    max_x = max_y = max_z = float("-inf")
    total_volume = 0.0
    total_area = 0.0

    offset = 84
    for _ in range(facet_count):
        if offset + 50 > len(data):
            break
        # Skip normal (12 bytes), read 3 vertices (36 bytes), skip attr (2 bytes)
        v1 = struct.unpack_from("<3f", data, offset + 12)
        v2 = struct.unpack_from("<3f", data, offset + 24)
        v3 = struct.unpack_from("<3f", data, offset + 36)
        offset += 50

        for v in (v1, v2, v3):
            rounded = tuple(round(c, 6) for c in v)
            vertices.add(rounded)
            min_x, min_y, min_z = min(min_x, v[0]), min(min_y, v[1]), min(min_z, v[2])
            max_x, max_y, max_z = max(max_x, v[0]), max(max_y, v[1]), max(max_z, v[2])

        total_volume += _signed_volume_of_triangle(v1, v2, v3)
        total_area += _triangle_area(v1, v2, v3)

        for a, b in ((v1, v2), (v2, v3), (v3, v1)):
            ek = _edge_key(a, b)
            edges[ek] = edges.get(ek, 0) + 1

    return StlMetadata(
        file_size_bytes=file_size,
        facet_count=facet_count,
        vertex_count=len(vertices),
        bounding_box=BoundingBox(min_x, min_y, min_z, max_x, max_y, max_z),
        volume_cm3=round(abs(total_volume) / 1000.0, 3),  # mm³ → cm³
        surface_area_cm2=round(total_area / 100.0, 3),  # mm² → cm²
        is_manifold=_check_manifold(edges),
    )


_VERTEX_RE = re.compile(r"vertex\s+([-\d.eE+]+)\s+([-\d.eE+]+)\s+([-\d.eE+]+)")


def _parse_ascii_stl(data: bytes, file_size: int) -> StlMetadata:
    """Parse an ASCII STL file."""
    text = data.decode("utf-8", errors="replace")
    matches = _VERTEX_RE.findall(text)

    if not matches:
        return _empty_metadata(file_size)

    vertices: set[tuple[float, ...]] = set()
    edges: dict[tuple[tuple[float, ...], tuple[float, ...]], int] = {}
    min_x = min_y = min_z = float("inf")
    max_x = max_y = max_z = float("-inf")
    total_volume = 0.0
    total_area = 0.0

    # Group vertices into triangles (3 per facet)
    all_verts = [(float(m[0]), float(m[1]), float(m[2])) for m in matches]
    facet_count = len(all_verts) // 3

    for i in range(facet_count):
        v1, v2, v3 = all_verts[i * 3], all_verts[i * 3 + 1], all_verts[i * 3 + 2]
        for v in (v1, v2, v3):
            rounded = tuple(round(c, 6) for c in v)
            vertices.add(rounded)
            min_x, min_y, min_z = min(min_x, v[0]), min(min_y, v[1]), min(min_z, v[2])
            max_x, max_y, max_z = max(max_x, v[0]), max(max_y, v[1]), max(max_z, v[2])

        total_volume += _signed_volume_of_triangle(v1, v2, v3)
        total_area += _triangle_area(v1, v2, v3)

        for a, b in ((v1, v2), (v2, v3), (v3, v1)):
            ek = _edge_key(a, b)
            edges[ek] = edges.get(ek, 0) + 1

    return StlMetadata(
        file_size_bytes=file_size,
        facet_count=facet_count,
        vertex_count=len(vertices),
        bounding_box=BoundingBox(min_x, min_y, min_z, max_x, max_y, max_z),
        volume_cm3=round(abs(total_volume) / 1000.0, 3),
        surface_area_cm2=round(total_area / 100.0, 3),
        is_manifold=_check_manifold(edges),
    )


def _empty_metadata(file_size: int) -> StlMetadata:
    return StlMetadata(
        file_size_bytes=file_size,
        facet_count=0,
        vertex_count=0,
        bounding_box=BoundingBox(0, 0, 0, 0, 0, 0),
        volume_cm3=0.0,
        surface_area_cm2=0.0,
        is_manifold=True,
    )
