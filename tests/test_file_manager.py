"""Property tests for FileManager (Properties 1, 2, 16, 17)."""

from __future__ import annotations

import base64
import tempfile
from pathlib import Path

from hypothesis import given, settings, strategies as st

from openscad_mcp_server.models import InspectionImage
from openscad_mcp_server.services.file_manager import FileManager

# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# Valid filename characters — ASCII letters, digits, dash, underscore, dot.
_filename_chars = st.sampled_from(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_."
)
_filenames = st.text(alphabet=_filename_chars, min_size=1, max_size=40).filter(
    lambda s: s.strip(".") != ""
    and any(c.isalnum() or c in "-_" for c in s)
    # Exclude bare dotfiles like ".scad" — pathlib treats them as having no suffix.
    and not (s.startswith(".") and "." not in s[1:])
)

# Arbitrary OpenSCAD code (any text).
_code = st.text(min_size=0, max_size=500)

# Small binary blobs for STL data.
_stl_bytes = st.binary(min_size=1, max_size=256)

# Angle labels matching the 8 predefined angles.
_ANGLE_LABELS = [
    "front", "back", "left", "right",
    "top", "bottom", "front-right-top-iso", "back-left-top-iso",
]


def _make_images(labels: list[str] | None = None) -> list[InspectionImage]:
    """Build a list of InspectionImage instances for the given angle labels."""
    labels = labels or _ANGLE_LABELS
    return [
        InspectionImage(
            angle=label,
            base64_png=base64.b64encode(f"png-{label}".encode()).decode(),
            camera_position=(0, 0, 0),
            camera_rotation=(0, 0, 0),
        )
        for label in labels
    ]


# ---------------------------------------------------------------------------
# Property 1: Save-code round trip
# ---------------------------------------------------------------------------


# Feature: openscad-mcp-server, Property 1: Save-code round trip
@given(code=_code, filename=_filenames)
@settings(max_examples=100)
def test_save_code_round_trip(code: str, filename: str) -> None:
    """Saving code and reading it back yields the exact same string.
    The returned path is absolute and ends with .scad."""
    with tempfile.TemporaryDirectory() as td:
        fm = FileManager(Path(td))
        result_path = fm.save_code(code, filename)

        assert result_path.is_absolute()
        assert result_path.suffix == ".scad"
        assert result_path.read_bytes().decode("utf-8") == code


# ---------------------------------------------------------------------------
# Property 2: Filename extension normalization
# ---------------------------------------------------------------------------


# Feature: openscad-mcp-server, Property 2: Filename extension normalization
@given(filename=_filenames)
@settings(max_examples=100)
def test_filename_extension_normalization(filename: str) -> None:
    """Output path always ends with .scad. If input already ends with .scad
    it is not doubled (no .scad.scad)."""
    with tempfile.TemporaryDirectory() as td:
        fm = FileManager(Path(td))
        result_path = fm.save_code("// test", filename)

        assert result_path.suffix == ".scad"
        assert not result_path.name.endswith(".scad.scad")


# ---------------------------------------------------------------------------
# Property 16: Working area overwrite invariant
# ---------------------------------------------------------------------------


# Feature: openscad-mcp-server, Property 16: Working area overwrite invariant
@given(
    codes=st.lists(_code, min_size=1, max_size=5),
    stl_blobs=st.lists(_stl_bytes, min_size=1, max_size=5),
)
@settings(max_examples=50)
def test_working_area_overwrite_invariant(
    codes: list[str], stl_blobs: list[bytes]
) -> None:
    """After a sequence of save-code, save-stl, and save-renders operations the
    working area contains at most one .scad, at most one .stl, and exactly the
    images from the most recent render."""
    with tempfile.TemporaryDirectory() as td:
        fm = FileManager(Path(td))

        for code in codes:
            fm.save_code(code, "model.scad")

        for blob in stl_blobs:
            fm.save_stl(blob, "model.stl")

        # Render twice — only the last set should survive.
        fm.save_renders(_make_images(["front"]))
        fm.save_renders(_make_images(_ANGLE_LABELS))

        scad_files = list(fm.working_dir.glob("*.scad"))
        stl_files = list(fm.working_dir.glob("*.stl"))
        render_files = list(fm.renders_dir.glob("*.png"))

        assert len(scad_files) == 1
        assert len(stl_files) == 1
        assert len(render_files) == len(_ANGLE_LABELS)
        assert {f.stem for f in render_files} == set(_ANGLE_LABELS)

        # Latest values are the last written.
        assert scad_files[0].read_bytes().decode("utf-8") == codes[-1]
        assert stl_files[0].read_bytes() == stl_blobs[-1]


# ---------------------------------------------------------------------------
# Property 17: Finalize copies all working area artifacts
# ---------------------------------------------------------------------------


# Feature: openscad-mcp-server, Property 17: Finalize copies all working area artifacts
@given(code=_code, stl_data=_stl_bytes)
@settings(max_examples=100)
def test_finalize_copies_all_artifacts(code: str, stl_data: bytes) -> None:
    """Finalize produces an output directory containing copies of all working
    area files with identical content."""
    with tempfile.TemporaryDirectory() as td:
        fm = FileManager(Path(td))

        fm.save_code(code, "model.scad")
        fm.save_stl(stl_data, "model.stl")
        fm.save_renders(_make_images(_ANGLE_LABELS))

        output_dir = fm.finalize()

        assert output_dir.exists()
        assert (output_dir / "model.scad").read_bytes().decode("utf-8") == code
        assert (output_dir / "model.stl").read_bytes() == stl_data

        output_renders = list((output_dir / "renders").glob("*.png"))
        assert len(output_renders) == len(_ANGLE_LABELS)
        assert {f.stem for f in output_renders} == set(_ANGLE_LABELS)

        for label in _ANGLE_LABELS:
            expected = f"png-{label}".encode()
            actual = (output_dir / "renders" / f"{label}.png").read_bytes()
            assert actual == expected
