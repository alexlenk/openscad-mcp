# Implementation Plan: OpenSCAD MCP Server

## Overview

Incremental implementation of the OpenSCAD MCP server in Python, building from core data models and services up through tool handlers, resources, prompts, container images, packaging, and CI/CD. Each task builds on previous work so there is no orphaned code.

NOTE: Always merge the feature branch after done developing a task

## Tasks

- [x] 1. Project scaffolding and package configuration
  - [x] 1.1 Create `pyproject.toml` with PEP 621 metadata, dependencies (`mcp`, `aiohttp`, `beautifulsoup4`), test extras (`pytest`, `pytest-asyncio`, `hypothesis`), console script entry point `openscad-mcp-server`, and build backend
    - _Requirements: 13.1, 13.2, 13.4, 13.5_
  - [x] 1.2 Create directory structure: `src/openscad_mcp_server/` with `__init__.py`, `__main__.py`, `tools/__init__.py`, `services/__init__.py`, `resources/__init__.py`, `prompts/__init__.py`, and `tests/__init__.py`
    - _Requirements: 13.3_
  - [x] 1.3 Implement `__main__.py` entry point that calls `main()` from `server.py`
    - _Requirements: 13.3_

- [x] 2. Data models and session state
  - [x] 2.1 Create `src/openscad_mcp_server/models.py` with dataclasses: `ContainerResult`, `LibraryCatalogEntry`, `ModuleSignature`, `LibrarySource`, `CameraAngle`, `InspectionImage`, `FeedbackRecord`, `FeedbackIndexEntry`, and the `CAMERA_ANGLES` constant (8 predefined angles)
    - _Requirements: 6.2, 7.2, 12.5_
  - [x] 2.2 Create `src/openscad_mcp_server/services/session.py` with `SessionState` class: `reviewed_libraries` set, `latest_confidence_score`, `container_runtime`, `container_executable`, `working_dir`, and methods `mark_library_reviewed`, `is_library_reviewed`, `set_confidence`
    - _Requirements: 17.6, 7.5_
  - [x] 2.3 Write property test for session state (Property 25: Reviewed libraries tracking round trip)
    - **Property 25: Reviewed libraries tracking round trip**
    - **Validates: Requirements 17.6**
  - [x] 2.4 Write property test for confidence score computation (Property 22: Overall confidence is minimum of per-angle scores)
    - **Property 22: Overall confidence is minimum of per-angle scores**
    - **Validates: Requirements 16.8**

- [x] 3. Container manager service
  - [x] 3.1 Create `src/openscad_mcp_server/services/container.py` with `ContainerManager` class: `__init__(runtime, executable)`, `detect()` static method probing Docker then Finch, `run(image, command, mounts, timeout)` executing container via `asyncio.create_subprocess_exec`, `image_exists(image)`, `build_image(dockerfile, tag)`
    - _Requirements: 5.1, 5.2, 6.3, 8.3, 10.1_
  - [x] 3.2 Write property test for container command generation (Property 3: Runtime-agnostic commands)
    - **Property 3: Container command generation is runtime-agnostic**
    - **Validates: Requirements 5.2, 6.3**
  - [x] 3.3 Write property test for container mount correctness (Property 4: Container mount correctness)
    - **Property 4: Container mount correctness**
    - **Validates: Requirements 5.5, 9.6**
  - [x] 3.4 Write property test for build error propagation (Property 5: Build error propagation)
    - **Property 5: Build error propagation**
    - **Validates: Requirements 5.4**
  - [x] 3.5 Write property test for container start failure diagnostics (Property 6: Container start failure diagnostics)
    - **Property 6: Container start failure diagnostics**
    - **Validates: Requirements 5.6, 8.4**

