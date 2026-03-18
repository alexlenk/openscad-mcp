"""Library catalog browsing, on-demand download, and source reading."""

from __future__ import annotations

import asyncio
import re
import shutil
from pathlib import Path

import aiohttp
from bs4 import BeautifulSoup

from openscad_mcp_server.models import LibraryCatalogEntry, LibrarySource, ModuleSignature


class LibraryServiceError(Exception):
    """Raised when a library operation fails."""

    def __init__(self, message: str, *, source_url: str | None = None) -> None:
        self.source_url = source_url
        super().__init__(message)


class LibraryService:
    """Handles catalog fetching, library downloading, caching, and source reading."""

    CATALOG_URL = "https://openscad.org/libraries.html"

    def __init__(self, libraries_dir: Path) -> None:
        self.libraries_dir = libraries_dir
        self.libraries_dir.mkdir(parents=True, exist_ok=True)
        self._catalog_cache: list[LibraryCatalogEntry] | None = None
        self._library_cache: dict[str, Path] = {}

    # ------------------------------------------------------------------
    # Catalog browsing
    # ------------------------------------------------------------------

    async def browse_catalog(self, force_refresh: bool = False) -> list[LibraryCatalogEntry]:
        """Fetch and parse the OpenSCAD library catalog.

        Returns cached results unless *force_refresh* is ``True``.
        """
        if self._catalog_cache is not None and not force_refresh:
            return self._catalog_cache

        html = await self._fetch_catalog_html()
        entries = self.parse_catalog_html(html)
        self._catalog_cache = entries
        return entries

    @staticmethod
    def parse_catalog_html(html: str) -> list[LibraryCatalogEntry]:
        """Parse HTML from the OpenSCAD libraries page into catalog entries."""
        soup = BeautifulSoup(html, "html.parser")
        entries: list[LibraryCatalogEntry] = []

        # The libraries page lists libraries in various HTML structures.
        # We look for list items or sections containing links to source repos.
        for li in soup.find_all("li"):
            links = li.find_all("a", href=True)
            if not links:
                continue

            # Extract name from the first link text or bold text
            name_tag = li.find("b") or li.find("strong") or links[0]
            name = name_tag.get_text(strip=True)
            if not name:
                continue

            # Extract description from the full text minus the name
            full_text = li.get_text(" ", strip=True)
            description = full_text

            # Classify links as source or docs
            source_url: str | None = None
            docs_url: str | None = None
            for link in links:
                href = link["href"]
                if any(host in href for host in ("github.com", "gitlab.com", "bitbucket.org")):
                    if source_url is None:
                        source_url = href
                    else:
                        docs_url = href
                elif docs_url is None and href.startswith("http"):
                    docs_url = href

            if source_url is None:
                # Use the first http link as source if no repo host matched
                for link in links:
                    href = link["href"]
                    if href.startswith("http"):
                        source_url = href
                        break

            if source_url is None:
                continue  # Skip entries without any usable URL

            entries.append(LibraryCatalogEntry(
                name=name,
                description=description,
                source_url=source_url,
                docs_url=docs_url,
            ))

        return entries

    async def _fetch_catalog_html(self) -> str:
        """Fetch the raw HTML from the catalog URL."""
        async with aiohttp.ClientSession() as session:
            async with session.get(self.CATALOG_URL, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                resp.raise_for_status()
                return await resp.text()

    # ------------------------------------------------------------------
    # Library fetching
    # ------------------------------------------------------------------

    async def fetch_library(
        self, name: str, source_url: str, force_refresh: bool = False
    ) -> Path:
        """Download a library from its source repository.

        Returns the local path to the library directory.  Uses a session-level
        cache; set *force_refresh* to re-download.

        Raises :class:`LibraryServiceError` on failure.
        """
        if name in self._library_cache and not force_refresh:
            return self._library_cache[name]

        lib_dir = self.libraries_dir / name

        if force_refresh and lib_dir.exists():
            shutil.rmtree(lib_dir)

        if not lib_dir.exists():
            try:
                await self._download_library(source_url, lib_dir)
            except Exception as exc:
                raise LibraryServiceError(
                    f"Failed to download library {name!r} from {source_url}: {exc}",
                    source_url=source_url,
                ) from exc

        # Verify at least one .scad file exists
        scad_files = list(lib_dir.rglob("*.scad"))
        if not scad_files:
            raise LibraryServiceError(
                f"Library {name!r} fetched from {source_url} contains no .scad files",
                source_url=source_url,
            )

        self._library_cache[name] = lib_dir
        return lib_dir

    async def _download_library(self, source_url: str, dest: Path) -> None:
        """Clone a git repository or download an archive into *dest*."""
        dest.mkdir(parents=True, exist_ok=True)

        # Try git clone first
        git_url = source_url
        if git_url.endswith("/"):
            git_url = git_url.rstrip("/")
        if not git_url.endswith(".git"):
            git_url = git_url + ".git"

        proc = await asyncio.create_subprocess_exec(
            "git", "clone", "--depth", "1", git_url, str(dest),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr_bytes = await proc.communicate()
        if proc.returncode != 0:
            # Clean up failed clone attempt
            if dest.exists():
                shutil.rmtree(dest)
            raise RuntimeError(
                f"git clone failed (exit {proc.returncode}): "
                f"{stderr_bytes.decode('utf-8', errors='replace')}"
            )

    # ------------------------------------------------------------------
    # Source reading
    # ------------------------------------------------------------------

    def read_source(self, name: str) -> LibrarySource:
        """Read all ``.scad`` files from a fetched library and extract module signatures.

        Raises :class:`LibraryServiceError` if the library has not been fetched.
        """
        lib_dir = self.libraries_dir / name
        if not lib_dir.exists():
            raise LibraryServiceError(
                f"Library {name!r} not found. Run fetch-library first.",
            )

        scad_files = sorted(lib_dir.rglob("*.scad"))
        if not scad_files:
            raise LibraryServiceError(
                f"Library {name!r} contains no .scad files.",
            )

        source_parts: list[str] = []
        all_modules: list[ModuleSignature] = []

        for scad_file in scad_files:
            content = scad_file.read_text(encoding="utf-8", errors="replace")
            source_parts.append(f"// --- {scad_file.relative_to(lib_dir)} ---\n{content}")
            all_modules.extend(self._extract_modules(content))

        source_code = "\n\n".join(source_parts)
        coordinate_system = self._detect_coordinate_system(source_code)
        units = self._detect_units(source_code)

        return LibrarySource(
            name=name,
            source_code=source_code,
            modules=all_modules,
            coordinate_system=coordinate_system,
            units=units,
        )

    # ------------------------------------------------------------------
    # Module signature extraction
    # ------------------------------------------------------------------

    # Matches: module name(param1, param2=default, ...)
    _MODULE_RE = re.compile(
        r"^\s*module\s+(\w+)\s*\(([^)]*)\)",
        re.MULTILINE,
    )

    @staticmethod
    def _extract_modules(source: str) -> list[ModuleSignature]:
        """Extract module signatures from OpenSCAD source code."""
        modules: list[ModuleSignature] = []
        for match in LibraryService._MODULE_RE.finditer(source):
            name = match.group(1)
            params_str = match.group(2).strip()
            parameters: list[dict] = []
            if params_str:
                for param in params_str.split(","):
                    param = param.strip()
                    if "=" in param:
                        pname, default = param.split("=", 1)
                        parameters.append({
                            "name": pname.strip(),
                            "default": default.strip(),
                        })
                    elif param:
                        parameters.append({"name": param.strip()})
            modules.append(ModuleSignature(name=name, parameters=parameters))
        return modules

    @staticmethod
    def _detect_coordinate_system(source: str) -> str | None:
        """Heuristic detection of coordinate system from source comments."""
        lower = source.lower()
        if "z-up" in lower or "z up" in lower:
            return "right-hand, Z-up"
        if "y-up" in lower or "y up" in lower:
            return "right-hand, Y-up"
        return None

    @staticmethod
    def _detect_units(source: str) -> str | None:
        """Heuristic detection of units from source comments."""
        lower = source.lower()
        if "millimeter" in lower or "mm" in lower:
            return "millimeters"
        if "inch" in lower or "inches" in lower:
            return "inches"
        return None
