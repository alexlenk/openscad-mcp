"""Data models for the OpenSCAD MCP Server."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ContainerResult:
    """Result of a container execution."""

    exit_code: int
    stdout: str
    stderr: str


@dataclass
class LibraryCatalogEntry:
    """An entry from the OpenSCAD library catalog."""

    name: str
    description: str
    source_url: str
    category: str | None = None
    docs_url: str | None = None
    license: str | None = None


@dataclass
class ModuleSignature:
    """Signature of an OpenSCAD module extracted from source."""

    name: str
    parameters: list[dict] = field(default_factory=list)


@dataclass
class LibrarySource:
    """Source code and metadata for a fetched OpenSCAD library."""

    name: str
    source_code: str
    modules: list[ModuleSignature] = field(default_factory=list)
    coordinate_system: str | None = None
    units: str | None = None


@dataclass
class CameraAngle:
    """A predefined camera viewing angle for rendering."""

    label: str
    position: tuple[float, float, float]
    rotation: tuple[float, float, float]


@dataclass
class InspectionImage:
    """A rendered inspection image from a specific viewing angle."""

    angle: str
    base64_png: str
    camera_position: tuple[float, float, float]
    camera_rotation: tuple[float, float, float]


@dataclass
class FeedbackRecord:
    """A user feedback record with associated artifacts."""

    id: str
    timestamp: str
    critique: str
    root_cause_category: str | None
    root_cause_analysis: str
    confidence_score: float | None
    confidence_disagreement: bool
    artifacts_dir: str


@dataclass
class FeedbackIndexEntry:
    """Summary entry for the feedback index file."""

    id: str
    timestamp: str
    critique_summary: str
    root_cause_category: str | None
    confidence_score: float | None
    confidence_disagreement: bool


# Predefined 8 camera angles for multi-angle rendering.
CAMERA_ANGLES: list[CameraAngle] = [
    CameraAngle("front", (0, -100, 0), (90, 0, 0)),
    CameraAngle("back", (0, 100, 0), (90, 0, 180)),
    CameraAngle("left", (-100, 0, 0), (90, 0, 270)),
    CameraAngle("right", (100, 0, 0), (90, 0, 90)),
    CameraAngle("top", (0, 0, 100), (0, 0, 0)),
    CameraAngle("bottom", (0, 0, -100), (180, 0, 0)),
    CameraAngle("front-right-top-iso", (80, -80, 80), (55, 0, 45)),
    CameraAngle("back-left-top-iso", (-80, 80, 80), (55, 0, 225)),
]
