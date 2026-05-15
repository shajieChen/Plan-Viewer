#!/usr/bin/env python3
"""Propagate changes through the dependency graph and emit candidate transitions."""

import argparse
import json
import sys
from pathlib import Path

import yaml


def find_artifact_by_path(status: dict, path: str) -> dict | None:
    """Find an artifact whose path matches."""
    for art in status.get("artifacts", []):
        if art.get("path", "").replace("\\", "/") == path.replace("\\", "/"):
            return art
    for rf in status.get("research_findings", []):
        if rf.get("path", "").replace("\\", "/") == path.replace("\\", "/"):
            return rf
    return None


def find_dependents(status: dict, artifact_id: str) -> list[dict]:
    """Find all artifacts that depend on the given artifact_id."""
    dependents = []
    for art in status.get("artifacts", []):
        deps = art.get("depends_on", [])
        if artifact_id in deps:
            dependents.append(art)
    return dependents


def main():
    parser = argparse.ArgumentParser(description="Propagate changes through dependency graph")
    parser.add_argument("--project", required=True, help="Project root path")
    args = parser.parse_args()

    project = Path(args.project).resolve()
    status_file = project / "status" / "status.yaml"
    cache_dir = project / "status" / ".cache"
    changed_file = cache_dir / "changed_files.json"

    if not status_file.exists():
        print(f"ERROR: {status_file} not found.", file=sys.stderr)
        sys.exit(1)

    if not changed_file.exists():
        print(f"ERROR: {changed_file} not found. Run scan_changes.py first.", file=sys.stderr)
        sys.exit(1)

    with open(status_file, "r", encoding="utf-8") as f:
        status = yaml.safe_load(f)

    with open(changed_file, "r", encoding="utf-8") as f:
        changed_data = json.load(f)

    changes = changed_data.get("changes", [])
    candidates = []

    for change in changes:
        path = change["path"]
        classification = change["classification"]
        change_type = change["change_type"]

        artifact = find_artifact_by_path(status, path)

        if artifact is None and change_type != "deleted":
            # New file not registered — candidate for registration
            candidates.append({
                "artifact": path,
                "from": None,
                "to": "draft",
                "reason": f"New {classification} file detected: {path}",
                "source": path,
                "requires_agent_review": True,
                "op": "register"
            })
            continue

        if artifact is None:
            continue  # Deleted file with no artifact — skip

        art_id = artifact.get("id", path)
        current_status = artifact.get("status", "draft")

        if change_type == "deleted":
            candidates.append({
                "artifact": art_id,
                "from": current_status,
                "to": "deprecated",
                "reason": f"File deleted: {path}",
                "source": path,
                "requires_agent_review": True,
                "op": "transition"
            })
            continue

        # File modified — propagate based on classification
        if classification == "research":
            # Research updated → find dependent Plans and mark as needs_update
            dependents = find_dependents(status, art_id)
            for dep in dependents:
                dep_status = dep.get("status", "draft")
                if dep_status in ("ready", "approved", "reviewed"):
                    candidates.append({
                        "artifact": dep.get("id"),
                        "from": dep_status,
                        "to": "needs_update",
                        "reason": f"Upstream research '{art_id}' was modified",
                        "source": path,
                        "requires_agent_review": True,
                        "op": "transition"
                    })

        elif classification == "plan":
            # Plan updated → dependent LPs and TPs need update
            dependents = find_dependents(status, art_id)
            for dep in dependents:
                dep_status = dep.get("status", "draft")
                if dep_status in ("ready", "approved", "reviewed"):
                    candidates.append({
                        "artifact": dep.get("id"),
                        "from": dep_status,
                        "to": "needs_update",
                        "reason": f"Upstream plan '{art_id}' was modified",
                        "source": path,
                        "requires_agent_review": True,
                        "op": "transition"
                    })

        elif classification == "landing":
            # LP updated → dependent TPs need update
            dependents = find_dependents(status, art_id)
            for dep in dependents:
                dep_status = dep.get("status", "draft")
                if dep_status in ("ready", "approved", "reviewed"):
                    candidates.append({
                        "artifact": dep.get("id"),
                        "from": dep_status,
                        "to": "needs_update",
                        "reason": f"Upstream landing prompt '{art_id}' was modified",
                        "source": path,
                        "requires_agent_review": True,
                        "op": "transition"
                    })

        elif classification == "test":
            # TP updated — no downstream propagation by default
            pass

    # Check handoff contexts for stale producers
    for hc in status.get("handoff_contexts", []):
        producer_id = hc.get("producer")
        hc_id = hc.get("id")
        hc_status = hc.get("status", "available")
        # Check if producer was in the changed files
        for change in changes:
            producer_art = find_artifact_by_path(status, change["path"])
            if producer_art and producer_art.get("id") == producer_id:
                if hc_status == "available":
                    candidates.append({
                        "artifact": hc_id,
                        "from": "available",
                        "to": "stale",
                        "reason": f"Producer '{producer_id}' file was modified",
                        "source": change["path"],
                        "requires_agent_review": True,
                        "op": "handoff_stale"
                    })

    # Write candidates
    output_path = cache_dir / "candidate_transitions.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump({"candidates": candidates, "total": len(candidates)}, f, indent=2, ensure_ascii=False)

    print(f"Propagation complete: {len(candidates)} candidate transition(s).")
    print(f"Output: {output_path}")


if __name__ == "__main__":
    main()
