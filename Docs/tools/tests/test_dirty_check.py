#!/usr/bin/env python3
"""Tests for dirty_check.py."""

import json
import os
import tempfile
import time
from pathlib import Path

import pytest

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
    status_dir = tmp_path / "status"
    status_dir.mkdir()
    (status_dir / "status.yaml").write_text("meta:\n  project_name: test\n", encoding="utf-8")
    (status_dir / ".cache").mkdir()

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
    dirty_check(project_dir)
    result = dirty_check(project_dir)
    assert result["status"] == "clean"
    assert result["dirty_files"] == []


def test_modified_file_detected(project_dir):
    """Modifying a file should be detected as dirty."""
    dirty_check(project_dir)

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
    dirty_check(project_dir)

    (project_dir / "research" / "R-002-new.md").write_text("# New", encoding="utf-8")

    result = dirty_check(project_dir)
    assert result["status"] == "dirty"
    dirty_paths = [d["path"] for d in result["dirty_files"]]
    assert "research/R-002-new.md" in dirty_paths
    new_entry = [d for d in result["dirty_files"] if d["path"] == "research/R-002-new.md"][0]
    assert new_entry["change_type"] == "new"


def test_deleted_file_detected(project_dir):
    """Deleting a file should be detected."""
    dirty_check(project_dir)

    os.remove(project_dir / "plan" / "P-001-test.md")

    result = dirty_check(project_dir)
    assert result["status"] == "dirty"
    dirty_paths = [d["path"] for d in result["dirty_files"]]
    assert "plan/P-001-test.md" in dirty_paths
    del_entry = [d for d in result["dirty_files"] if d["path"] == "plan/P-001-test.md"][0]
    assert del_entry["change_type"] == "deleted"


def test_touch_without_content_change_is_clean(project_dir):
    """Touching a file (mtime changes but content same) should NOT be dirty."""
    dirty_check(project_dir)

    research_file = project_dir / "research" / "R-001-test.md"
    content = research_file.read_text(encoding="utf-8")
    time.sleep(0.05)
    research_file.write_text(content, encoding="utf-8")

    result = dirty_check(project_dir)
    assert result["status"] == "clean"
    assert result["dirty_files"] == []


def test_missing_tracked_dir_no_error(project_dir):
    """Missing tracked directory (e.g., prompts/) should not cause errors."""
    result = dirty_check(project_dir)
    assert result["status"] == "dirty"
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


def test_no_status_yaml_collect_empty():
    """collect_current_files handles empty/missing dirs gracefully."""
    with tempfile.TemporaryDirectory() as tmp:
        project = Path(tmp)
        files = collect_current_files(project)
        assert files == {}
