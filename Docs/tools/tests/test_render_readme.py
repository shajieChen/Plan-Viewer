#!/usr/bin/env python3
"""Tests for README rendering functions in render_status.py."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from render_status import build_dependency_graph


class TestBuildDependencyGraph:
    def test_simple_chain(self):
        """R-001 <- D-001 <- Plan.x"""
        status = {
            "artifacts": [
                {"id": "Plan.x", "type": "plan", "status": "draft", "depends_on": ["D-001"]},
            ],
            "research_findings": [
                {"id": "R-001", "title": "Research", "status": "reviewed"},
            ],
            "decisions": [
                {"id": "D-001", "title": "Decision", "status": "accepted", "based_on": ["R-001"]},
            ],
        }
        result = build_dependency_graph(status)
        assert "R-001" in result
        assert "D-001" in result
        assert "Plan.x" in result
        assert "\u2190" in result  # ← character

    def test_no_dependencies(self):
        """Single artifact with no deps."""
        status = {
            "artifacts": [
                {"id": "R-001", "type": "research", "status": "draft", "depends_on": []},
            ],
            "research_findings": [],
            "decisions": [],
        }
        result = build_dependency_graph(status)
        assert "R-001" in result

    def test_empty_artifacts(self):
        """No artifacts at all."""
        status = {"artifacts": [], "research_findings": [], "decisions": []}
        result = build_dependency_graph(status)
        assert "\u65e0\u4f9d\u8d56\u5173\u7cfb" in result  # 无依赖关系
