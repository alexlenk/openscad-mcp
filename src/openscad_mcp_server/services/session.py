"""Per-session state tracking for the OpenSCAD MCP Server."""

from __future__ import annotations

from pathlib import Path


class SessionState:
    """Tracks reviewed libraries, confidence scores, and runtime config for a session."""

    def __init__(self) -> None:
        self.reviewed_libraries: set[str] = set()
        self.latest_confidence_score: float | None = None
        self.container_runtime: str | None = None
        self.container_executable: str | None = None
        self.working_dir: Path | None = None

    def mark_library_reviewed(self, name: str) -> None:
        """Record that a library's source has been read."""
        self.reviewed_libraries.add(name)

    def is_library_reviewed(self, name: str) -> bool:
        """Check whether a library has been reviewed this session."""
        return name in self.reviewed_libraries

    def set_confidence(self, score: float) -> None:
        """Store the latest overall confidence score."""
        self.latest_confidence_score = score
