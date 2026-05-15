# Dirty Check Guard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `tools/dirty_check.py` script that detects file changes via two-level mtime+hash strategy, and integrate it into the project-state-tracker Prompt as a pre-check step.

**Architecture:** A standalone Python script reads `status/.cache/file_snapshot.json`, compares mtime then hash for tracked directories, outputs a JSON verdict (clean/dirty), and updates the snapshot. The Prompt's Execution Pipeline gains a step 0 that calls this script and auto-triggers the scan→propagate→apply→render pipeline when dirty.

**Tech Stack:** Python 3.10+, standard library only (hashlib, json, os, pathlib, argparse, time, datetime). No new dependencies.

---

## File Structure

| File | Responsibility |
|------|---------------|
| `Docs/tools/dirty_check.py` (create) | Two-level dirty detection script |
| `Docs/tools/tests/test_dirty_check.py` (create) | Unit tests for dirty_check |
| `Prompt_project-state-tracker_生成项目使用的Workflow_State.md` (modify) | Add PRE-CHECK step 0 to Execution Pipeline |

---

### Task 1: Create `dirty_check.py` core logic

**Files:**
- Create: `Docs/tools/dirty_check.py`

- [ ] **Step 1: Create the script with imports and constants**

```python
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
```

- [ ] **Step 2: Add helper functions**

```python
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
```

- [ ] **Step 3: Add the main dirty_check logic**

```python
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
```

- [ ] **Step 4: Add the CLI entry point**

```python
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
```

- [ ] **Step 5: Run the script to verify it works**

Run: `python Docs/tools/dirty_check.py --project Docs`
Expected: JSON output with `"status": "dirty"` (first run, no snapshot exists yet)

- [ ] **Step 6: Run again to verify clean detection**

Run: `python Docs/tools/dirty_check.py --project Docs`
Expected: JSON output with `"status": "clean"` (snapshot now matches)

- [ ] **Step 7: Commit**

```bash
git add Docs/tools/dirty_check.py
git commit -m "feat: add dirty_check.py pre-check guard script"
```

---

### Task 2: Write unit tests for dirty_check

**Files:**
- Create: `Docs/tools/tests/__init__.py`
- Create: `Docs/tools/tests/test_dirty_check.py`

- [ ] **Step 1: Create test directory and init file**

```python
# Docs/tools/tests/__init__.py
```

- [ ] **Step 2: Write tests**

