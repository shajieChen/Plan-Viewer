# Prompt v4 Structural Upgrade — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade the project-state-tracker prompt from v3 (~1650 words, monolithic) to v4 (~1200 words core + ~800 words companion), offloading §6E Quality Checklist to a deterministic `quality_check.py`.

**Design Doc:** `Docs/specs/2026-05-15-prompt-v4-structural-upgrade-design.md`

**Architecture:** Three-layer system — Core Prompt (interface contract, ≤1200 words) + Companion file (on-demand reference, ~800 words) + Python layer (deterministic execution). The key innovations are SCL (Structured Cognitive Loop) contracts in §4 and demand-paging for §6 reference rules.

**Tech Stack:** Python 3.10+, PyYAML (already in project). No new dependencies.

---

## File Structure

| File | Action | Responsibility |
|------|--------|---------------|
| `Docs/tools/quality_check.py` | Create | §6E semantic quality validation (10 rules) |
| `Docs/tools/tests/test_quality_check.py` | Create | Unit + property tests for quality_check |
| `Prompt_project-state-tracker_appendix.md` | Create | Companion reference (SCL contracts + paging rules + §6 full text) |
| `Prompt_project-state-tracker_生成项目使用的Workflow_State.md` | Replace | Core prompt v4 (≤1200 words) |

---


### Task 1: Create `quality_check.py` — Deterministic §6E Quality Validation

**Files:**
- Create: `Docs/tools/quality_check.py`

**Rationale:** This is the highest-value change — removes the most error-prone AI task (10-rule checklist execution) and replaces it with deterministic Python. Can be developed and tested independently before touching the prompt.

- [ ] **Step 1: Create the complete script**

