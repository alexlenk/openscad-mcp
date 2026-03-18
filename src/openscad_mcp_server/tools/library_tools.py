"""Library tools — browse catalog, fetch, read source, and list reviewed libraries."""

from __future__ import annotations

from dataclasses import dataclass

from openscad_mcp_server.models import LibraryCatalogEntry, LibrarySource
from openscad_mcp_server.services.library_service import LibraryService, LibraryServiceError
from openscad_mcp_server.services.session import SessionState


# ------------------------------------------------------------------
# Result types
# ------------------------------------------------------------------

@dataclass
class BrowseCatalogResult:
    """Result from the browse-library-catalog tool."""

    libraries: list[LibraryCatalogEntry]


@dataclass
class FetchLibraryResult:
    """Result from the fetch-library tool."""

    library_path: str
    message: str


@dataclass
class ReadLibrarySourceResult:
    """Result from the read-library-source tool."""

    source: LibrarySource


@dataclass
class ListReviewedResult:
    """Result from the list-reviewed-libraries tool."""

    reviewed: list[str]


@dataclass
class ReadLibraryFileResult:
    """Result from the read-library-file tool."""

    file_path: str
    source: str


# ------------------------------------------------------------------
# Tool implementations
# ------------------------------------------------------------------

async def run_browse_library_catalog(
    library_service: LibraryService,
    force_refresh: bool = False,
) -> BrowseCatalogResult:
    """Fetch and return the OpenSCAD library catalog.

    Delegates to :meth:`LibraryService.browse_catalog`.
    """
    entries = await library_service.browse_catalog(force_refresh=force_refresh)
    return BrowseCatalogResult(libraries=entries)


async def run_fetch_library(
    library_name: str,
    source_url: str,
    library_service: LibraryService,
    force_refresh: bool = False,
) -> FetchLibraryResult:
    """Download a library from its source repository.

    Delegates to :meth:`LibraryService.fetch_library`.

    Raises
    ------
    LibraryServiceError
        If the download fails (error includes the source URL).
    """
    lib_path = await library_service.fetch_library(
        name=library_name,
        source_url=source_url,
        force_refresh=force_refresh,
    )
    return FetchLibraryResult(
        library_path=str(lib_path),
        message=f"Library {library_name!r} is available at {lib_path}. "
                f"Use read-library-source to inspect it before writing code.",
    )


def run_read_library_source(
    library_name: str,
    library_service: LibraryService,
    session: SessionState,
) -> ReadLibrarySourceResult:
    """Read library source code and mark the library as reviewed.

    Delegates to :meth:`LibraryService.read_source` and records the review
    in the session so that ``save-code`` will accept references to this library.

    Raises
    ------
    LibraryServiceError
        If the library has not been fetched yet.
    """
    source = library_service.read_source(library_name)
    session.mark_library_reviewed(library_name)
    return ReadLibrarySourceResult(source=source)


def run_list_reviewed_libraries(session: SessionState) -> ListReviewedResult:
    """Return the list of libraries reviewed in the current session."""
    return ListReviewedResult(reviewed=sorted(session.reviewed_libraries))


def run_read_library_file(
    library_name: str,
    file_path: str,
    library_service: LibraryService,
    module_name: str | None = None,
) -> ReadLibraryFileResult:
    """Read a specific file or module from a fetched library.

    Use this for targeted deep-dives after ``read-library-source`` has
    returned the signatures overview.

    Raises
    ------
    LibraryServiceError
        If the library or file is not found, or the module doesn't exist.
    """
    source = library_service.read_source_file(library_name, file_path, module_name)
    return ReadLibraryFileResult(file_path=file_path, source=source)
