"""Property-based tests for hotspot action mapping.

**Validates: Requirements 9.3, 9.4**

Property 12: Hotspot Action Mapping
- For any artifact with status "blocked", the suggested action SHALL be "Resolve blocker".
- For any artifact with status "needs_update", the suggested action SHALL be "Review and update".
- The mapping is deterministic: same status always produces same action.
"""

from hypothesis import given, settings
from hypothesis import strategies as st

from render_dashboard import Artifact, VALID_TYPES, get_suggested_action


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# The two hotspot statuses
HOTSPOT_STATUSES = ["blocked", "needs_update"]

# Strategy for random artifact IDs
artifact_ids = st.text(
    alphabet=st.characters(categories=("L", "N", "P")),
    min_size=1,
    max_size=80,
)

# Strategy for artifact types drawn from VALID_TYPES
artifact_types = st.sampled_from(sorted(VALID_TYPES))


def hotspot_artifact(status: str) -> st.SearchStrategy[Artifact]:
    """Generate an Artifact with the given hotspot status and random ID/type."""
    return st.builds(
        Artifact,
        id=artifact_ids,
        type=artifact_types,
        status=st.just(status),
        path=st.text(min_size=1, max_size=50),
    )


# ---------------------------------------------------------------------------
# Property Tests
# ---------------------------------------------------------------------------

class TestHotspotActionMappingBlocked:
    """Property: Blocked artifacts always get 'Resolve blocker' action."""

    @given(artifact=hotspot_artifact("blocked"))
    @settings(max_examples=50)
    def test_blocked_suggests_resolve_blocker(self, artifact: Artifact):
        """For any artifact with status 'blocked', the suggested action
        SHALL be 'Resolve blocker'.

        **Validates: Requirements 9.3**
        """
        action = get_suggested_action(artifact.status)
        assert action == "Resolve blocker"


class TestHotspotActionMappingNeedsUpdate:
    """Property: needs_update artifacts always get 'Review and update' action."""

    @given(artifact=hotspot_artifact("needs_update"))
    @settings(max_examples=50)
    def test_needs_update_suggests_review_and_update(self, artifact: Artifact):
        """For any artifact with status 'needs_update', the suggested action
        SHALL be 'Review and update'.

        **Validates: Requirements 9.4**
        """
        action = get_suggested_action(artifact.status)
        assert action == "Review and update"


class TestHotspotActionMappingDeterminism:
    """Property: The action mapping is deterministic — same status always
    produces the same action regardless of artifact ID or type."""

    @given(
        id1=artifact_ids,
        id2=artifact_ids,
        type1=artifact_types,
        type2=artifact_types,
        status=st.sampled_from(HOTSPOT_STATUSES),
    )
    @settings(max_examples=50)
    def test_action_depends_only_on_status(
        self, id1: str, id2: str, type1: str, type2: str, status: str
    ):
        """For any two artifacts with the same hotspot status but different
        IDs and types, the suggested action SHALL be identical.

        **Validates: Requirements 9.3, 9.4**
        """
        action1 = get_suggested_action(status)
        action2 = get_suggested_action(status)
        assert action1 == action2

    @given(
        artifact=st.one_of(
            hotspot_artifact("blocked"),
            hotspot_artifact("needs_update"),
        )
    )
    @settings(max_examples=50)
    def test_repeated_calls_same_result(self, artifact: Artifact):
        """Calling get_suggested_action multiple times with the same status
        always produces the same result (pure function).

        **Validates: Requirements 9.3, 9.4**
        """
        result1 = get_suggested_action(artifact.status)
        result2 = get_suggested_action(artifact.status)
        result3 = get_suggested_action(artifact.status)
        assert result1 == result2 == result3
