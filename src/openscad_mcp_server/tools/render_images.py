"""Render-images tool — multi-angle rendering returning MCP ImageContent blocks."""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass, field
from pathlib import Path

from openscad_mcp_server.models import CAMERA_ANGLES, CameraAngle
from openscad_mcp_server.services.container import ContainerError, ContainerManager
from openscad_mcp_server.services.file_manager import FileManager

RENDER_IMAGE = "openscad/openscad:latest"
CONTAINER_WORK_DIR = "/work"
CONTAINER_LIB_DIR = "/work/libraries"
IMG_SIZE = "1024,1024"


@dataclass
class RenderFailure:
    """A single angle that failed to render."""

    label: str
    error: str


@dataclass
class RenderResult:
    """Result of a render-images invocation.

    *text_content* holds camera metadata as a JSON string.
    *image_contents* holds (label, base64_png) pairs for successful renders.
    *failures* lists angles that could not be rendered.
    """

    text_content: str
    image_contents: list[tuple[str, str]] = field(default_factory=list)
    failures: list[RenderFailure] = field(default_factory=list)


def build_render_command(angle: CameraAngle, input_file: str, output_png: str, timeout: int = 45) -> list[str]:
    """Build the container command for rendering a single angle.

    Wraps OpenSCAD in ``xvfb-run`` because PNG export requires OpenGL/X11,
    which isn't available in headless containers without a virtual framebuffer.
    """
    rot = angle.rotation
    camera_arg = f"0,0,0,{rot[0]},{rot[1]},{rot[2]},0"
    openscad_cmd = (
        f"timeout {timeout} xvfb-run --auto-servernum "
        f'--server-args="-screen 0 1024x1024x24" '
        f"openscad "
        f"--camera={camera_arg} "
        f"--imgsize={IMG_SIZE} "
        f"--autocenter --viewall --render "
        f"--projection=p "
        f"--colorscheme Cornfield "
        f"-o {output_png} "
        f"{input_file}"
    )
    return ["bash", "-c", openscad_cmd]


SCAD_WRAPPER_TEMPLATE = 'import("{stl_file}");\n'


def _ensure_scad_input(stl_file: str, file_manager: FileManager) -> str:
    """If the input is an STL, create a wrapper .scad file and return its container path.

    Returns the container path to use as the OpenSCAD input file.
    """
    stl_name = Path(stl_file).name
    if not stl_name.lower().endswith(".stl"):
        # Already a .scad file, use directly
        return f"{CONTAINER_WORK_DIR}/{stl_name}"

    wrapper_name = "_render_wrapper.scad"
    wrapper_local = file_manager.working_dir / wrapper_name
    wrapper_local.write_text(SCAD_WRAPPER_TEMPLATE.format(stl_file=stl_name))
    return f"{CONTAINER_WORK_DIR}/{wrapper_name}"


async def run_render_images(
    stl_file: str,
    container_manager: ContainerManager,
    file_manager: FileManager,
    timeout: int = 300,
    angles: list[str] | None = None,
) -> RenderResult:
    """Render an STL from camera angles and return MCP-compatible content blocks.

    Parameters
    ----------
    stl_file:
        Filename (relative to the working area) of the ``.stl`` or ``.scad`` file.
    container_manager:
        Configured container manager for the current runtime.
    file_manager:
        File manager providing working-area and library paths.
    timeout:
        Maximum seconds per render container invocation.
    angles:
        Optional list of angle labels to render. If ``None``, renders all 8.

    Returns
    -------
    RenderResult with camera metadata, base64 image data, and any failures.
    """
    file_manager.clear_renders()

    mounts: dict[str, str] = {
        str(file_manager.working_dir): CONTAINER_WORK_DIR,
    }
    if file_manager.libraries_dir.exists():
        mounts[str(file_manager.libraries_dir)] = CONTAINER_LIB_DIR

    stl_container_path = _ensure_scad_input(stl_file, file_manager)
    renders_container_dir = f"{CONTAINER_WORK_DIR}/renders"

    # Filter angles if a subset was requested
    if angles is not None:
        requested = {a.lower() for a in angles}
        selected_angles = [a for a in CAMERA_ANGLES if a.label.lower() in requested]
        unknown = requested - {a.label.lower() for a in selected_angles}
        if unknown:
            valid = [a.label for a in CAMERA_ANGLES]
            return RenderResult(
                text_content=json.dumps({"error": f"Unknown angles: {sorted(unknown)}. Valid: {valid}"}),
                failures=[RenderFailure(label=u, error="Unknown angle label") for u in sorted(unknown)],
            )
    else:
        selected_angles = list(CAMERA_ANGLES)

    image_contents: list[tuple[str, str]] = []
    failures: list[RenderFailure] = []

    for angle in selected_angles:
        output_png = f"{renders_container_dir}/{angle.label}.png"
        command = build_render_command(angle, stl_container_path, output_png)

        try:
            result = await container_manager.run(
                image=RENDER_IMAGE,
                command=command,
                mounts=mounts,
                timeout=timeout,
            )
        except ContainerError as exc:
            failures.append(RenderFailure(label=angle.label, error=str(exc)))
            continue

        if result.exit_code != 0:
            failures.append(RenderFailure(
                label=angle.label,
                error=result.stderr or result.stdout or "Unknown render error",
            ))
            continue

        # Read the rendered PNG from disk
        local_png = file_manager.renders_dir / f"{angle.label}.png"
        if not local_png.exists():
            failures.append(RenderFailure(
                label=angle.label,
                error=f"Render completed but output file not found: {local_png}",
            ))
            continue

        b64_data = base64.b64encode(local_png.read_bytes()).decode("utf-8")
        image_contents.append((angle.label, b64_data))

    # Build camera metadata text block
    metadata = {
        "angles": [
            {
                "label": angle.label,
                "camera_position": list(angle.position),
                "camera_rotation": list(angle.rotation),
            }
            for angle in selected_angles
        ],
    }
    if failures:
        metadata["failed_angles"] = [
            {"label": f.label, "error": f.error} for f in failures
        ]

    return RenderResult(
        text_content=json.dumps(metadata),
        image_contents=image_contents,
        failures=failures,
    )
