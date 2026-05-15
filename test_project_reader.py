"""Tests for ProjectReader.read_status_yaml()."""

from pathlib import Path
import pytest
import yaml

from render_dashboard import ProjectReader, REQUIRED_STATUS_KEYS


@pytest.fixture
def valid_status_data():
    """Return a minimal valid status.yaml dict with all required keys."""
    return {
        "meta": {"project_name": "TestProject"},
        "artifacts": [],
        "research_findings": [],
        "decisions": [],
        "assumptions": [],
        "evidence": [],
        "blockers": [],
        "gates": [],
        "preconditions": [],
        "handoff_contexts": [],
        "change_events": [],
        "snapshots": {},
    }


@pytest.fixture
def project_with_status(tmp_path, valid_status_data):
    """Create a temporary project directory with a valid status.yaml."""
    status_dir = tmp_path / "status"
    status_dir.mkdir()
    status_file = status_dir / "status.yaml"
    status_file.write_text(yaml.dump(valid_status_data), encoding="utf-8")
    return tmp_path


class TestReadStatusYaml:
    """Tests for ProjectReader.read_status_yaml()."""

    def test_reads_valid_status_yaml(self, project_with_status, valid_status_data):
        """Successfully reads and returns a valid status.yaml."""
        reader = ProjectReader(project_with_status)
        result = reader.read_status_yaml()
        assert result["meta"]["project_name"] == "TestProject"
        # All required keys should be present
        for key in REQUIRED_STATUS_KEYS:
            assert key in result

    def test_file_not_found_raises_error(self, tmp_path):
        """Raises FileNotFoundError when status/status.yaml is missing."""
        reader = ProjectReader(tmp_path)
        with pytest.raises(FileNotFoundError) as exc_info:
            reader.read_status_yaml()
        # Error message should include the expected file path
        assert "status.yaml" in str(exc_info.value)
        assert str(tmp_path) in str(exc_info.value)

    def test_missing_keys_raises_value_error(self, tmp_path):
        """Raises ValueError listing all missing keys when schema validation fails."""
        status_dir = tmp_path / "status"
        status_dir.mkdir()
        # Write YAML with only 'meta' key - missing all others
        incomplete_data = {"meta": {"project_name": "Incomplete"}}
        (status_dir / "status.yaml").write_text(
            yaml.dump(incomplete_data), encoding="utf-8"
        )

        reader = ProjectReader(tmp_path)
        with pytest.raises(ValueError) as exc_info:
            reader.read_status_yaml()

        error_msg = str(exc_info.value)
        # Should list all missing keys (not just the first one)
        expected_missing = REQUIRED_STATUS_KEYS - {"meta"}
        for key in expected_missing:
            assert key in error_msg, f"Missing key '{key}' not listed in error"

    def test_malformed_yaml_raises_value_error(self, tmp_path):
        """Raises ValueError when YAML is malformed (unparseable)."""
        status_dir = tmp_path / "status"
        status_dir.mkdir()
        # Write invalid YAML content
        (status_dir / "status.yaml").write_text(
            "invalid: yaml: content:\n  - [unclosed bracket",
            encoding="utf-8",
        )

        reader = ProjectReader(tmp_path)
        with pytest.raises(ValueError) as exc_info:
            reader.read_status_yaml()
        error_msg = str(exc_info.value)
        assert "parse" in error_msg.lower() or "YAML" in error_msg

    def test_empty_yaml_raises_value_error(self, tmp_path):
        """Raises ValueError when YAML file is empty (parses to None)."""
        status_dir = tmp_path / "status"
        status_dir.mkdir()
        (status_dir / "status.yaml").write_text("", encoding="utf-8")

        reader = ProjectReader(tmp_path)
        with pytest.raises(ValueError) as exc_info:
            reader.read_status_yaml()
        # All keys should be reported as missing
        error_msg = str(exc_info.value)
        for key in REQUIRED_STATUS_KEYS:
            assert key in error_msg

    def test_extra_keys_are_allowed(self, tmp_path, valid_status_data):
        """Extra keys beyond the required set do not cause errors."""
        valid_status_data["extra_field"] = "some value"
        status_dir = tmp_path / "status"
        status_dir.mkdir()
        (status_dir / "status.yaml").write_text(
            yaml.dump(valid_status_data), encoding="utf-8"
        )

        reader = ProjectReader(tmp_path)
        result = reader.read_status_yaml()
        assert result["extra_field"] == "some value"

    def test_reads_real_project_status(self):
        """Reads the actual project's status.yaml (integration test)."""
        # Use the Docs directory as the project path since status.yaml is at Docs/status/status.yaml
        project_path = Path(__file__).resolve().parent / "Docs"
        reader = ProjectReader(project_path)
        result = reader.read_status_yaml()
        assert "meta" in result
        assert result["meta"]["project_name"] == "Plan_Viewer"
