"""Property tests for LibraryService (Properties 11, 12, 13, 14, 23)."""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, patch

from hypothesis import given, settings, strategies as st

from openscad_mcp_server.models import LibraryCatalogEntry
from openscad_mcp_server.services.library_service import LibraryService, LibraryServiceError

# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# Library names: ASCII alphanumeric with hyphens/underscores, filesystem-safe
_lib_names = st.text(
    alphabet="abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_",
    min_size=1,
    max_size=30,
).filter(lambda s: s.strip("-_") != "")

# Descriptions: arbitrary non-empty text
_descriptions = st.text(min_size=1, max_size=200).filter(lambda s: s.strip() != "")

# Source URLs pointing to a repo host
_source_urls = st.builds(
    lambda owner, repo: f"https://github.com/{owner}/{repo}",
    owner=st.text(alphabet="abcdefghijklmnopqrstuvwxyz", min_size=1, max_size=15),
    repo=st.text(alphabet="abcdefghijklmnopqrstuvwxyz0123456789-", min_size=1, max_size=20),
)

# Optional docs URLs
_docs_urls = st.one_of(
    st.none(),
    st.builds(
        lambda name: f"https://example.com/docs/{name}",
        name=st.text(alphabet="abcdefghijklmnopqrstuvwxyz", min_size=1, max_size=15),
    ),
)


def _build_catalog_html(entries: list[dict]) -> str:
    """Build a minimal HTML page with library list items."""
    items = []
    for e in entries:
        links = f'<a href="{e["source_url"]}">{e["name"]}</a>'
        if e.get("docs_url"):
            links += f' <a href="{e["docs_url"]}">docs</a>'
        items.append(f'<li><b>{e["name"]}</b> - {e["description"]} {links}</li>')
    return f"<html><body><ul>{''.join(items)}</ul></body></html>"


# Strategy for generating catalog entry dicts
_catalog_entry_dicts = st.fixed_dictionaries({
    "name": _lib_names,
    "description": _descriptions,
    "source_url": _source_urls,
    "docs_url": _docs_urls,
})


# ---------------------------------------------------------------------------
# Property 11: Catalog parser extracts structured entries
# ---------------------------------------------------------------------------


# Feature: openscad-mcp-server, Property 11: Catalog parser extracts structured entries
@given(entry_dicts=st.lists(_catalog_entry_dicts, min_size=1, max_size=10))
@settings(max_examples=100)
def test_catalog_parser_extracts_structured_entries(entry_dicts: list[dict]) -> None:
    """For any well-formed HTML page containing library listings, the parser
    should extract at least one LibraryCatalogEntry where each entry has a
    non-empty name, description, and source URL."""
    html = _build_catalog_html(entry_dicts)
    entries = LibraryService.parse_catalog_html(html)

    assert len(entries) >= 1

    for entry in entries:
        assert isinstance(entry, LibraryCatalogEntry)
        assert entry.name.strip() != ""
        assert entry.description.strip() != ""
        assert entry.source_url.startswith("http")


# ---------------------------------------------------------------------------
# Property 12: Library cache hit avoids re-download
# ---------------------------------------------------------------------------


# Feature: openscad-mcp-server, Property 12: Library cache hit avoids re-download
@given(name=_lib_names, source_url=_source_urls)
@settings(max_examples=100)
def test_library_cache_hit_avoids_redownload(name: str, source_url: str) -> None:
    """For any library fetched once, calling fetch_library again without
    force_refresh returns the same path without triggering a new download.
    Calling with force_refresh=True triggers a fresh download."""
    import asyncio

    with tempfile.TemporaryDirectory() as td:
        libs_dir = Path(td) / "libraries"
        svc = LibraryService(libs_dir)

        # Pre-populate the library directory with a .scad file to simulate a fetch
        lib_dir = libs_dir / name
        lib_dir.mkdir(parents=True, exist_ok=True)
        (lib_dir / "main.scad").write_text("module test() {}")

        download_count = 0
        original_download = svc._download_library

        async def mock_download(url: str, dest: Path) -> None:
            nonlocal download_count
            download_count += 1
            dest.mkdir(parents=True, exist_ok=True)
            (dest / "main.scad").write_text("module test() {}")

        svc._download_library = mock_download  # type: ignore[assignment]

        # First fetch — uses pre-populated dir, no download needed
        path1 = asyncio.run(svc.fetch_library(name, source_url))
        assert path1 == lib_dir
        first_download_count = download_count

        # Second fetch — should use cache, no new download
        path2 = asyncio.run(svc.fetch_library(name, source_url))
        assert path2 == path1
        assert download_count == first_download_count  # No additional download

        # Force refresh — should trigger a new download
        path3 = asyncio.run(svc.fetch_library(name, source_url, force_refresh=True))
        assert path3 == lib_dir
        assert download_count == first_download_count + 1


