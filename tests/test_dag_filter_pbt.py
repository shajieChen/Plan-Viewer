"""Property-based tests for DAG filter exclusion logic.

**Validates: Requirements 6.2, 6.4**

Property 7: DAG Filter Exclusion
- For any set of active type filters and artifact list, the filtered output SHALL
  contain ONLY artifacts whose type is in the active filter set.
- For any filtered artifact list and dependency list, the visible edges SHALL only
  connect nodes that are both visible (not filtered out).
- No artifact with a type NOT in the active filter set SHALL appear in the filtered
  output.
"""

from hypothesis import given, settings
from hypothesis import strategies as st

from render_dashboard import Artifact, Dependency, VALID_TYPES


# ---------------------------------------------------------------------------
# DAG Filter Logic (Python helpers replicating browser-side logic)
# ---------------------------------------------------------------------------

def filter_artifacts_by_type(
    artifacts: list[Artifact],
    active_filters: set[str],
) -> list[Artifact]:
    """Return only artifacts whose type is in the active filter set.

    This replicates the DAGView filtering logic from the browser-side React
    component for testability in Python.
    """
    return [a for a in artifacts if a.type in active_filters]


def filter_visible_edges(
    dependencies: list[Dependency],
    visible_artifacts: list[Artifact],
) -> list[Dependency]:
    """Return only edges where both endpoints are visible.

    An edge is visible if both from_id and to_id correspond to artifacts
    that passed the type filter.
    """
    visible_ids = {a.id for a in visible_artifacts}
    return [d for d in dependencies if d.from_id in visible_ids and d.to_id in visible_ids]


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# Strategy for a single artifact type from the valid set
artifact_type_st = st.sampled_from(sorted(VALID_TYPES))

# Strategy for a non-empty subset of VALID_TYPES as active filters
active_filters_st = st.frozensets(artifact_type_st, min_size=0, max_size=len(VALID_TYPES))

# Strategy for generating a single artifact with a random valid type
def artifact_st(id_prefix: str = "art") -> st.SearchStrategy[Artifact]:
    """Generate an Artifact with a random valid type and unique ID."""
    return st.builds(
        Artifact,
        id=st.builds(lambda i: f"{id_prefix}_{i}", st.integers(min_value=0, max_value=999)),
        type=artifact_type_st,
        status=st.sampled_from(["draft", "reviewed", "approved", "ready", "blocked"]),
        path=st.just("path/to/file.md"),
    )


# Strategy for a list of artifacts with unique IDs
artifacts_st = st.lists(
    st.builds(
        Artifact,
        id=st.from_regex(r"art_[a-z0-9]{1,8}", fullmatch=True),
        type=artifact_type_st,
        status=st.sampled_from(["draft", "reviewed", "approved", "ready", "blocked"]),
        path=st.just("path/to/file.md"),
    ),
    min_size=0,
    max_size=20,
    unique_by=lambda a: a.id,
)


# Strategy for dependencies between artifacts in a given list
@st.composite
def artifacts_with_deps_st(draw):
    """Generate a list of artifacts and valid dependencies between them."""
    artifacts = draw(artifacts_st)
    if len(artifacts) < 2:
        return artifacts, []

    # Generate dependencies between existing artifacts
    artifact_ids = [a.id for a in artifacts]
    dep_count = draw(st.integers(min_value=0, max_value=min(len(artifacts) * 2, 30)))
    deps = []
    for _ in range(dep_count):
        from_id = draw(st.sampled_from(artifact_ids))
        to_id = draw(st.sampled_from(artifact_ids))
        if from_id != to_id:
            dep_type = draw(st.sampled_from(["requires", "implements", "verifies"]))
            deps.append(Dependency(from_id=from_id, to_id=to_id, dep_type=dep_type))

    return artifacts, deps


# ---------------------------------------------------------------------------
# Property Tests
# ---------------------------------------------------------------------------