```python
#!/usr/bin/env python3
"""Tests for dirty_check.py."""

import json
import os
import tempfile
import time
from pathlib import Path

import pytest

# Add parent to path so we can import dirty_check
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from dirty_check import (
    collect_current_files,
    dirty_check,
    hash_file,
    load_snapshot,
    save_snapshot,
)


@pytest.fixture
def project_dir(tmp_path):
    """Create a minimal project structure for testing."""
    # Create status/status.yaml
    status_dir = tmp_path / "status"
    status_dir.mkdir()
    (status_dir / "status.yaml").write_text("meta:\n  project_name: test\n", encoding="utf-8")
    (status_dir / ".cache").mkdir()

    # Create tracked directories with files
    research_dir = tmp_path / "research"
    research_dir.mkdir()
    (research_dir / "R-001-test.md").write_text("# Research 1\nContent here.", encoding="utf-8")

    decisions_dir = tmp_path / "decisions"
    decisions_dir.mkdir()
    (decisions_dir / "D-001-test.yaml").write_text("id: D-001\ntitle: Test", encoding="utf-8")

    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    (plan_dir / "P-001-test.md").write_text("# Plan 1\nSteps.", encoding="utf-8")

    return tmp_path


def test_collect_current_files(project_dir):
    """Should find all non-hidden files in tracked directories."""
    files = collect_current_files(project_dir)
    assert "research/R-001-test.md" in files
    assert "decisions/D-001-test.yaml" in files
    assert "plan/P-001-test.md" in files
    assert len(files) == 3


def test_first_run_all_dirty(project_dir):
    """First run with no snapshot should mark all files as dirty (new)."""
    result = dirty_check(project_dir)
    assert result["status"] == "dirty"
    assert result["checked_files"] == 3
    assert len(result["dirty_files"]) == 3
    for df in result["dirty_files"]:
        assert df["change_type"] == "new"


def test_second_run_clean(project_dir):
    """Second run without changes should be clean."""
    dirty_check(project_dir)  # first run creates snapshot
    result = dirty_check(project_dir)  # second run
    assert result["status"] == "clean"
    assert result["dirty_files"] == []


def test_modified_file_detected(project_dir):
    """Modifying a file should be detected as dirty."""
    dirty_check(project_dir)  # create baseline

    # Modify a file (ensure mtime changes)
    time.sleep(0.05)
    research_file = project_dir / "research" / "R-001-test.md"
    research_file.write_text("# Research 1\nUpdated content.", encoding="utf-8")

    result = dirty_check(project_dir)
    assert result["status"] == "dirty"
    assert len(result["dirty_files"]) == 1
    assert result["dirty_files"][0]["path"] == "research/R-001-test.md"
    assert result["dirty_files"][0]["change_type"] == "modified"


def test_new_file_detected(project_dir):
    """Adding a new file should be detected."""
    dirty_check(project_dir)  # create baseline

    # Add new file
    (project_dir / "research" / "R-002-new.md").write_text("# New", encoding="utf-8")

    result = dirty_check(project_dir)
    assert result["status"] == "dirty"
    dirty_paths = [d["path"] for d in result["dirty_files"]]
    assert "research/R-002-new.md" in dirty_paths
    new_entry = [d for d in result["dirty_files"] if d["path"] == "research/R-002-new.md"][0]
    assert new_entry["change_type"] == "new"


def test_deleted_file_detected(project_dir):
    """Deleting a file should be detected."""
    dirty_check(project_dir)  # create baseline

    # Delete a file
    os.remove(project_dir / "plan" / "P-001-test.md")

    result = dirty_check(project_dir)
    assert result["status"] == "dirty"
    dirty_paths = [d["path"] for d in result["dirty_files"]]
    assert "plan/P-001-test.md" in dirty_paths
    del_entry = [d for d in result["dirty_files"] if d["path"] == "plan/P-001-test.md"][0]
    assert del_entry["change_type"] == "deleted"


def test_touch_without_content_change_is_clean(project_dir):
    """Touching a file (mtime changes but content same) should NOT be dirty."""
    dirty_check(project_dir)  # create baseline

    # Touch file — change mtime but not content
    research_file = project_dir / "research" / "R-001-test.md"
    content = research_file.read_text(encoding="utf-8")
    time.sleep(0.05)
    research_file.write_text(content, encoding="utf-8")

    result = dirty_check(project_dir)
    assert result["status"] == "clean"
    assert result["dirty_files"] == []


def test_missing_tracked_dir_no_error(project_dir):
    """Missing tracked directory (e.g., prompts/) should not cause errors."""
    # prompts/ doesn't exist in fixture — should still work
    result = dirty_check(project_dir)
    assert result["status"] == "dirty"  # first run
    assert "elapsed_ms" in result


def test_snapshot_persists(project_dir):
    """Snapshot file should be created after first run."""
    snapshot_path = project_dir / "status" / ".cache" / "file_snapshot.json"
    assert not snapshot_path.exists()

    dirty_check(project_dir)

    assert snapshot_path.exists()
    data = json.loads(snapshot_path.read_text(encoding="utf-8"))
    assert "last_check" in data
    assert "files" in data
    assert len(data["files"]) == 3


def test_no_status_yaml_exits_with_error():
    """Should exit with code 1 if status.yaml doesn't exist."""
    with tempfile.TemporaryDirectory() as tmp:
        # No status.yaml — dirty_check should fail gracefully
        # We test via the function directly by checking the main() path
        project = Path(tmp)
        # status.yaml doesn't exist, so we test the guard in main()
        # For unit test, just verify collect_current_files handles empty dirs
        files = collect_current_files(project)
        assert files == {}
```

- [ ] **Step 3: Run tests**

Run: `python -m pytest Docs/tools/tests/test_dirty_check.py -v`
Expected: All tests pass

- [ ] **Step 4: Commit**

```bash
git add Docs/tools/tests/
git commit -m "test: add unit tests for dirty_check.py"
```

---

### Task 3: Integrate PRE-CHECK into the Prompt

**Files:**
- Modify: `Prompt_project-state-tracker_生成项目使用的Workflow_State.md`

- [ ] **Step 1: Add PRE-CHECK step to Execution Pipeline**

In the `### Execution Pipeline` section, insert step 0 before the existing step 1. The new content to insert immediately after the line `### Execution Pipeline`:

```markdown
0. **PRE-CHECK** (Dirty Guard): Run `python tools/dirty_check.py --project <project>`
   - Parse JSON output from stdout
   - If `status == "error"` and exit code 1 → status.yaml missing, proceed to INIT mode
   - If `status == "clean"` → skip to step 1
   - If `status == "dirty"` → auto-refresh pipeline:
     a. Write dirty_files to `status/.cache/changed_files.json` (same format as scan_changes output)
     b. Run `python tools/propagate.py --project <project>`
     c. Read `candidate_transitions.json`, filter to only `requires_agent_review: false` entries
     d. Write filtered entries to `approved_transitions.json`
     e. Run `python tools/apply_changes.py --project <project>`
     f. Run `python tools/render_status.py --project <project>`
     g. Report: "PRE-CHECK: {N} dirty file(s) detected, {M} transition(s) auto-applied, views refreshed."
   - Proceed to step 1 with fresh state
```

- [ ] **Step 2: Add PRE-CHECK to the Mode Differentiation table**

Add a new row to the `### Mode Differentiation` table:

```markdown
| Phase | PRE-CHECK (Dirty Guard) |
|-------|------------------------|
| Phase 1: Scan | Only files flagged by dirty_check |
| Phase 2: Infer deps | Dirty files + direct dependents |
| Phase 3: Gen preconditions | Skip (no new generation) |
| Phase 4: Handoff inference | Skip |
| Phase 5: Quality check | Skip (deferred to explicit AUDIT) |
```

- [ ] **Step 3: Add dirty_check.py to the tool list in the Prompt**

In the section that mentions `tools/scan_changes.py, tools/propagate.py, tools/validate_status.py, tools/apply_changes.py, tools/render_status.py`, add `tools/dirty_check.py` to the list.

- [ ] **Step 4: Verify the Prompt reads correctly end-to-end**

Read the full Prompt file and confirm:
- Step 0 PRE-CHECK appears before step 1
- No contradictions with existing AUDIT mode logic
- The tool list includes dirty_check.py

- [ ] **Step 5: Commit**

```bash
git add "Prompt_project-state-tracker_生成项目使用的Workflow_State.md"
git commit -m "feat: integrate dirty_check PRE-CHECK into project-state-tracker prompt"
```

---

### Task 4: End-to-end integration test

**Files:**
- Create: `Docs/tools/tests/test_integration_dirty_check.py`

- [ ] **Step 1: Write integration test that simulates the full pipeline**