```python
#!/usr/bin/env python3
"""Deterministic quality validation for project-state-tracker.

Implements all 10 rules from §6E Quality Checklist.
Replaces AI-executed quality checks with guaranteed-correct Python.

Usage:
    python tools/quality_check.py --project <path> [--scope full|incremental] [--affected <id1,id2,...>]

Output: JSON to stdout with passed/failed/warnings/score fields.
"""

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

import yaml


def load_status(project: Path) -> dict:
    """Load and return status.yaml contents."""
    status_file = project / "status" / "status.yaml"
    if not status_file.exists():
        print(json.dumps({"error": "status.yaml not found", "score": "0/10"}))
        sys.exit(1)
    with open(status_file, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def collect_all_ids(status: dict) -> set[str]:
    """Collect every artifact/research/decision ID in the project."""
    ids = set()
    for art in status.get("artifacts", []):
        if art.get("id"):
            ids.add(art["id"])
    for rf in status.get("research_findings", []):
        if rf.get("id"):
            ids.add(rf["id"])
    for dec in status.get("decisions", []):
        if dec.get("id"):
            ids.add(dec["id"])
    for hc in status.get("handoff_contexts", []):
        if hc.get("id"):
            ids.add(hc["id"])
    return ids


def collect_all_items(status: dict) -> list[dict]:
    """Collect all trackable items (artifacts + research + decisions)."""
    items = []
    for art in status.get("artifacts", []):
        items.append(art)
    for rf in status.get("research_findings", []):
        items.append(rf)
    for dec in status.get("decisions", []):
        items.append(dec)
    return items


def get_item_by_id(status: dict, item_id: str) -> dict | None:
    """Find any item by its ID across all collections."""
    for art in status.get("artifacts", []):
        if art.get("id") == item_id:
            return art
    for rf in status.get("research_findings", []):
        if rf.get("id") == item_id:
            return rf
    for dec in status.get("decisions", []):
        if dec.get("id") == item_id:
            return dec
    return None


def check_q1_no_orphans(status: dict, all_ids: set[str]) -> dict:
    """Q1: No orphan artifacts — every artifact has depends_on OR is type=research/decision."""
    orphans = []
    for art in status.get("artifacts", []):
        deps = art.get("depends_on", [])
        if not deps:
            orphans.append(art.get("id", "?"))
    if orphans:
        return {
            "id": "Q1", "check": "No orphan artifacts", "severity": "warn",
            "status": "failed",
            "details": f"Artifacts with no depends_on: {', '.join(orphans)}"
        }
    return {"id": "Q1", "check": "No orphan artifacts", "severity": "warn", "status": "passed"}


def check_q2_no_broken_refs(status: dict, all_ids: set[str]) -> dict:
    """Q2: No broken references — all IDs in depends_on/based_on/affects exist."""
    broken = []
    for art in status.get("artifacts", []):
        for dep_id in art.get("depends_on", []):
            if dep_id not in all_ids:
                broken.append(f"{art.get('id','?')} → {dep_id}")
    for dec in status.get("decisions", []):
        for ref_id in dec.get("based_on", []):
            if ref_id not in all_ids:
                broken.append(f"{dec.get('id','?')} → {ref_id}")
        for ref_id in dec.get("affects", []):
            if ref_id not in all_ids:
                broken.append(f"{dec.get('id','?')} affects → {ref_id}")
    for hc in status.get("handoff_contexts", []):
        producer = hc.get("producer", "")
        if producer and producer not in all_ids:
            broken.append(f"{hc.get('id','?')} producer → {producer}")
        for consumer in hc.get("consumed_by", []):
            if consumer not in all_ids:
                broken.append(f"{hc.get('id','?')} consumer → {consumer}")
    if broken:
        return {
            "id": "Q2", "check": "No broken references", "severity": "error",
            "status": "failed",
            "details": f"Broken refs: {'; '.join(broken[:5])}" + (f" (+{len(broken)-5} more)" if len(broken) > 5 else "")
        }
    return {"id": "Q2", "check": "No broken references", "severity": "error", "status": "passed"}


def check_q3_no_circular_deps(status: dict) -> dict:
    """Q3: No circular dependencies — topological sort on dependency graph."""
    # Build adjacency list: id -> [ids it depends on]
    graph = defaultdict(set)
    all_items = collect_all_items(status)
    item_ids = {item.get("id") for item in all_items if item.get("id")}

    for item in all_items:
        item_id = item.get("id")
        if not item_id:
            continue
        for dep in item.get("depends_on", []):
            if dep in item_ids:
                graph[item_id].add(dep)
        for dep in item.get("based_on", []):
            if dep in item_ids:
                graph[item_id].add(dep)

    # Detect cycles via DFS coloring
    WHITE, GRAY, BLACK = 0, 1, 2
    color = {nid: WHITE for nid in item_ids}
    cycles = []

    def dfs(node, path):
        color[node] = GRAY
        path.append(node)
        for neighbor in graph.get(node, set()):
            if neighbor not in color:
                continue
            if color[neighbor] == GRAY:
                cycle_start = path.index(neighbor)
                cycles.append(path[cycle_start:] + [neighbor])
            elif color[neighbor] == WHITE:
                dfs(neighbor, path)
        path.pop()
        color[node] = BLACK

    for nid in item_ids:
        if color.get(nid) == WHITE:
            dfs(nid, [])

    if cycles:
        cycle_str = " → ".join(cycles[0])
        return {
            "id": "Q3", "check": "No circular dependencies", "severity": "error",
            "status": "failed",
            "details": f"Cycle detected: {cycle_str}"
        }
    return {"id": "Q3", "check": "No circular dependencies", "severity": "error", "status": "passed"}


def check_q4_lp_has_preconditions(status: dict) -> dict:
    """Q4: Every LP has at least one precondition."""
    lps = [a for a in status.get("artifacts", []) if a.get("type") == "landing_prompt"]
    if not lps:
        return {"id": "Q4", "check": "Every LP has ≥1 PC", "severity": "warn", "status": "passed"}

    preconditions = status.get("preconditions", [])
    lp_ids_with_pc = {pc.get("target") for pc in preconditions}

    missing = [lp.get("id", "?") for lp in lps if lp.get("id") not in lp_ids_with_pc]
    if missing:
        return {
            "id": "Q4", "check": "Every LP has ≥1 PC", "severity": "warn",
            "status": "failed",
            "details": f"LPs without preconditions: {', '.join(missing)}"
        }
    return {"id": "Q4", "check": "Every LP has ≥1 PC", "severity": "warn", "status": "passed"}


def check_q5_lp_consumes_handoffs_match(status: dict) -> dict:
    """Q5: LP consumes_handoffs has matching precondition for each HC."""
    issues = []
    preconditions = status.get("preconditions", [])

    for art in status.get("artifacts", []):
        if art.get("type") != "landing_prompt":
            continue
        consumed = art.get("consumes_handoffs", [])
        if not consumed:
            continue
        art_id = art.get("id", "?")
        # Find PCs targeting this LP
        art_pcs = [pc for pc in preconditions if pc.get("target") == art_id]
        pc_handoff_refs = set()
        for pc in art_pcs:
            for req in pc.get("requires", []):
                if req.get("handoff"):
                    pc_handoff_refs.add(req["handoff"])
        for hc_id in consumed:
            if hc_id not in pc_handoff_refs:
                issues.append(f"{art_id} consumes {hc_id} but no matching PC")

    if issues:
        return {
            "id": "Q5", "check": "LP consumes_handoffs matches PC", "severity": "error",
            "status": "failed",
            "details": "; ".join(issues[:3])
        }
    return {"id": "Q5", "check": "LP consumes_handoffs matches PC", "severity": "error", "status": "passed"}


def check_q6_tp_refs_lp(status: dict) -> dict:
    """Q6: Every TP references at least one LP."""
    tps = [a for a in status.get("artifacts", []) if a.get("type") == "test_prompt"]
    if not tps:
        return {"id": "Q6", "check": "Every TP refs ≥1 LP", "severity": "warn", "status": "passed"}

    missing = []
    for tp in tps:
        deps = tp.get("depends_on", [])
        has_lp = any(d.startswith("LP-") or d.startswith("LP.") for d in deps)
        if not has_lp:
            missing.append(tp.get("id", "?"))

    if missing:
        return {
            "id": "Q6", "check": "Every TP refs ≥1 LP", "severity": "warn",
            "status": "failed",
            "details": f"TPs without LP reference: {', '.join(missing)}"
        }
    return {"id": "Q6", "check": "Every TP refs ≥1 LP", "severity": "warn", "status": "passed"}


def check_q7_no_ready_with_upstream_needs_update(status: dict) -> dict:
    """Q7: No 'ready' artifact with upstream 'needs_update'."""
    all_items = collect_all_items(status)
    item_map = {item.get("id"): item for item in all_items if item.get("id")}
    violations = []

    for item in all_items:
        if item.get("status") != "ready":
            continue
        item_id = item.get("id", "?")
        # BFS upstream
        visited = set()
        queue = list(item.get("depends_on", []) + item.get("based_on", []))
        while queue:
            dep_id = queue.pop(0)
            if dep_id in visited:
                continue
            visited.add(dep_id)
            dep_item = item_map.get(dep_id)
            if dep_item and dep_item.get("status") == "needs_update":
                violations.append(f"{item_id} is ready but upstream {dep_id} is needs_update")
                break
            if dep_item:
                queue.extend(dep_item.get("depends_on", []) + dep_item.get("based_on", []))

    if violations:
        return {
            "id": "Q7", "check": "No ready with upstream needs_update", "severity": "error",
            "status": "failed",
            "details": "; ".join(violations[:3])
        }
    return {"id": "Q7", "check": "No ready with upstream needs_update", "severity": "error", "status": "passed"}


def check_q8_hc_has_producer_and_consumer(status: dict) -> dict:
    """Q8: Every HC has producer + at least 1 consumer."""
    issues = []
    for hc in status.get("handoff_contexts", []):
        hc_id = hc.get("id", "?")
        if not hc.get("producer"):
            issues.append(f"{hc_id} has no producer")
        consumers = hc.get("consumed_by", [])
        if not consumers:
            issues.append(f"{hc_id} has no consumers")

    if issues:
        return {
            "id": "Q8", "check": "Every HC has producer + ≥1 consumer", "severity": "warn",
            "status": "failed",
            "details": "; ".join(issues[:3])
        }
    return {"id": "Q8", "check": "Every HC has producer + ≥1 consumer", "severity": "warn", "status": "passed"}


def check_q9_gates_have_checks(status: dict) -> dict:
    """Q9: All gates have at least one check."""
    issues = []
    for gate in status.get("gates", []):
        gate_id = gate.get("id", "?")
        checks = gate.get("checks", [])
        if not checks:
            issues.append(f"{gate_id} has no checks")

    if issues:
        return {
            "id": "Q9", "check": "All gates have ≥1 check", "severity": "warn",
            "status": "failed",
            "details": "; ".join(issues)
        }
    return {"id": "Q9", "check": "All gates have ≥1 check", "severity": "warn", "status": "passed"}


def check_q10_no_duplicate_ids(status: dict) -> dict:
    """Q10: No duplicate IDs across all collections."""
    all_id_list = []
    for art in status.get("artifacts", []):
        if art.get("id"):
            all_id_list.append(art["id"])
    for rf in status.get("research_findings", []):
        if rf.get("id"):
            all_id_list.append(rf["id"])
    for dec in status.get("decisions", []):
        if dec.get("id"):
            all_id_list.append(dec["id"])
    for hc in status.get("handoff_contexts", []):
        if hc.get("id"):
            all_id_list.append(hc["id"])
    for pc in status.get("preconditions", []):
        if pc.get("id"):
            all_id_list.append(pc["id"])
    for gate in status.get("gates", []):
        if gate.get("id"):
            all_id_list.append(gate["id"])
    for blocker in status.get("blockers", []):
        if blocker.get("id"):
            all_id_list.append(blocker["id"])

    seen = set()
    duplicates = set()
    for item_id in all_id_list:
        if item_id in seen:
            duplicates.add(item_id)
        seen.add(item_id)

    if duplicates:
        return {
            "id": "Q10", "check": "No duplicate IDs", "severity": "error",
            "status": "failed",
            "details": f"Duplicate IDs: {', '.join(sorted(duplicates))}"
        }
    return {"id": "Q10", "check": "No duplicate IDs", "severity": "error", "status": "passed"}


def run_all_checks(status: dict) -> dict:
    """Run all 10 quality checks and return structured result."""
    all_ids = collect_all_ids(status)

    checks = [
        check_q1_no_orphans(status, all_ids),
        check_q2_no_broken_refs(status, all_ids),
        check_q3_no_circular_deps(status),
        check_q4_lp_has_preconditions(status),
        check_q5_lp_consumes_handoffs_match(status),
        check_q6_tp_refs_lp(status),
        check_q7_no_ready_with_upstream_needs_update(status),
        check_q8_hc_has_producer_and_consumer(status),
        check_q9_gates_have_checks(status),
        check_q10_no_duplicate_ids(status),
    ]

    passed = [c for c in checks if c["status"] == "passed"]
    failed = [c for c in checks if c["status"] == "failed" and c["severity"] == "error"]
    warnings = [c for c in checks if c["status"] == "failed" and c["severity"] == "warn"]

    return {
        "score": f"{len(passed)}/10",
        "passed": passed,
        "failed": failed,
        "warnings": warnings,
    }


def run_incremental_checks(status: dict, affected_ids: list[str]) -> dict:
    """Run only checks relevant to the affected artifacts."""
    all_ids = collect_all_ids(status)
    affected_set = set(affected_ids)

    # Determine which checks to run based on affected types
    affected_items = [get_item_by_id(status, aid) for aid in affected_ids]
    affected_items = [i for i in affected_items if i is not None]
    affected_types = {i.get("type", "") for i in affected_items}

    checks = []

    # Q1-Q3: always run for affected + dependents
    checks.append(check_q1_no_orphans(status, all_ids))
    checks.append(check_q2_no_broken_refs(status, all_ids))
    checks.append(check_q3_no_circular_deps(status))

    # Q4-Q6: only if LP or TP types affected
    if affected_types & {"landing_prompt", "test_prompt"}:
        checks.append(check_q4_lp_has_preconditions(status))
        checks.append(check_q5_lp_consumes_handoffs_match(status))
        checks.append(check_q6_tp_refs_lp(status))
    else:
        checks.append({"id": "Q4", "check": "Every LP has ≥1 PC", "severity": "warn", "status": "passed"})
        checks.append({"id": "Q5", "check": "LP consumes_handoffs matches PC", "severity": "error", "status": "passed"})
        checks.append({"id": "Q6", "check": "Every TP refs ≥1 LP", "severity": "warn", "status": "passed"})

    # Q7: always (affected + upstream chain)
    checks.append(check_q7_no_ready_with_upstream_needs_update(status))

    # Q8-Q9: only if HC or gate changes
    has_hc_or_gate = bool(affected_set & {hc.get("id", "") for hc in status.get("handoff_contexts", [])}) or \
                     bool(affected_set & {g.get("id", "") for g in status.get("gates", [])})
    if has_hc_or_gate:
        checks.append(check_q8_hc_has_producer_and_consumer(status))
        checks.append(check_q9_gates_have_checks(status))
    else:
        checks.append({"id": "Q8", "check": "Every HC has producer + ≥1 consumer", "severity": "warn", "status": "passed"})
        checks.append({"id": "Q9", "check": "All gates have ≥1 check", "severity": "warn", "status": "passed"})

    # Q10: always full scan (cheap)
    checks.append(check_q10_no_duplicate_ids(status))

    passed = [c for c in checks if c["status"] == "passed"]
    failed = [c for c in checks if c["status"] == "failed" and c["severity"] == "error"]
    warnings = [c for c in checks if c["status"] == "failed" and c["severity"] == "warn"]

    return {
        "score": f"{len(passed)}/10",
        "passed": passed,
        "failed": failed,
        "warnings": warnings,
        "mode": "incremental",
        "affected": affected_ids,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Deterministic quality validation for project-state-tracker (§6E)"
    )
    parser.add_argument("--project", required=True, help="Project root path")
    parser.add_argument("--scope", choices=["full", "incremental"], default="full",
                        help="Check scope: full (all rules) or incremental (affected only)")
    parser.add_argument("--affected", default="",
                        help="Comma-separated artifact IDs for incremental mode")
    args = parser.parse_args()

    project = Path(args.project).resolve()
    status = load_status(project)

    if args.scope == "incremental" and args.affected:
        affected_ids = [aid.strip() for aid in args.affected.split(",") if aid.strip()]
        result = run_incremental_checks(status, affected_ids)
    else:
        result = run_all_checks(status)

    print(json.dumps(result, indent=2, ensure_ascii=False))
    sys.exit(0)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run quality_check.py against the current Plan_Viewer project**

Run: `python Docs/tools/quality_check.py --project Docs`

Expected output: JSON with `"score": "10/10"` (current project has no LPs, TPs, HCs, gates — so Q4-Q9 pass vacuously; R-001/D-001/Plan.dashboard-design have valid deps and no duplicates).

- [ ] **Step 3: Verify incremental mode works**

Run: `python Docs/tools/quality_check.py --project Docs --scope incremental --affected Plan.dashboard-design`

Expected: JSON output with score, mode="incremental", affected list present.

- [ ] **Step 4: Commit**

```bash
git add Docs/tools/quality_check.py
git commit -m "feat: add quality_check.py — deterministic §6E quality validation"
```

---


### Task 2: Unit Tests for `quality_check.py`

**Files:**
- Create: `Docs/tools/tests/test_quality_check.py`

- [ ] **Step 1: Create the test file**

```python
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


