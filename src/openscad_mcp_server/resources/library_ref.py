"""Dynamic library reference resource (openscad://library-reference/{library_name})."""

from __future__ import annotations

from openscad_mcp_server.models import LibrarySource, ModuleSignature


RESOURCE_URI_TEMPLATE = "openscad://library-reference/{library_name}"
RESOURCE_NAME = "OpenSCAD Library Reference"
RESOURCE_DESCRIPTION = (
    "Dynamic reference for a fetched OpenSCAD library including module signatures, "
    "parameter types/defaults, coordinate system conventions, and usage examples."
)


def generate_library_reference(library_source: LibrarySource) -> str:
    """Generate a formatted reference document from a :class:`LibrarySource`."""
    sections: list[str] = []

    sections.append(f"# Library Reference: {library_source.name}\n")

    # Coordinate system and units
    sections.append("## Conventions\n")
    coord = library_source.coordinate_system or "Not detected"
    units = library_source.units or "Not detected"
    sections.append(f"- Coordinate system: {coord}")
    sections.append(f"- Units: {units}\n")

    # Module signatures
    if library_source.modules:
        sections.append("## Module Signatures\n")
        for mod in library_source.modules:
            sections.append(_format_module(mod))
        sections.append("")

    # Usage examples
    if library_source.modules:
        sections.append("## Usage Examples\n")
        sections.append(_generate_usage_examples(library_source))

    return "\n".join(sections)


def _format_module(mod: ModuleSignature) -> str:
    """Format a single module signature as a readable block."""
    params = ", ".join(_format_param(p) for p in mod.parameters)
    return f"### {mod.name}\n  {mod.name}({params})\n"


def _format_param(param: dict) -> str:
    """Format a parameter dict into a readable string."""
    name = param.get("name", "?")
    default = param.get("default")
    if default is not None:
        return f"{name}={default}"
    return name


def _generate_usage_examples(library_source: LibrarySource) -> str:
    """Generate basic usage examples for the library's modules."""
    lines: list[str] = []
    lines.append(f"```scad")
    lines.append(f"use <{library_source.name}/main.scad>")
    lines.append("")

    # Show up to 3 example calls
    for mod in library_source.modules[:3]:
        args = ", ".join(_example_arg(p) for p in mod.parameters)
        lines.append(f"{mod.name}({args});")

    lines.append("```")
    return "\n".join(lines)


def _example_arg(param: dict) -> str:
    """Generate an example argument value for a parameter."""
    default = param.get("default")
    if default is not None:
        return str(default)
    return "10"