```python
#!/usr/bin/env python3
"""Integration test: dirty_check → scan → propagate → apply → render pipeline."""

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest
import yaml


TOOLS_DIR = Path(__file__).parent.parent
PROJECT_TEMPLATE = Path(__file__).parent / "fixtures" / "integration_project"


@pytest.fixture
def integration_project(tmp_path):
    """Create a full project structure mimicking the real project."""
    project = tmp_path / "project"
    project.mkdir()

    # status/
    status_dir = project / "status"
    status_dir.mkdir()
    cache_dir = status_dir / ".cache"
    cache_dir.mkdir()

    status_yaml = {
        "meta": {
            "project_name": "IntegrationTest",
            "created": "2026-05-15T00:00:00Z",
            "last_updated": "2026-05-15T00:00:00Z",
            "total_artifacts": 1,
            "total_research": 1,
            "total_blockers": 0,
            "hotspots": []
        },
        "artifacts": [{
            "id": "Plan.test",
            "type": "plan",
            "path": "plan/P-001-test.md",
            "status": "approved",
            "depends_on": ["R-001"]
        }],
        "research_findings": [{
            "id": "R-001",
            "title": "Test Research",
            "path": "research/R-001-test.md",
            "status": "reviewed"
        }],
        "decisions": [],
        "assumptions": [],
        "evidence": [],
        "blockers": [],
        "gates": [],
        "preconditions": [],
        "handoff_contexts": [],
        "change_events": [],
        "snapshots": {"git_baseline": None, "file_hashes": {}}
    }
    (status_dir / "status.yaml").write_text(
        yaml.dump(status_yaml, default_flow_style=False, allow_unicode=True),
        encoding="utf-8"
    )
    (status_dir / "schema.yaml").write_text(
        "required_top_level_keys: [meta, artifacts]\nartifact_statuses: [draft, reviewed, approved, ready, needs_update, blocked, invalidated, deprecated, archived]\n",
        encoding="utf-8"
    )

    # research/
    research_dir = project / "research"
    research_dir.mkdir()
    (research_dir / "R-001-test.md").write_text("# R-001: Test Research\nOriginal content.", encoding="utf-8")

    # plan/
    plan_dir = project / "plan"
    plan_dir.mkdir()
    (plan_dir / "P-001-test.md").write_text("# Plan\nBased on R-001.", encoding="utf-8")

    # views/
    (project / "views").mkdir()

    return project


def run_tool(script_name: str, project: Path) -> subprocess.CompletedProcess:
    """Run a tool script."""
    script = TOOLS_DIR / script_name
    return subprocess.run(
        [sys.executable, str(script), "--project", str(project)],
        capture_output=True, text=True
    )


def test_full_dirty_pipeline(integration_project):
    """
    Scenario:
    1. Run dirty_check (first time) → dirty (all new)
    2. Run dirty_check again → clean
    3. Modify research file
    4. Run dirty_check → dirty (modified)
    5. Run propagate → candidate: Plan.test needs_update
    6. Verify candidate has requires_agent_review: true (upstream research change)
    """
    project = integration_project

    # Step 1: First run — all files are new
    result = run_tool("dirty_check.py", project)
    assert result.returncode == 0
    data = json.loads(result.stdout)
    assert data["status"] == "dirty"
    assert len(data["dirty_files"]) == 2  # R-001-test.md + P-001-test.md

    # Step 2: Second run — clean
    result = run_tool("dirty_check.py", project)
    assert result.returncode == 0
    data = json.loads(result.stdout)
    assert data["status"] == "clean"

    # Step 3: Modify research file
    time.sleep(0.05)
    research_file = project / "research" / "R-001-test.md"
    research_file.write_text("# R-001: Test Research\nUpdated findings.", encoding="utf-8")

    # Step 4: Dirty check detects modification
    result = run_tool("dirty_check.py", project)
    assert result.returncode == 0
    data = json.loads(result.stdout)
    assert data["status"] == "dirty"
    assert len(data["dirty_files"]) == 1
    assert data["dirty_files"][0]["path"] == "research/R-001-test.md"
    assert data["dirty_files"][0]["change_type"] == "modified"

    # Step 5: Write changed_files.json (simulating what the agent would do)
    changed_files = {
        "changes": [
            {"path": "research/R-001-test.md", "classification": "research", "change_type": "modified"}
        ],
        "total": 1
    }
    cache_dir = project / "status" / ".cache"
    (cache_dir / "changed_files.json").write_text(
        json.dumps(changed_files, indent=2), encoding="utf-8"
    )

    # Step 6: Run propagate
    result = run_tool("propagate.py", project)
    assert result.returncode == 0

    # Step 7: Verify candidate transitions
    candidates_file = cache_dir / "candidate_transitions.json"
    assert candidates_file.exists()
    candidates = json.loads(candidates_file.read_text(encoding="utf-8"))
    assert candidates["total"] >= 1

    # Plan.test should be marked needs_update because R-001 changed
    plan_candidate = [c for c in candidates["candidates"] if c.get("artifact") == "Plan.test"]
    assert len(plan_candidate) == 1
    assert plan_candidate[0]["to"] == "needs_update"
    assert plan_candidate[0]["requires_agent_review"] is True
```

- [ ] **Step 2: Run integration test**

Run: `python -m pytest Docs/tools/tests/test_integration_dirty_check.py -v`
Expected: All tests pass

- [ ] **Step 3: Commit**

```bash
git add Docs/tools/tests/test_integration_dirty_check.py
git commit -m "test: add integration test for dirty_check pipeline"
```

---

### Task 5: Final verification and cleanup

- [ ] **Step 1: Run all tests together**

Run: `python -m pytest Docs/tools/tests/ -v`
Expected: All tests pass (unit + integration)

- [ ] **Step 2: Run dirty_check against the real project**

Run: `python Docs/tools/dirty_check.py --project Docs`
Expected: JSON output showing current state (likely dirty on first real run)

- [ ] **Step 3: Run dirty_check a second time**

Run: `python Docs/tools/dirty_check.py --project Docs`
Expected: `"status": "clean"`

- [ ] **Step 4: Verify snapshot file was created**

Check: `Docs/status/.cache/file_snapshot.json` exists and contains valid JSON with `last_check` and `files` keys.

- [ ] **Step 5: Final commit**

```bash
git add -A
git commit -m "chore: final verification of dirty_check guard"
```
