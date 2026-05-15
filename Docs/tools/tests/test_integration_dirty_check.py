#!/usr/bin/env python3
"""Integration test: dirty_check → propagate pipeline."""

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest
import yaml


TOOLS_DIR = Path(__file__).parent.parent


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
        yaml.dump(status_yaml, default_flow_style=False, allow_unicode=True, sort_keys=False),
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


def test_first_run_detects_all_new(integration_project):
    """First dirty_check run should detect all files as new."""
    result = run_tool("dirty_check.py", integration_project)
    assert result.returncode == 0
    data = json.loads(result.stdout)
    assert data["status"] == "dirty"
    assert len(data["dirty_files"]) == 2  # R-001-test.md + P-001-test.md
    change_types = {d["change_type"] for d in data["dirty_files"]}
    assert change_types == {"new"}


def test_second_run_is_clean(integration_project):
    """Second run without changes should be clean."""
    run_tool("dirty_check.py", integration_project)
    result = run_tool("dirty_check.py", integration_project)
    assert result.returncode == 0
    data = json.loads(result.stdout)
    assert data["status"] == "clean"
    assert data["dirty_files"] == []


def test_modified_research_triggers_propagation(integration_project):
    """
    Full pipeline:
    1. Baseline dirty_check
    2. Modify research file
    3. dirty_check detects modification
    4. Write changed_files.json
    5. propagate.py generates candidate: Plan.test → needs_update
    """
    project = integration_project

    # Step 1: Baseline
    run_tool("dirty_check.py", project)

    # Step 2: Modify research file
    time.sleep(0.05)
    research_file = project / "research" / "R-001-test.md"
    research_file.write_text("# R-001: Test Research\nUpdated findings.", encoding="utf-8")

    # Step 3: Dirty check detects modification
    result = run_tool("dirty_check.py", project)
    assert result.returncode == 0
    data = json.loads(result.stdout)
    assert data["status"] == "dirty"
    assert len(data["dirty_files"]) == 1
    assert data["dirty_files"][0]["path"] == "research/R-001-test.md"
    assert data["dirty_files"][0]["change_type"] == "modified"

    # Step 4: Write changed_files.json (simulating what the agent does in PRE-CHECK step a)
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

    # Step 5: Run propagate
    result = run_tool("propagate.py", project)
    assert result.returncode == 0

    # Step 6: Verify candidate transitions
    candidates_file = cache_dir / "candidate_transitions.json"
    assert candidates_file.exists()
    candidates = json.loads(candidates_file.read_text(encoding="utf-8"))
    assert candidates["total"] >= 1

    # Plan.test should be marked needs_update because upstream R-001 changed
    plan_candidates = [c for c in candidates["candidates"] if c.get("artifact") == "Plan.test"]
    assert len(plan_candidates) == 1
    assert plan_candidates[0]["to"] == "needs_update"
    assert plan_candidates[0]["requires_agent_review"] is True


def test_new_file_detected_in_pipeline(integration_project):
    """Adding a new file should be detected by dirty_check."""
    project = integration_project

    # Baseline
    run_tool("dirty_check.py", project)

    # Add new research file
    (project / "research" / "R-002-new.md").write_text("# R-002: New Research", encoding="utf-8")

    # Dirty check
    result = run_tool("dirty_check.py", project)
    data = json.loads(result.stdout)
    assert data["status"] == "dirty"
    new_files = [d for d in data["dirty_files"] if d["change_type"] == "new"]
    assert len(new_files) == 1
    assert new_files[0]["path"] == "research/R-002-new.md"


def test_deleted_file_detected_in_pipeline(integration_project):
    """Deleting a file should be detected by dirty_check."""
    project = integration_project

    # Baseline
    run_tool("dirty_check.py", project)

    # Delete plan file
    os.remove(project / "plan" / "P-001-test.md")

    # Dirty check
    result = run_tool("dirty_check.py", project)
    data = json.loads(result.stdout)
    assert data["status"] == "dirty"
    deleted = [d for d in data["dirty_files"] if d["change_type"] == "deleted"]
    assert len(deleted) == 1
    assert deleted[0]["path"] == "plan/P-001-test.md"


def test_no_status_yaml_returns_error(tmp_path):
    """dirty_check should return error status when status.yaml is missing."""
    result = run_tool("dirty_check.py", tmp_path)
    assert result.returncode == 1
    data = json.loads(result.stdout)
    assert data["status"] == "error"
    assert "status.yaml" in data.get("error", "")
