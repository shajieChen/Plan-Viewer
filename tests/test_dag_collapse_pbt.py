"""Property-based tests for DAG collapse behavior.

**Validates: Requirements 6.3**

Property 8: DAG Collapse Produces Placeholder
- For any collapsed group, the generated DAG node list SHALL contain exactly
  ONE placeholder node for that group.
- For any collapsed group, the generated DAG node list SHALL NOT contain
  individual artifact nodes belonging to that group.
- For any expanded group, the generated DAG node list SHALL contain all
  individual artifact nodes and NO placeholder.
"""

from hypothesis import given, settings, HealthCheck
from hypothesis import strategies as st

from render_dashboard import Artifact, VALID_TYPES, VALID_STATUSES


# ---------------------------------------------------------------------------
# Helper: DAG collapse logic (replicates browser-side React component logic)
# ---------------------------------------------------------------------------

def compute_dag_nodes(
    artifacts: list[Artifact],
    collapsed_groups: set[str],
) -> list[str]:
    """Compute the node list for the DAG view given artifacts and collapsed groups.

    For collapsed groups: produce exactly one placeholder node "{GroupName}_collapsed".
    For expanded groups: produce individual artifact nodes (artifact.id).

    This replicates the core logic of the DAGView component's node generation,
    which groups artifacts by their `group` field and either shows individual
    nodes or a single placeholder depending on collapse state.
    """
    # Group artifacts by their group field
    groups: dict[str, list[Artifact]] = {}
    for artifact in artifacts:
        groups.setdefault(artifact.group, []).append(artifact)

    nodes: list[str] = []
    for group_name, group_artifacts in sorted(groups.items()):
        if group_name in collapsed_groups:
            # Collapsed: single placeholder node
            nodes.append(f"{group_name}_collapsed")
        else:
            # Expanded: individual artifact nodes
            for artifact in group_artifacts:
                nodes.append(artifact.id)

    return nodes


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

VALID_GROUPS = ["Phase1", "Phase2", "Phase3", "Phase4", "Phase5", "CodeGen", "Other"]

# Simple ID alphabet for fast generation
_id_alphabet = st.characters(whitelist_categories=("L", "N"), whitelist_characters="_-")


@st.composite
def dag_collapse_scenario(draw):
    """Generate a scenario with artifacts and a subset of their groups collapsed.

    Produces a tuple of (artifacts: list[Artifact], collapsed_groups: set[str]).
    Artifacts have unique IDs and are assigned to random groups.
    """
    count = draw(st.integers(min_value=1, max_value=15))

    # Pre-generate unique IDs using st.lists with unique_by
    ids = draw(
        st.lists(
            st.text(alphabet=_id_alphabet, min_size=3, max_size=20),
            min_size=count,
            max_size=count,
            unique=True,
        )
    )

    # Generate artifacts with those IDs
    artifacts = []
    for artifact_id in ids:
        art_type = draw(st.sampled_from(sorted(VALID_TYPES)))
        art_status = draw(st.sampled_from(sorted(VALID_STATUSES)))
        art_group = draw(st.sampled_from(VALID_GROUPS))
        artifacts.append(
            Artifact(
                id=artifact_id,
                type=art_type,
                status=art_status,
                path="path/to/file.md",
                group=art_group,
            )
        )

    # Determine which groups are present and collapse a random subset
    present_groups = sorted({a.group for a in artifacts})
    collapsed = set(
        draw(
            st.lists(
                st.sampled_from(present_groups),
                min_size=0,
                max_size=len(present_groups),
                unique=True,
            )
        )
    )

    return artifacts, collapsed


# ---------------------------------------------------------------------------
# Property Tests
# ---------------------------------------------------------------------------

class TestDAGCollapsePlaceholder:
    """Property 8: DAG Collapse Produces Placeholder."""

    @given(data=dag_collapse_scenario())
    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
    def test_collapsed_group_has_exactly_one_placeholder(self, data):
        """For any collapsed group, the output SHALL contain exactly ONE
        placeholder node for that group.

        **Validates: Requirements 6.3**
        """
        artifacts, collapsed_groups = data
        nodes = compute_dag_nodes(artifacts, collapsed_groups)

        # For each collapsed group that has artifacts, check exactly one placeholder
        groups_with_artifacts = {a.group for a in artifacts}
        for group in collapsed_groups:
            if group in groups_with_artifacts:
                placeholder = f"{group}_collapsed"
                count = nodes.count(placeholder)
                assert count == 1, (
                    f"Expected exactly 1 placeholder for collapsed group '{group}', "
                    f"got {count}. Nodes: {nodes}"
                )

    @given(data=dag_collapse_scenario())
    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
    def test_collapsed_group_has_no_individual_nodes(self, data):
        """For any collapsed group, the output SHALL NOT contain individual
        artifact nodes belonging to that group.

        **Validates: Requirements 6.3**
        """
        artifacts, collapsed_groups = data
        nodes = compute_dag_nodes(artifacts, collapsed_groups)
        node_set = set(nodes)

        # For each collapsed group, no individual artifact IDs should appear
        for artifact in artifacts:
            if artifact.group in collapsed_groups:
                assert artifact.id not in node_set, (
                    f"Individual node '{artifact.id}' from collapsed group "
                    f"'{artifact.group}' should not appear in nodes. Nodes: {nodes}"
                )

    @given(data=dag_collapse_scenario())
    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
    def test_expanded_group_has_all_individual_nodes(self, data):
        """For any expanded group, the output SHALL contain all individual
        artifact nodes and NO placeholder.

        **Validates: Requirements 6.3**
        """
        artifacts, collapsed_groups = data
        nodes = compute_dag_nodes(artifacts, collapsed_groups)
        node_set = set(nodes)

        # Determine expanded groups (groups that have artifacts but are not collapsed)
        groups_with_artifacts: dict[str, list[Artifact]] = {}
        for a in artifacts:
            groups_with_artifacts.setdefault(a.group, []).append(a)

        for group, group_artifacts in groups_with_artifacts.items():
            if group not in collapsed_groups:
                # All individual nodes should be present
                for artifact in group_artifacts:
                    assert artifact.id in node_set, (
                        f"Individual node '{artifact.id}' from expanded group "
                        f"'{group}' should appear in nodes. Nodes: {nodes}"
                    )
                # No placeholder should exist for expanded groups
                placeholder = f"{group}_collapsed"
                assert placeholder not in node_set, (
                    f"Placeholder '{placeholder}' should not appear for "
                    f"expanded group '{group}'. Nodes: {nodes}"
                )

    @given(data=dag_collapse_scenario())
    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
    def test_total_node_count_consistency(self, data):
        """The total number of nodes SHALL equal the number of individual
        artifact nodes from expanded groups plus one placeholder per collapsed
        group (that has artifacts).

        **Validates: Requirements 6.3**
        """
        artifacts, collapsed_groups = data
        nodes = compute_dag_nodes(artifacts, collapsed_groups)

        # Count expected nodes
        groups_with_artifacts: dict[str, list[Artifact]] = {}
        for a in artifacts:
            groups_with_artifacts.setdefault(a.group, []).append(a)

        expected_count = 0
        for group, group_artifacts in groups_with_artifacts.items():
            if group in collapsed_groups:
                expected_count += 1  # One placeholder
            else:
                expected_count += len(group_artifacts)  # Individual nodes

        assert len(nodes) == expected_count, (
            f"Expected {expected_count} nodes, got {len(nodes)}. "
            f"Collapsed: {collapsed_groups}, Nodes: {nodes}"
        )
