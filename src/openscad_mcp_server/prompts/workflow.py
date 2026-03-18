"""Workflow prompt for the OpenSCAD MCP server (openscad-workflow)."""

from __future__ import annotations

PROMPT_NAME = "openscad-workflow"
PROMPT_DESCRIPTION = (
    "Step-by-step instructions for creating a 3D model with OpenSCAD, "
    "covering init, library discovery, code generation, build, render, "
    "systematic multi-angle inspection with confidence scoring, iteration, "
    "finalize, and feedback handling."
)


def get_workflow_prompt() -> str:
    """Return the full workflow prompt text."""
    return _WORKFLOW_PROMPT


_WORKFLOW_PROMPT = """\
# OpenSCAD Model Creation Workflow

Follow these steps in order when creating a 3D model with OpenSCAD. \
Do not skip steps or reorder them.

---

## Step 1: Initialization and Settings Check

1. Check your memory/persisted settings for previously saved OpenSCAD MCP \
server configuration (container runtime, executable path, working directory).
2. If persisted settings are found, use them directly and skip to Step 2.
3. If no persisted settings are found, invoke the `init` tool.
   - The init tool detects whether Docker or Finch is available, runs a test \
container, and returns the detected runtime, executable path, working \
directory, and formatted persistence content.
4. Persist the returned settings using your native memory mechanism \
(e.g., a steering file for Kiro, CLAUDE.md for Claude Code, or equivalent) \
so future sessions skip this step.
5. If the init tool reports that neither Docker nor Finch is available, \
inform the user and stop. Do not proceed without a working container runtime.

**Tools used:** `init`

---

## Step 2: Understand the User Request

1. Read the user's description of the desired 3D model carefully.
2. Identify the key geometric features, dimensions, proportions, and any \
specific requirements (e.g., printability, tolerances, symmetry).
3. Identify components mentioned by the user (e.g., ESP32, display, \
speaker, microphone) and note their physical requirements.
4. Determine whether any external OpenSCAD libraries might be needed \
(see the library recommendation table in Step 3).

---

## Step 3: Library Discovery (Library-First Design)

Before writing any code, always check for existing library solutions. \
Libraries produce more reliable results than hand-written code and save \
significant iteration time.

1. Invoke the `browse-library-catalog` tool to fetch the current list of \
available OpenSCAD libraries from the official catalog.
2. Review the catalog entries — each contains a library name, description, \
source repository URL, and documentation URL.
3. Use the following table to identify relevant libraries based on the task:

| Keywords in user request | Recommended Library | Why |
|---|---|---|
| enclosure, box, case, housing, project box | YAPP_Box | Parametric project boxes with cutouts, standoffs, lids, snap-fits |
| gear, bearing, screw, thread, bolt, nut | BOSL2 | Mechanical components, threading, fasteners |
| ESP32, Arduino, Raspberry Pi, PCB | YAPP_Box | PCB enclosures with standoff patterns and connector cutouts |
| display, speaker, microphone, LED | YAPP_Box | Component cutouts with proper tolerances and orientation |
| hinge, snap-fit, clip, latch | BOSL2 or YAPP_Box | Mechanical joints and closures |
| rounded, fillet, chamfer, bezier | BOSL2 | Advanced geometry primitives |
| organic, sculpted, curved surface | BOSL2 | Bezier surfaces, rounded primitives |

4. Select libraries that match the task. Prefer library modules over \
hand-written equivalents — a library's parametric enclosure is more \
reliable than a custom one.
5. If no external libraries are needed, skip to Step 5.

### PROHIBITION: No Reinventing the Wheel

Before writing any custom module, verify:
- Have you checked the library catalog for existing solutions?
- Are you about to hand-code something that a library already provides?
- If a library covers 80% of the need, use it and customize the rest — \
do not rewrite the 80% from scratch.

**Tools used:** `browse-library-catalog`

---

## Step 4: Library Fetch and Mandatory Source Review

For each library you intend to use:

1. Invoke the `fetch-library` tool with the library name and source URL \
from the catalog. This downloads the library to the working directory.
2. Invoke the `read-library-source` tool with the library name. This \
returns the full source code of all `.scad` files in the library along \
with a structured summary of module signatures, parameter types, defaults, \
coordinate system conventions, and unit conventions.
3. Study the returned source code and summary carefully. Record:
   - Every module name and its full parameter signature
   - The coordinate system orientation (e.g., right-hand, Z-up)
   - The unit conventions (e.g., millimeters)
   - Any special parameter conventions or ordering requirements

### PROHIBITION: No Guessing at Library APIs

- You MUST NOT write any OpenSCAD code that calls a library module unless \
you have first invoked `read-library-source` for that library in this session.
- You MUST NOT guess at module names, parameter names, parameter order, \
default values, or coordinate conventions.
- If you are unsure about any aspect of a library's API, re-read the source.
- The `save-code` tool will reject code that references libraries whose \
source has not been reviewed in the current session.

**Tools used:** `fetch-library`, `read-library-source`

---

## Step 5: Generate OpenSCAD Code

1. Write OpenSCAD code that implements the user's requested model.
2. Use the correct `include` or `use` statements for any libraries.
3. Apply the coordinate system and parameter conventions you recorded \
in Step 4.
4. Invoke the `save-code` tool with the code and a descriptive filename.
   - The filename will automatically get a `.scad` extension if missing.
   - The tool verifies that all referenced libraries have been reviewed.
5. If the save is rejected due to unreviewed libraries, go back to Step 4 \
and review the missing libraries before retrying.

**Tools used:** `save-code`

---

## Step 6: Build STL

1. Invoke the `build-stl` tool with the saved `.scad` file path.
2. If the build succeeds, note the returned STL file path and proceed \
to Step 7.
3. If the build fails, read the full error output carefully:
   - Identify the error type (syntax error, undefined module, manifold \
error, etc.).
   - Fix the OpenSCAD code based on the error details.
   - Re-save the code with `save-code` and retry the build.
   - Repeat until the build succeeds.

**Tools used:** `build-stl`

---

## Step 7: Render Multi-Angle Images

1. Invoke the `render-images` tool with the STL file path.
2. The tool renders the model from 8 predefined camera angles:
   - front, back, left, right, top, bottom
   - front-right-top-iso (isometric), back-left-top-iso (isometric)
3. The tool returns:
   - A text block with camera position and rotation metadata for all angles
   - 8 image blocks (base64-encoded PNG at 1024x1024), one per angle
4. If any angles fail to render, the tool reports which angles failed. \
Note the failures and proceed with the available images, but flag the \
missing angles for re-examination after fixing any issues.

**Tools used:** `render-images`

---

## Step 8: Systematic Per-Angle Inspection

This is the most critical step. You must inspect every rendered angle \
individually and thoroughly.

### 8a: Build a Feature Checklist

Before examining any image, create a checklist of expected geometric \
features based on the user's request. For each feature, list which \
camera angles should make that feature visible. Example:

| Feature | Expected Visible In |
|---|---|
| Main body cylinder | front, back, left, right, both isos |
| Top mounting holes | top, front-right-top-iso |
| Bottom chamfer | bottom, front, back-left-top-iso |

### 8b: Examine Each Angle Individually

For EACH of the 8 angles, in order:

1. Look at the rendered image for this angle.
2. Describe what you see: the visible geometry, shapes, features, \
proportions, and orientation.
3. Check each item on your feature checklist that should be visible \
from this angle:
   - Is the feature present?
   - Is it the correct size and proportion relative to other features?
   - Is it correctly positioned?
   - Is it correctly oriented?
4. Check for defects:
   - Symmetry: Are symmetric features actually symmetric?
   - Alignment: Are features properly aligned with each other?
   - Proportions: Do relative sizes match the user's specifications?
   - Artifacts: Is there z-fighting, missing faces, or unexpected geometry?
   - Surface quality: Are curves smooth (sufficient `$fn`)?

### 8b-2: Functional Validation Checklist

After the geometric checklist, answer these functional questions. \
Skip items that do not apply to the current design.

**For enclosures and multi-part designs:**
- Can cables/wires route between all parts? Is there a physical path?
- Do mating features align when assembled? (grilles over speakers, \
cutouts over displays)
- Is every component accessible for installation?
- Are connectors (USB, power, etc.) accessible from outside?
- Do moving/removable parts have clearance?

**For each placed component:**
- Which direction does this component face? (speaker toward grille, \
display toward cutout, antenna away from metal)
- Is there enough clearance around it for the component + connector + cable?
- Does the mounting method work? (standoffs have screw holes, press-fit \
has tolerance)

**Component-specific checks:**
- ESP32/microcontroller: USB-C access, antenna clearance (no metal near \
antenna end), GPIO access if needed
- Display: FPC ribbon cable has routing path, display faces outward \
through cutout, cutout matches active area
- Speaker: faces toward grille/opening, acoustic chamber behind it, \
grille holes are open (not solid)
- Microphone: clear sound path to outside, not placed adjacent to speaker

### 8c: Assign a Per-Angle Confidence Score

After examining each angle, assign a confidence score between 0.0 and 1.0 \
for that angle:

- Start at 1.0 for the angle.
- For each checklist item that fails or is uncertain, reduce the score \
proportionally.
- A score of 1.0 means every expected feature is correct in this angle.
- A score of 0.0 means the angle shows a completely wrong model.

### 8d: Handle Low Per-Angle Confidence

If any per-angle confidence score is below 0.5:

1. STOP and re-examine that angle carefully.
2. Explicitly question your initial assessment — could you be \
misinterpreting the viewing angle?
3. List the specific features that are uncertain or incorrect.
4. Determine whether a code correction is needed.
5. If a correction is needed, go to Step 9 (Iteration).

### PROHIBITION: No Skipping Angles

- You MUST examine ALL 8 rendered angles individually.
- You MUST NOT declare a model correct after examining fewer than 8 angles.
- You MUST NOT skip an angle because it "looks similar" to another angle.
- Every angle provides unique information; treat each one independently.

---

## Step 9: Compute Overall Confidence and Decide

1. After examining all 8 angles, compute the overall confidence score as \
the MINIMUM of all 8 per-angle confidence scores.
   - Overall confidence = min(front, back, left, right, top, bottom, \
front-right-top-iso, back-left-top-iso)
   - This ensures that weakness in any single angle is not masked by \
averaging.
2. Record the overall confidence score.

### If overall confidence >= 0.5:

- Proceed to Step 10 (Finalize).

### If overall confidence < 0.5:

- You MUST NOT declare the model complete.
- Identify the angles with the lowest per-angle scores.
- Hypothesize what is wrong in the OpenSCAD code based on the defects \
observed in those angles.
- Go to Step 9a (Iteration).

### PROHIBITION: No Completion Below 0.5

- You are FORBIDDEN from declaring a model complete when the overall \
confidence score is below 0.5.
- You MUST iterate with code corrections targeting the weakest angles.

### PROHIBITION: No Finalization Without Full 8-Angle Render

- The `angles` parameter on `render-images` is for quick iteration only.
- Before proceeding to Step 10 (Finalize), you MUST have rendered and \
inspected ALL 8 angles in the most recent render cycle.
- If your last render used selective angles, re-run `render-images` \
without the `angles` parameter to produce the full set before finalizing.

---

## Step 9a: Iteration

1. Based on the defects identified during inspection:
   - Hypothesize the root cause in the OpenSCAD code.
   - Write corrected OpenSCAD code.
2. Save the corrected code with `save-code` (this overwrites the previous \
version in the working area).
3. Rebuild with `build-stl`.
4. Re-render with `render-images`.
5. Return to Step 8 and repeat the full inspection process.
6. Continue iterating until the overall confidence score is >= 0.5 or \
you have exhausted reasonable correction attempts.

**Tools used:** `save-code`, `build-stl`, `render-images`

---

## Step 10: Finalize

1. When the overall confidence score is >= 0.5 and you are satisfied \
with the model:
2. Invoke the `finalize` tool.
   - This copies the latest STL, OpenSCAD code, and rendered images \
from the working area to the final output directory.
3. Report the final output directory and file list to the user.
4. Include the overall confidence score and a brief summary of the \
inspection results.

**Tools used:** `finalize`

---

## Step 11: Handle User Feedback

If the user is not satisfied with the final model:

1. Ask the user for specific critique — what is wrong, what they expected, \
and any details about the defect.
2. Invoke the `submit-feedback` tool with:
   - The user's critique text
   - An optional root cause category (e.g., "geometry", "proportions", \
"orientation", "missing feature", "library misuse")
3. The feedback tool automatically:
   - Creates a timestamped feedback record
   - Copies the current working area artifacts (code, STL, images)
   - Records the confidence score from the most recent inspection
   - Flags confidence disagreement if the score was above 0.5 but the \
user is unhappy (indicating the self-assessment was inaccurate)
4. After submitting feedback, return to Step 5 to iterate on the design \
based on the user's critique.

To review past feedback at any time, invoke the `list-feedback` tool.

**Tools used:** `submit-feedback`, `list-feedback`

---

## Tool Reference Summary

| Tool | Purpose |
|---|---|
| `init` | Detect container runtime, return persistence content |
| `browse-library-catalog` | Fetch official OpenSCAD library catalog |
| `fetch-library` | Download a library from its source repository |
| `read-library-source` | Read library source code and extract module signatures |
| `list-reviewed-libraries` | List libraries reviewed in this session |
| `save-code` | Save OpenSCAD code to working area (enforces library review) |
| `check-syntax` | Fast syntax validation without full STL compilation |
| `build-stl` | Compile OpenSCAD code to STL via container (returns mesh metadata) |
| `measure-stl` | Parse an STL file and return dimensional metadata without rendering |
| `render-images` | Render from 8 angles (or selective via `angles` param), return images inline |
| `submit-feedback` | Record user feedback with artifacts and confidence data |
| `list-feedback` | List all feedback records |
| `finalize` | Copy working area to final output directory |

---

## Key Rules

1. ALWAYS check for persisted settings before running `init`.
2. ALWAYS check the library catalog before writing custom geometry code.
3. ALWAYS read library source code before writing code that uses it.
4. NEVER guess at library module signatures or coordinate conventions.
5. NEVER hand-code geometry that an available library already provides.
6. ALWAYS use `check-syntax` for quick validation before a full `build-stl`.
7. ALWAYS inspect ALL 8 rendered angles individually.
8. ALWAYS assign per-angle confidence scores after inspecting each angle.
9. ALWAYS compute overall confidence as the minimum of per-angle scores.
10. NEVER declare a model complete with overall confidence below 0.5.
11. ALWAYS iterate when confidence is low, targeting the weakest angles.
12. ALWAYS complete the functional validation checklist (Step 8b-2) for \
enclosures and multi-component designs.
13. ALWAYS render all 8 angles before finalizing — selective rendering \
is for iteration only.
14. ALWAYS use `submit-feedback` when the user provides negative feedback.
15. ALWAYS `finalize` before delivering the completed model to the user.
"""