- [x] 4. File manager service
  - [x] 4.1 Create `src/openscad_mcp_server/services/file_manager.py` with `FileManager` class: manages working area (`working/`), final output (`output/`), libraries (`libraries/`), feedback (`feedback/`) directories. Methods: `save_code(code, filename)` with `.scad` extension normalization, `save_stl(data, filename)`, `save_renders(images)`, `clear_renders()`, `finalize()` copying working area to output, `ensure_dirs()` for auto-creation
    - _Requirements: 4.1, 4.3, 4.4, 11.1, 11.2, 11.3, 11.4, 11.5, 11.6_
  - [x] 4.2 Write property test for save-code round trip (Property 1: Save-code round trip)
    - **Property 1: Save-code round trip**
    - **Validates: Requirements 4.1, 4.4**
  - [x] 4.3 Write property test for filename extension normalization (Property 2: Filename extension normalization)
    - **Property 2: Filename extension normalization**
    - **Validates: Requirements 4.3**
  - [x] 4.4 Write property test for working area overwrite invariant (Property 16: Working area overwrite invariant)
    - **Property 16: Working area overwrite invariant**
    - **Validates: Requirements 11.1, 11.2, 11.3, 11.4**
  - [x] 4.5 Write property test for finalize copies all artifacts (Property 17: Finalize copies all working area artifacts)
    - **Property 17: Finalize copies all working area artifacts**
    - **Validates: Requirements 11.5**

- [~] 5. Checkpoint - Core services
  - Ensure all tests pass, ask the user if questions arise.

- [~] 6. Library service
  - [ ] 6.1 Create `src/openscad_mcp_server/services/library_service.py` with `LibraryService` class: `browse_catalog(force_refresh)` fetching and parsing `openscad.org/libraries.html` with BeautifulSoup, `fetch_library(name, source_url, force_refresh)` cloning/downloading from source repo, `read_source(name)` reading `.scad` files and extracting module signatures. Includes session-level catalog cache and library cache with force-refresh support
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5, 9.7, 9.8, 17.1, 17.4_
  - [ ] 6.2 Write property test for catalog parser (Property 11: Catalog parser extracts structured entries)
    - **Property 11: Catalog parser extracts structured entries**
    - **Validates: Requirements 9.1**
  - [ ] 6.3 Write property test for library cache hit (Property 12: Library cache hit avoids re-download)
    - **Property 12: Library cache hit avoids re-download**
    - **Validates: Requirements 9.5**
  - [ ] 6.4 Write property test for fetch success (Property 13: Fetch-library success returns valid path)
    - **Property 13: Fetch-library success returns valid path**
    - **Validates: Requirements 9.7**
  - [ ] 6.5 Write property test for fetch failure (Property 14: Fetch-library failure includes source URL)
    - **Property 14: Fetch-library failure includes source URL**
    - **Validates: Requirements 9.8**
  - [ ] 6.6 Write property test for read-library-source (Property 23: Read-library-source returns source and summary)
    - **Property 23: Read-library-source returns source and summary**
    - **Validates: Requirements 2.2, 2.4, 17.1, 17.4**

- [x] 7. Feedback service
  - [x] 7.1 Create `src/openscad_mcp_server/services/feedback_service.py` with `FeedbackService` class: `submit(critique, root_cause, working_area, confidence_score)` creating timestamped feedback record with artifact copies and index update, `list_records()` returning all feedback summaries. Feedback index stored as `feedback-index.json`
    - _Requirements: 12.1, 12.2, 12.3, 12.4, 12.5, 12.6, 12.7, 12.8, 12.9, 12.10_
  - [x] 7.2 Write property test for feedback record completeness (Property 18: Feedback record completeness)
    - **Property 18: Feedback record completeness**
    - **Validates: Requirements 12.2, 12.3, 12.4, 12.5, 12.8**
  - [x] 7.3 Write property test for feedback index round trip (Property 19: Feedback index round trip)
    - **Property 19: Feedback index round trip**
    - **Validates: Requirements 12.6, 12.7, 12.10**
  - [x] 7.4 Write property test for confidence disagreement flag (Property 20: Confidence disagreement flag logic)
    - **Property 20: Confidence disagreement flag logic**
    - **Validates: Requirements 12.9**

