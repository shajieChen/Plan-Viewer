"""Tests for project_store.py persistence functions."""

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from project_store import load_projects, save_projects, PROJECTS_FILE


@pytest.fixture
def tmp_projects_file(tmp_path):
    """Patch PROJECTS_FILE to use a temporary directory."""
    tmp_file = tmp_path / "projects.json"
    with patch("project_store.PROJECTS_FILE", tmp_file):
        yield tmp_file


class TestLoadProjects:
    """Tests for load_projects()."""

    def test_creates_file_when_missing(self, tmp_projects_file):
        """When projects.json doesn't exist, creates it with empty list."""
        assert not tmp_projects_file.exists()

        result = load_projects()

        assert result == []
        assert tmp_projects_file.exists()
        data = json.loads(tmp_projects_file.read_text(encoding="utf-8"))
        assert data == {"projects": []}

    def test_reads_existing_projects(self, tmp_projects_file):
        """When projects.json exists with projects, returns them."""
        content = {"projects": [{"path": "Q:\\Project1"}, {"path": "Q:\\Project2"}]}
        tmp_projects_file.write_text(json.dumps(content), encoding="utf-8")

        result = load_projects()

        assert len(result) == 2
        assert result[0]["path"] == "Q:\\Project1"
        assert result[1]["path"] == "Q:\\Project2"

    def test_returns_empty_list_when_no_projects_key(self, tmp_projects_file):
        """When file exists but has no 'projects' key, returns []."""
        tmp_projects_file.write_text("{}", encoding="utf-8")

        result = load_projects()

        assert result == []

    def test_reads_empty_projects_list(self, tmp_projects_file):
        """When file has empty projects list, returns []."""
        content = {"projects": []}
        tmp_projects_file.write_text(json.dumps(content), encoding="utf-8")

        result = load_projects()

        assert result == []


class TestSaveProjects:
    """Tests for save_projects()."""

    def test_writes_utf8_with_indent(self, tmp_projects_file):
        """File is written in UTF-8 with indentation."""
        projects = [{"path": "Q:\\MyProject"}]

        save_projects(projects)

        raw = tmp_projects_file.read_text(encoding="utf-8")
        # Should be indented (multi-line)
        assert "\n" in raw
        data = json.loads(raw)
        assert data["projects"][0]["path"] == "Q:\\MyProject"

    def test_normalizes_relative_paths_to_absolute(self, tmp_projects_file):
        """Relative paths are resolved to absolute paths."""
        projects = [{"path": "."}]

        save_projects(projects)

        data = json.loads(tmp_projects_file.read_text(encoding="utf-8"))
        saved_path = data["projects"][0]["path"]
        # Should be an absolute path
        assert Path(saved_path).is_absolute()

    def test_preserves_absolute_paths(self, tmp_projects_file):
        """Absolute paths remain absolute after save."""
        abs_path = "Q:\\PortNotes\\UE_Iris"
        projects = [{"path": abs_path}]

        save_projects(projects)

        data = json.loads(tmp_projects_file.read_text(encoding="utf-8"))
        assert data["projects"][0]["path"] == abs_path

    def test_saves_multiple_projects(self, tmp_projects_file):
        """Multiple projects are all saved correctly."""
        projects = [
            {"path": "Q:\\Project1"},
            {"path": "Q:\\Project2"},
            {"path": "Q:\\Project3"},
        ]

        save_projects(projects)

        data = json.loads(tmp_projects_file.read_text(encoding="utf-8"))
        assert len(data["projects"]) == 3

    def test_saves_empty_list(self, tmp_projects_file):
        """Saving empty list creates valid JSON with empty projects array."""
        save_projects([])

        data = json.loads(tmp_projects_file.read_text(encoding="utf-8"))
        assert data == {"projects": []}

    def test_overwrites_existing_file(self, tmp_projects_file):
        """Saving overwrites previous content completely."""
        # Write initial content
        save_projects([{"path": "Q:\\Old"}])
        # Overwrite
        save_projects([{"path": "Q:\\New"}])

        data = json.loads(tmp_projects_file.read_text(encoding="utf-8"))
        assert len(data["projects"]) == 1
        assert data["projects"][0]["path"] == "Q:\\New"


class TestRoundTrip:
    """Tests for load/save round-trip behavior."""

    def test_save_then_load_preserves_data(self, tmp_projects_file):
        """Data saved can be loaded back identically."""
        projects = [{"path": "Q:\\PortNotes\\UE_Iris"}, {"path": "Q:\\Another"}]

        save_projects(projects)
        loaded = load_projects()

        assert len(loaded) == 2
        assert loaded[0]["path"] == "Q:\\PortNotes\\UE_Iris"
        assert loaded[1]["path"] == "Q:\\Another"
