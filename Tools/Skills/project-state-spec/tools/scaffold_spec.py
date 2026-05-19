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
import subprocess
import sys
from pathlib import Path

# Make sibling _spec_helpers importable when the script is run directly.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _spec_helpers import (  # noqa: E402
    FileExistsRefuseError,
    StatusYamlMissingError,
    find_artifact_by_topic,
    load_status,
    next_id,
    safe_write,
    slugify,
    today_iso,
)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _topic_title(topic: str) -> str:
    """Convert kebab-case slug to Title Case for display."""
    return " ".join(word.capitalize() for word in topic.split("-"))


def _write_transitions_and_apply(
    pst_root: Path,
    transitions: list[dict],
    event_summary: str,
    event_type: str,
) -> None:
    """Write approved_transitions.json then invoke apply_changes.py.

    Raises subprocess.CalledProcessError on apply_changes failure.
    """
    cache_dir = pst_root / "status" / ".cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "event_summary": event_summary,
        "event_type": event_type,
        "transitions": transitions,
    }
    (cache_dir / "approved_transitions.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    apply_script = pst_root / "tools" / "apply_changes.py"
    if not apply_script.is_file():
        raise FileNotFoundError(
            f"apply_changes.py not found at {apply_script}. "
            "Run PST INIT to create the tools/ directory."
        )
    subprocess.run(
        [sys.executable, str(apply_script), "--project", str(pst_root)],
        check=True,
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
    if not args.r_content or not args.d_content:
        print("ERROR: --stage requirement requires --r-content and --d-content",
              file=sys.stderr)
        return 2

    pst_root = Path(args.pst_root)
    try:
        status = load_status(pst_root)
    except StatusYamlMissingError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    topic = slugify(args.topic)

    # Reuse existing ids if topic already has artifacts so safe_write detects
    # the collision and refuses (Property: idempotent without --force).
    existing_r = find_artifact_by_topic(status, topic, "research_finding")
    existing_d = find_artifact_by_topic(status, topic, "decision")
    r_id = existing_r["id"] if existing_r else next_id(status, "R")
    d_id = existing_d["id"] if existing_d else next_id(status, "D")
    title = _topic_title(topic)

    r_path_rel = f"research/{r_id}-{topic}.md"
    d_path_rel = f"decisions/{d_id}-{topic}.yaml"
    r_path = pst_root / r_path_rel
    d_path = pst_root / d_path_rel

    r_body = Path(args.r_content).read_text(encoding="utf-8")
    d_body = Path(args.d_content).read_text(encoding="utf-8")

    r_full = f"# {r_id}: {title}\n\n{r_body.lstrip()}"
    d_full = (
        f"id: {d_id}\n"
        f"title: \"{title}\"\n"
        f"status: draft\n"
        f"based_on: [{r_id}]\n"
        f"{d_body.lstrip()}"
    )

    try:
        safe_write(r_path, r_full, force=args.force)
        safe_write(d_path, d_full, force=args.force)
    except FileExistsRefuseError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    transitions = [
        {"artifact": r_id, "type": "research_finding",
         "from": None, "to": "draft",
         "path": r_path_rel,
         "reason": f"project-state-spec scaffold: requirement stage for {topic}",
         "source": "project-state-spec"},
        {"artifact": d_id, "type": "decision",
         "from": None, "to": "draft",
         "path": d_path_rel,
         "depends_on": [r_id],
         "reason": f"project-state-spec scaffold: requirement stage for {topic}",
         "source": "project-state-spec"},
    ]
    try:
        _write_transitions_and_apply(
            pst_root,
            transitions,
            event_summary=f"project-state-spec scaffold: requirement stage for {topic}",
            event_type="spec_scaffold",
        )
    except FileNotFoundError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        print("Files were written but status.yaml was not updated. "
              "Run PST AUDIT to reconcile.", file=sys.stderr)
        return 3
    except subprocess.CalledProcessError as exc:
        print(f"ERROR: apply_changes.py failed (exit {exc.returncode}): {exc}",
              file=sys.stderr)
        print("Files were written but status.yaml was not updated. "
              "Run PST AUDIT to reconcile.", file=sys.stderr)
        return 3

    print(json.dumps({
        "r_id": r_id, "d_id": d_id,
        "r_path": r_path_rel, "d_path": d_path_rel,
    }, ensure_ascii=False, indent=2))
    return 0


def cmd_design(args: argparse.Namespace) -> int:
    if not args.plan_content:
        print("ERROR: --stage design requires --plan-content", file=sys.stderr)
        return 2

    pst_root = Path(args.pst_root)
    try:
        status = load_status(pst_root)
    except StatusYamlMissingError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    topic = slugify(args.topic)

    r = find_artifact_by_topic(status, topic, "research_finding")
    d = find_artifact_by_topic(status, topic, "decision")
    if r is None or d is None:
        print(
            f"ERROR: No R/D found for topic {topic!r}. "
            "Run --stage requirement first.",
            file=sys.stderr,
        )
        return 2

    plan_id = f"Plan.{topic}"
    # Reuse existing Plan path on regeneration so cross-day --force does not
    # orphan the original file under a new date prefix.
    existing_plan = find_artifact_by_topic(status, topic, "plan")
    if existing_plan and isinstance(existing_plan.get("path"), str):
        plan_path_rel = existing_plan["path"]
    else:
        plan_path_rel = f"plan/{today_iso()}-{topic}-design.md"
    plan_path = pst_root / plan_path_rel

    title = _topic_title(topic)
    body = Path(args.plan_content).read_text(encoding="utf-8")
    full = (
        f"# {plan_id}: {title}\n\n"
        f"<!-- based_on: [{r['id']}, {d['id']}] -->\n\n"
        f"{body.lstrip()}"
    )

    try:
        safe_write(plan_path, full, force=args.force)
    except FileExistsRefuseError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    transitions = [{
        "artifact": plan_id, "type": "plan",
        "from": None, "to": "draft",
        "path": plan_path_rel,
        "depends_on": [r["id"], d["id"]],
        "reason": f"project-state-spec scaffold: design stage for {topic}",
        "source": "project-state-spec",
    }]
    try:
        _write_transitions_and_apply(
            pst_root,
            transitions,
            event_summary=f"project-state-spec scaffold: design stage for {topic}",
            event_type="spec_scaffold",
        )
    except FileNotFoundError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        print("Files were written but status.yaml was not updated. "
              "Run PST AUDIT to reconcile.", file=sys.stderr)
        return 3
    except subprocess.CalledProcessError as exc:
        print(f"ERROR: apply_changes.py failed (exit {exc.returncode}): {exc}",
              file=sys.stderr)
        print("Files were written but status.yaml was not updated. "
              "Run PST AUDIT to reconcile.", file=sys.stderr)
        return 3

    print(json.dumps({
        "plan_id": plan_id, "plan_path": plan_path_rel,
    }, ensure_ascii=False, indent=2))
    return 0


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
