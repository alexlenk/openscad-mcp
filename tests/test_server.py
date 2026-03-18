"""Tests for MCP server initialization — tool, resource, and prompt registration."""

from __future__ import annotations

import pytest

from openscad_mcp_server.server import (
    app,
    list_prompts,
    list_resource_templates,
    list_resources,
    list_tools,
)


EXPECTED_TOOLS = sorted([
    "init",
    "save-code",
    "build-stl",
    "render-images",
    "browse-library-catalog",
    "fetch-library",
    "read-library-source",
    "list-reviewed-libraries",
    "submit-feedback",
    "list-feedback",
    "finalize",
])


@pytest.mark.asyncio
async def test_server_name():
    assert app.name == "openscad-mcp-server"


@pytest.mark.asyncio
async def test_list_tools_returns_all_11():
    tools = await list_tools()
    names = sorted(t.name for t in tools)
    assert names == EXPECTED_TOOLS
    assert len(tools) == 11


@pytest.mark.asyncio
async def test_list_tools_have_descriptions():
    tools = await list_tools()
    for tool in tools:
        assert tool.description, f"Tool {tool.name!r} has no description"


@pytest.mark.asyncio
async def test_list_tools_have_input_schemas():
    tools = await list_tools()
    for tool in tools:
        assert "type" in tool.inputSchema, f"Tool {tool.name!r} missing inputSchema type"
        assert tool.inputSchema["type"] == "object"


@pytest.mark.asyncio
async def test_list_resources_returns_static_resources():
    resources = await list_resources()
    uris = sorted(str(r.uri) for r in resources)
    assert "openscad://pitfalls" in uris
    assert "openscad://syntax-reference" in uris
    assert len(resources) == 2


@pytest.mark.asyncio
async def test_list_resource_templates_returns_library_ref():
    templates = await list_resource_templates()
    assert len(templates) == 1
    assert templates[0].uriTemplate == "openscad://library-reference/{library_name}"


@pytest.mark.asyncio
async def test_list_prompts_returns_workflow():
    prompts = await list_prompts()
    assert len(prompts) == 1
    assert prompts[0].name == "openscad-workflow"
    assert prompts[0].description