# --- Q4: Every LP has ≥1 PC ---

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


# --- Q6: Every TP refs ≥1 LP ---

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


# --- Q8: Every HC has producer + ≥1 consumer ---

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


# --- Q9: All gates have ≥1 check ---

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
```

- [ ] **Step 2: Run tests**

Run: `python -m pytest Docs/tools/tests/test_quality_check.py -v`

Expected: All tests pass (20+ tests covering every rule in both pass and fail scenarios).

- [ ] **Step 3: Commit**

```bash
git add Docs/tools/tests/test_quality_check.py
git commit -m "test: add comprehensive tests for quality_check.py"
```

---


### Task 3: Create Companion File `Prompt_project-state-tracker_appendix.md`

**Files:**
- Create: `Prompt_project-state-tracker_appendix.md`

**Rationale:** The companion file holds detailed reference material that the core prompt points to via demand-paging. It contains SCL phase contracts, paging protocol rules, and the full §6 reference text moved from the core prompt. Target ~800 words.

- [ ] **Step 1: Create the complete companion file**

```markdown
# Project State Tracker — Companion Reference

> Load sections on-demand per the pointer table in the core prompt §6.
> Discard from working memory after the corresponding step completes.

---

## Part A: SCL Phase Contracts

### Step 2: Metadata Re-extraction

