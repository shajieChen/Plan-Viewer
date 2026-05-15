#!/usr/bin/env python3
"""Apply approved transitions to status.yaml."""

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import yaml


TRACKED_DIRS = ["research", "decisions", "plan", "prompts"]


def hash_file(path: Path) -> str:
    """SHA-256 hash of file contents."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def next_ce_id(change_events: list) -> str:
    """Generate next CE-xxx id."""
    max_num = 0
    for ce in change_events:
        ce_id = ce.get("id", "")
        if ce_id.startswith("CE-"):
            try:
                num = int(ce_id[3:])
                max_num = max(max_num, num)
            except ValueError:
                pass
    return f"CE-{max_num + 1:03d}"


def recompute_hashes(project: Path) -> dict:
    """Recompute file hashes for all tracked files."""
    hashes = {}
    for dir_name in TRACKED_DIRS:
        dir_path = project / dir_name
        if not dir_path.exists():
            continue
        for root, _, files in os.walk(dir_path):
            for fname in files:
                if fname.startswith("."):
                    continue
                full_path = Path(root) / fname
                rel_path = str(full_path.relative_to(project)).replace("\\", "/")
                hashes[rel_path] = hash_file(full_path)
    return hashes


def get_git_head(project: Path) -> str | None:
    """Get current git HEAD."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(project), capture_output=True, text=True
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except FileNotFoundError:
        pass
    return None


def main():
    parser = argparse.ArgumentParser(description="Apply approved transitions to status.yaml")
    parser.add_argument("--project", required=True, help="Project root path")
    args = parser.parse_args()

    project = Path(args.project).resolve()
    status_file = project / "status" / "status.yaml"
    cache_dir = project / "status" / ".cache"
    approved_file = cache_dir / "approved_transitions.json"

    if not status_file.exists():
        print(f"ERROR: {status_file} not found.", file=sys.stderr)
        sys.exit(1)

    if not approved_file.exists():
        print("No approved_transitions.json found. Nothing to apply.")
        sys.exit(0)

    with open(status_file, "r", encoding="utf-8") as f:
        status = yaml.safe_load(f)

    with open(approved_file, "r", encoding="utf-8") as f:
        approved_data = json.load(f)

    transitions = approved_data.get("transitions", [])
    if not transitions:
        print("No transitions to apply.")
        sys.exit(0)

    change_events = status.get("change_events", [])
    now = datetime.now(timezone.utc).isoformat()

    for t in transitions:
        op = t.get("op", "transition")
        artifact_id = t.get("artifact")
        to_status = t.get("to")
        reason = t.get("reason", "")
        source = t.get("source", "")

        ce_id = next_ce_id(change_events)

        if op == "register":
            # Register a new artifact
            new_art = {
                "id": t.get("new_id", artifact_id),
                "type": t.get("type", "plan"),
                "path": t.get("path", artifact_id),
                "status": to_status or "draft",
                "depends_on": t.get("depends_on", [])
            }
            if t.get("produces_handoffs"):
                new_art["produces_handoffs"] = t["produces_handoffs"]
            if t.get("consumes_handoffs"):
                new_art["consumes_handoffs"] = t["consumes_handoffs"]

            # Decide where to register
            art_type = t.get("type", "plan")
            if art_type == "research":
                status.setdefault("research_findings", []).append({
                    "id": new_art["id"],
                    "path": new_art["path"],
                    "title": t.get("title", new_art["id"]),
                    "status": new_art["status"]
                })
            else:
                status.setdefault("artifacts", []).append(new_art)

            change_events.append({
                "id": ce_id,
                "time": now,
                "source": source,
                "event_type": "register",
                "affected": [new_art["id"]],
                "transitions": [{"artifact": new_art["id"], "from": None, "to": to_status}],
                "reason": reason
            })

        elif op == "transition":
            # Find and update existing artifact
            found = False
            for art in status.get("artifacts", []):
                if art.get("id") == artifact_id:
                    old_status = art.get("status")
                    art["status"] = to_status
                    found = True
                    change_events.append({
                        "id": ce_id,
                        "time": now,
                        "source": source,
                        "event_type": "status_change",
                        "affected": [artifact_id],
                        "transitions": [{"artifact": artifact_id, "from": old_status, "to": to_status}],
                        "reason": reason
                    })
                    break
            if not found:
                for rf in status.get("research_findings", []):
                    if rf.get("id") == artifact_id:
                        old_status = rf.get("status")
                        rf["status"] = to_status
                        change_events.append({
                            "id": ce_id,
                            "time": now,
                            "source": source,
                            "event_type": "status_change",
                            "affected": [artifact_id],
                            "transitions": [{"artifact": artifact_id, "from": old_status, "to": to_status}],
                            "reason": reason
                        })
                        break

        elif op == "handoff_stale":
            for hc in status.get("handoff_contexts", []):
                if hc.get("id") == artifact_id:
                    old_status = hc.get("status")
                    hc["status"] = "stale"
                    change_events.append({
                        "id": ce_id,
                        "time": now,
                        "source": source,
                        "event_type": "handoff_stale",
                        "affected": [artifact_id],
                        "transitions": [{"artifact": artifact_id, "from": old_status, "to": "stale"}],
                        "reason": reason
                    })
                    break

        elif op == "handoff_version":
            for hc in status.get("handoff_contexts", []):
                if hc.get("id") == artifact_id:
                    hc["version"] = hc.get("version", 0) + 1
                    hc["status"] = "available"
                    # Reset consumed_status for all consumers
                    for cs in hc.get("consumed_status", []):
                        cs["status"] = "stale"
                    change_events.append({
                        "id": ce_id,
                        "time": now,
                        "source": source,
                        "event_type": "handoff_version_bump",
                        "affected": [artifact_id],
                        "transitions": [{"artifact": artifact_id, "from": "stale", "to": "available"}],
                        "reason": reason
                    })
                    break

        elif op == "handoff_consume":
            for hc in status.get("handoff_contexts", []):
                if hc.get("id") == artifact_id:
                    consumer_id = t.get("consumer")
                    for cs in hc.get("consumed_status", []):
                        if cs.get("consumer") == consumer_id:
                            cs["status"] = "consumed"
                            cs["consumed_version"] = hc.get("version", 1)
                            cs["consumed_at"] = now
                            break
                    change_events.append({
                        "id": ce_id,
                        "time": now,
                        "source": source,
                        "event_type": "handoff_consumed",
                        "affected": [artifact_id, consumer_id],
                        "transitions": [],
                        "reason": reason
                    })
                    break

    # Update meta
    status["change_events"] = change_events
    status["meta"]["last_updated"] = now
    status["meta"]["total_artifacts"] = len(status.get("artifacts", []))
    status["meta"]["total_research"] = len(status.get("research_findings", []))
    status["meta"]["total_blockers"] = len([b for b in status.get("blockers", []) if b.get("status") == "open"])

    # Recompute snapshots
    status["snapshots"]["file_hashes"] = recompute_hashes(project)
    git_head = get_git_head(project)
    if git_head:
        status["snapshots"]["git_baseline"] = git_head

    # Write atomically
    tmp_fd, tmp_path = tempfile.mkstemp(dir=str(project / "status"), suffix=".yaml")
    try:
        with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
            yaml.dump(status, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
        os.replace(tmp_path, str(status_file))
    except Exception:
        os.unlink(tmp_path)
        raise

    print(f"Applied {len(transitions)} transition(s) to status.yaml.")

    # Clean up approved file
    os.remove(str(approved_file))
    print("Removed approved_transitions.json.")


if __name__ == "__main__":
    main()
