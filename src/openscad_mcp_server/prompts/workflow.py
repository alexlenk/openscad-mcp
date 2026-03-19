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
   - Pass the user's project directory as `workspace_dir` so all files \
(code, STL, renders, libraries) are stored there and visible in the IDE.
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

1. Check the OpenSCAD library catalog at \
https://openscad.org/libraries.html to find relevant libraries.
2. Use the following table to identify relevant libraries based on the task:

| Keywords in user request | Recommended Library | Why |
|---|---|---|
| enclosure, box, case, housing, project box | YAPP_Box | Parametric project boxes with cutouts, standoffs, lids, snap-fits |
| gear, bearing, screw, thread, bolt, nut | BOSL2 | Mechanical components, threading, fasteners |
| ESP32, Arduino, Raspberry Pi, PCB | YAPP_Box | PCB enclosures with standoff patterns and connector cutouts |
| display, speaker, microphone, LED | YAPP_Box | Component cutouts with proper tolerances and orientation |
| hinge, snap-fit, clip, latch | BOSL2 or YAPP_Box | Mechanical joints and closures |
| rounded, fillet, chamfer, bezier | BOSL2 | Advanced geometry primitives |
| organic, sculpted, curved surface | BOSL2 | Bezier surfaces, rounded primitives |

3. Select libraries that match the task. Prefer library modules over \
hand-written equivalents — a library's parametric enclosure is more \
reliable than a custom one.
4. If no external libraries are needed, skip to Step 5.

### PROHIBITION: No Reinventing the Wheel

Before writing any custom module, verify:
- Have you checked the library catalog for existing solutions?
- Are you about to hand-code something that a library already provides?
- If a library covers 80% of the need, use it and customize the rest — \
do not rewrite the 80% from scratch.

---

## Step 4: Library Download and Source Review

For each library you intend to use:

1. Download the library from its GitHub repository into the working \
directory. Use git clone or download the archive.
2. Read the library's main .scad files to understand the available \
modules, their parameter signatures, coordinate system, and unit \
conventions.
3. Study the module signatures carefully. Record:
   - Every module name and its full parameter signature
   - The coordinate system orientation (e.g., right-hand, Z-up)
   - The unit conventions (e.g., millimeters)
   - Any special parameter conventions or ordering requirements
4. Check the library's README or documentation for usage examples.

### PROHIBITION: No Guessing at Library APIs

- You MUST NOT write any OpenSCAD code that calls a library module unless \
you have first read the library source to understand its API.
- You MUST NOT guess at module names, parameter names, parameter order, \
default values, or coordinate conventions.
- If you are unsure about any aspect of a library's API, read the \
specific module source file.

---

## Step 5: Generate OpenSCAD Code

1. Write OpenSCAD code that implements the user's requested model.
2. Use the correct `include` or `use` statements for any libraries.
3. Apply the coordinate system and parameter conventions you recorded \
in Step 4.
4. Save the code as a `.scad` file in the working directory.
5. When using libraries via `include`, prefer literal values over \
computed variables in array definitions. OpenSCAD's variable scoping \
with `include` can cause unexpected `undef` values.

---

## Step 6: Build STL

1. Invoke the `build-stl` tool with the saved `.scad` file path.
2. If the build succeeds:
   a. Call `measure-stl` on the output and check `is_manifold`.
   b. If `is_manifold` is false, STOP. Do NOT present a non-manifold STL \
to the user. Try to fix it: simplify boolean operations, remove hooks \
one at a time to isolate the cause, increase `$fn`, or restructure the \
geometry. Re-build after each fix attempt.
   c. If `is_manifold` is true, proceed to Step 7.
3. If the build fails, read the full error output carefully:
   - Identify the error type (syntax error, undefined module, manifold \
error, etc.).
   - Fix the OpenSCAD code based on the error details.
   - Re-save the code and retry the build.
   - Repeat until the build succeeds.
4. After any failure (build error, non-manifold), attempt at least one \
fix before reporting to the user. Only report after 3 failed attempts.

**Tools used:** `build-stl`, `measure-stl`

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

If any per-angle confidence score is below 0.8:

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

### If overall confidence >= 0.8:

- Proceed to Step 10 (Finalize).

### If overall confidence < 0.5:

- You MUST NOT declare the model complete.
- Identify the angles with the lowest per-angle scores.
- Hypothesize what is wrong in the OpenSCAD code based on the defects \
observed in those angles.
- Go to Step 9a (Iteration).

### PROHIBITION: No Completion Below 0.8

- You are FORBIDDEN from declaring a model complete when the overall \
confidence score is below 0.8.
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
2. Save the corrected code (this overwrites the previous \
version in the working area).
3. Rebuild with `build-stl`.
4. Re-render with `render-images`.
5. Return to Step 8 and repeat the full inspection process.
6. Continue iterating until the overall confidence score is >= 0.8 or \
you have exhausted reasonable correction attempts.

**Tools used:** `build-stl`, `render-images`

---

## Step 10: Finalize

1. When the overall confidence score is >= 0.8 and you are satisfied \
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
   - Flags confidence disagreement if the score was above 0.8 but the \
user is unhappy (indicating the self-assessment was inaccurate)
4. After submitting feedback, return to Step 5 to iterate on the design \
based on the user's critique.

To review past feedback at any time, invoke the `list-feedback` tool.

**Tools used:** `submit-feedback`, `list-feedback`

---

## Tool Reference Summary

| Tool | Purpose |
|---|---|
| `init` | Detect container runtime, return persistence content and steering rules |
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
2. ALWAYS check the library catalog at https://openscad.org/libraries.html \
before writing custom geometry code.
3. ALWAYS read library source code before writing code that uses it.
4. NEVER guess at library module signatures or coordinate conventions.
5. NEVER hand-code geometry that an available library already provides.
6. ALWAYS use `check-syntax` for quick validation before a full `build-stl`.
7. ALWAYS call `measure-stl` after `build-stl` and check `is_manifold`. \
If false, fix it before proceeding.
8. ALWAYS render ALL 8 angles with `render-images` (omit angles parameter).
9. ALWAYS inspect ALL 8 rendered angles individually.
10. ALWAYS assign per-angle confidence scores after inspecting each angle.
11. ALWAYS compute overall confidence as the minimum of per-angle scores.
12. NEVER declare a model complete with overall confidence below 8.
13. ALWAYS iterate when confidence is low, targeting the weakest angles.
14. ALWAYS complete the functional validation checklist (Step 8b-2) for \
enclosures and multi-component designs.
15. ALWAYS render all 8 angles before finalizing — selective rendering \
is for iteration only.
16. ALWAYS use `submit-feedback` when the user provides negative feedback.
17. ALWAYS `finalize` before delivering the completed model to the user.
18. ALWAYS render the STL file, not the .scad file — .scad rendering \
with include libraries may produce undef variables and broken output.
19. After any failure, attempt at least one fix before reporting to the user.
20. ALWAYS save the steering_content from init to your memory/steering file.
"""
