"""MCP server setup — tool, resource, and prompt registration."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import (
    GetPromptResult,
    ImageContent,
    Prompt,
    PromptArgument,
    PromptMessage,
    Resource,
    ResourceTemplate,
    TextContent,
    Tool,
)

from openscad_mcp_server.prompts.workflow import (
    PROMPT_DESCRIPTION,
    PROMPT_NAME,
    get_workflow_prompt,
)
from openscad_mcp_server.resources.library_ref import (
    RESOURCE_DESCRIPTION as LIB_REF_DESCRIPTION,
    RESOURCE_NAME as LIB_REF_NAME,
    RESOURCE_URI_TEMPLATE as LIB_REF_URI_TEMPLATE,
    generate_library_reference,
)
from openscad_mcp_server.resources.openscad_syntax import (
    RESOURCE_DESCRIPTION as SYNTAX_DESCRIPTION,
    RESOURCE_NAME as SYNTAX_NAME,
    RESOURCE_URI as SYNTAX_URI,
    get_syntax_reference,
)
from openscad_mcp_server.resources.pitfalls import (
    RESOURCE_DESCRIPTION as PITFALLS_DESCRIPTION,
    RESOURCE_NAME as PITFALLS_NAME,
    RESOURCE_URI as PITFALLS_URI,
    get_pitfalls,
)
from openscad_mcp_server.services.container import ContainerManager
from openscad_mcp_server.services.feedback_service import FeedbackService
from openscad_mcp_server.services.file_manager import FileManager
from openscad_mcp_server.services.library_service import LibraryService, LibraryServiceError
from openscad_mcp_server.services.session import SessionState
from openscad_mcp_server.tools.build_stl import run_build_stl
from openscad_mcp_server.tools.check_syntax import run_check_syntax
from openscad_mcp_server.tools.feedback_tools import run_list_feedback, run_submit_feedback
from openscad_mcp_server.tools.finalize import run_finalize
from openscad_mcp_server.tools.init_tool import run_init
from openscad_mcp_server.tools.library_tools import (
    run_browse_library_catalog,
    run_fetch_library,
    run_list_reviewed_libraries,
    run_read_library_file,
    run_read_library_source,
)
from openscad_mcp_server.tools.measure_stl import run_measure_stl
from openscad_mcp_server.tools.render_images import run_render_images
from openscad_mcp_server.tools.save_code import LibraryNotReviewedError, run_save_code

app = Server("openscad-mcp-server")
session = SessionState()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_file_manager() -> FileManager:
    """Return a FileManager rooted at the session's working directory."""
    if session.working_dir is None:
        raise RuntimeError("Run the init tool first to configure the working directory.")
    return FileManager(session.working_dir)


def _get_container_manager() -> ContainerManager:
    """Return a ContainerManager for the detected runtime."""
    if session.container_runtime is None or session.container_executable is None:
        raise RuntimeError("Run the init tool first to detect a container runtime.")
    return ContainerManager(session.container_runtime, session.container_executable)


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

