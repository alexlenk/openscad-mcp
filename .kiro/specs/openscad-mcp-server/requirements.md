# Requirements Document

## Introduction

This document defines the requirements for an OpenSCAD MCP (Model Context Protocol) server. The server enables LLMs to generate 3D models by providing tools and knowledge for OpenSCAD code generation, STL compilation via containerized OpenSCAD, and multi-angle image rendering for visual inspection. The MCP server orchestrates the full workflow — from code authoring through build and verification — and ensures the LLM has sufficient knowledge of OpenSCAD syntax, libraries, and coordinate systems to produce correct models.

## Glossary

- **MCP_Server**: The Model Context Protocol server that exposes tools, resources, and prompts to LLM clients for OpenSCAD 3D model creation workflows
- **LLM_Client**: The large language model client that connects to the MCP_Server and uses its tools to generate and verify 3D models
- **OpenSCAD_Code**: Source code written in the OpenSCAD language that defines a parametric 3D model
- **STL_File**: A Standard Tessellation Language file representing a 3D model's surface geometry, produced by compiling OpenSCAD_Code
- **Build_Container**: A Docker or Finch container with OpenSCAD installed, used to compile OpenSCAD_Code into STL_Files
- **Render_Container**: A Docker or Finch container used to render STL_Files into 2D images from multiple viewing angles
- **Library_Reference**: Documentation and usage instructions for OpenSCAD libraries including coordinate systems, module signatures, and parameter conventions, obtained dynamically from fetched library source code
- **Library_Catalog**: A structured listing of available OpenSCAD libraries fetched from the official catalog at https://openscad.org/libraries.html, containing library names, descriptions, source repository URLs, and documentation URLs
- **Workflow_Prompt**: An MCP prompt resource that provides the LLM_Client with step-by-step instructions for the model creation workflow
- **Inspection_Image**: A rendered 2D image of an STL_File taken from a specific viewing angle for visual verification
- **Container_Runtime**: The container execution environment, supporting either Docker or Finch
- **Working_Area**: The directory within the working directory where the current (latest) OpenSCAD_Code, STL_File, and Inspection_Images are stored, overwritten on each new iteration
- **Final_Output**: A designated directory within the working directory where the completed STL_File and Inspection_Images are copied when the workflow finishes
- **Confidence_Score**: A numeric value between 0.0 and 1.0 assigned by the LLM_Client during model inspection, representing the LLM_Client's assessed likelihood that the model correctly matches the user's intent, where values below 0.5 indicate low confidence
- **Confidence_Disagreement**: A condition where the LLM_Client assigned a Confidence_Score above 0.5 for an inspection but the user subsequently submitted negative feedback via the submit-feedback tool, indicating the LLM_Client's self-assessment was inaccurate
- **Feedback_Record**: A structured entry containing user-provided critique text, the current Inspection_Images at the time of feedback, the Confidence_Score from the most recent inspection, and a root cause analysis of the issue
- **Feedback_Store**: A dedicated directory within the working directory that stores Feedback_Records for future analysis and MCP_Server improvement
- **Package_Manifest**: The pyproject.toml file that defines the Python package metadata, dependencies, entry points, and build configuration for the MCP_Server
- **Release_Pipeline**: A GitHub Actions workflow that publishes the MCP_Server package to PyPI when a new git tag is pushed
- **Auto_Tag_Pipeline**: A GitHub Actions workflow that automatically creates a git tag and GitHub release when a pull request is merged to the main branch
- **PyPI**: The Python Package Index, the official repository for publishing Python packages so they can be installed via pip or uvx

## Requirements

### Requirement 1: MCP Server Initialization

**User Story:** As an LLM_Client, I want to connect to the MCP_Server, so that I can access tools and resources for OpenSCAD model creation.

#### Acceptance Criteria

1. THE MCP_Server SHALL expose a Model Context Protocol-compliant interface supporting tool invocation, resource access, and prompt retrieval
2. WHEN the LLM_Client connects, THE MCP_Server SHALL return a list of available tools, resources, and prompts
3. THE MCP_Server SHALL support communication over stdio transport

### Requirement 2: OpenSCAD Knowledge Resources

