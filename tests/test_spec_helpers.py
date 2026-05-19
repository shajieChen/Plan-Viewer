"""Unit tests for project-state-spec helpers."""

import sys
from pathlib import Path

import pytest

_SKILL_TOOLS = (
    Path(__file__).resolve().parent.parent
    / "Tools" / "Skills" / "project-state-spec" / "tools"
)
sys.path.insert(0, str(_SKILL_TOOLS))

from _spec_helpers import slugify  # noqa: E402


class TestSlugify:
    def test_basic_phrase(self):
        assert slugify("README Guide Button") == "readme-guide-button"

    def test_collapses_repeated_separators(self):
        assert slugify("Hello   --  World") == "hello-world"

    def test_strips_edge_separators(self):
        assert slugify("  spaced out  ") == "spaced-out"

    def test_keeps_digits(self):
        assert slugify("Phase 2 Cleanup") == "phase-2-cleanup"

    def test_handles_chinese_with_fallback(self):
        # Non-ASCII is replaced with '-'; collapsed; result must be non-empty
        # for at least the surrounding ASCII tokens.
        result = slugify("v2 一键启动 server")
        assert result.startswith("v2-")
        assert result.endswith("-server")
        assert "--" not in result
        assert not result.startswith("-")
        assert not result.endswith("-")

    def test_empty_after_normalize_raises(self):
        with pytest.raises(ValueError):
            slugify("   ")

    def test_pure_non_ascii_raises(self):
        with pytest.raises(ValueError):
            slugify("中文")


import re as _re
import textwrap

from _spec_helpers import today_iso, load_status, StatusYamlMissingError  # noqa: E402


class TestTodayIso:
    def test_format_is_yyyy_mm_dd(self):
        s = today_iso()
        assert _re.fullmatch(r"\d{4}-\d{2}-\d{2}", s), s


class TestLoadStatus:
    def test_loads_existing_yaml(self, tmp_path):
        status_dir = tmp_path / "status"
        status_dir.mkdir()
        (status_dir / "status.yaml").write_text(
            textwrap.dedent(
                """\
                meta:
                  project_name: demo
                artifacts: []
                """
            ),
            encoding="utf-8",
        )
        data = load_status(tmp_path)
        assert data["meta"]["project_name"] == "demo"
        assert data["artifacts"] == []

    def test_missing_status_raises(self, tmp_path):
        with pytest.raises(StatusYamlMissingError):
            load_status(tmp_path)

    def test_empty_yaml_returns_empty_dict(self, tmp_path):
        (tmp_path / "status").mkdir()
        (tmp_path / "status" / "status.yaml").write_text("", encoding="utf-8")
        assert load_status(tmp_path) == {}

    def test_non_mapping_yaml_raises(self, tmp_path):
        (tmp_path / "status").mkdir()
        (tmp_path / "status" / "status.yaml").write_text("- a\n- b\n", encoding="utf-8")
        with pytest.raises(ValueError):
            load_status(tmp_path)


from _spec_helpers import next_id  # noqa: E402


class TestNextId:
    def test_empty_returns_001(self):
        status = {"artifacts": [], "research_findings": [], "decisions": []}
        assert next_id(status, "R") == "R-001"
        assert next_id(status, "D") == "D-001"
        assert next_id(status, "LP") == "LP-001"
        assert next_id(status, "TP") == "TP-001"

    def test_continues_from_max(self):
        status = {
            "artifacts": [
                {"id": "R-001", "type": "research_finding"},
                {"id": "R-009", "type": "research_finding"},
                {"id": "D-005", "type": "decision"},
            ],
            "research_findings": [
                {"id": "R-001"},
                {"id": "R-009"},
            ],
            "decisions": [
                {"id": "D-005"},
            ],
        }
        assert next_id(status, "R") == "R-010"
        assert next_id(status, "D") == "D-006"

    def test_pools_independent(self):
        # Many R's must not affect the LP counter.
        status = {
            "artifacts": [{"id": f"R-{i:03d}"} for i in range(1, 50)] + [
                {"id": "LP-002"}
            ],
        }
        assert next_id(status, "LP") == "LP-003"
        assert next_id(status, "TP") == "TP-001"

    def test_handles_three_digit_pad(self):
        status = {"artifacts": [{"id": "R-099"}]}
        assert next_id(status, "R") == "R-100"

    def test_unknown_prefix_raises(self):
        with pytest.raises(ValueError):
            next_id({"artifacts": []}, "ZZ")


from _spec_helpers import find_artifact_by_topic  # noqa: E402


class TestFindArtifactByTopic:
    @pytest.fixture
    def status(self):
        return {
            "artifacts": [
                {"id": "R-001", "type": "research_finding",
                 "path": "research/R-001-readme-guide-button.md"},
                {"id": "D-001", "type": "decision",
                 "path": "decisions/D-001-readme-guide-button.yaml"},
                {"id": "Plan.readme-guide-button", "type": "plan",
                 "path": "plan/2026-05-19-readme-guide-button-design.md"},
                {"id": "R-002", "type": "research_finding",
                 "path": "research/R-002-other-topic.md"},
            ]
        }

    def test_finds_research(self, status):
        found = find_artifact_by_topic(status, "readme-guide-button", "research_finding")
        assert found is not None
        assert found["id"] == "R-001"

    def test_finds_decision(self, status):
        found = find_artifact_by_topic(status, "readme-guide-button", "decision")
        assert found["id"] == "D-001"

    def test_finds_plan(self, status):
        found = find_artifact_by_topic(status, "readme-guide-button", "plan")
        assert found["id"] == "Plan.readme-guide-button"

    def test_returns_none_on_miss(self, status):
        assert find_artifact_by_topic(status, "nonexistent", "research_finding") is None

    def test_does_not_match_partial_substring(self, status):
        # "readme" alone must NOT match "readme-guide-button"
        assert find_artifact_by_topic(status, "readme", "research_finding") is None