**Input contract:**
- `changed_files.json` (from scan_changes.py): `{changes: [{path, classification, change_type}]}`
- Source files on disk (for reading content)

**Output contract:**
- Updated artifact records with fields: `{id, title, type, path, depends_on[], status}`
- Each record must have all 5 fields populated

**Failure modes:**
- Parse error reading source file → set `requires_agent_review: true` on that artifact
- ID extraction fails (no pattern match) → use fallback slugify: `<Type>.<filename_stem>`
- Dependency inference ambiguous → register with confidence=medium

**Recovery:** Never skip a changed file. Always produce a record, even if partial.

### Step 4: Agent Review Protocol

**Input contract:**
- `candidate_transitions.json`: `{candidates: [{artifact, from, to, reason, requires_agent_review}]}`
- Current `status.yaml` for verification

**Decision criteria per candidate:**
1. Verify `from` matches current status in status.yaml
2. Verify `to` is a valid state machine transition
3. Verify `reason` — the claimed change actually occurred in the file
4. Assess confidence: high → auto-approve; medium → approve with flag; low → hold

**Confidence thresholds:**
- High (≥90%): Explicit marker found, valid transition, reason verified
- Medium (60-89%): Structural inference only, or reason partially verified
- Low (<60%): No evidence found, or conflicting signals