**User Story:** As an LLM_Client, I want access to OpenSCAD syntax documentation, library references, and coordinate system conventions, so that I can generate correct OpenSCAD_Code.

#### Acceptance Criteria

1. THE MCP_Server SHALL provide a resource containing OpenSCAD language syntax reference including primitive shapes, transformations, boolean operations, and module definitions
2. THE MCP_Server SHALL provide a resource containing Library_Reference documentation for each supported OpenSCAD library, including module signatures, parameter types, default values, and coordinate system conventions
3. THE MCP_Server SHALL provide a resource containing examples of correct library usage patterns including import statements, module calls, and parameter ordering
4. WHEN the LLM_Client requests a Library_Reference, THE MCP_Server SHALL return the coordinate system orientation (axes, origin, units) used by that library
5. THE MCP_Server SHALL provide a resource describing common OpenSCAD pitfalls and error patterns to avoid

### Requirement 3: Workflow Orchestration Prompts

**User Story:** As an LLM_Client, I want the MCP_Server to provide workflow instructions, so that I follow the correct sequence of steps when creating a 3D model.

#### Acceptance Criteria

1. THE MCP_Server SHALL provide a Workflow_Prompt that describes the complete model creation workflow in sequential steps: (a) understand the user request, (b) read and understand all library source code that will be used, (c) generate OpenSCAD_Code, (d) build STL_File, (e) render Inspection_Images, (f) systematically inspect each rendered angle, (g) iterate if needed
2. WHEN the LLM_Client retrieves the Workflow_Prompt, THE MCP_Server SHALL include instructions on which tools to call at each step and what inputs each tool expects
3. THE MCP_Server SHALL include in the Workflow_Prompt guidance on how to interpret Inspection_Images to verify placement, feature visibility, and dimensional correctness
4. THE Workflow_Prompt SHALL instruct the LLM_Client to examine each Inspection_Image individually, describe what is visible in each angle, and explicitly confirm or deny the presence of expected features before concluding the model is correct
5. THE Workflow_Prompt SHALL instruct the LLM_Client to read the source code of every OpenSCAD library and included file BEFORE writing any OpenSCAD_Code that references those libraries, and SHALL prohibit guessing at module signatures, parameter conventions, or coordinate systems
6. THE Workflow_Prompt SHALL instruct the LLM_Client to document the coordinate system orientation, module signatures, and parameter conventions discovered from library source code before generating OpenSCAD_Code that uses those libraries


### Requirement 4: OpenSCAD Code Generation Tool

**User Story:** As an LLM_Client, I want a tool that accepts OpenSCAD_Code and saves it to a working directory, so that the code can be compiled into an STL_File.

#### Acceptance Criteria

1. WHEN the LLM_Client invokes the save-code tool with OpenSCAD_Code and a filename, THE MCP_Server SHALL write the code to a file in the designated working directory
2. WHEN the LLM_Client provides OpenSCAD_Code that references external libraries, THE MCP_Server SHALL ensure the library files are accessible in the working directory or a configured library path
3. IF the provided filename does not end with the ".scad" extension, THEN THE MCP_Server SHALL append the ".scad" extension to the filename
4. WHEN the save-code tool completes successfully, THE MCP_Server SHALL return the absolute file path of the saved file

### Requirement 5: STL Build Tool

**User Story:** As an LLM_Client, I want a tool that compiles OpenSCAD_Code into an STL_File using a containerized OpenSCAD instance, so that I can produce a 3D-printable model.

#### Acceptance Criteria

1. WHEN the LLM_Client invokes the build-stl tool with a path to an OpenSCAD_Code file, THE MCP_Server SHALL launch the Build_Container to compile the file into an STL_File
2. THE MCP_Server SHALL support both Docker and Finch as Container_Runtime options for the Build_Container
3. WHEN the Build_Container completes compilation successfully, THE MCP_Server SHALL return the file path of the generated STL_File
4. IF the Build_Container reports a compilation error, THEN THE MCP_Server SHALL return the full OpenSCAD error output including line numbers and error descriptions
5. WHEN the build-stl tool is invoked, THE MCP_Server SHALL mount the working directory into the Build_Container so that source files and libraries are accessible
6. IF the Build_Container fails to start, THEN THE MCP_Server SHALL return an error message indicating whether the Container_Runtime is unavailable or the container image is missing