- [ ] 8. Checkpoint - All services complete
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 9. MCP tool handlers - init and save-code
  - [ ] 9.1 Create `src/openscad_mcp_server/tools/init_tool.py` with `init` tool: probes Docker then Finch via `ContainerManager.detect()`, runs test container, returns runtime info and persistence content for LLM memory
    - _Requirements: 10.1, 10.5, 10.6_
  - [ ] 9.2 Write property test for init runtime detection (Property 15: Init tool runtime detection)
    - **Property 15: Init tool runtime detection**
    - **Validates: Requirements 10.1, 10.5**
  - [ ] 9.3 Create `src/openscad_mcp_server/tools/save_code.py` with `save-code` tool: validates filename, parses `include`/`use` statements, checks session for library review status, delegates to `FileManager.save_code()`. Rejects save if referenced libraries not reviewed
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 17.2, 17.3_
  - [ ] 9.4 Write property test for library review enforcement (Property 24: Library review enforcement on save)
    - **Property 24: Library review enforcement on save**
    - **Validates: Requirements 17.2, 17.3**

- [ ] 10. MCP tool handlers - build and render
  - [ ] 10.1 Create `src/openscad_mcp_server/tools/build_stl.py` with `build-stl` tool: launches build container via `ContainerManager.run()` with working directory and library mounts, runs `openscad -o output.stl <file>`, returns STL path or full error output
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6_
  - [ ] 10.2 Create `src/openscad_mcp_server/tools/render_images.py` with `render-images` tool: launches render container for each of 8 camera angles, generates 1024x1024 PNG images, reads PNGs from disk, returns list of MCP `TextContent` (camera metadata) and `ImageContent` blocks (base64 PNG). Handles partial failures by reporting failed angles
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 7.1, 7.2_
  - [ ] 10.3 Write property test for render produces 8 images (Property 7: Render produces exactly 8 images with correct angles)
    - **Property 7: Render produces exactly 8 images with correct angles**
    - **Validates: Requirements 6.1, 6.2, 6.4**
  - [ ] 10.4 Write property test for render command spec (Property 8: Render command specifies PNG at 1024x1024)
    - **Property 8: Render command specifies PNG at 1024x1024**
    - **Validates: Requirements 6.5**
  - [ ] 10.5 Write property test for partial render failure (Property 9: Partial render failure reports failed angles)
    - **Property 9: Partial render failure reports failed angles**
    - **Validates: Requirements 6.6**
  - [ ] 10.6 Write property test for MCP ImageContent blocks (Property 10: Render tool returns MCP ImageContent blocks)
    - **Property 10: Render tool returns MCP ImageContent blocks**
    - **Validates: Requirements 7.1, 7.2**

- [ ] 11. MCP tool handlers - library and feedback tools
  - [ ] 11.1 Create `src/openscad_mcp_server/tools/library_tools.py` with four tools: `browse-library-catalog` (delegates to `LibraryService.browse_catalog`), `fetch-library` (delegates to `LibraryService.fetch_library`), `read-library-source` (delegates to `LibraryService.read_source`, marks library reviewed in session), `list-reviewed-libraries` (reads from session state)
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5, 9.6, 9.7, 9.8, 17.1, 17.4, 17.5, 17.6_
  - [ ] 11.2 Create `src/openscad_mcp_server/tools/feedback_tools.py` with two tools: `submit-feedback` (delegates to `FeedbackService.submit`, records confidence score and disagreement flag), `list-feedback` (delegates to `FeedbackService.list_records`)
    - _Requirements: 12.1, 12.2, 12.3, 12.4, 12.5, 12.6, 12.7, 12.8, 12.9, 12.10_
  - [ ] 11.3 Create `src/openscad_mcp_server/tools/finalize.py` with `finalize` tool: delegates to `FileManager.finalize()`, returns final output directory path and file list
    - _Requirements: 11.5, 11.6_