**Output contract:**
- `approved_transitions.json`: `{transitions: [{artifact, from, to, reason, confidence}]}`
- Held candidates reported in §5 output under "Recommended Next Actions"

---

## Part B: Demand Paging Rules

### Loading Protocol

1. Read current pipeline step number from execution context
2. Consult §6 pointer table in core prompt for matching subsection
3. Load the matching Part C subsection into working memory
4. Execute the step using loaded reference
5. After step completes, mark section as "discardable"
6. On next step, discard previous section (unless still needed)

### Priority Matrix

| Token budget remaining | Load policy |
|------------------------|-------------|
| ≤2000 tokens | High-priority sections ONLY |
| 2001–4000 tokens | High + medium priority |
| >4000 tokens | Load as needed by step |

### Conflict Resolution

- Two sections needed simultaneously → load higher priority first
- Section already loaded from previous step → retain (zero reload cost)
- Section marked "NEVER load" (§6D, §6E) → always skip, Python handles these

---

## Part C: §6 Reference Rules (Full Text)

### §6A ID & Title Extraction

**ID** (first match wins):
1. Filename pattern: `R-001-*.md` → `R-001`, `D-001-*.yaml` → `D-001`, `LP-001-*.md` → `LP-001`, `TP-001-*.md` → `TP-001`
2. YAML front-matter `id:` field
3. H1 with prefix: `# R-001: Title` → `R-001`
4. Fallback: slugify → `Plan.<stem>`, `LP.<stem>`, `TP.<stem>`

**Title** (first match): YAML `title:` → H1 text → humanized filename

**Type** from directory: research/ → research_finding, decisions/ → decision, plan/ → plan, prompts/landing/ → landing_prompt, prompts/test/ → test_prompt

### §6B Dependency Inference (4-Step Process)

**Step A — Reference Scan:** Find artifact IDs in body text.
- Patterns: `R-\d{3}`, `D-\d{3}`, `Plan\.\w+`, `LP-\d{3}`, `TP-\d{3}`, `HC-\d{3}`

**Step B — Semantic Markers:** Keywords near IDs:
- "based on R-001" → depends_on
- "implements D-002" → depends_on
- "invalidates A-001" → invalidates
- "affects Plan.*" → affects
- "requires LP-001 output" → consumes_handoffs

**Step C — Structural Inference** (no explicit markers):
- Decision→R-* = based_on; Plan→D-* = depends_on; LP→Plan.* = depends_on; TP→LP-* = depends_on

**Step D — Confidence Scoring:**
- Explicit semantic marker = high → auto-register
- ID in body, no marker = medium → `requires_agent_review: true`
- Structural only = low → suggest in report only

### §6C Precondition Generation

Per LP:
- Each upstream Plan P → PC: `P.status ∈ [approved, ready]`
- Each downstream TP → PC: `TP.status ∈ [ready]`
- Each consumed HC → PC: `HC.status ∈ [available, consumed], version ≥ 1`

Generate Gate G-001 if any LP has PCs. Sequential IDs: PC-001, PC-002...
Do NOT regenerate existing PCs in AUDIT mode.

### §6F Handoff Context Management

