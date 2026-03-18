"""Property tests for version-tag matching (Property 21: Version-tag matching)."""

from hypothesis import given, settings, strategies as st

# Strategy: version strings like "X.Y.Z" with reasonable component ranges
version_component = st.integers(min_value=0, max_value=999)
version_strings = st.builds(
    lambda major, minor, patch: f"{major}.{minor}.{patch}",
    version_component,
    version_component,
    version_component,
)


def version_matches_tag(version: str, tag: str) -> bool:
    """Check if a version string matches a git tag. Tag must equal 'v' + version."""
    return tag == f"v{version}"


# Feature: openscad-mcp-server, Property 21: Version-tag matching
@given(version=version_strings)
@settings(max_examples=200)
def test_version_tag_matching_valid(version: str) -> None:
    """For any version string, 'v' + version should be the only matching tag."""
    tag = f"v{version}"
    assert version_matches_tag(version, tag)


@given(version=version_strings)
@settings(max_examples=200)
def test_version_tag_mismatch_without_prefix(version: str) -> None:
    """A tag without the 'v' prefix should never match."""
    assert not version_matches_tag(version, version)


@given(v1=version_strings, v2=version_strings)
@settings(max_examples=200)
def test_version_tag_mismatch_different_versions(v1: str, v2: str) -> None:
    """Two different versions should not cross-match tags."""
    tag = f"v{v2}"
    if v1 != v2:
        assert not version_matches_tag(v1, tag)


@given(version=version_strings, junk=st.text(min_size=1, max_size=10))
@settings(max_examples=200)
def test_version_tag_rejects_extra_content(version: str, junk: str) -> None:
    """A tag with extra content appended should not match."""
    tag = f"v{version}{junk}"
    # Only matches if junk is empty, which min_size=1 prevents
    assert not version_matches_tag(version, tag)
