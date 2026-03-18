"""Property tests for FeedbackService (Properties 18, 19, 20)."""

from __future__ import annotations

import json
import tempfile
from datetime import datetime
from pathlib import Path

from hypothesis import given, settings, strategies as st

from openscad_mcp_server.services.feedback_service import FeedbackService

# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

_critique = st.text(min_size=1, max_size=300)
_root_cause = st.one_of(st.none(), st.text(min_size=1, max_size=80))
_confidence = st.one_of(
    st.none(),
    st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
)


def _populate_working_area(working: Path) -> None:
    """Create minimal artifacts in a working area for snapshot testing."""
    working.mkdir(parents=True, exist_ok=True)
    (working / "model.scad").write_text("cube([1,1,1]);", encoding="utf-8")
    (working / "model.stl").write_bytes(b"solid cube endsolid cube")
    renders = working / "renders"
    renders.mkdir(exist_ok=True)
    (renders / "front.png").write_bytes(b"PNG-front")
    (renders / "back.png").write_bytes(b"PNG-back")


# ---------------------------------------------------------------------------
# Property 18: Feedback record completeness
# ---------------------------------------------------------------------------


# Feature: openscad-mcp-server, Property 18: Feedback record completeness
@given(critique=_critique, root_cause=_root_cause, confidence=_confidence)
@settings(max_examples=100)
def test_feedback_record_completeness(
    critique: str,
    root_cause: str | None,
    confidence: float | None,
) -> None:
    """For any feedback submission the created record contains the critique,
    a valid ISO 8601 timestamp, a root cause analysis, the confidence score,
    and a subdirectory with copies of working-area artifacts."""
    with tempfile.TemporaryDirectory() as td:
        base = Path(td)
        feedback_dir = base / "feedback"
        working = base / "working"
        _populate_working_area(working)

        svc = FeedbackService(feedback_dir)
        record = svc.submit(critique, root_cause, working, confidence)

        # Critique preserved
        assert record.critique == critique

        # Valid ISO 8601 timestamp
        datetime.fromisoformat(record.timestamp)

        # Root cause analysis is non-empty
        assert len(record.root_cause_analysis) > 0

        # Confidence score stored
        assert record.confidence_score == confidence

        # Artifacts directory exists and contains copies
        artifacts = Path(record.artifacts_dir)
        assert artifacts.is_dir()
        assert (artifacts / "model.scad").exists()
        assert (artifacts / "model.stl").exists()
        assert (artifacts / "renders" / "front.png").exists()
        assert (artifacts / "renders" / "back.png").exists()

        # record.json persisted
        record_json = json.loads(
            (artifacts / "record.json").read_text(encoding="utf-8")
        )
        assert record_json["critique"] == critique
        assert record_json["confidence_score"] == confidence


# ---------------------------------------------------------------------------
# Property 19: Feedback index round trip
# ---------------------------------------------------------------------------


# Feature: openscad-mcp-server, Property 19: Feedback index round trip
@given(
    n=st.integers(min_value=1, max_value=10),
    critiques=st.lists(_critique, min_size=10, max_size=10),
    root_causes=st.lists(_root_cause, min_size=10, max_size=10),
    scores=st.lists(_confidence, min_size=10, max_size=10),
)
@settings(max_examples=50)
def test_feedback_index_round_trip(
    n: int,
    critiques: list[str],
    root_causes: list[str | None],
    scores: list[float | None],
) -> None:
    """For any sequence of N submissions the index contains exactly N entries
    and list_records returns all N with correct fields."""
    with tempfile.TemporaryDirectory() as td:
        base = Path(td)
        feedback_dir = base / "feedback"
        working = base / "working"
        _populate_working_area(working)

        svc = FeedbackService(feedback_dir)

        submitted = []
        for i in range(n):
            rec = svc.submit(critiques[i], root_causes[i], working, scores[i])
            submitted.append(rec)

        entries = svc.list_records()
        assert len(entries) == n

        # Verify the raw JSON index also has N entries
        raw = json.loads(
            (feedback_dir / FeedbackService.INDEX_FILENAME).read_text(encoding="utf-8")
        )
        assert len(raw) == n

        for idx, entry in enumerate(entries):
            rec = submitted[idx]
            assert entry.id == rec.id
            assert entry.timestamp == rec.timestamp
            assert entry.critique_summary == rec.critique[:200]
            assert entry.root_cause_category == rec.root_cause_category
            assert entry.confidence_score == rec.confidence_score
            assert entry.confidence_disagreement == rec.confidence_disagreement


# ---------------------------------------------------------------------------
# Property 20: Confidence disagreement flag logic
# ---------------------------------------------------------------------------


# Feature: openscad-mcp-server, Property 20: Confidence disagreement flag logic
@given(confidence=_confidence)
@settings(max_examples=100)
def test_confidence_disagreement_flag(confidence: float | None) -> None:
    """If the most recent confidence score is above 0.5 the disagreement flag
    is True. If the score is 0.5 or below (or absent) the flag is False."""
    with tempfile.TemporaryDirectory() as td:
        base = Path(td)
        feedback_dir = base / "feedback"
        working = base / "working"
        _populate_working_area(working)

        svc = FeedbackService(feedback_dir)
        record = svc.submit("test critique", None, working, confidence)

        if confidence is not None and confidence > 0.5:
            assert record.confidence_disagreement is True
        else:
            assert record.confidence_disagreement is False
