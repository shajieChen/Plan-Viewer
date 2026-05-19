#!/usr/bin/env python3
"""project-state-spec scaffold script.

Owns all side effects for the project-state-spec skill:
  - ID allocation (R-NNN, D-NNN, LP-NNN, TP-NNN, Plan.<topic>)
  - File writes under PST conventions (research/, decisions/, plan/, prompts/)
  - approved_transitions.json construction
  - tools/apply_changes.py invocation

Usage: see argparse help.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Make sibling _spec_helpers importable when the script is run directly.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _spec_helpers import (  # noqa: E402
    StatusYamlMissingError,
    find_artifact_by_topic,
    load_status,
)


# ---------------------------------------------------------------------------
# Stage handlers
# ---------------------------------------------------------------------------


def cmd_status(args: argparse.Namespace) -> int:
    pst_root = Path(args.pst_root)
    try:
        status = load_status(pst_root)
    except StatusYamlMissingError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    r = find_artifact_by_topic(status, args.topic, "research_finding")
    d = find_artifact_by_topic(status, args.topic, "decision")
    p = find_artifact_by_topic(status, args.topic, "plan")

    lp_count = 0
    tp_count = 0
    if p is not None:
        plan_id = p["id"]
        for entry in status.get("artifacts", []) or []:
            if not isinstance(entry, dict):
                continue
            depends = entry.get("depends_on") or []
            if entry.get("type") == "landing_prompt" and plan_id in depends:
                lp_count += 1
            if entry.get("type") == "test_prompt":
                # TP depends on its LP; check whether ANY LP under this plan is in chain.
                for dep in depends:
                    parent = next(
                        (a for a in status.get("artifacts", []) or []
                         if isinstance(a, dict) and a.get("id") == dep
                         and a.get("type") == "landing_prompt"
                         and plan_id in (a.get("depends_on") or [])),
                        None,
                    )
                    if parent is not None:
                        tp_count += 1
                        break

    req_complete = r is not None and d is not None
    design_complete = req_complete and p is not None
    tasks_complete = (
        design_complete and lp_count > 0 and lp_count == tp_count
    )

    if not req_complete:
        next_stage = "requirement"
    elif not design_complete:
        next_stage = "design"
    elif not tasks_complete:
        next_stage = "tasks"
    else:
        next_stage = "done"

    out = {
        "topic": args.topic,
        "stages": {
            "requirement": {
                "complete": req_complete,
                "r_id": r["id"] if r else None,
                "d_id": d["id"] if d else None,
            },
            "design": {
                "complete": design_complete,
                "plan_id": p["id"] if p else None,
            },
            "tasks": {
                "complete": tasks_complete,
                "lp_count": lp_count,
                "tp_count": tp_count,
            },
        },
        "next_stage": next_stage,
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


def cmd_requirement(args: argparse.Namespace) -> int:
    raise NotImplementedError("requirement stage — implemented in Task 7")


def cmd_design(args: argparse.Namespace) -> int:
    raise NotImplementedError("design stage — implemented in Task 8")


def cmd_tasks(args: argparse.Namespace) -> int:
    raise NotImplementedError("tasks stage — implemented in Task 9")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="scaffold_spec.py",
        description="project-state-spec scaffold script.",
    )
    p.add_argument("--stage", required=True,
                   choices=["requirement", "design", "tasks", "status"])
    p.add_argument("--topic", required=True,
                   help="kebab-case slug uniquely identifying this spec")
    p.add_argument("--pst-root", required=True,
                   help="PST project root (directory containing status/status.yaml)")
    p.add_argument("--force", action="store_true",
                   help="overwrite existing files for this stage")
    p.add_argument("--r-content", help="path to tmpfile with R markdown body (stage=requirement)")
    p.add_argument("--d-content", help="path to tmpfile with D yaml body (stage=requirement)")
    p.add_argument("--plan-content", help="path to tmpfile with Plan markdown body (stage=design)")
    p.add_argument("--tasks-manifest", help="path to tmpfile with tasks JSON manifest (stage=tasks)")
    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.stage == "status":
        return cmd_status(args)
    if args.stage == "requirement":
        return cmd_requirement(args)
    if args.stage == "design":
        return cmd_design(args)
    if args.stage == "tasks":
        return cmd_tasks(args)
    parser.error(f"unknown stage: {args.stage}")
    return 2


if __name__ == "__main__":
    sys.exit(main())
