# openscad-mcp-server

An MCP server that gives LLMs the ability to design, build, and visually verify 3D models using [OpenSCAD](https://openscad.org) — all through natural conversation.

The server handles the entire workflow: discovering and downloading OpenSCAD libraries on demand, saving code, compiling STL files in Docker/Finch containers, rendering 8-angle inspection images, and returning those images directly to the LLM's vision model as inline base64 PNGs. A built-in workflow prompt guides the LLM through systematic per-angle inspection with confidence scoring, so it catches defects before declaring a model complete.

## Why this exists

LLMs can write OpenSCAD code, but they can't run it, see the result, or iterate on mistakes. This server closes that loop. The LLM writes code, the server compiles and renders it in a container, and the LLM sees the rendered model from 8 angles — then decides whether to fix issues or finalize.

Key design choices:
- **Vision-native**: Rendered images come back as MCP `ImageContent` blocks, not file paths. The LLM sees the model directly.
- **Zero config**: The `init` tool auto-detects Docker or Finch and persists settings via the LLM's memory mechanism. No env vars or config files needed.
- **Library-aware**: Libraries are discovered from the [official OpenSCAD catalog](https://openscad.org/libraries.html) and downloaded on demand. The server enforces that the LLM reads library source code before using it — no guessing at APIs.
- **Correctness-first**: The workflow prompt requires per-angle confidence scoring (overall = min of all angles) and forbids declaring a model complete below 0.5 confidence.

## Quick start

### Prerequisites

- [Docker](https://docs.docker.com/get-docker/) or [Finch](https://runfinch.com/) installed and running
- Python 3.11+ (for development) or [uv](https://docs.astral.sh/uv/) (for running directly)

### Run with uvx (no install needed)

```bash
uvx openscad-mcp-server
```

### Or install and run

```bash
pip install openscad-mcp-server
openscad-mcp-server
```

The server communicates over stdio, so it's meant to be launched by an MCP client (Claude Desktop, Kiro, etc.), not run interactively.

The server uses the official [`openscad/openscad`](https://hub.docker.com/r/openscad/openscad) Docker Hub image for both STL compilation and rendering. It's pulled automatically on first use — no manual image builds needed.

## MCP client configuration

### Kiro

Add to `.kiro/settings/mcp.json`:

```json
{
  "mcpServers": {
    "openscad": {
      "command": "uvx",
      "args": ["openscad-mcp-server"]
    }
  }
}
```

### Claude Desktop

Add to your Claude Desktop config:

```json
{
  "mcpServers": {
    "openscad": {
      "command": "uvx",
      "args": ["openscad-mcp-server"]
    }
  }
}
```


## Tools

The server exposes 13 tools:

| Tool | Description |
|---|---|
| `init` | Auto-detect Docker/Finch, configure working directory, return persistence content |
| `save-code` | Save OpenSCAD code to the working area (enforces library review) |
| `check-syntax` | Fast syntax validation without full STL compilation |
| `build-stl` | Compile `.scad` → `.stl` in a container (returns mesh metadata) |
| `measure-stl` | Parse an STL file and return dimensional metadata without rendering |
| `render-images` | Render STL from 8 camera angles (or selective via `angles` param), return inline base64 PNG images |
| `browse-library-catalog` | Fetch the official OpenSCAD library listing |
| `fetch-library` | Download a library from its source repository |
| `read-library-source` | Read library `.scad` files and extract module signatures |
| `list-reviewed-libraries` | Show which libraries have been reviewed this session |
| `submit-feedback` | Record user feedback with artifact snapshots and confidence data |
| `list-feedback` | List all feedback records for analysis |
| `finalize` | Copy working area artifacts to the final output directory |

## Resources

| Resource | URI | Description |
|---|---|---|
| Syntax Reference | `openscad://syntax-reference` | OpenSCAD language reference (primitives, transforms, booleans, modules) |
| Library Reference | `openscad://library-reference/{name}` | Dynamic reference generated from fetched library source |
| Common Pitfalls | `openscad://pitfalls` | Manifold errors, z-fighting, boolean order, missing `$fn`, etc. |

## Prompts

| Prompt | Description |
|---|---|
| `openscad-workflow` | Full step-by-step workflow: init → library discovery → code → build → render → inspect → iterate → finalize |

## How the workflow works

```
User: "Make me a phone stand with a 75° angle"
  │
  ▼
┌─────────────────────────────────────────────┐
│ 1. init          → detect Docker/Finch      │
│ 2. browse-catalog → find relevant libraries │
│ 3. fetch-library  → download BOSL2          │
│ 4. read-source    → understand the API      │
│ 5. save-code      → write OpenSCAD code     │
│ 6. build-stl      → compile to STL          │
│ 7. render-images  → 8 angles, inline PNGs   │
│ 8. inspect        → per-angle confidence     │
│ 9. iterate        → fix issues, re-render   │
│ 10. finalize      → copy to output dir      │
└─────────────────────────────────────────────┘
  │
  ▼
Output: model.stl + model.scad + 8 inspection images
```

The LLM inspects each rendered angle individually, assigns per-angle confidence scores, and computes the overall confidence as the minimum across all angles. If any angle scores below 0.5, the LLM must iterate before finalizing.

## Artifact layout

```
{working_dir}/
├── working/          # Latest iteration (overwritten each cycle)
│   ├── model.scad
│   ├── model.stl
│   └── renders/
│       ├── front.png
│       ├── back.png
│       ├── left.png
│       ├── right.png
│       ├── top.png
│       ├── bottom.png
│       ├── front-right-top-iso.png
│       └── back-left-top-iso.png
├── output/           # Final output (populated on finalize)
├── libraries/        # Downloaded OpenSCAD libraries
└── feedback/         # User feedback records with artifact snapshots
```

## Development

```bash
# Clone and install with test dependencies
git clone https://github.com/your-org/openscad-mcp-server.git
cd openscad-mcp-server
uv sync --extra test

# Run tests
uv run pytest tests/ -v

# Run with Hypothesis verbose output
uv run pytest tests/ -v --hypothesis-show-statistics
```

### Test suite

The test suite includes 67 tests covering all 25 correctness properties from the design spec, validated with [Hypothesis](https://hypothesis.readthedocs.io/) property-based testing:

- Save-code round trip and filename normalization
- Container command generation (runtime-agnostic)
- Mount correctness and error propagation
- Render output (8 angles, PNG format, MCP ImageContent blocks)
- Library catalog parsing, caching, and fetch error handling
- Feedback record completeness, index round trip, confidence disagreement
- Working area overwrite invariant and finalize correctness
- Session state tracking and confidence score computation
- Version-tag matching for release pipeline
- Server registration (tools, resources, prompts)

## CI/CD

- **PR merge → main**: Automatically creates a git tag and GitHub release from the version in `pyproject.toml`
- **Tag push (`v*`)**: Builds and publishes to PyPI using trusted publishing (OIDC)

## License

MIT