- [ ] 12. Checkpoint - All tools implemented
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 13. MCP resources
  - [ ] 13.1 Create `src/openscad_mcp_server/resources/openscad_syntax.py` with `openscad://syntax-reference` resource: returns OpenSCAD language reference covering primitives, transformations, boolean operations, module definitions, variable scoping
    - _Requirements: 2.1_
  - [ ] 13.2 Create `src/openscad_mcp_server/resources/library_ref.py` with `openscad://library-reference/{library_name}` dynamic resource: generates reference from fetched library source including module signatures, parameter types/defaults, coordinate system conventions, usage examples
    - _Requirements: 2.2, 2.3, 2.4_
  - [ ] 13.3 Create `src/openscad_mcp_server/resources/pitfalls.py` with `openscad://pitfalls` resource: returns common pitfalls (manifold errors, z-fighting, boolean order, coordinate mismatches, missing `$fn`)
    - _Requirements: 2.5_

- [ ] 14. MCP workflow prompt
  - [ ] 14.1 Create `src/openscad_mcp_server/prompts/workflow.py` with `openscad-workflow` prompt: full step-by-step instructions covering init/settings check, library discovery/fetch/review, code generation, build, render, systematic per-angle inspection with checklist, per-angle confidence scoring, overall confidence as min of per-angle scores, iteration on low confidence, finalize, and feedback handling. Includes prohibitions on skipping angles, declaring complete below 0.5 confidence, and guessing at library APIs
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 7.4, 7.5, 7.6, 7.7, 9.9, 10.2, 10.3, 10.4, 16.1, 16.2, 16.3, 16.4, 16.5, 16.6, 16.7, 16.8, 16.9, 17.5_

- [ ] 15. MCP server wiring
  - [ ] 15.1 Create `src/openscad_mcp_server/server.py`: instantiate `Server("openscad-mcp-server")`, create shared `SessionState`, register all 11 tools via `@app.tool()` decorators, register 3 resources via `@app.resource()`, register workflow prompt via `@app.prompt()`, implement `main()` async function running stdio transport
    - _Requirements: 1.1, 1.2, 1.3_
  - [ ] 15.2 Write unit tests for server initialization verifying tool/resource/prompt registration returns expected names
    - _Requirements: 1.1, 1.2_

- [ ] 16. Checkpoint - Server fully wired
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 17. Container images
  - [ ] 17.1 Create `Dockerfile.build` based on `ubuntu:24.04`, installing `openscad` package, with entrypoint `openscad`, working directory mount at `/work`, and `OPENSCADPATH` set to `/work/libraries`
    - _Requirements: 8.1, 5.5, 9.6_
  - [ ] 17.2 Create `Dockerfile.render` based on same base image, configured for OpenSCAD PNG export with `--camera` and `--imgsize` parameters
    - _Requirements: 8.2_

- [ ] 18. GitHub Actions CI/CD
  - [ ] 18.1 Create `.github/workflows/auto-tag.yml`: triggers on PR merge to main, reads version from `pyproject.toml`, creates git tag `v{version}`, creates GitHub release with auto-generated notes. Skips if tag already exists. Uses `GITHUB_TOKEN`
    - _Requirements: 15.1, 15.2, 15.3, 15.4, 15.5_
  - [ ] 18.2 Create `.github/workflows/publish.yml`: triggers on `v*` tag push, builds Python package, publishes to PyPI using trusted publishing (OIDC). Verifies package version matches tag. Reports errors on build or publish failure
    - _Requirements: 14.1, 14.2, 14.3, 14.4, 14.5_
  - [ ] 18.3 Write property test for version-tag matching (Property 21: Version-tag matching)
    - **Property 21: Version-tag matching**
    - **Validates: Requirements 14.5**

- [ ] 19. Final checkpoint - Full integration
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- All tasks are required — no optional tasks
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties from the design document (25 properties)
- The design uses Python throughout — all code examples and tests use Python with Hypothesis for PBT
- Container images may share a single base image since OpenSCAD handles both STL compilation and PNG export