### Requirement 6: Multi-Angle Image Rendering Tool

**User Story:** As an LLM_Client, I want a tool that renders an STL_File from multiple viewing angles, so that I can visually inspect the model from all sides.

#### Acceptance Criteria

1. WHEN the LLM_Client invokes the render-images tool with a path to an STL_File, THE MCP_Server SHALL launch the Render_Container to produce Inspection_Images from 8 distinct viewing angles
2. THE MCP_Server SHALL render Inspection_Images from the following 8 viewing angles: front, back, left, right, top, bottom, front-right-top isometric, and back-left-top isometric
3. THE MCP_Server SHALL support both Docker and Finch as Container_Runtime options for the Render_Container
4. WHEN the Render_Container completes rendering, THE MCP_Server SHALL return the file paths of all generated Inspection_Images
5. THE MCP_Server SHALL generate Inspection_Images in PNG format with a minimum resolution of 1024x1024 pixels
6. IF the Render_Container fails to render one or more angles, THEN THE MCP_Server SHALL return an error message identifying which angles failed and the associated error output

### Requirement 7: Model Inspection and Verification

**User Story:** As an LLM_Client, I want to receive rendered images in a format I can analyze and state my confidence in the model's correctness, so that I can verify the 3D model matches the user's intent and self-correct when uncertain.

#### Acceptance Criteria

1. WHEN the render-images tool returns Inspection_Images, THE MCP_Server SHALL return each image as a base64-encoded PNG with a label indicating the viewing angle
2. THE MCP_Server SHALL include with each Inspection_Image the camera position and rotation parameters used for that viewing angle
3. WHEN the LLM_Client determines the model needs corrections after inspecting images, THE LLM_Client SHALL be able to invoke the save-code tool with updated OpenSCAD_Code and repeat the build-render-inspect cycle
4. WHEN the LLM_Client completes inspection of all Inspection_Images, THE Workflow_Prompt SHALL require the LLM_Client to assign a Confidence_Score between 0.0 and 1.0 representing the LLM_Client's assessed likelihood that the model correctly matches the user's intent
5. THE MCP_Server SHALL include the Confidence_Score in the inspection result returned to the LLM_Client so that the score is recorded alongside the inspection outcome
6. WHEN the LLM_Client assigns a Confidence_Score below 0.5, THE Workflow_Prompt SHALL require the LLM_Client to list specific concerns driving the low confidence, hypothesize corrections in the OpenSCAD_Code, and iterate with a code correction before re-rendering rather than declaring the model complete
7. THE Workflow_Prompt SHALL prohibit the LLM_Client from declaring a model complete when the Confidence_Score is below 0.5

### Requirement 8: Container Image Management

**User Story:** As a developer, I want the MCP_Server to manage container images for building and rendering, so that the tools work without manual container setup.

#### Acceptance Criteria

1. THE MCP_Server SHALL provide a Dockerfile or container image specification for the Build_Container with OpenSCAD installed
2. THE MCP_Server SHALL provide a Dockerfile or container image specification for the Render_Container with a 3D rendering tool installed
3. WHEN the MCP_Server starts and the required container images are not present locally, THE MCP_Server SHALL provide instructions or a tool to build the container images
4. IF a required container image is not available and cannot be built, THEN THE MCP_Server SHALL return a descriptive error message listing the missing image and build instructions

### Requirement 9: Dynamic Library Discovery and On-Demand Download

**User Story:** As an LLM_Client, I want the MCP_Server to fetch the official OpenSCAD library catalog and download libraries on demand from their source repositories, so that I can discover and use the latest version of any library without relying on pre-bundled or hardcoded selections.

#### Acceptance Criteria

