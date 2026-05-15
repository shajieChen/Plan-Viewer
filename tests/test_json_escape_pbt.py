"""Property-based tests for JSON escape safety.

**Validates: Requirements 3.3**

Property 3: JSON Escape Safety
- For any project data that when serialized contains `</`, the output SHALL
  contain `<\\/` in place of every `</` occurrence (no unescaped `</` in output).
- The output SHALL NOT contain the literal string `</script>`.
- After replacing `<\\/` back with `</`, the result SHALL be valid JSON.
"""

import json

from hypothesis import given, settings
from hypothesis import strategies as st

from render_dashboard import (
    serialize_dashboard_data,
    DashboardData,
    ProjectData,
    Artifact,
    MarkdownPreview,
)


# --- Strategies ---

# Characters that are safe for use in strings (no null bytes or bare surrogates)
_safe_chars = st.characters(
    whitelist_categories=("L", "N", "P", "S", "Z"),
    blacklist_characters="\x00",
)

# Strategy for strings that deliberately include `</` sequences
_script_injection_text = st.one_of(
    st.just("</script>"),
    st.just("</SCRIPT>"),
    st.just("</Script>"),
    st.just("</style>"),
    st.just("</div>"),
    st.just("prefix</script>suffix"),
    st.just("a]</b"),
    st.builds(
        lambda prefix, suffix: f"{prefix}</{suffix}",
        st.text(min_size=0, max_size=20, alphabet=_safe_chars),
        st.text(min_size=0, max_size=20, alphabet=_safe_chars),
    ),
)

# Strategy for artifact paths/IDs that may contain `</` sequences
_artifact_path_with_injection = st.one_of(
    _script_injection_text,
    st.text(min_size=1, max_size=60, alphabet=_safe_chars),
)

# Strategy for artifact IDs (must be non-empty)
_artifact_id = st.text(
    min_size=1,
    max_size=40,
    alphabet=st.characters(whitelist_categories=("L", "N", "P"), blacklist_characters="\x00\r\n"),
)

# Valid statuses and types
_valid_status = st.sampled_from([
    "draft", "reviewed", "approved", "ready", "blocked",
    "needs_update", "invalidated", "deprecated", "archived",
])
_valid_type = st.sampled_from(["plan", "landing_prompt", "test_prompt"])


# Strategy for generating Artifact instances with potentially dangerous paths
_artifact_strategy = st.builds(
    Artifact,
    id=_artifact_id,
    type=_valid_type,
    status=_valid_status,
    path=_artifact_path_with_injection,
    depends_on=st.just([]),
    produces_handoffs=st.just([]),
    consumes_handoffs=st.just([]),
    last_checked=st.just("2025-01-01T00:00:00Z"),
    group=st.sampled_from(["Phase1", "Phase2", "Phase3", "Phase4", "Phase5", "CodeGen", "Other"]),
)

# Strategy for MarkdownPreview with potentially dangerous content
_markdown_preview_strategy = st.builds(
    MarkdownPreview,
    title=_artifact_path_with_injection,
    excerpt=_artifact_path_with_injection,
)

# Strategy for ProjectData with artifacts containing injection strings
_project_data_strategy = st.builds(
    ProjectData,
    meta=st.fixed_dictionaries({"project_name": st.just("test_project")}),
    artifacts=st.lists(_artifact_strategy, min_size=1, max_size=5),
    dependencies=st.just([]),
    research_findings=st.just([]),
    decisions=st.just([]),
    gates=st.just([]),
    blockers=st.just([]),
    change_events=st.just([]),
    markdown_previews=st.dictionaries(
        keys=_artifact_id,
        values=_markdown_preview_strategy,
        min_size=0,
        max_size=3,
    ),
)

# Strategy for DashboardData
_dashboard_data_strategy = st.builds(
    DashboardData,
    projects=st.dictionaries(
        keys=st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=("L", "N"), blacklist_characters="\x00")),
        values=_project_data_strategy,
        min_size=1,
        max_size=3,
    ),
    generated_at=st.just("2025-01-01T00:00:00Z"),
    generator_version=st.just("1.0.0"),
)


class TestJsonEscapeSafety:
    """Property 3: JSON Escape Safety.

    **Validates: Requirements 3.3**

    For any project data that when serialized to JSON contains `</`,
    the output SHALL contain `<\\/` in place of every `</` occurrence,
    ensuring no unescaped `</script>` appears in the HTML.
    """

    @given(dashboard_data=_dashboard_data_strategy)
    @settings(max_examples=50, deadline=None)
    def test_no_unescaped_close_tag_in_output(self, dashboard_data: DashboardData) -> None:
        """The serialized output SHALL NOT contain any unescaped `</` sequence.

        **Validates: Requirements 3.3**
        """
        result = serialize_dashboard_data(dashboard_data)

        assert "</" not in result, (
            f"Found unescaped '</' in serialized output: "
            f"{result[max(0, result.index('</') - 20):result.index('</') + 20]!r}"
        )

    @given(dashboard_data=_dashboard_data_strategy)
    @settings(max_examples=50, deadline=None)
    def test_no_script_close_tag_in_output(self, dashboard_data: DashboardData) -> None:
        """The output SHALL NOT contain the literal string `</script>`.

        **Validates: Requirements 3.3**
        """
        result = serialize_dashboard_data(dashboard_data)

        assert "</script>" not in result.lower(), (
            f"Found '</script>' (case-insensitive) in serialized output"
        )

    @given(dashboard_data=_dashboard_data_strategy)
    @settings(max_examples=50, deadline=None)
    def test_output_is_valid_json_after_unescaping(self, dashboard_data: DashboardData) -> None:
        """After replacing `<\\/` back with `</`, the result SHALL be valid JSON.

        **Validates: Requirements 3.3**
        """
        result = serialize_dashboard_data(dashboard_data)

        # Reverse the escape: <\/ → </
        unescaped = result.replace(r"<\/", "</")

        # Must be valid JSON
        try:
            parsed = json.loads(unescaped)
        except json.JSONDecodeError as e:
            raise AssertionError(
                f"After unescaping '<\\/' back to '</', result is not valid JSON: {e}"
            ) from e

        # The parsed structure should have the expected top-level keys
        assert "projects" in parsed
        assert "generated_at" in parsed
        assert "generator_version" in parsed
