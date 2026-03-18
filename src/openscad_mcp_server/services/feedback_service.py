"""Feedback store management: submit records, copy artifacts, maintain index."""

from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

from openscad_mcp_server.models import FeedbackIndexEntry, FeedbackRecord


class FeedbackService:
    """Manages the feedback store and its JSON index.

    Each feedback submission creates a timestamped subdirectory containing a
    ``record.json`` and copies of the current working-area artifacts (code,
    STL, renders).  A top-level ``feedback-index.json`` tracks all records.
    """

    INDEX_FILENAME = "feedback-index.json"

    def __init__(self, feedback_dir: Path) -> None:
        self.feedback_dir = feedback_dir
        self.feedback_dir.mkdir(parents=True, exist_ok=True)
        self._index_path = feedback_dir / self.INDEX_FILENAME

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def submit(
        self,
        critique: str,
        root_cause: str | None,
        working_area: Path,
        confidence_score: float | None,
    ) -> FeedbackRecord:
        """Create a feedback record, copy working-area artifacts, update index.

        Parameters
        ----------
        critique:
            Free-text user critique.
        root_cause:
            Optional root-cause category string.
        working_area:
            Path to the current working directory whose artifacts are snapshotted.
        confidence_score:
            The most recent overall confidence score (may be ``None``).

        Returns
        -------
        FeedbackRecord
            The newly created record.
        """
        now = datetime.now(timezone.utc)
        record_id = now.strftime("%Y%m%dT%H%M%S")
        timestamp = now.isoformat()

        confidence_disagreement = (
            confidence_score is not None and confidence_score > 0.5
        )

        root_cause_analysis = self._generate_root_cause_analysis(critique, root_cause)

        record_dir = self.feedback_dir / record_id
        record_dir.mkdir(parents=True, exist_ok=True)

        # Copy working-area artifacts into the record directory.
        self._copy_artifacts(working_area, record_dir)

        record = FeedbackRecord(
            id=record_id,
            timestamp=timestamp,
            critique=critique,
            root_cause_category=root_cause,
            root_cause_analysis=root_cause_analysis,
            confidence_score=confidence_score,
            confidence_disagreement=confidence_disagreement,
            artifacts_dir=str(record_dir),
        )

        # Persist the full record.
        (record_dir / "record.json").write_text(
            json.dumps(self._record_to_dict(record), indent=2), encoding="utf-8"
        )

        # Update the index.
        self._append_index(record)

        return record

    def list_records(self) -> list[FeedbackIndexEntry]:
        """Return all feedback index entries."""
        index = self._read_index()
        return [
            FeedbackIndexEntry(
                id=entry["id"],
                timestamp=entry["timestamp"],
                critique_summary=entry["critique_summary"],
                root_cause_category=entry.get("root_cause_category"),
                confidence_score=entry.get("confidence_score"),
                confidence_disagreement=entry.get("confidence_disagreement", False),
            )
            for entry in index
        ]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _generate_root_cause_analysis(critique: str, root_cause: str | None) -> str:
        """Produce a root-cause analysis string from the critique and category."""
        if root_cause:
            return f"Root cause category: {root_cause}. User critique: {critique}"
        return f"User critique: {critique}"

    @staticmethod
    def _copy_artifacts(working_area: Path, dest: Path) -> None:
        """Copy code, STL, and render files from *working_area* into *dest*."""
        for pattern in ("*.scad", "*.stl"):
            for src_file in working_area.glob(pattern):
                shutil.copy2(src_file, dest / src_file.name)

        renders_src = working_area / "renders"
        if renders_src.is_dir():
            renders_dest = dest / "renders"
            if renders_dest.exists():
                shutil.rmtree(renders_dest)
            shutil.copytree(renders_src, renders_dest)

    def _read_index(self) -> list[dict]:
        """Read the JSON index file, returning an empty list if absent."""
        if not self._index_path.exists():
            return []
        return json.loads(self._index_path.read_text(encoding="utf-8"))

    def _write_index(self, entries: list[dict]) -> None:
        """Overwrite the JSON index file."""
        self._index_path.write_text(
            json.dumps(entries, indent=2), encoding="utf-8"
        )

    def _append_index(self, record: FeedbackRecord) -> None:
        """Add a summary entry for *record* to the index."""
        entries = self._read_index()
        entries.append(
            {
                "id": record.id,
                "timestamp": record.timestamp,
                "critique_summary": record.critique[:200],
                "root_cause_category": record.root_cause_category,
                "confidence_score": record.confidence_score,
                "confidence_disagreement": record.confidence_disagreement,
            }
        )
        self._write_index(entries)

    @staticmethod
    def _record_to_dict(record: FeedbackRecord) -> dict:
        """Serialize a FeedbackRecord to a plain dict for JSON storage."""
        return {
            "id": record.id,
            "timestamp": record.timestamp,
            "critique": record.critique,
            "root_cause_category": record.root_cause_category,
            "root_cause_analysis": record.root_cause_analysis,
            "confidence_score": record.confidence_score,
            "confidence_disagreement": record.confidence_disagreement,
            "artifacts_dir": record.artifacts_dir,
        }