1. THE MCP_Server SHALL provide a browse-library-catalog tool that fetches and parses the official OpenSCAD library listing at https://openscad.org/libraries.html and returns a structured catalog where each entry contains the library name, description, source repository URL, and documentation URL
2. WHEN the LLM_Client invokes the browse-library-catalog tool, THE MCP_Server SHALL fetch the latest content from https://openscad.org/libraries.html so that the catalog reflects the current state of available libraries
3. THE MCP_Server SHALL NOT bundle, pre-select, or hardcode any specific set of OpenSCAD libraries; all library selection decisions SHALL be made by the LLM_Client based on catalog descriptions and the current task requirements
4. WHEN the LLM_Client invokes the fetch-library tool with a library name from the catalog, THE MCP_Server SHALL download the latest version of that library from its source repository and place the library files in the working directory
5. WHEN a library has already been fetched during the current session, THE MCP_Server SHALL use the cached copy instead of re-downloading, and SHALL provide a force-refresh option to override the cache and pull the latest version from the source repository
6. THE MCP_Server SHALL ensure fetched library files are mounted into the Build_Container at the standard OpenSCAD library path so they are accessible during STL compilation
7. WHEN the fetch-library tool completes successfully, THE MCP_Server SHALL return the local file path of the fetched library and confirm the library is available for the read-library-source tool (Requirement 17) to inspect
8. IF the fetch-library tool fails to download a library, THEN THE MCP_Server SHALL return an error message including the source repository URL and the reason for the failure so the LLM_Client can report the issue or attempt an alternative approach
9. THE Workflow_Prompt SHALL instruct the LLM_Client to invoke the browse-library-catalog tool to discover available libraries, then invoke the fetch-library tool for selected libraries, and then invoke the read-library-source tool to review the library source code before writing any OpenSCAD_Code that references those libraries

### Requirement 10: Automatic Setup Detection and LLM-Persisted Configuration

**User Story:** As a developer, I want the MCP_Server to automatically detect my container runtime and environment on first use and persist the settings via the LLM_Client's memory mechanism, so that I never need to manually configure environment variables or configuration files.

#### Acceptance Criteria

1. THE MCP_Server SHALL provide an init tool that tests whether Docker is available, then whether Finch is available, verifies the detected Container_Runtime can successfully run a test container, and returns a structured result containing the detected Container_Runtime type, the container executable path, the working directory path, and formatted persistence content suitable for the LLM_Client to save using the LLM_Client's native memory mechanism (e.g., a steering file for Kiro, CLAUDE.md for Claude Code, or equivalent)
2. THE Workflow_Prompt SHALL instruct the LLM_Client to check for previously persisted MCP_Server settings in the LLM_Client's memory mechanism before invoking the init tool
3. WHEN persisted settings are found, THE Workflow_Prompt SHALL instruct the LLM_Client to skip the init tool and use the persisted Container_Runtime and working directory settings directly
4. WHEN no persisted settings are found, THE Workflow_Prompt SHALL instruct the LLM_Client to invoke the init tool and then persist the returned content using the LLM_Client's native memory mechanism
5. IF the init tool finds neither Docker nor Finch available, THEN THE MCP_Server SHALL return an error message listing the supported Container_Runtime options and installation instructions for each
6. THE MCP_Server SHALL NOT require any environment variables, configuration files, or manual setup from the developer for Container_Runtime selection or working directory configuration


### Requirement 11: Artifact Storage and Cleanup

**User Story:** As a user, I want the latest renders, STL_File, and OpenSCAD_Code kept in a working area and the final output preserved separately, so that I do not lose important results without accumulating unnecessary intermediate files.

#### Acceptance Criteria

1. THE MCP_Server SHALL maintain a Working_Area directory that contains only the latest OpenSCAD_Code file, STL_File, and Inspection_Images
2. WHEN the save-code tool writes a new OpenSCAD_Code file, THE MCP_Server SHALL overwrite the previous OpenSCAD_Code file in the Working_Area
3. WHEN the build-stl tool produces a new STL_File, THE MCP_Server SHALL overwrite the previous STL_File in the Working_Area
4. WHEN the render-images tool produces new Inspection_Images, THE MCP_Server SHALL remove the previous Inspection_Images from the Working_Area and store the new Inspection_Images
5. WHEN the workflow completes, THE MCP_Server SHALL copy the latest STL_File, OpenSCAD_Code, and Inspection_Images from the Working_Area to the Final_Output directory
6. THE MCP_Server SHALL create the Working_Area and Final_Output directories automatically if they do not exist

### Requirement 12: User Feedback and Critique Tool

**User Story:** As a user, I want to provide feedback when a design is not satisfactory, so that the feedback, associated images, confidence data, and root cause analysis are stored for future MCP_Server improvement.

