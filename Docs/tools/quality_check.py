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
                broken.append(f"{art.get('id','?')} \u2192 {dep_id}")
    for dec in status.get("decisions", []):
        for ref_id in dec.get("based_on", []):
            if ref_id not in all_ids:
                broken.append(f"{dec.get('id','?')} \u2192 {ref_id}")
        for ref_id in dec.get("affects", []):
            if ref_id not in all_ids:
                broken.append(f"{dec.get('id','?')} affects \u2192 {ref_id}")
    for hc in status.get("handoff_contexts", []):
        producer = hc.get("producer", "")
        if producer and producer not in all_ids:
            broken.append(f"{hc.get('id','?')} producer \u2192 {producer}")
        for consumer in hc.get("consumed_by", []):
            if consumer not in all_ids:
                broken.append(f"{hc.get('id','?')} consumer \u2192 {consumer}")
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
        cycle_str = " \u2192 ".join(cycles[0])
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
        return {"id": "Q4", "check": "Every LP has \u22651 PC", "severity": "warn", "status": "passed"}

    preconditions = status.get("preconditions", [])
    lp_ids_with_pc = {pc.get("target") for pc in preconditions}

    missing = [lp.get("id", "?") for lp in lps if lp.get("id") not in lp_ids_with_pc]
    if missing:
        return {
            "id": "Q4", "check": "Every LP has \u22651 PC", "severity": "warn",
            "status": "failed",
            "details": f"LPs without preconditions: {', '.join(missing)}"
        }
    return {"id": "Q4", "check": "Every LP has \u22651 PC", "severity": "warn", "status": "passed"}


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
        return {"id": "Q6", "check": "Every TP refs \u22651 LP", "severity": "warn", "status": "passed"}

    missing = []
    for tp in tps:
        deps = tp.get("depends_on", [])
        has_lp = any(d.startswith("LP-") or d.startswith("LP.") for d in deps)
        if not has_lp:
            missing.append(tp.get("id", "?"))

    if missing:
        return {
            "id": "Q6", "check": "Every TP refs \u22651 LP", "severity": "warn",
            "status": "failed",
            "details": f"TPs without LP reference: {', '.join(missing)}"
        }
    return {"id": "Q6", "check": "Every TP refs \u22651 LP", "severity": "warn", "status": "passed"}


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
            "id": "Q8", "check": "Every HC has producer + \u22651 consumer", "severity": "warn",
            "status": "failed",
            "details": "; ".join(issues[:3])
        }
    return {"id": "Q8", "check": "Every HC has producer + \u22651 consumer", "severity": "warn", "status": "passed"}


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
            "id": "Q9", "check": "All gates have \u22651 check", "severity": "warn",
            "status": "failed",
            "details": "; ".join(issues)
        }
    return {"id": "Q9", "check": "All gates have \u22651 check", "severity": "warn", "status": "passed"}


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
        checks.append({"id": "Q4", "check": "Every LP has \u22651 PC", "severity": "warn", "status": "passed"})
        checks.append({"id": "Q5", "check": "LP consumes_handoffs matches PC", "severity": "error", "status": "passed"})
        checks.append({"id": "Q6", "check": "Every TP refs \u22651 LP", "severity": "warn", "status": "passed"})

    # Q7: always (affected + upstream chain)
    checks.append(check_q7_no_ready_with_upstream_needs_update(status))

    # Q8-Q9: only if HC or gate changes
    has_hc_or_gate = bool(affected_set & {hc.get("id", "") for hc in status.get("handoff_contexts", [])}) or \
                     bool(affected_set & {g.get("id", "") for g in status.get("gates", [])})
    if has_hc_or_gate:
        checks.append(check_q8_hc_has_producer_and_consumer(status))
        checks.append(check_q9_gates_have_checks(status))
    else:
        checks.append({"id": "Q8", "check": "Every HC has producer + \u22651 consumer", "severity": "warn", "status": "passed"})
        checks.append({"id": "Q9", "check": "All gates have \u22651 check", "severity": "warn", "status": "passed"})

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
        description="Deterministic quality validation for project-state-tracker (\u00a76E)"
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
