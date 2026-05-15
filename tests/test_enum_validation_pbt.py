"""Property-based tests for enum validation.

**Validates: Requirements 4.1, 4.2, 4.3**

Property 4: Enum Validation
- For any artifact status string NOT in VALID_STATUSES, validate_artifacts SHALL reject it
  (raise ValueError).
- For any artifact type NOT in VALID_TYPES, validate_artifacts SHALL reject it
  (raise ValueError).
- For any dependency type NOT in VALID_DEP_TYPES, validate_dependencies SHALL reject it
  (raise ValueError).
- For any artifact with status IN VALID_STATUSES and type IN VALID_TYPES,
  validate_artifacts SHALL accept it.
- For any dependency with dep_type IN VALID_DEP_TYPES and valid IDs,
  validate_dependencies SHALL accept it.
"""

import tempfile
from pathlib import Path

import pytest
from hypothesis import given, assume, settings
from hypothesis import strategies as st

from render_dashboard import (
    ProjectReader,
    VALID_STATUSES,
    VALID_TYPES,
    VALID_DEP_TYPES,
)


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# Strategy for arbitrary non-empty strings (potential enum values)
arbitrary_strings = st.text(
    alphabet=st.characters(categories=("L", "N", "P", "S")),
    min_size=1,
    max_size=50,
)

# Strategy for strings guaranteed NOT in VALID_STATUSES
invalid_statuses = arbitrary_strings.filter(lambda s: s not in VALID_STATUSES)

# Strategy for strings guaranteed NOT in VALID_TYPES
invalid_types = arbitrary_strings.filter(lambda s: s not in VALID_TYPES)

# Strategy for strings guaranteed NOT in VALID_DEP_TYPES
invalid_dep_types = arbitrary_strings.filter(lambda s: s not in VALID_DEP_TYPES)

# Strategy for valid statuses
valid_statuses = st.sampled_from(sorted(VALID_STATUSES))

# Strategy for valid types
valid_types = st.sampled_from(sorted(VALID_TYPES))

# Strategy for valid dependency types
valid_dep_types = st.sampled_from(sorted(VALID_DEP_TYPES))

# Strategy for artifact IDs
artifact_ids = st.text(
    alphabet=st.characters(categories=("L", "N")),
    min_size=1,
    max_size=30,
)


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

# Use a single shared reader instance since validate_artifacts/validate_dependencies
# are stateless methods that only check their arguments.
_READER = ProjectReader(Path(tempfile.gettempdir()))


# ---------------------------------------------------------------------------
# Property Tests: Invalid Enum Values Are Rejected
# ---------------------------------------------------------------------------

class TestInvalidStatusRejection:
    """Property: Any status NOT in VALID_STATUSES is rejected by validate_artifacts."""

    @given(status=invalid_statuses, art_id=artifact_ids)
    @settings(max_examples=50)
    def test_invalid_status_raises_value_error(self, status: str, art_id: str):
        """For any artifact status string NOT in VALID_STATUSES,
        validate_artifacts SHALL reject it (raise ValueError).

        **Validates: Requirements 4.1**
        """
        artifacts = [{"id": art_id, "status": status, "type": "plan"}]
        with pytest.raises(ValueError):
            _READER.validate_artifacts(artifacts)


class TestInvalidTypeRejection:
    """Property: Any type NOT in VALID_TYPES is rejected by validate_artifacts."""

    @given(art_type=invalid_types, art_id=artifact_ids)
    @settings(max_examples=50)
    def test_invalid_type_raises_value_error(self, art_type: str, art_id: str):
        """For any artifact type NOT in VALID_TYPES,
        validate_artifacts SHALL reject it (raise ValueError).

        **Validates: Requirements 4.2**
        """
        artifacts = [{"id": art_id, "status": "draft", "type": art_type}]
        with pytest.raises(ValueError):
            _READER.validate_artifacts(artifacts)


class TestInvalidDepTypeRejection:
    """Property: Any dep_type NOT in VALID_DEP_TYPES is rejected by validate_dependencies."""

    @given(dep_type=invalid_dep_types, from_id=artifact_ids, to_id=artifact_ids)
    @settings(max_examples=50)
    def test_invalid_dep_type_raises_value_error(
        self, dep_type: str, from_id: str, to_id: str
    ):
        """For any dependency type NOT in VALID_DEP_TYPES,
        validate_dependencies SHALL reject it (raise ValueError).

        **Validates: Requirements 4.3**
        """
        valid_ids = {from_id, to_id}
        deps = [{"from_id": from_id, "to_id": to_id, "dep_type": dep_type}]
        with pytest.raises(ValueError):
            _READER.validate_dependencies(deps, valid_ids)


# ---------------------------------------------------------------------------
# Property Tests: Valid Enum Values Are Accepted
# ---------------------------------------------------------------------------

class TestValidStatusAcceptance:
    """Property: Any status IN VALID_STATUSES with valid type is accepted."""

    @given(status=valid_statuses, art_type=valid_types, art_id=artifact_ids)
    @settings(max_examples=50)
    def test_valid_status_and_type_accepted(
        self, status: str, art_type: str, art_id: str
    ):
        """For any artifact with status IN VALID_STATUSES and type IN VALID_TYPES,
        validate_artifacts SHALL accept it (no exception raised).

        **Validates: Requirements 4.1, 4.2**
        """
        artifacts = [{"id": art_id, "status": status, "type": art_type}]
        # Should not raise
        _READER.validate_artifacts(artifacts)


class TestValidDepTypeAcceptance:
    """Property: Any dep_type IN VALID_DEP_TYPES with valid IDs is accepted."""

    @given(dep_type=valid_dep_types, from_id=artifact_ids, to_id=artifact_ids)
    @settings(max_examples=50)
    def test_valid_dep_type_with_valid_ids_accepted(
        self, dep_type: str, from_id: str, to_id: str
    ):
        """For any dependency with dep_type IN VALID_DEP_TYPES and valid IDs,
        validate_dependencies SHALL accept it (no exception raised).

        **Validates: Requirements 4.3**
        """
        valid_ids = {from_id, to_id}
        deps = [{"from_id": from_id, "to_id": to_id, "dep_type": dep_type}]
        # Should not raise
        _READER.validate_dependencies(deps, valid_ids)