#### Acceptance Criteria

1. THE MCP_Server SHALL provide a submit-feedback tool that accepts user critique text and an optional root cause category
2. WHEN the submit-feedback tool is invoked, THE MCP_Server SHALL create a Feedback_Record in the Feedback_Store containing the user critique text and a timestamp
3. WHEN the submit-feedback tool is invoked, THE MCP_Server SHALL copy the current Inspection_Images and OpenSCAD_Code from the Working_Area into the Feedback_Record directory so the state at the time of feedback is preserved
4. WHEN the submit-feedback tool is invoked, THE MCP_Server SHALL generate a root cause analysis entry in the Feedback_Record that describes the likely cause of the design deficiency based on the user critique
5. THE MCP_Server SHALL store each Feedback_Record in a separate subdirectory within the Feedback_Store, named with the Feedback_Record timestamp
6. THE MCP_Server SHALL maintain a feedback-index file in the Feedback_Store that lists all Feedback_Records with their timestamps, critique summaries, and root cause categories
7. THE MCP_Server SHALL provide a list-feedback tool that returns all Feedback_Records with their summaries, enabling future analysis of common failure patterns
8. WHEN the submit-feedback tool is invoked, THE MCP_Server SHALL record the Confidence_Score from the most recent model inspection in the Feedback_Record
9. WHEN the submit-feedback tool is invoked and the most recent Confidence_Score was above 0.5, THE MCP_Server SHALL flag the Feedback_Record as a Confidence_Disagreement, indicating the LLM_Client assessed the model as likely correct but the user disagreed
10. THE MCP_Server SHALL include the Confidence_Disagreement flag and the associated Confidence_Score in the feedback-index file so that Confidence_Disagreement occurrences can be queried and analyzed across all Feedback_Records


### Requirement 13: Python Packaging for uvx Distribution

**User Story:** As a developer, I want the MCP_Server packaged as a standard Python package with proper entry points, so that users can install and run it via `uvx openscad-mcp-server` without manual setup.

#### Acceptance Criteria

1. THE MCP_Server SHALL include a Package_Manifest (pyproject.toml) that defines the package name, version, description, dependencies, and Python version requirements
2. THE Package_Manifest SHALL declare a console script entry point named "openscad-mcp-server" that launches the MCP_Server
3. WHEN a user runs `uvx openscad-mcp-server`, THE MCP_Server SHALL start and accept MCP connections over stdio transport
4. THE Package_Manifest SHALL declare all runtime dependencies required by the MCP_Server so that uvx resolves them automatically during installation
5. THE Package_Manifest SHALL use a PEP 621-compliant format with a build backend compatible with PyPI publishing

### Requirement 14: GitHub Actions Release to PyPI

**User Story:** As a maintainer, I want a Release_Pipeline that publishes the MCP_Server package to PyPI when a new tag is pushed, so that updated versions are available to users via uvx.

#### Acceptance Criteria

1. WHEN a git tag matching the pattern "v*" is pushed, THE Release_Pipeline SHALL build the MCP_Server Python package and publish it to PyPI
2. THE Release_Pipeline SHALL use PyPI trusted publishing (OIDC) for authentication instead of storing API tokens as secrets
3. IF the package build step fails, THEN THE Release_Pipeline SHALL report the build error and stop without publishing to PyPI
4. IF the PyPI publish step fails, THEN THE Release_Pipeline SHALL report the publish error including the PyPI response
5. THE Release_Pipeline SHALL verify that the package version in the Package_Manifest matches the git tag version before publishing

### Requirement 15: GitHub Actions Auto-Tag and Release on PR Merge

**User Story:** As a maintainer, I want an Auto_Tag_Pipeline that creates a git tag and GitHub release when a pull request is merged to main, so that releases are automated and consistent.

#### Acceptance Criteria

1. WHEN a pull request is merged to the main branch, THE Auto_Tag_Pipeline SHALL read the current version from the Package_Manifest
2. WHEN a pull request is merged to the main branch, THE Auto_Tag_Pipeline SHALL create a git tag in the format "v{version}" using the version from the Package_Manifest
3. WHEN the git tag is created, THE Auto_Tag_Pipeline SHALL create a GitHub release associated with that tag, including auto-generated release notes
4. IF a git tag with the same version already exists, THEN THE Auto_Tag_Pipeline SHALL skip tag creation and report that the version has already been released
5. THE Auto_Tag_Pipeline SHALL use the GitHub Actions built-in GITHUB_TOKEN for authentication when creating tags and releases


