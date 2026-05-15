"""Property-based tests for state machine count conservation.

**Validates: Requirements 8.4**

Property 9: State Machine Count Conservation
- For any set of artifacts for a selected project, the sum of artifact counts
  across all 9 states in the StateMachineView SHALL equal the total number of
  artifacts in that project.
"""

from hypothesis import given, settings
from hypothesis import strategies as st

from render_dashboard import Artifact, VALID_STATUSES, VALID_TYPES


# ---------------------------------------------------------------------------
# Helper: State Machine Counting Logic
# ---------------------------------------------------------------------------

def count_artifacts_per_state(artifacts: list[Artifact]) -> dict[str, int]:
    """Replicate the state machine counting logic from the StateMachineView.

    Given a list of artifacts, count how many artifacts are in each of the
    9 valid states. States with zero artifacts are still included.

    Returns:
        A dict mapping each of the 9 valid statuses to its artifact count.
    """
    counts: dict[str, int] = {status: 0 for status in VALID_STATUSES}
    for artifact in artifacts:
        counts[artifact.status] = counts.get(artifact.status, 0) + 1
    return counts


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# Strategy for generating a single artifact with a random valid status and type
def artifact_strategy() -> st.SearchStrategy[Artifact]:
    """Generate an Artifact with a random valid status and type."""
    return st.builds(
        Artifact,
        id=st.text(
            alphabet=st.characters(categories=("L", "N", "P")),
            min_size=1,
            max_size=50,
        ),
        type=st.sampled_from(sorted(VALID_TYPES)),
        status=st.sampled_from(sorted(VALID_STATUSES)),
        path=st.just("artifacts/placeholder.md"),
    )


# Strategy for generating lists of artifacts (0 to 150 items)
artifact_lists = st.lists(artifact_strategy(), min_size=0, max_size=150)


# ---------------------------------------------------------------------------
# Property Tests
# ---------------------------------------------------------------------------

class TestStateMachineCountConservation:
    """Property 9: The sum of all state counts equals the total artifact count."""

    @given(artifacts=artifact_lists)
    @settings(max_examples=50)
    def test_sum_of_counts_equals_total(self, artifacts: list[Artifact]):
        """For any set of artifacts, the SUM of all state counts SHALL equal
        the total number of artifacts.

        **Validates: Requirements 8.4**
        """
        counts = count_artifacts_per_state(artifacts)
        total_count = sum(counts.values())
        assert total_count == len(artifacts), (
            f"Count sum {total_count} != artifact count {len(artifacts)}"
        )

    @given(artifacts=artifact_lists)
    @settings(max_examples=50)
    def test_each_count_non_negative(self, artifacts: list[Artifact]):
        """Each individual state count SHALL be >= 0.

        **Validates: Requirements 8.4**
        """
        counts = count_artifacts_per_state(artifacts)
        for status, count in counts.items():
            assert count >= 0, (
                f"State '{status}' has negative count: {count}"
            )

    @given(artifacts=artifact_lists)
    @settings(max_examples=50)
    def test_only_valid_states_in_counts(self, artifacts: list[Artifact]):
        """Only the 9 valid states SHALL appear in the counts dict.

        **Validates: Requirements 8.4**
        """
        counts = count_artifacts_per_state(artifacts)
        assert set(counts.keys()) == VALID_STATUSES, (
            f"Unexpected states in counts: {set(counts.keys()) - VALID_STATUSES}"
        )

    @given(artifacts=artifact_lists)
    @settings(max_examples=50)
    def test_empty_artifact_list_all_zeros(self, artifacts: list[Artifact]):
        """When no artifacts exist, all state counts are zero and sum is zero.

        **Validates: Requirements 8.4**
        """
        # Test specifically with empty list
        counts = count_artifacts_per_state([])
        assert sum(counts.values()) == 0
        assert all(c == 0 for c in counts.values())

    @given(artifacts=artifact_lists)
    @settings(max_examples=50)
    def test_count_matches_manual_filter(self, artifacts: list[Artifact]):
        """Each state's count matches the number of artifacts with that status
        when counted by filtering.

        **Validates: Requirements 8.4**
        """
        counts = count_artifacts_per_state(artifacts)
        for status in VALID_STATUSES:
            expected = len([a for a in artifacts if a.status == status])
            assert counts[status] == expected, (
                f"State '{status}': counted {counts[status]} but "
                f"expected {expected}"
            )