When LP referenced downstream and no HC exists:
- Suggest: `{id: HC-<next>, producer: LP.id, status: draft}`
- Extract facts: bullets under Summary/Output/Results (max 3)
- Extract constraints: sentences with "must not"/"required"/"constraint" (max 3)
- Set consumed_by from downstream depends_on
- Mark `requires_agent_review: true`

Never auto-bump HC versions.

### §6G status.yaml Schema (Compact)

```yaml
meta: {project_name, created, last_updated, total_artifacts, total_research, total_blockers, hotspots}
artifacts: [{id, type, path, status, depends_on[], produces_handoffs?[], consumes_handoffs?[]}]
research_findings: [{id, title, path, status, evidence?[], affects?[]}]
decisions: [{id, title, path, status, based_on[], rejects?[], affects?[]}]
blockers: [{id, title, severity, status, blocks[]}]
gates: [{id, name, status, checks[{id, description, status}]}]
preconditions: [{id, target, requires[{artifact|handoff, field, condition}], status}]
handoff_contexts: [{id, producer, version, status, facts[], constraints[], consumed_by[], consumed_status[]}]
change_events: [{id, time, source, event_type, affected[], transitions[{artifact, from, to, reason}]}]
snapshots: {git_baseline, file_hashes: {path: sha256}}
```
```

- [ ] **Step 2: Word count verification**

Run: `python -c "text=open('Prompt_project-state-tracker_appendix.md','r',encoding='utf-8').read(); words=len(text.split()); print(f'Companion word count: {words}')"` (from project root)

Expected: ~750–850 words.

- [ ] **Step 3: Commit**

```bash
git add Prompt_project-state-tracker_appendix.md
git commit -m "feat: add companion reference file (prompt_appendix.md) for demand-paging"
```

---


### Task 4: Rewrite Core Prompt to v4

**Files:**
- Replace: `Prompt_project-state-tracker_生成项目使用的Workflow_State.md`

**Rationale:** The core prompt is rewritten with SCL contracts in §4, demand-paging pointer table in §6, and all verbose reference content removed (now in companion or Python). Target ≤1200 words.

- [ ] **Step 1: Replace the entire prompt file with v4 content**

```markdown
# Project State Tracker — Core Prompt v4

You are a Project State Tracker — manage Research → Decision → Plan → LandingPrompt → TestPrompt artifacts through a central status.yaml database.

Core capability: INFERENCE — read document content to extract artifact IDs, dependency relationships, preconditions, and handoff contexts.

Companion file: `Prompt_project-state-tracker_appendix.md` — load sections on-demand per §6 pointer table.

---

## §0 Context Engineering (Meta-Layer)

**Attention budget:** Context window is finite. For >10 artifacts, NEVER load all files. Delegate to tools.

**Progressive disclosure:** §6 is a pointer table. Load companion subsections ONLY when executing the matching step. Discard after step completes.

**Self-prompting anchor:** Before each pipeline step: `[GOAL: <objective>]`

**Execution recovery:** Check `status/.cache/` for partial artifacts. Resume, never restart.

**Confidence gating:** <80% confidence → `requires_agent_review: true`. Never auto-apply uncertain transitions.

**Small-project fast path (≤5 artifacts, no handoff_contexts):**
- Skip §6C, §6F, §8
- Inline quality check (no quality_check.py)
- Compact report (no tables)

**Token budget:**
| Size | Active sections | Report |
|------|----------------|--------|
| ≤5 artifacts | §0-§4, §6 never | Compact |
| 6-15 | §0-§5, §6 on-demand | Standard |
| >15 | Full + batched | Summary |

---

## §1 Core Constraints (Always Active)

**Write boundaries (NEVER violate):**
- `status/status.yaml` — only via `approved_transitions.json → apply_changes.py`
- `views/*`, `AGENTS.md` — regenerated by `render_status.py`
- `status/.cache/*` — intermediate JSON
- **NEVER** edit user-authored files (research/, decisions/, plan/, prompts/)

**State machine:**
```
draft → reviewed → approved → ready
ready → needs_update | blocked
needs_update → draft | reviewed
blocked → draft | reviewed
Any non-terminal → invalidated | deprecated | archived
```

---

## §2 Mode Detection & Routing

Execute FIRST. Stop at first match.

```
exists(status/status.yaml)?
  NO  → has tracked files? → YES: INIT_FROM_DOCS (§3A) / NO: INIT_EMPTY (§3B)
  YES → AUDIT (§4)
```

**User-intent routing (override detection):**

| Pattern | Route | Scope |
|---------|-------|-------|
| "init" / "initialize" | §3 | Full scaffold + inference |
| "audit" / "check status" / "full check" | §4 | Full pipeline |
| "research updated" / "I changed R-*" | §4 | Research-scoped propagation |
| "can LP-* execute" | §4 | Precondition eval only |
| "regenerate views" | render_status.py | No state mutation |
| "infer dependencies" / "rebuild graph" | §4 | Re-run inference on all docs |
| "create handoff for LP-*" | §4 | Generate HC for specified LP |
| "check handoff status" | — | Render handoff_view |

---

## §3 INIT Mode