### Requirement 16: Thorough Model Inspection

**User Story:** As a user, I want the LLM_Client to carefully and systematically inspect every rendered angle of my model and assign confidence scores based on the inspection, so that defects are caught before the model is declared complete and the LLM_Client's certainty is quantified.

#### Acceptance Criteria

1. WHEN the render-images tool returns Inspection_Images, THE Workflow_Prompt SHALL require the LLM_Client to examine each of the 8 Inspection_Images individually and describe the visible geometry, features, and orientation in each image before making a correctness determination
2. THE Workflow_Prompt SHALL prohibit the LLM_Client from declaring a model correct after examining fewer than all 8 Inspection_Images
3. THE Workflow_Prompt SHALL require the LLM_Client to create a per-angle checklist that maps each expected geometric feature to the angles where that feature should be visible, and verify each checklist item against the corresponding Inspection_Image
4. WHEN the LLM_Client identifies a discrepancy between an expected feature and an Inspection_Image, THE Workflow_Prompt SHALL require the LLM_Client to describe the discrepancy, hypothesize the root cause in the OpenSCAD_Code, and iterate with a code correction before re-rendering
5. THE Workflow_Prompt SHALL instruct the LLM_Client to pay specific attention to symmetry, alignment, relative proportions, and the absence of unintended artifacts or z-fighting in each Inspection_Image
6. WHEN the LLM_Client completes the per-angle checklist verification for a single Inspection_Image, THE Workflow_Prompt SHALL require the LLM_Client to assign a per-angle Confidence_Score between 0.0 and 1.0 for that angle, where each checklist item that fails or is uncertain reduces the score proportionally
7. WHEN the LLM_Client assigns a per-angle Confidence_Score below 0.5 for any individual Inspection_Image, THE Workflow_Prompt SHALL require the LLM_Client to re-examine that angle, explicitly question its initial assessment, list specific features that are uncertain, and determine whether a code correction is needed before proceeding
8. WHEN the LLM_Client has examined all 8 Inspection_Images and assigned per-angle Confidence_Scores, THE Workflow_Prompt SHALL require the LLM_Client to compute an overall Confidence_Score as the minimum of all per-angle Confidence_Scores, ensuring that weakness in any single angle is not masked by averaging
9. THE Workflow_Prompt SHALL prohibit the LLM_Client from declaring a model complete when the overall Confidence_Score is below 0.5, and SHALL require the LLM_Client to iterate with code corrections targeting the angles with the lowest per-angle Confidence_Scores

### Requirement 17: Mandatory Library Source Code Review

**User Story:** As a user, I want the MCP_Server to enforce that the LLM_Client reads and understands library source code before writing any OpenSCAD_Code that uses those libraries, so that the LLM_Client does not waste iterations guessing at library behavior.

#### Acceptance Criteria

1. THE MCP_Server SHALL provide a read-library-source tool that accepts a library name and returns the full source code of that library's OpenSCAD files
2. WHEN the LLM_Client invokes the save-code tool with OpenSCAD_Code that contains `include` or `use` statements referencing a library, THE MCP_Server SHALL verify that the read-library-source tool was invoked for that library during the current workflow session
3. IF the LLM_Client attempts to save OpenSCAD_Code that references a library whose source has not been read in the current workflow session, THEN THE MCP_Server SHALL reject the save and return an error message instructing the LLM_Client to first invoke the read-library-source tool for the referenced library
4. WHEN the read-library-source tool returns library source code, THE MCP_Server SHALL include a structured summary header listing the library's module names, parameter signatures, coordinate system conventions, and unit conventions extracted from the source
5. THE Workflow_Prompt SHALL instruct the LLM_Client to invoke the read-library-source tool for every library it intends to use and to record the discovered module signatures and coordinate conventions before writing any OpenSCAD_Code
6. THE MCP_Server SHALL track which libraries have been reviewed by the LLM_Client during the current workflow session and make this tracking state available via a list-reviewed-libraries tool
