#!/usr/bin/env python3
"""Pre-check guard: detect dirty files via two-level mtime + hash strategy."""

import argparse
import hashlib
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


TRACKED_DIRS = ["research", "decisions", "plan", "prompts"]


def is_external_path(path: str) -> bool:
    """Check if an artifact path is external (managed by ELP, not file-scannable)."""
    return path.startswith("external:")


def hash_file(path: Path) -> str:
    """SHA-256 hash of file contents."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def collect_current_files(project: Path) -> dict[str, float]:
    """Collect all tracked files with their mtime. Returns {rel_path: mtime}."""
    current = {}
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
                current[rel_path] = os.path.getmtime(full_path)
    return current


def load_snapshot(snapshot_path: Path) -> dict:
    """Load file_snapshot.json. Returns empty structure if not found."""
    if not snapshot_path.exists():
        return {"last_check": None, "files": {}}
    with open(snapshot_path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_snapshot(snapshot_path: Path, current_files: dict[str, float], project: Path) -> None:
    """Save updated snapshot with current mtime and hash for all tracked files."""
    files_data = {}
    for rel_path, mtime in current_files.items():
        full_path = project / rel_path.replace("/", os.sep)
        files_data[rel_path] = {
            "mtime": mtime,
            "hash": hash_file(full_path)
        }
    snapshot = {
        "last_check": datetime.now(timezone.utc).isoformat(),
        "files": files_data
    }
    snapshot_path.parent.mkdir(parents=True, exist_ok=True)
    with open(snapshot_path, "w", encoding="utf-8") as f:
        json.dump(snapshot, f, indent=2, ensure_ascii=False)


def dirty_check(project: Path) -> dict:
    """
    Two-level dirty check:
      Level 1: mtime comparison (fast, no file reads)
      Level 2: hash comparison (only for mtime-changed files)

    Returns result dict with status, dirty_files, checked_files, elapsed_ms.
    """
    start = time.perf_counter()

    snapshot_path = project / "status" / ".cache" / "file_snapshot.json"
    snapshot = load_snapshot(snapshot_path)
    old_files = snapshot.get("files", {})

    current_files = collect_current_files(project)
    dirty_files = []

    # Level 1 + 2: Check existing and modified files
    for rel_path, current_mtime in current_files.items():
        if rel_path not in old_files:
            # New file — no need for hash check
            dirty_files.append({"path": rel_path, "change_type": "new"})
        else:
            old_entry = old_files[rel_path]
            old_mtime = old_entry.get("mtime", 0)
            if abs(current_mtime - old_mtime) > 0.001:
                # Level 2: mtime changed, verify with hash
                full_path = project / rel_path.replace("/", os.sep)
                current_hash = hash_file(full_path)
                old_hash = old_entry.get("hash", "")
                if current_hash != old_hash:
                    dirty_files.append({"path": rel_path, "change_type": "modified"})

    # Check for deleted files
    for rel_path in old_files:
        if rel_path not in current_files:
            dirty_files.append({"path": rel_path, "change_type": "deleted"})

    # Update snapshot
    save_snapshot(snapshot_path, current_files, project)

    elapsed_ms = round((time.perf_counter() - start) * 1000, 1)

    status = "dirty" if dirty_files else "clean"
    return {
        "status": status,
        "dirty_files": dirty_files,
        "checked_files": len(current_files),
        "elapsed_ms": elapsed_ms
    }


def main():
    parser = argparse.ArgumentParser(description="Pre-check guard for project-state-tracker")
    parser.add_argument("--project", required=True, help="Project root path")
    args = parser.parse_args()

    project = Path(args.project).resolve()
    status_file = project / "status" / "status.yaml"

    if not status_file.exists():
        print(json.dumps({"error": "status.yaml not found", "status": "error"}))
        sys.exit(1)

    try:
        result = dirty_check(project)
        print(json.dumps(result, ensure_ascii=False))
        sys.exit(0)
    except Exception as e:
        print(json.dumps({"error": str(e), "status": "error"}))
        sys.exit(2)


if __name__ == "__main__":
    main()