# ---------------------------------------------------------------------------
# Property 13: Fetch-library success returns valid path
# ---------------------------------------------------------------------------


# Feature: openscad-mcp-server, Property 13: Fetch-library success returns valid path
@given(
    name=_lib_names,
    source_url=_source_urls,
    scad_filenames=st.lists(
        st.text(alphabet="abcdefghijklmnopqrstuvwxyz", min_size=1, max_size=15).map(lambda s: s + ".scad"),
        min_size=1,
        max_size=5,
        unique=True,
    ),
)
@settings(max_examples=100)
def test_fetch_library_success_returns_valid_path(
    name: str, source_url: str, scad_filenames: list[str]
) -> None:
    """For any successful library fetch, the returned path should exist on disk
    and contain at least one .scad file."""
    import asyncio

    with tempfile.TemporaryDirectory() as td:
        libs_dir = Path(td) / "libraries"
        svc = LibraryService(libs_dir)

        async def mock_download(url: str, dest: Path) -> None:
            dest.mkdir(parents=True, exist_ok=True)
            for fn in scad_filenames:
                (dest / fn).write_text(f"module {fn.removesuffix('.scad')}() {{}}")

        svc._download_library = mock_download  # type: ignore[assignment]

        path = asyncio.run(svc.fetch_library(name, source_url))

        assert path.exists()
        assert path.is_dir()
        scad_files = list(path.rglob("*.scad"))
        assert len(scad_files) >= 1


# ---------------------------------------------------------------------------
# Property 14: Fetch-library failure includes source URL
# ---------------------------------------------------------------------------


# Feature: openscad-mcp-server, Property 14: Fetch-library failure includes source URL
@given(
    name=_lib_names,
    source_url=_source_urls,
    reason=st.text(min_size=1, max_size=100).filter(lambda s: s.strip() != ""),
)
@settings(max_examples=100)
def test_fetch_library_failure_includes_source_url(
    name: str, source_url: str, reason: str
) -> None:
    """For any failed library download, the error message should contain the
    source repository URL and a non-empty reason string."""
    import asyncio

    with tempfile.TemporaryDirectory() as td:
        libs_dir = Path(td) / "libraries"
        svc = LibraryService(libs_dir)

        async def mock_download_fail(url: str, dest: Path) -> None:
            raise RuntimeError(reason)

        svc._download_library = mock_download_fail  # type: ignore[assignment]

        try:
            asyncio.run(svc.fetch_library(name, source_url))
            raise AssertionError("Expected LibraryServiceError")
        except LibraryServiceError as exc:
            assert source_url in str(exc)
            assert exc.source_url == source_url
            assert len(str(exc)) > 0


# ---------------------------------------------------------------------------
# Property 23: Read-library-source returns source and summary
# ---------------------------------------------------------------------------

# Strategy for generating OpenSCAD module definitions
_param_names = st.text(alphabet="abcdefghijklmnopqrstuvwxyz_", min_size=1, max_size=10)
_module_names = st.text(alphabet="abcdefghijklmnopqrstuvwxyz_", min_size=1, max_size=20)

_module_defs = st.builds(
    lambda name, params: f"module {name}({', '.join(params)}) {{}}\n",
    name=_module_names,
    params=st.lists(_param_names, min_size=0, max_size=4, unique=True),
)


