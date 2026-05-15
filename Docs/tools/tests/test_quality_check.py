#!/usr/bin/env python3
"""Tests for quality_check.py — covers all 10 quality rules."""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from quality_check import (
    check_q1_no_orphans,
    check_q2_no_broken_refs,
    check_q3_no_circular_deps,
    check_q4_lp_has_preconditions,
    check_q5_lp_consumes_handoffs_match,
    check_q6_tp_refs_lp,
    check_q7_no_ready_with_upstream_needs_update,
    check_q8_hc_has_producer_and_consumer,
    check_q9_gates_have_checks,
    check_q10_no_duplicate_ids,
    collect_all_ids,
    run_all_checks,
    run_incremental_checks,
)


@pytest.fixture
def healthy_status():
    """A status.yaml with no quality issues."""
    return {
        "artifacts": [
            {"id": "Plan.alpha", "type": "plan", "path": "plan/alpha.md",
             "status": "approved", "depends_on": ["D-001"]},
            {"id": "LP-001", "type": "landing_prompt", "path": "prompts/landing/LP-001.md",
             "status": "draft", "depends_on": ["Plan.alpha"], "consumes_handoffs": []},
            {"id": "TP-001", "type": "test_prompt", "path": "prompts/test/TP-001.md",
             "status": "draft", "depends_on": ["LP-001"]},
        ],
        "research_findings": [
            {"id": "R-001", "title": "Research", "path": "research/R-001.md", "status": "reviewed"},
        ],
        "decisions": [
            {"id": "D-001", "title": "Decision", "path": "decisions/D-001.yaml",
             "status": "accepted", "based_on": ["R-001"], "affects": ["Plan.alpha"]},
        ],
        "handoff_contexts": [],
        "preconditions": [
            {"id": "PC-001", "target": "LP-001", "requires": [
                {"artifact": "Plan.alpha", "field": "status", "in": ["approved", "ready"]}
            ], "status": "passing"},
        ],
        "gates": [
            {"id": "G-001", "name": "LP gate", "status": "open",
             "checks": [{"id": "CHK-001", "description": "Plan approved", "status": "passing"}]},
        ],
        "blockers": [],
        "change_events": [],
        "snapshots": {"git_baseline": None, "file_hashes": {}},
    }


# --- Q1: No orphan artifacts ---

def test_q1_passes_when_all_have_deps(healthy_status):
    all_ids = collect_all_ids(healthy_status)
    result = check_q1_no_orphans(healthy_status, all_ids)
    assert result["status"] == "passed"


def test_q1_fails_on_orphan():
    status = {
        "artifacts": [
            {"id": "Plan.orphan", "type": "plan", "path": "plan/x.md", "status": "draft", "depends_on": []},
        ],
        "research_findings": [], "decisions": [], "handoff_contexts": [],
    }
    result = check_q1_no_orphans(status, collect_all_ids(status))
    assert result["status"] == "failed"
    assert "Plan.orphan" in result["details"]


# --- Q2: No broken references ---

def test_q2_passes_with_valid_refs(healthy_status):
    all_ids = collect_all_ids(healthy_status)
    result = check_q2_no_broken_refs(healthy_status, all_ids)
    assert result["status"] == "passed"


def test_q2_fails_on_broken_ref():
    status = {
        "artifacts": [
            {"id": "Plan.x", "type": "plan", "path": "p.md", "status": "draft",
             "depends_on": ["NONEXISTENT"]},
        ],
        "research_findings": [], "decisions": [], "handoff_contexts": [],
    }
    result = check_q2_no_broken_refs(status, collect_all_ids(status))
    assert result["status"] == "failed"
    assert "NONEXISTENT" in result["details"]


# --- Q3: No circular deps ---

def test_q3_passes_acyclic(healthy_status):
    result = check_q3_no_circular_deps(healthy_status)
    assert result["status"] == "passed"


def test_q3_fails_on_cycle():
    status = {
        "artifacts": [
            {"id": "A", "type": "plan", "path": "a.md", "status": "draft", "depends_on": ["B"]},
            {"id": "B", "type": "plan", "path": "b.md", "status": "draft", "depends_on": ["A"]},
        ],
        "research_findings": [], "decisions": [], "handoff_contexts": [],
    }
    result = check_q3_no_circular_deps(status)
    assert result["status"] == "failed"
    assert "Cycle" in result["details"]


# --- Q4: Every LP has >= 1 PC ---

def test_q4_passes_with_pc(healthy_status):
    result = check_q4_lp_has_preconditions(healthy_status)
    assert result["status"] == "passed"


def test_q4_fails_lp_without_pc():
    status = {
        "artifacts": [
            {"id": "LP-001", "type": "landing_prompt", "path": "lp.md",
             "status": "draft", "depends_on": ["Plan.x"]},
        ],
        "research_findings": [], "decisions": [], "handoff_contexts": [],
        "preconditions": [],
    }
    result = check_q4_lp_has_preconditions(status)
    assert result["status"] == "failed"
    assert "LP-001" in result["details"]


def test_q4_passes_when_no_lps():
    status = {"artifacts": [], "research_findings": [], "decisions": [],
              "handoff_contexts": [], "preconditions": []}
    result = check_q4_lp_has_preconditions(status)
    assert result["status"] == "passed"


