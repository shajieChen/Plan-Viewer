"""Tests for ProjectReader.validate_artifacts() and validate_dependencies()."""

from pathlib import Path

import pytest

from render_dashboard import (
    ProjectReader,
    VALID_STATUSES,
    VALID_TYPES,
    VALID_DEP_TYPES,
)


@pytest.fixture
def reader(tmp_path):
    """Create a ProjectReader instance for testing validation methods."""
    return ProjectReader(tmp_path)


class TestValidateArtifacts:
    """Tests for ProjectReader.validate_artifacts()."""

    def test_valid_artifacts_pass(self, reader):
        """Artifacts with valid status and type pass without error."""
        artifacts = [
            {"id": "art-1", "status": "draft", "type": "plan"},
            {"id": "art-2", "status": "ready", "type": "landing_prompt"},
            {"id": "art-3", "status": "archived", "type": "test_prompt"},
        ]
        reader.validate_artifacts(artifacts)  # Should not raise

    def test_all_valid_statuses_accepted(self, reader):
        """Every valid status value is accepted."""
        for status in VALID_STATUSES:
            artifacts = [{"id": f"art-{status}", "status": status, "type": "plan"}]
            reader.validate_artifacts(artifacts)  # Should not raise

    def test_all_valid_types_accepted(self, reader):
        """Every valid type value is accepted."""
        for art_type in VALID_TYPES:
            artifacts = [{"id": f"art-{art_type}", "status": "draft", "type": art_type}]
            reader.validate_artifacts(artifacts)  # Should not raise

    def test_invalid_status_raises_value_error(self, reader):
        """Invalid status raises ValueError identifying artifact ID and value."""
        artifacts = [{"id": "art-bad", "status": "unknown_status", "type": "plan"}]
        with pytest.raises(ValueError) as exc_info:
            reader.validate_artifacts(artifacts)
        error_msg = str(exc_info.value)
        assert "art-bad" in error_msg
        assert "unknown_status" in error_msg

    def test_invalid_type_raises_value_error(self, reader):
        """Invalid type raises ValueError identifying artifact ID and value."""
        artifacts = [{"id": "art-bad", "status": "draft", "type": "invalid_type"}]
        with pytest.raises(ValueError) as exc_info:
            reader.validate_artifacts(artifacts)
        error_msg = str(exc_info.value)
        assert "art-bad" in error_msg
        assert "invalid_type" in error_msg

    def test_empty_status_raises_value_error(self, reader):
        """Empty status string raises ValueError."""
        artifacts = [{"id": "art-empty", "status": "", "type": "plan"}]
        with pytest.raises(ValueError):
            reader.validate_artifacts(artifacts)

    def test_empty_type_raises_value_error(self, reader):
        """Empty type string raises ValueError."""
        artifacts = [{"id": "art-empty", "status": "draft", "type": ""}]
        with pytest.raises(ValueError):
            reader.validate_artifacts(artifacts)

    def test_empty_list_passes(self, reader):
        """Empty artifact list passes validation."""
        reader.validate_artifacts([])  # Should not raise

    def test_first_invalid_artifact_raises(self, reader):
        """Validation stops at the first invalid artifact."""
        artifacts = [
            {"id": "art-good", "status": "draft", "type": "plan"},
            {"id": "art-bad", "status": "INVALID", "type": "plan"},
            {"id": "art-also-bad", "status": "nope", "type": "plan"},
        ]
        with pytest.raises(ValueError) as exc_info:
            reader.validate_artifacts(artifacts)
        assert "art-bad" in str(exc_info.value)


class TestValidateDependencies:
    """Tests for ProjectReader.validate_dependencies()."""

    def test_valid_dependencies_pass(self, reader):
        """Dependencies with valid types and existing IDs pass."""
        valid_ids = {"art-1", "art-2", "research-1", "decision-1"}
        dependencies = [
            {"from_id": "art-1", "to_id": "art-2", "dep_type": "requires"},
            {"from_id": "art-2", "to_id": "research-1", "dep_type": "implements"},
            {"from_id": "art-1", "to_id": "decision-1", "dep_type": "verifies"},
        ]
        reader.validate_dependencies(dependencies, valid_ids)  # Should not raise

    def test_all_valid_dep_types_accepted(self, reader):
        """Every valid dependency type is accepted."""
        valid_ids = {"a", "b"}
        for dep_type in VALID_DEP_TYPES:
            deps = [{"from_id": "a", "to_id": "b", "dep_type": dep_type}]
            reader.validate_dependencies(deps, valid_ids)  # Should not raise

    def test_invalid_dep_type_raises_value_error(self, reader):
        """Invalid dep_type raises ValueError identifying the source ID."""
        valid_ids = {"art-1", "art-2"}
        deps = [{"from_id": "art-1", "to_id": "art-2", "dep_type": "bad_type"}]
        with pytest.raises(ValueError) as exc_info:
            reader.validate_dependencies(deps, valid_ids)
        error_msg = str(exc_info.value)
        assert "art-1" in error_msg
        assert "bad_type" in error_msg

    def test_unresolved_from_id_raises_value_error(self, reader):
        """from_id not in valid_ids raises ValueError."""
        valid_ids = {"art-2"}
        deps = [{"from_id": "art-missing", "to_id": "art-2", "dep_type": "requires"}]
        with pytest.raises(ValueError) as exc_info:
            reader.validate_dependencies(deps, valid_ids)
        error_msg = str(exc_info.value)
        assert "art-missing" in error_msg

    def test_unresolved_to_id_raises_value_error(self, reader):
        """to_id not in valid_ids raises ValueError identifying source and target."""
        valid_ids = {"art-1"}
        deps = [{"from_id": "art-1", "to_id": "art-missing", "dep_type": "requires"}]
        with pytest.raises(ValueError) as exc_info:
            reader.validate_dependencies(deps, valid_ids)
        error_msg = str(exc_info.value)
        assert "art-1" in error_msg
        assert "art-missing" in error_msg

    def test_empty_dependencies_pass(self, reader):
        """Empty dependency list passes validation."""
        reader.validate_dependencies([], set())  # Should not raise

    def test_empty_dep_type_raises_value_error(self, reader):
        """Empty dep_type string raises ValueError."""
        valid_ids = {"a", "b"}
        deps = [{"from_id": "a", "to_id": "b", "dep_type": ""}]
        with pytest.raises(ValueError):
            reader.validate_dependencies(deps, valid_ids)

    def test_referential_integrity_with_research_and_decisions(self, reader):
        """valid_ids includes research findings and decisions for integrity checks."""
        valid_ids = {"art-1", "RF-001", "D-001"}
        deps = [
            {"from_id": "art-1", "to_id": "RF-001", "dep_type": "implements"},
            {"from_id": "art-1", "to_id": "D-001", "dep_type": "verifies"},
        ]
        reader.validate_dependencies(deps, valid_ids)  # Should not raise
