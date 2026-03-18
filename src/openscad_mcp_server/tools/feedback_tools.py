"""Feedback tools — submit feedback and list feedback records."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from openscad_mcp_server.models import FeedbackIndexEntry, FeedbackRecord
from openscad_mcp_server.services.feedback_service import FeedbackService
from openscad_mcp_server.services.session import SessionState


# ------------------------------------------------------------------
# Result types
# ------------------------------------------------------------------

@dataclass
class SubmitFeedbackResult:
    """Result from the submit-feedback tool."""

    feedback_id: str
    confidence_disagreement: bool


@dataclass
class ListFeedbackResult:
    """Result from the list-feedback tool."""

    records: list[FeedbackIndexEntry]


# ------------------------------------------------------------------
# Tool implementations
# ------------------------------------------------------------------

def run_submit_feedback(
    critique: str,
    feedback_service: FeedbackService,
    session: SessionState,
    working_area: Path,
    root_cause_category: str | None = None,
) -> SubmitFeedbackResult:
    """Submit user feedback, snapshot artifacts, and record confidence data.

    Reads the latest confidence score from the session and passes it to the
    feedback service, which handles disagreement flag logic (score > 0.5
    means the LLM thought the model was correct but the user disagreed).

    Delegates to :meth:`FeedbackService.submit`.
    """
    record = feedback_service.submit(
        critique=critique,
        root_cause=root_cause_category,
        working_area=working_area,
        confidence_score=session.latest_confidence_score,
    )
    return SubmitFeedbackResult(
        feedback_id=record.id,
        confidence_disagreement=record.confidence_disagreement,
    )


def run_list_feedback(feedback_service: FeedbackService) -> ListFeedbackResult:
    """Return all feedback records from the index.

    Delegates to :meth:`FeedbackService.list_records`.
    """
    records = feedback_service.list_records()
    return ListFeedbackResult(records=records)
