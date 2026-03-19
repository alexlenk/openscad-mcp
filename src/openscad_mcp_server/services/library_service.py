"""Library catalog browsing, on-demand download, and source reading."""

from __future__ import annotations

import asyncio
import re
import shutil
from pathlib import Path

from openscad_mcp_server.models import LibrarySource, ModuleSignature


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
        self._library_cache: dict[str, Path] = {}

    # ------------------------------------------------------------------
    # Catalog browsing
    # ------------------------------------------------------------------

    def browse_catalog(self) -> str:
        """Return the catalog URL with instructions for the LLM.

        Instead of fetching and parsing the HTML (which is fragile),
        we simply point the LLM to the canonical page.
        """
        return (
            f"Browse the OpenSCAD library catalog at: {self.CATALOG_URL}\n\n"
            "Visit the link above to see all available libraries with descriptions, "
            "source repository URLs, documentation links, and licenses.\n\n"
            "Key libraries to consider:\n"
            "- BOSL2: General-purpose library with mechanical primitives, "
            "attachments, and helpers (https://github.com/BelfrySCAD/BOSL2)\n"
            "- YAPP_Box: Parametric enclosure/project box generator "
            "(https://github.com/mrWheel/YAPP_Box)\n\n"
            "Use fetch-library with the library name and its GitHub URL "
            "to download any library for use in your designs."
        )

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
