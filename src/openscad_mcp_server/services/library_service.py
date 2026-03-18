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
        """Parse HTML from the OpenSCAD libraries page into catalog entries.

        The page groups libraries under ``<h3>`` category headers (e.g.
        "General", "Single Topic").  Each library is a ``<li>`` containing:
        - A ``<b>`` tag with the library name
        - Description text (direct text nodes after the name)
        - A nested ``<ul>`` with links (Library, Documentation, Tutorials)
          and a license line
        """
        import re

        soup = BeautifulSoup(html, "html.parser")
        entries: list[LibraryCatalogEntry] = []

        # Build a map of <ul> → category from preceding <h3> headers.
        category_map: dict[int, str] = {}
        for h3 in soup.find_all("h3"):
            # The next <ul> sibling after this <h3> belongs to this category.
            sibling = h3.find_next_sibling("ul")
            if sibling:
                category_map[id(sibling)] = h3.get_text(strip=True)

        # Process each top-level <ul> that has a category.
        for ul in soup.find_all("ul"):
            ul_id = id(ul)
            category = category_map.get(ul_id)
            if category is None:
                continue  # Skip nested <ul> (link lists inside <li>)

            for li in ul.find_all("li", recursive=False):
                # --- Name from <b> or <strong> ---
                name_tag = li.find("b") or li.find("strong")
                if not name_tag:
                    continue
                name = name_tag.get_text(strip=True)
                if not name:
                    continue

                # --- Description: direct text of the <li>, excluding
                #     the name tag and the nested <ul> (links/license). ---
                nested_ul = li.find("ul")
                desc_parts: list[str] = []
                for child in li.children:
                    if child is name_tag or child is nested_ul:
                        continue
                    text = child.get_text(strip=True) if hasattr(child, "get_text") else str(child).strip()
                    if text:
                        desc_parts.append(text)
                description = " ".join(desc_parts).strip()
                # Clean up stray whitespace / double spaces
                description = re.sub(r"\s+", " ", description)

                # --- Links and license from the nested <ul> ---
                source_url: str | None = None
                docs_url: str | None = None
                license_str: str | None = None

                if nested_ul:
                    for sub_li in nested_ul.find_all("li", recursive=False):
                        text = sub_li.get_text(strip=True)

                        # License line (e.g. "License: MIT")
                        if text.startswith("License:"):
                            license_str = text.removeprefix("License:").strip()
                            continue

                        link = sub_li.find("a", href=True)
                        if not link:
                            continue
                        href = link["href"]
                        link_text = link.get_text(strip=True)

                        if link_text == "Library" or source_url is None and any(
                            host in href for host in ("github.com", "gitlab.com", "bitbucket.org")
                        ):
                            if source_url is None:
                                source_url = href
                        elif link_text in ("Documentation", "Docs") and docs_url is None:
                            docs_url = href

                if source_url is None:
                    continue  # Skip entries without any usable URL

                entries.append(LibraryCatalogEntry(
                    name=name,
                    description=description,
                    source_url=source_url,
                    category=category,
                    docs_url=docs_url,
                    license=license_str,
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

        Returns signatures only (no full source code) to avoid blowing the
        context window on large libraries like BOSL2 or YAPP_Box.

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

        all_modules: list[ModuleSignature] = []
        file_listing: list[str] = []
        sample_source = ""

        for scad_file in scad_files:
            content = scad_file.read_text(encoding="utf-8", errors="replace")
            rel_path = str(scad_file.relative_to(lib_dir))
            file_modules = self._extract_modules(content)
            all_modules.extend(file_modules)
            if file_modules:
                sigs = ", ".join(m.name for m in file_modules)
                file_listing.append(f"{rel_path}: {sigs}")
            else:
                file_listing.append(rel_path)
            if not sample_source:
                sample_source = content[:500]

        coordinate_system = self._detect_coordinate_system(sample_source)
        units = self._detect_units(sample_source)

        # Build a compact summary instead of full source
        summary_lines = [f"# {name} — {len(scad_files)} files, {len(all_modules)} modules\n"]
        summary_lines.append("## File listing\n")
        for entry in file_listing:
            summary_lines.append(f"  {entry}")
        summary_lines.append("\n## Module signatures\n")
        for mod in all_modules:
            params = ", ".join(
                p["name"] + (f"={p['default']}" if "default" in p else "")
                for p in mod.parameters
            )
            summary_lines.append(f"  module {mod.name}({params})")

        source_code = "\n".join(summary_lines)

        return LibrarySource(
            name=name,
            source_code=source_code,
            modules=all_modules,
            coordinate_system=coordinate_system,
            units=units,
        )

    def read_source_file(self, name: str, file_path: str, module_name: str | None = None) -> str:
        """Read a specific file (or a specific module within it) from a fetched library.

        Parameters
        ----------
        name
            Library name.
        file_path
            Relative path to a ``.scad`` file within the library.
        module_name
            If provided, return only the source of this module definition.

        Raises :class:`LibraryServiceError` if the library or file is not found.
        """
        lib_dir = self.libraries_dir / name
        if not lib_dir.exists():
            raise LibraryServiceError(
                f"Library {name!r} not found. Run fetch-library first.",
            )

        target = lib_dir / file_path
        if not target.exists():
            raise LibraryServiceError(
                f"File {file_path!r} not found in library {name!r}.",
            )

        content = target.read_text(encoding="utf-8", errors="replace")

        if module_name is None:
            return content

        # Extract the specific module definition
        return self._extract_module_source(content, module_name)

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

    @staticmethod
    def _extract_module_source(source: str, module_name: str) -> str:
        """Extract the full source of a specific module definition by tracking braces.

        Returns the module source from ``module name(...)`` through its closing brace.
        Raises :class:`LibraryServiceError` if the module is not found.
        """
        pattern = re.compile(rf"^\s*module\s+{re.escape(module_name)}\s*\(", re.MULTILINE)
        match = pattern.search(source)
        if not match:
            raise LibraryServiceError(
                f"Module {module_name!r} not found in file.",
            )

        start = match.start()
        # Find the opening brace
        brace_pos = source.find("{", match.end())
        if brace_pos == -1:
            # No body — return just the signature line
            line_end = source.find("\n", match.end())
            return source[start:line_end if line_end != -1 else len(source)]

        depth = 1
        pos = brace_pos + 1
        while pos < len(source) and depth > 0:
            if source[pos] == "{":
                depth += 1
            elif source[pos] == "}":
                depth -= 1
            pos += 1

        return source[start:pos]