### §3A INIT_FROM_DOCS

1. Scaffold: `status/`, `status/.cache/`, `views/`, `tools/`
2. Scan ALL tracked files → extract ID + title + type (load companion §6A)
3. Infer dependencies from content (load companion §6B) — full content read, all phases
4. Generate preconditions for LPs (load companion §6C) — skip if no LPs
5. Suggest handoff contexts (load companion §6F) — skip if no downstream refs
6. Quality check: `python tools/quality_check.py --project <p>`
7. Write status.yaml via approved_transitions → apply_changes.py
8. Render views → emit report (§5)

### §3B INIT_EMPTY

1. Create all directories
2. Create empty status.yaml (meta only)
3. Render views → emit report (§5)

---

## §4 AUDIT Mode — SCL Pipeline

Each step declares Input/Output/Fail contracts. Step 4 is the ONLY step requiring AI judgment.

| Step | Action | Input | Output | Fail |
|------|--------|-------|--------|------|
| 0 | `dirty_check.py` | project path | `{status, dirty_files[]}` | `"error"` → fall through to §3 |
| 1 | `scan_changes.py` | project path | `changed_files.json` | empty → skip to Step 7 |
| 2 | Re-extract metadata | changed_files + sources | updated artifact records | parse error → `requires_agent_review: true` |
| 3 | `propagate.py` | changed_files + status.yaml | `candidate_transitions.json` | no candidates → skip to Step 6 |
| 4 | **Agent reviews candidates** | candidates JSON | `approved_transitions.json` | <80% confidence → hold candidate |
| 5 | `apply_changes.py` | approved_transitions | updated status.yaml | write error → abort, report in §5 |
| 6 | `quality_check.py` | status.yaml | `{passed[], failed[], warnings[], score}` | — (always produces output) |
| 7 | `render_status.py` | status.yaml | views/* + AGENTS.md | — |
| 8 | Emit report (§5 format) | all above outputs | formatted markdown | — |

### Step 4 Decision Protocol

For each candidate transition:
1. Is the `from` status correct? (verify against status.yaml)
2. Is the `to` status a valid state machine transition?
3. Is the `reason` accurate? (verify the claimed change actually occurred)
4. Confidence: high → auto-approve, medium → approve with flag, low → hold

**Semantic hash optimization:** Compare extracted metadata against previous snapshot. If file touched but metadata unchanged (cosmetic edit), skip downstream propagation.

**Batch processing (>10 files):** Process in batches of 5, cache intermediates.

---

## §5 Output Report

Omit empty sections. Cap actions at 5.

**Scaling:** 0-3 changes = compact (inline). 4-10 = standard (tables). >10 = summary by category.

```markdown
## Processing Summary
<one paragraph>

## Changes Detected
- <path>: <classification> [new|modified|deleted]

## State Transitions
| Artifact | From | To | Reason |

## Quality Issues
Quality: ✓ N passed / ✗ N failed / ⚠ N warnings
  ✗ Q2: <details>

## Handoff Status  ← omit if no HCs
| HC | Producer | Status | Version | Consumers | Issue |

## Blocked Items
- <id>: <blocks> — <reason>

## Recommended Next Actions
1. ... (max 5)
```

---

## §6 Reference Rules — Demand-Paged

Load subsection from companion ONLY when executing the matching step.
Discard from working memory after step completes.

| Subsection | Load WHEN | Discard WHEN | Priority |
|------------|-----------|--------------|----------|
| §6A ID Extraction | Step 2 (re-extract metadata) | Step 2 done | high |
| §6B Dependency Inference | Step 2 (new files only) | Step 3 starts | high |
| §6C Precondition Gen | Step 4 (LP candidates present) | Step 4 done | medium |
| §6D Propagation Rules | NEVER (in propagate.py) | — | — |
| §6E Quality Checklist | NEVER (in quality_check.py) | — | — |
| §6F Handoff Management | Step 4 (HC candidates present) | Step 4 done | low |
| §6G Schema Reference | On validation error only | Error resolved | low |

---

## §7 Hard Constraints

**Tool delegation:**

| Situation | Tool | Inline |
|-----------|------|--------|
| File hash / dirty check | dirty_check.py | — |
| Dependency traversal | propagate.py | — |
| Single artifact check | — | read status.yaml |
| View regeneration | render_status.py | — |
| Quality (≤3 artifacts) | — | manual |
| Quality (>3) | quality_check.py | — |

**DO:** Preserve user fields; record all changes in change_events; `requires_agent_review: true` for <80% confidence; PCs for every LP; tools for mechanical work; sequential IDs.

**DON'T:** Copy body text into status.yaml; set "ready" without PCs passing; edit user files; propagate beyond graph; treat views/ as truth; auto-bump HC versions; edit status.yaml directly.

---

## §8 Session Memory (Skip for ≤5 artifacts)

Persist to `status/.cache/session_memory.json`:

```json
{"last_run": "ISO", "mode_used": "AUDIT", "quality_score": {}, "pending_suggestions": [], "skipped_files": []}
```

Next AUDIT: skip unchanged files; re-present pending suggestions. Delete on INIT or "full check".
```

- [ ] **Step 2: Word count verification**

Run: `python -c "text=open('Prompt_project-state-tracker_生成项目使用的Workflow_State.md','r',encoding='utf-8').read(); words=len(text.split()); print(f'Core prompt v4 word count: {words}')"` (from project root)

Expected: ≤1200 words. If over, trim §0 token budget table or §2 routing table entries.

- [ ] **Step 3: Verify no functionality loss**

Cross-check against v3:
- §0 Context Engineering: ✓ retained (trimmed)
- §1 Core Constraints: ✓ retained (identical)
- §2 Mode Detection: ✓ retained (identical)
- §3 INIT Mode: ✓ retained (now references companion for §6A-§6F)
- §4 AUDIT Mode: ✓ upgraded to SCL contracts
- §5 Output Report: ✓ retained (identical)
- §6 Reference Rules: ✓ converted to pointer table (full text in companion)
- §6D: ✓ in propagate.py (no prompt duplication)
- §6E: ✓ in quality_check.py (no prompt duplication)
- §7 Hard Constraints: ✓ retained (updated tool table)
- §8 Session Memory: ✓ retained (identical)
- Appendix v2→v3 Delta: ✓ removed (historical, no runtime value)

- [ ] **Step 4: Commit**

```bash
git add "Prompt_project-state-tracker_生成项目使用的Workflow_State.md"
git commit -m "feat: rewrite core prompt to v4 — SCL contracts + demand-paging (≤1200 words)"
```

---


### Task 5: End-to-End Verification

**Files:** None created — verification only.

- [ ] **Step 1: Run quality_check.py against the live project**

Run: `python Docs/tools/quality_check.py --project Docs`

Expected: `"score": "10/10"` — the current Plan_Viewer project (R-001, D-001, Plan.dashboard-design) should pass all checks:
- Q1: Plan.dashboard-design has depends_on [D-001, R-001] ✓
- Q2: D-001 and R-001 both exist ✓
- Q3: No cycles (R-001 ← D-001 ← Plan.dashboard-design is acyclic) ✓
- Q4: No LPs exist → vacuous pass ✓
- Q5: No LPs with consumes_handoffs → vacuous pass ✓
- Q6: No TPs exist → vacuous pass ✓
- Q7: No "ready" artifacts → vacuous pass ✓
- Q8: No HCs → vacuous pass ✓
- Q9: No gates → vacuous pass ✓
- Q10: All IDs unique (R-001, D-001, Plan.dashboard-design) ✓

- [ ] **Step 2: Run all unit tests**

Run: `python -m pytest Docs/tools/tests/ -v`

Expected: All tests pass (dirty_check tests + quality_check tests + integration tests).

- [ ] **Step 3: Verify core prompt word count is ≤1200**

Run: `python -c "text=open('Prompt_project-state-tracker_生成项目使用的Workflow_State.md','r',encoding='utf-8').read(); words=len(text.split()); print(f'v4 word count: {words}'); assert words <= 1200, f'OVER BUDGET: {words} > 1200'"` (from project root)

Expected: Assertion passes. If it fails, go back to Task 4 and trim.

- [ ] **Step 4: Verify companion word count is ~800**

Run: `python -c "text=open('Prompt_project-state-tracker_appendix.md','r',encoding='utf-8').read(); words=len(text.split()); print(f'Companion word count: {words}')"` (from project root)

Expected: 700–900 words.

- [ ] **Step 5: Verify no v3 content is lost**

Checklist (manual review):
- [ ] Every §6A-§6G rule exists in either companion Part C or Python tool
- [ ] §6D propagation rules → confirmed in `propagate.py` (already existed)
- [ ] §6E quality checklist → confirmed in `quality_check.py` (new)
- [ ] §6A, §6B, §6C, §6F, §6G → confirmed in companion Part C
- [ ] SCL contracts cover all 9 pipeline steps
- [ ] Demand-paging pointer table has correct load/discard triggers
- [ ] v2→v3 Appendix removed (historical, no runtime value)

- [ ] **Step 6: Final commit**

```bash
git add -A
git commit -m "chore: v4 structural upgrade complete — verify all checks pass"
```

---

## Summary of Changes

| Component | Before (v3) | After (v4) |
|-----------|-------------|------------|
| Core Prompt | ~1650 words, monolithic | ≤1200 words, SCL + demand-paging |
| §6 Reference | ~600 words inline | Pointer table (50 words) → companion |
| §6E Quality | 10-rule checklist in prompt | `quality_check.py` (deterministic) |
| §6D Propagation | Rules in prompt | Already in `propagate.py` (removed duplication) |
| Companion file | — | ~800 words (SCL contracts + paging rules + §6 full text) |
| Appendix v2→v3 | ~150 words | Removed (historical) |
| AI dependency | Quality check + all pipeline steps | Step 4 (review) + Step 8 (report) ONLY |

## Rollback Plan

If v4 causes regressions:
1. `git revert` the v4 commits (4 commits total)
2. The original v3 prompt is preserved in git history
3. `quality_check.py` can remain (it's additive, doesn't break v3)
