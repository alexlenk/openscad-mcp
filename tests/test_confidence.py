"""Property tests for confidence score computation (Property 22: Overall confidence is minimum of per-angle scores)."""

from hypothesis import given, settings, strategies as st

# Strategy: exactly 8 finite floats in [0.0, 1.0] representing per-angle scores
per_angle_scores = st.lists(
    st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
    min_size=8,
    max_size=8,
)


def compute_overall_confidence(per_angle: list[float]) -> float:
    """Overall confidence is the minimum of all per-angle scores."""
    return min(per_angle)


# Feature: openscad-mcp-server, Property 22: Overall confidence is minimum of per-angle scores
@given(scores=per_angle_scores)
@settings(max_examples=100)
def test_overall_confidence_is_minimum_of_per_angle_scores(scores: list[float]) -> None:
    """For any list of 8 per-angle confidence scores (each between 0.0 and 1.0),
    the overall confidence score should equal the minimum value in the list."""
    overall = compute_overall_confidence(scores)

    assert overall == min(scores)
    # Overall should be <= every individual score
    for s in scores:
        assert overall <= s


# Feature: openscad-mcp-server, Property 22 (supplemental): uniform scores
@given(score=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False))
@settings(max_examples=100)
def test_uniform_scores_yield_same_overall(score: float) -> None:
    """When all 8 angles have the same score, overall equals that score."""
    scores = [score] * 8
    assert compute_overall_confidence(scores) == score