# --- Q5: LP consumes_handoffs matches PC ---

def test_q5_passes_no_consumed(healthy_status):
    result = check_q5_lp_consumes_handoffs_match(healthy_status)
    assert result["status"] == "passed"


def test_q5_fails_missing_pc_for_consumed_hc():
    status = {
        "artifacts": [
            {"id": "LP-001", "type": "landing_prompt", "path": "lp.md",
             "status": "draft", "depends_on": [], "consumes_handoffs": ["HC-001"]},
        ],
        "research_findings": [], "decisions": [], "handoff_contexts": [],
        "preconditions": [],
    }
    result = check_q5_lp_consumes_handoffs_match(status)
    assert result["status"] == "failed"
    assert "HC-001" in result["details"]


# --- Q6: Every TP refs >= 1 LP ---

def test_q6_passes_tp_with_lp(healthy_status):
    result = check_q6_tp_refs_lp(healthy_status)
    assert result["status"] == "passed"


def test_q6_fails_tp_without_lp():
    status = {
        "artifacts": [
            {"id": "TP-001", "type": "test_prompt", "path": "tp.md",
             "status": "draft", "depends_on": ["Plan.x"]},
        ],
        "research_findings": [], "decisions": [], "handoff_contexts": [],
    }
    result = check_q6_tp_refs_lp(status)
    assert result["status"] == "failed"
    assert "TP-001" in result["details"]


# --- Q7: No ready with upstream needs_update ---

def test_q7_passes_healthy(healthy_status):
    result = check_q7_no_ready_with_upstream_needs_update(healthy_status)
    assert result["status"] == "passed"


def test_q7_fails_ready_with_upstream_needs_update():
    status = {
        "artifacts": [
            {"id": "Plan.x", "type": "plan", "path": "p.md",
             "status": "needs_update", "depends_on": []},
            {"id": "LP-001", "type": "landing_prompt", "path": "lp.md",
             "status": "ready", "depends_on": ["Plan.x"]},
        ],
        "research_findings": [], "decisions": [], "handoff_contexts": [],
    }
    result = check_q7_no_ready_with_upstream_needs_update(status)
    assert result["status"] == "failed"
    assert "LP-001" in result["details"]


# --- Q8: Every HC has producer + >= 1 consumer ---

def test_q8_passes_no_hcs(healthy_status):
    result = check_q8_hc_has_producer_and_consumer(healthy_status)
    assert result["status"] == "passed"


def test_q8_fails_hc_no_consumer():
    status = {
        "artifacts": [], "research_findings": [], "decisions": [],
        "handoff_contexts": [
            {"id": "HC-001", "producer": "LP-001", "version": 1,
             "status": "available", "consumed_by": [], "consumed_status": []},
        ],
    }
    result = check_q8_hc_has_producer_and_consumer(status)
    assert result["status"] == "failed"
    assert "no consumers" in result["details"]


# --- Q9: All gates have >= 1 check ---

def test_q9_passes_with_checks(healthy_status):
    result = check_q9_gates_have_checks(healthy_status)
    assert result["status"] == "passed"


def test_q9_fails_gate_no_checks():
    status = {
        "artifacts": [], "research_findings": [], "decisions": [],
        "handoff_contexts": [],
        "gates": [{"id": "G-001", "name": "Empty gate", "status": "open", "checks": []}],
    }
    result = check_q9_gates_have_checks(status)
    assert result["status"] == "failed"
    assert "G-001" in result["details"]


# --- Q10: No duplicate IDs ---

def test_q10_passes_unique(healthy_status):
    result = check_q10_no_duplicate_ids(healthy_status)
    assert result["status"] == "passed"


def test_q10_fails_duplicate():
    status = {
        "artifacts": [
            {"id": "DUP", "type": "plan", "path": "a.md", "status": "draft", "depends_on": []},
        ],
        "research_findings": [
            {"id": "DUP", "title": "Dup", "path": "r.md", "status": "draft"},
        ],
        "decisions": [], "handoff_contexts": [], "preconditions": [],
        "gates": [], "blockers": [],
    }
    result = check_q10_no_duplicate_ids(status)
    assert result["status"] == "failed"
    assert "DUP" in result["details"]


# --- Integration: run_all_checks ---

def test_run_all_checks_healthy(healthy_status):
    result = run_all_checks(healthy_status)
    assert result["score"] == "10/10"
    assert len(result["failed"]) == 0
    assert len(result["warnings"]) == 0


def test_run_all_checks_with_issues():
    status = {
        "artifacts": [
            {"id": "Plan.orphan", "type": "plan", "path": "p.md", "status": "draft", "depends_on": []},
        ],
        "research_findings": [], "decisions": [], "handoff_contexts": [],
        "preconditions": [], "gates": [], "blockers": [],
    }
    result = run_all_checks(status)
    # Q1 should fail (orphan), rest should pass
    assert result["score"] == "9/10"
    assert len(result["warnings"]) == 1
    assert result["warnings"][0]["id"] == "Q1"


# --- Incremental mode ---

def test_incremental_skips_irrelevant_checks(healthy_status):
    # Affect only a plan — Q4/Q5/Q6 should be skipped (auto-pass)
    result = run_incremental_checks(healthy_status, ["Plan.alpha"])
    assert result["mode"] == "incremental"
    assert result["score"] == "10/10"
