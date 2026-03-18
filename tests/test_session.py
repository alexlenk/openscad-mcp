"""Property tests for SessionState (Property 25: Reviewed libraries tracking round trip)."""

from hypothesis import given, settings, strategies as st

from openscad_mcp_server.services.session import SessionState

# Strategy: non-empty library name strings (stripped of null bytes for sanity)
library_names = st.text(min_size=1, max_size=50).filter(lambda s: s.strip() != "")


# Feature: openscad-mcp-server, Property 25: Reviewed libraries tracking round trip
@given(names=st.lists(library_names, min_size=0, max_size=30))
@settings(max_examples=100)
def test_reviewed_libraries_tracking_round_trip(names: list[str]) -> None:
    """For any sequence of mark_library_reviewed calls for distinct library names,
    the set of reviewed libraries should equal exactly those names.
    Marking the same library twice should not produce duplicates."""
    session = SessionState()

    for name in names:
        session.mark_library_reviewed(name)

    expected = set(names)

    # Every marked library is reported as reviewed
    for name in expected:
        assert session.is_library_reviewed(name)

    # The reviewed set matches exactly
    assert session.reviewed_libraries == expected


# Feature: openscad-mcp-server, Property 25 (supplemental): unmarked libraries are not reviewed
@given(
    marked=st.lists(library_names, min_size=1, max_size=20),
    unmarked=library_names,
)
@settings(max_examples=100)
def test_unmarked_library_is_not_reviewed(marked: list[str], unmarked: str) -> None:
    """A library that was never marked should not appear as reviewed."""
    # Only interesting when unmarked is not in the marked set
    if unmarked in marked:
        return

    session = SessionState()
    for name in marked:
        session.mark_library_reviewed(name)

    assert not session.is_library_reviewed(unmarked)
