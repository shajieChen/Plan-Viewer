#!/usr/bin/env python3
"""Tests for README rendering functions in render_status.py."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from render_status import build_dependency_graph, topological_sort_lps


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


class TestTopologicalSortLps:
    def test_linear_chain(self):
        """LP-001 -> LP-002 -> LP-003"""
        artifacts = [
            {"id": "LP-003", "type": "landing_prompt", "depends_on": ["LP-002"]},
            {"id": "LP-001", "type": "landing_prompt", "depends_on": ["Plan.x"]},
            {"id": "LP-002", "type": "landing_prompt", "depends_on": ["LP-001"]},
        ]
        result = topological_sort_lps(artifacts)
        assert result == ["LP-001", "LP-002", "LP-003"]

    def test_no_lps(self):
        """No landing prompts in artifacts."""
        artifacts = [
            {"id": "Plan.x", "type": "plan", "depends_on": []},
        ]
        result = topological_sort_lps(artifacts)
        assert result == []

    def test_single_lp(self):
        """One LP with no LP dependencies."""
        artifacts = [
            {"id": "LP-001", "type": "landing_prompt", "depends_on": ["Plan.x"]},
        ]
        result = topological_sort_lps(artifacts)
        assert result == ["LP-001"]

    def test_cycle_fallback_to_sorted(self):
        """Cycle between LPs falls back to alphabetical."""
        artifacts = [
            {"id": "LP-002", "type": "landing_prompt", "depends_on": ["LP-001"]},
            {"id": "LP-001", "type": "landing_prompt", "depends_on": ["LP-002"]},
        ]
        result = topological_sort_lps(artifacts)
        # Cycle detected - fallback to sorted by ID
        assert result == ["LP-001", "LP-002"]
