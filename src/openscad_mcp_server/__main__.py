"""Entry point for `python -m openscad_mcp_server` and the console script."""

import asyncio

from openscad_mcp_server.server import main


def run() -> None:
    """Synchronous wrapper that runs the async MCP server."""
    asyncio.run(main())


if __name__ == "__main__":
    run()