@app.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="init",
            description="Detect container runtime and configure working directory. IMPORTANT: After init, call browse-library-catalog before writing any code.",
            inputSchema={
                "type": "object",
                "properties": {
                    "workspace_dir": {
                        "type": "string",
                        "description": "An EXISTING directory on the user's machine where files will be stored. Must already exist — do not invent or guess paths. If unsure, omit this parameter to use the server's working directory.",
                    },
                },
                "required": [],
            },
        ),
        Tool(
            name="save-code",
            description="Save OpenSCAD code to the working area. Tip: Before writing custom modules, call browse-library-catalog — libraries like BOSL2 (mechanical primitives) and YAPP_Box (parametric enclosures) produce more robust designs with less code.",
            inputSchema={
                "type": "object",
                "properties": {
                    "code": {"type": "string", "description": "OpenSCAD source code"},
                    "filename": {"type": "string", "description": "Target filename (.scad appended if missing)"},
                },
                "required": ["code", "filename"],
            },
        ),
        Tool(
            name="build-stl",
            description="Compile an OpenSCAD file into an STL using a build container",
            inputSchema={
                "type": "object",
                "properties": {
                    "scad_file": {"type": "string", "description": "Filename of the .scad file in the working area"},
                },
                "required": ["scad_file"],
            },
        ),
        Tool(
            name="render-images",
            description="Render a model from camera angles, returning base64 PNG images. Accepts .stl or .scad files. Renders all 8 angles by default, or a subset if angles are specified.",
            inputSchema={
                "type": "object",
                "properties": {
                    "stl_file": {"type": "string", "description": "Filename of the .stl or .scad file in the working area"},
                    "angles": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional list of angle labels to render (e.g. ['top', 'front']). Omit for all 8 angles. Valid: front, back, left, right, top, bottom, front-right-top-iso, back-left-top-iso",
                    },
                },
                "required": ["stl_file"],
            },
        ),
        Tool(
            name="check-syntax",
            description="Fast syntax validation of an OpenSCAD file without full CGAL geometry computation",
            inputSchema={
                "type": "object",
                "properties": {
                    "scad_file": {"type": "string", "description": "Filename of the .scad file in the working area"},
                },
                "required": ["scad_file"],
            },
        ),
        Tool(
            name="measure-stl",
            description="Analyze an STL file and return dimensional metadata (bounding box, volume, surface area, manifold check) without rendering",
            inputSchema={
                "type": "object",
                "properties": {
                    "stl_file": {"type": "string", "description": "Filename of the .stl file in the working area"},
                },
                "required": ["stl_file"],
            },
        ),
        Tool(
            name="browse-library-catalog",
            description="Fetch the official OpenSCAD library catalog from openscad.org. CALL THIS FIRST before writing any code — libraries like YAPP_Box (enclosures) and BOSL2 (mechanical parts) save significant effort.",
            inputSchema={
                "type": "object",
                "properties": {
                    "force_refresh": {"type": "boolean", "description": "Bypass cache and re-fetch", "default": False},
                },
                "required": [],
            },
        ),
        Tool(
            name="fetch-library",
            description="Download an OpenSCAD library from its source repository",
            inputSchema={
                "type": "object",
                "properties": {
                    "library_name": {"type": "string", "description": "Name of the library"},
                    "source_url": {"type": "string", "description": "Source repository URL"},
                    "force_refresh": {"type": "boolean", "description": "Re-download even if cached", "default": False},
                },
                "required": ["library_name", "source_url"],
            },
        ),
        Tool(
            name="read-library-source",
            description="Read library module signatures and file listing (compact overview, no full source). Use read-library-file for specific file/module source.",
            inputSchema={
                "type": "object",
                "properties": {
                    "library_name": {"type": "string", "description": "Name of the fetched library"},
                },
                "required": ["library_name"],
            },
        ),
        Tool(
            name="read-library-file",
            description="Read the source of a specific file or module from a fetched library. Use after read-library-source to dive into specific implementations.",
            inputSchema={
                "type": "object",
                "properties": {
                    "library_name": {"type": "string", "description": "Name of the fetched library"},
                    "file_path": {"type": "string", "description": "Relative path to a .scad file within the library"},
                    "module_name": {"type": "string", "description": "Optional: return only this module's source from the file"},
                },
                "required": ["library_name", "file_path"],
            },
        ),
        Tool(
            name="list-reviewed-libraries",
            description="List libraries whose source has been reviewed this session",
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
        Tool(
            name="submit-feedback",
            description="Submit user feedback with optional root cause category",
            inputSchema={
                "type": "object",
                "properties": {
                    "critique": {"type": "string", "description": "User critique text"},
                    "root_cause_category": {"type": "string", "description": "Optional root cause category"},
                },
                "required": ["critique"],
            },
        ),
        Tool(
            name="list-feedback",
            description="List all feedback records",
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
        Tool(
            name="finalize",
            description="Copy working area artifacts to the final output directory",
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent | ImageContent]:
    if name == "init":
        try:
            result = await run_init(session, workspace_dir=arguments.get("workspace_dir"))
        except ValueError as exc:
            return [TextContent(type="text", text=json.dumps({"error": str(exc)}))]
        return [TextContent(type="text", text=json.dumps(asdict(result)))]

    elif name == "save-code":
        fm = _get_file_manager()
        try:
            result = run_save_code(
                code=arguments["code"],
                filename=arguments["filename"],
                session=session,
                file_manager=fm,
            )
        except LibraryNotReviewedError as exc:
            return [TextContent(type="text", text=json.dumps({"error": str(exc)}))]
        return [TextContent(type="text", text=json.dumps(asdict(result)))]

    elif name == "build-stl":
        fm = _get_file_manager()
        cm = _get_container_manager()
        result = await run_build_stl(
            scad_file=arguments["scad_file"],
            container_manager=cm,
            file_manager=fm,
        )
        return [TextContent(type="text", text=json.dumps(asdict(result)))]

    elif name == "render-images":
        fm = _get_file_manager()
        cm = _get_container_manager()
        result = await run_render_images(
            stl_file=arguments["stl_file"],
            container_manager=cm,
            file_manager=fm,
            angles=arguments.get("angles"),
        )
        blocks: list[TextContent | ImageContent] = [
            TextContent(type="text", text=result.text_content),
        ]
        for _label, b64_data in result.image_contents:
            blocks.append(ImageContent(type="image", data=b64_data, mimeType="image/png"))
        if result.failures:
            blocks.append(TextContent(
                type="text",
                text=json.dumps({"failed_angles": [asdict(f) for f in result.failures]}),
            ))
        return blocks

    elif name == "check-syntax":
        fm = _get_file_manager()
        cm = _get_container_manager()
        result = await run_check_syntax(
            scad_file=arguments["scad_file"],
            container_manager=cm,
            file_manager=fm,
        )
        return [TextContent(type="text", text=json.dumps(asdict(result)))]

    elif name == "measure-stl":
        fm = _get_file_manager()
        try:
            result = run_measure_stl(
                stl_file=arguments["stl_file"],
                file_manager=fm,
            )
        except FileNotFoundError as exc:
            return [TextContent(type="text", text=json.dumps({"error": str(exc)}))]
        return [TextContent(type="text", text=json.dumps(asdict(result)))]

    elif name == "browse-library-catalog":
        fm = _get_file_manager()
        ls = LibraryService(fm.libraries_dir)
        result = await run_browse_library_catalog(
            library_service=ls,
            force_refresh=arguments.get("force_refresh", False),
        )
        return [TextContent(type="text", text=json.dumps([asdict(e) for e in result.libraries]))]

    elif name == "fetch-library":
        fm = _get_file_manager()
        ls = LibraryService(fm.libraries_dir)
        try:
            result = await run_fetch_library(
                library_name=arguments["library_name"],
                source_url=arguments["source_url"],
                library_service=ls,
                force_refresh=arguments.get("force_refresh", False),
            )
        except LibraryServiceError as exc:
            return [TextContent(type="text", text=json.dumps({"error": str(exc)}))]
        return [TextContent(type="text", text=json.dumps(asdict(result)))]

    elif name == "read-library-source":
        fm = _get_file_manager()
        ls = LibraryService(fm.libraries_dir)
        try:
            result = run_read_library_source(
                library_name=arguments["library_name"],
                library_service=ls,
                session=session,
            )
        except LibraryServiceError as exc:
            return [TextContent(type="text", text=json.dumps({"error": str(exc)}))]
        return [TextContent(type="text", text=json.dumps(asdict(result.source)))]

    elif name == "read-library-file":
        fm = _get_file_manager()
        ls = LibraryService(fm.libraries_dir)
        try:
            result = run_read_library_file(
                library_name=arguments["library_name"],
                file_path=arguments["file_path"],
                library_service=ls,
                module_name=arguments.get("module_name"),
            )
        except LibraryServiceError as exc:
            return [TextContent(type="text", text=json.dumps({"error": str(exc)}))]
        return [TextContent(type="text", text=json.dumps(asdict(result)))]

    elif name == "list-reviewed-libraries":
        result = run_list_reviewed_libraries(session)
        return [TextContent(type="text", text=json.dumps(asdict(result)))]

    elif name == "submit-feedback":
        fm = _get_file_manager()
        fs = FeedbackService(fm.feedback_dir)
        result = run_submit_feedback(
            critique=arguments["critique"],
            feedback_service=fs,
            session=session,
            working_area=fm.working_dir,
            root_cause_category=arguments.get("root_cause_category"),
        )
        return [TextContent(type="text", text=json.dumps(asdict(result)))]

    elif name == "list-feedback":
        fm = _get_file_manager()
        fs = FeedbackService(fm.feedback_dir)
        result = run_list_feedback(fs)
        return [TextContent(type="text", text=json.dumps([asdict(r) for r in result.records]))]

    elif name == "finalize":
        fm = _get_file_manager()
        result = run_finalize(fm)
        return [TextContent(type="text", text=json.dumps(asdict(result)))]

    else:
        return [TextContent(type="text", text=json.dumps({"error": f"Unknown tool: {name}"}))]


# ---------------------------------------------------------------------------
# Resources
# ---------------------------------------------------------------------------

@app.list_resources()
async def list_resources() -> list[Resource]:
    return [
        Resource(
            uri=SYNTAX_URI,
            name=SYNTAX_NAME,
            description=SYNTAX_DESCRIPTION,
            mimeType="text/plain",
        ),
        Resource(
            uri=PITFALLS_URI,
            name=PITFALLS_NAME,
            description=PITFALLS_DESCRIPTION,
            mimeType="text/plain",
        ),
    ]


@app.list_resource_templates()
async def list_resource_templates() -> list[ResourceTemplate]:
    return [
        ResourceTemplate(
            uriTemplate=LIB_REF_URI_TEMPLATE,
            name=LIB_REF_NAME,
            description=LIB_REF_DESCRIPTION,
            mimeType="text/plain",
        ),
    ]


@app.read_resource()
async def read_resource(uri) -> str:
    uri_str = str(uri)
    if uri_str == SYNTAX_URI:
        return get_syntax_reference()
    elif uri_str == PITFALLS_URI:
        return get_pitfalls()
    elif uri_str.startswith("openscad://library-reference/"):
        library_name = uri_str.split("/")[-1]
        fm = _get_file_manager()
        ls = LibraryService(fm.libraries_dir)
        source = ls.read_source(library_name)
        return generate_library_reference(source)
    else:
        raise ValueError(f"Unknown resource URI: {uri_str}")


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

@app.list_prompts()
async def list_prompts() -> list[Prompt]:
    return [
        Prompt(
            name=PROMPT_NAME,
            description=PROMPT_DESCRIPTION,
        ),
    ]


@app.get_prompt()
async def get_prompt(name: str, arguments: dict[str, str] | None) -> GetPromptResult:
    if name == PROMPT_NAME:
        return GetPromptResult(
            description=PROMPT_DESCRIPTION,
            messages=[
                PromptMessage(
                    role="user",
                    content=TextContent(type="text", text=get_workflow_prompt()),
                ),
            ],
        )
    raise ValueError(f"Unknown prompt: {name}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

async def main() -> None:
    """Start the OpenSCAD MCP server on stdio transport."""
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())
