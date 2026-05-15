"""Property-based tests for hotspot identification completeness.

**Validates: Requirements 9.1**

Property 11: Hotspot Identification Completeness
- For any set of artifacts, the hotspot list SHALL contain EXACTLY those
  artifacts whose status is "blocked" or "needs_update" — no more, no less.
- All "blocked" artifacts SHALL appear before all "needs_update" artifacts.
- Within each group, artifacts SHALL be sorted alphabetically by ID.
- No artifact with a status other than "blocked" or "needs_update" SHALL
  appear in the hotspot list.
"""

from hypothesis import given, settings
from hypothesis import strategies as st

from render_dashboard import Artifact, VALID_STATUSES, VALID_TYPES, identify_hotspots


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# Strategy for random artifact IDs (letters, digits, punctuation)
artifact_ids = st.text(
    alphabet=st.characters(categories=("L", "N", "P")),
    min_size=1,
    max_size=80,
)

# Strategy for artifact types drawn from VALID_TYPES
artifact_types = st.sampled_from(sorted(VALID_TYPES))

# Strategy for any valid artifact status
artifact_statuses = st.sampled_from(sorted(VALID_STATUSES))

# Non-hotspot statuses (everything except blocked and needs_update)
NON_HOTSPOT_STATUSES = sorted(VALID_STATUSES - {"blocked", "needs_update"})
non_hotspot_statuses = st.sampled_from(NON_HOTSPOT_STATUSES)


def artifact_strategy(status: st.SearchStrategy[str] | None = None) -> st.SearchStrategy[Artifact]:
    """Generate an Artifact with a given or random status."""
    status_strat = status if status is not None else artifact_statuses
    return st.builds(
        Artifact,
        id=artifact_ids,
        type=artifact_types,
        status=status_strat,
        path=st.text(min_size=1, max_size=50),
    )


# Strategy for a list of artifacts with mixed statuses
artifact_lists = st.lists(artifact_strategy(), min_size=0, max_size=30)


# ---------------------------------------------------------------------------
# Property Tests
# ---------------------------------------------------------------------------

class TestHotspotIdentificationCompleteness:
    """Property 11: The hotspot list contains exactly those artifacts whose
    status is 'blocked' or 'needs_update'."""

    @given(artifacts=artifact_lists)
    @settings(max_examples=50)
    def test_contains_all_blocked_and_needs_update(self, artifacts: list[Artifact]):
        """For any set of artifacts, the hotspot list SHALL contain EXACTLY
        those artifacts whose status is 'blocked' or 'needs_update' — no more,
        no less.

        **Validates: Requirements 9.1**
        """
        hotspots = identify_hotspots(artifacts)
        expected_ids = {
            a.id for a in artifacts if a.status in ("blocked", "needs_update")
        }
        actual_ids = {a.id for a in hotspots}
        # Every hotspot artifact must be in the result
        assert expected_ids == actual_ids

    @given(artifacts=artifact_lists)
    @settings(max_examples=50)
    def test_hotspot_count_matches_expected(self, artifacts: list[Artifact]):
        """The number of hotspots returned must equal the number of artifacts
        with status 'blocked' or 'needs_update'.

        **Validates: Requirements 9.1**
        """
        hotspots = identify_hotspots(artifacts)
        expected_count = sum(
            1 for a in artifacts if a.status in ("blocked", "needs_update")
        )
        assert len(hotspots) == expected_count


class TestHotspotOrdering:
    """Property 11: Blocked artifacts appear before needs_update artifacts,
    each group sorted alphabetically by ID."""

    @given(artifacts=artifact_lists)
    @settings(max_examples=50)
    def test_blocked_before_needs_update(self, artifacts: list[Artifact]):
        """All 'blocked' artifacts SHALL appear before all 'needs_update'
        artifacts in the hotspot list.

        **Validates: Requirements 9.1**
        """
        hotspots = identify_hotspots(artifacts)
        saw_needs_update = False
        for h in hotspots:
            if h.status == "needs_update":
                saw_needs_update = True
            elif h.status == "blocked":
                # If we already saw a needs_update, ordering is violated
                assert not saw_needs_update, (
                    f"Blocked artifact '{h.id}' appeared after a needs_update artifact"
                )

    @given(artifacts=artifact_lists)
    @settings(max_examples=50)
    def test_alphabetical_within_blocked_group(self, artifacts: list[Artifact]):
        """Within the 'blocked' group, artifacts SHALL be sorted
        alphabetically by ID.

        **Validates: Requirements 9.1**
        """
        hotspots = identify_hotspots(artifacts)
        blocked_ids = [h.id for h in hotspots if h.status == "blocked"]
        assert blocked_ids == sorted(blocked_ids)

    @given(artifacts=artifact_lists)
    @settings(max_examples=50)
    def test_alphabetical_within_needs_update_group(self, artifacts: list[Artifact]):
        """Within the 'needs_update' group, artifacts SHALL be sorted
        alphabetically by ID.

        **Validates: Requirements 9.1**
        """
        hotspots = identify_hotspots(artifacts)
        needs_update_ids = [h.id for h in hotspots if h.status == "needs_update"]
        assert needs_update_ids == sorted(needs_update_ids)


class TestHotspotExclusion:
    """Property 11: No artifact with a status other than 'blocked' or
    'needs_update' shall appear in the hotspot list."""

    @given(
        artifacts=st.lists(
            artifact_strategy(status=non_hotspot_statuses),
            min_size=1,
            max_size=20,
        )
    )
    @settings(max_examples=50)
    def test_non_hotspot_statuses_excluded(self, artifacts: list[Artifact]):
        """When all artifacts have non-hotspot statuses, the hotspot list
        SHALL be empty.

        **Validates: Requirements 9.1**
        """
        hotspots = identify_hotspots(artifacts)
        assert hotspots == []

    @given(artifacts=artifact_lists)
    @settings(max_examples=50)
    def test_no_non_hotspot_in_result(self, artifacts: list[Artifact]):
        """No artifact with a status other than 'blocked' or 'needs_update'
        SHALL appear in the hotspot list.

        **Validates: Requirements 9.1**
        """
        hotspots = identify_hotspots(artifacts)
        for h in hotspots:
            assert h.status in ("blocked", "needs_update"), (
                f"Artifact '{h.id}' with status '{h.status}' should not be a hotspot"
            )