# Feature: openscad-mcp-server, Property 23: Read-library-source returns source and summary
@given(
    name=_lib_names,
    module_sources=st.lists(_module_defs, min_size=1, max_size=5),
    coord_hint=st.sampled_from(["// Z-up coordinate system\n", "// Y-up\n", ""]),
    unit_hint=st.sampled_from(["// Units: millimeters\n", "// inches\n", ""]),
)
@settings(max_examples=100)
def test_read_library_source_returns_source_and_summary(
    name: str,
    module_sources: list[str],
    coord_hint: str,
    unit_hint: str,
) -> None:
    """For any fetched library containing .scad files, read_source should return
    a compact signatures-only summary (not full source) and a structured list of
    module names and parameter signatures."""
    with tempfile.TemporaryDirectory() as td:
        libs_dir = Path(td) / "libraries"
        lib_dir = libs_dir / name
        lib_dir.mkdir(parents=True, exist_ok=True)

        # Write .scad files with module definitions
        full_source = coord_hint + unit_hint + "\n".join(module_sources)
        (lib_dir / "main.scad").write_text(full_source)

        svc = LibraryService(libs_dir)
        result = svc.read_source(name)

        # Source code should be a compact summary, not the full source
        assert result.name == name
        assert result.source_code != ""
        # Summary should contain "Module signatures" section
        assert "Module signatures" in result.source_code
        # Summary should contain module keyword for each extracted module
        for mod in result.modules:
            assert f"module {mod.name}(" in result.source_code

        # The summary should NOT contain the full implementation bodies
        # (no curly braces from module bodies in the summary)
        assert "{}" not in result.source_code

        # Modules list should have entries for each module definition
        assert len(result.modules) >= 1
        module_names_found = {m.name for m in result.modules}
        for mod_src in module_sources:
            # Extract the module name from the source string
            mod_name = mod_src.split("module ")[1].split("(")[0]
            assert mod_name in module_names_found

        # Each module should have a parameters list (possibly empty)
        for mod in result.modules:
            assert isinstance(mod.parameters, list)

        # Coordinate system detection
        if "Z-up" in coord_hint or "z-up" in coord_hint.lower():
            assert result.coordinate_system is not None
        if "Y-up" in coord_hint or "y-up" in coord_hint.lower():
            assert result.coordinate_system is not None

        # Units detection
        if "millimeter" in unit_hint.lower():
            assert result.units is not None
        if "inches" in unit_hint.lower():
            assert result.units is not None



# ---------------------------------------------------------------------------
# Property: read_source_file returns specific file content
# ---------------------------------------------------------------------------


@given(name=_lib_names)
@settings(max_examples=50)
def test_read_source_file_returns_file_content(name: str) -> None:
    """read_source_file should return the full content of a specific .scad file."""
    with tempfile.TemporaryDirectory() as td:
        libs_dir = Path(td) / "libraries"
        lib_dir = libs_dir / name
        lib_dir.mkdir(parents=True, exist_ok=True)

        content = "module box(w, d, h) {\n  cube([w, d, h]);\n}\n"
        (lib_dir / "box.scad").write_text(content)

        svc = LibraryService(libs_dir)
        result = svc.read_source_file(name, "box.scad")
        assert result == content


def test_read_source_file_extracts_module() -> None:
    """read_source_file with module_name should return only that module's source."""
    with tempfile.TemporaryDirectory() as td:
        libs_dir = Path(td) / "libraries"
        lib_dir = libs_dir / "testlib"
        lib_dir.mkdir(parents=True, exist_ok=True)

        content = (
            "module foo(a) {\n  cube(a);\n}\n\n"
            "module bar(b, c) {\n  cylinder(h=b, r=c);\n}\n"
        )
        (lib_dir / "shapes.scad").write_text(content)

        svc = LibraryService(libs_dir)

        foo_src = svc.read_source_file("testlib", "shapes.scad", module_name="foo")
        assert "module foo(a)" in foo_src
        assert "cube(a)" in foo_src
        assert "module bar" not in foo_src

        bar_src = svc.read_source_file("testlib", "shapes.scad", module_name="bar")
        assert "module bar(b, c)" in bar_src
        assert "cylinder" in bar_src
        assert "module foo" not in bar_src


def test_read_source_file_missing_file() -> None:
    """read_source_file should raise LibraryServiceError for a missing file."""
    with tempfile.TemporaryDirectory() as td:
        libs_dir = Path(td) / "libraries"
        lib_dir = libs_dir / "testlib"
        lib_dir.mkdir(parents=True, exist_ok=True)
        (lib_dir / "main.scad").write_text("module m() {}")

        svc = LibraryService(libs_dir)
        try:
            svc.read_source_file("testlib", "nonexistent.scad")
            raise AssertionError("Expected LibraryServiceError")
        except LibraryServiceError as exc:
            assert "nonexistent.scad" in str(exc)


def test_read_source_file_missing_module() -> None:
    """read_source_file should raise LibraryServiceError for a missing module."""
    with tempfile.TemporaryDirectory() as td:
        libs_dir = Path(td) / "libraries"
        lib_dir = libs_dir / "testlib"
        lib_dir.mkdir(parents=True, exist_ok=True)
        (lib_dir / "main.scad").write_text("module existing() {}")

        svc = LibraryService(libs_dir)
        try:
            svc.read_source_file("testlib", "main.scad", module_name="nonexistent")
            raise AssertionError("Expected LibraryServiceError")
        except LibraryServiceError as exc:
            assert "nonexistent" in str(exc)