class TestDAGFilterExclusionArtifacts:
    """Property: Filtered output contains ONLY artifacts whose type is in the
    active filter set."""

    @given(artifacts=artifacts_st, active_filters=active_filters_st)
    @settings(max_examples=50)
    def test_filtered_artifacts_have_type_in_filter_set(
        self, artifacts: list[Artifact], active_filters: frozenset[str]
    ):
        """Every artifact in the filtered output has its type in the active
        filter set.

        **Validates: Requirements 6.2**
        """
        filtered = filter_artifacts_by_type(artifacts, set(active_filters))
        for artifact in filtered:
            assert artifact.type in active_filters, (
                f"Artifact {artifact.id} has type '{artifact.type}' which is "
                f"not in active filters {active_filters}"
            )

    @given(artifacts=artifacts_st, active_filters=active_filters_st)
    @settings(max_examples=50)
    def test_no_excluded_type_in_filtered_output(
        self, artifacts: list[Artifact], active_filters: frozenset[str]
    ):
        """No artifact with a type NOT in the active filter set appears in the
        filtered output.

        **Validates: Requirements 6.2**
        """
        filtered = filter_artifacts_by_type(artifacts, set(active_filters))
        excluded_types = VALID_TYPES - set(active_filters)
        for artifact in filtered:
            assert artifact.type not in excluded_types, (
                f"Artifact {artifact.id} has excluded type '{artifact.type}' "
                f"but appeared in filtered output"
            )

    @given(artifacts=artifacts_st, active_filters=active_filters_st)
    @settings(max_examples=50)
    def test_all_matching_artifacts_are_included(
        self, artifacts: list[Artifact], active_filters: frozenset[str]
    ):
        """Every artifact whose type IS in the active filter set appears in the
        filtered output (no false exclusions).

        **Validates: Requirements 6.2**
        """
        filtered = filter_artifacts_by_type(artifacts, set(active_filters))
        filtered_ids = {a.id for a in filtered}
        for artifact in artifacts:
            if artifact.type in active_filters:
                assert artifact.id in filtered_ids, (
                    f"Artifact {artifact.id} has type '{artifact.type}' in "
                    f"active filters but was excluded from output"
                )


class TestDAGFilterExclusionEdges:
    """Property: Visible edges only connect nodes that are both visible."""

    @given(data=artifacts_with_deps_st(), active_filters=active_filters_st)
    @settings(max_examples=50)
    def test_visible_edges_connect_only_visible_nodes(
        self, data: tuple, active_filters: frozenset[str]
    ):
        """Every visible edge has both from_id and to_id in the set of visible
        artifact IDs.

        **Validates: Requirements 6.4**
        """
        artifacts, dependencies = data
        visible_artifacts = filter_artifacts_by_type(artifacts, set(active_filters))
        visible_ids = {a.id for a in visible_artifacts}
        visible_edges = filter_visible_edges(dependencies, visible_artifacts)

        for edge in visible_edges:
            assert edge.from_id in visible_ids, (
                f"Edge from '{edge.from_id}' to '{edge.to_id}': from_id is not "
                f"a visible artifact"
            )
            assert edge.to_id in visible_ids, (
                f"Edge from '{edge.from_id}' to '{edge.to_id}': to_id is not "
                f"a visible artifact"
            )

    @given(data=artifacts_with_deps_st(), active_filters=active_filters_st)
    @settings(max_examples=50)
    def test_no_edge_to_filtered_out_node(
        self, data: tuple, active_filters: frozenset[str]
    ):
        """No visible edge references a node that was filtered out.

        **Validates: Requirements 6.4**
        """
        artifacts, dependencies = data
        visible_artifacts = filter_artifacts_by_type(artifacts, set(active_filters))
        filtered_out_ids = {a.id for a in artifacts} - {a.id for a in visible_artifacts}
        visible_edges = filter_visible_edges(dependencies, visible_artifacts)

        for edge in visible_edges:
            assert edge.from_id not in filtered_out_ids, (
                f"Edge from '{edge.from_id}' references a filtered-out node"
            )
            assert edge.to_id not in filtered_out_ids, (
                f"Edge to '{edge.to_id}' references a filtered-out node"
            )

    @given(data=artifacts_with_deps_st(), active_filters=active_filters_st)
    @settings(max_examples=50)
    def test_all_valid_edges_are_preserved(
        self, data: tuple, active_filters: frozenset[str]
    ):
        """Every dependency where both endpoints are visible appears in the
        visible edges output (no false edge exclusions).

        **Validates: Requirements 6.4**
        """
        artifacts, dependencies = data
        visible_artifacts = filter_artifacts_by_type(artifacts, set(active_filters))
        visible_ids = {a.id for a in visible_artifacts}
        visible_edges = filter_visible_edges(dependencies, visible_artifacts)

        # All deps where both endpoints are visible should be in visible_edges
        expected_edges = [
            d for d in dependencies
            if d.from_id in visible_ids and d.to_id in visible_ids
        ]
        assert len(visible_edges) == len(expected_edges), (
            f"Expected {len(expected_edges)} visible edges but got "
            f"{len(visible_edges)}"
        )
