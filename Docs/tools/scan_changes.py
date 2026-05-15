#!/usr/bin/env python3
"""Scan project for changed files and write status/.cache/changed_files.json."""

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import yaml


TRACKED_DIRS = ["research", "decisions", "plan", "prompts"]


def classify_path(rel_path: str) -> str:
    """Classify a file path into an artifact type."""
    parts = rel_path.replace("\\", "/").split("/")
    if parts[0] == "research":
        return "research"
    elif parts[0] == "decisions":
        return "decision"
    elif parts[0] == "plan":
        return "plan"
    elif parts[0] == "prompts" and len(parts) > 1:
        if parts[1] == "landing":
            return "landing"
        elif parts[1] == "test":
            return "test"
    return "other"


def hash_file(path: Path) -> str:
    """SHA-256 hash of file contents."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def is_git_repo(project: Path) -> bool:
    """Check if project is inside a git repo."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            cwd=str(project), capture_output=True, text=True
        )
        return result.returncode == 0
    except FileNotFoundError:
        return False


def scan_git(project: Path, baseline: str | None) -> list[dict]:
    """Scan using git diff."""
    changes = []
    cmd = ["git", "status", "-s"]
    result = subprocess.run(cmd, cwd=str(project), capture_output=True, text=True)
    for line in result.stdout.strip().splitlines():
        if not line.strip():
            continue
        status_code = line[:2].strip()
        file_path = line[3:].strip().strip('"')
        classification = classify_path(file_path)
        if classification == "other":
            continue
        if status_code in ("D", "DD"):
            change_type = "deleted"
        elif status_code in ("?", "??", "A"):
            change_type = "new"
        else:
            change_type = "modified"
        changes.append({
            "path": file_path.replace("\\", "/"),
            "classification": classification,
            "change_type": change_type
        })
    return changes


def scan_hashes(project: Path, old_hashes: dict) -> list[dict]:
    """Scan by comparing file hashes."""
    changes = []
    current_files = set()

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
                current_files.add(rel_path)
                current_hash = hash_file(full_path)
                old_hash = old_hashes.get(rel_path)
                if old_hash is None:
                    changes.append({
                        "path": rel_path,
                        "classification": classify_path(rel_path),
                        "change_type": "new"
                    })
                elif current_hash != old_hash:
                    changes.append({
                        "path": rel_path,
                        "classification": classify_path(rel_path),
                        "change_type": "modified"
                    })

    # Check for deleted files
    for old_path in old_hashes:
        if old_path not in current_files:
            classification = classify_path(old_path)
            if classification != "other":
                changes.append({
                    "path": old_path,
                    "classification": classification,
                    "change_type": "deleted"
                })

    return changes


def main():
    parser = argparse.ArgumentParser(description="Scan project for changes")
    parser.add_argument("--project", required=True, help="Project root path")
    args = parser.parse_args()

    project = Path(args.project).resolve()
    status_file = project / "status" / "status.yaml"

    if not status_file.exists():
        print(f"ERROR: {status_file} not found. Run init first.", file=sys.stderr)
        sys.exit(1)

    with open(status_file, "r", encoding="utf-8") as f:
        status = yaml.safe_load(f)

    snapshots = status.get("snapshots", {})

    if is_git_repo(project):
        baseline = snapshots.get("git_baseline")
        changes = scan_git(project, baseline)
    else:
        old_hashes = snapshots.get("file_hashes", {}) or {}
        changes = scan_hashes(project, old_hashes)

    cache_dir = project / "status" / ".cache"
    cache_dir.mkdir(parents=True, exist_ok=True)

    output_path = cache_dir / "changed_files.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump({"changes": changes, "total": len(changes)}, f, indent=2, ensure_ascii=False)

    print(f"Scan complete: {len(changes)} change(s) detected.")
    print(f"Output: {output_path}")


if __name__ == "__main__":
    main()
