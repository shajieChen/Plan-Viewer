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
