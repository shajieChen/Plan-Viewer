"""Property-based tests for dependency referential integrity.

**Validates: Requirements 4.4**

Property 5: Dependency Referential Integrity
- For any dependency where both from_id and to_id exist in valid_ids,
  validation SHALL pass.
- For any dependency where from_id does NOT exist in valid_ids,
  validation SHALL raise ValueError.
- For any dependency where to_id does NOT exist in valid_ids,
  validation SHALL raise ValueError.
- The ValueError SHALL identify the source ID and the unresolved target ID.
"""

import pytest
from hypothesis import given, assume, settings
from hypothesis import strategies as st

from render_dashboard import ProjectReader, VALID_DEP_TYPES


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# Strategy for valid IDs (non-empty alphanumeric strings)
valid_id_strategy = st.text(
    alphabet=st.characters(categories=("L", "N"), whitelist_characters="_-"),
    min_size=1,
    max_size=30,
)

# Strategy for sets of valid IDs (at least 2 so we can form dependencies)
valid_id_set_strategy = st.frozensets(valid_id_strategy, min_size=2, max_size=20)

# Strategy for dependency types drawn from the valid set
dep_type_strategy = st.sampled_from(sorted(VALID_DEP_TYPES))


def dependency_with_valid_ids(valid_ids: frozenset[str]) -> st.SearchStrategy[dict]:
    """Generate a dependency dict where both from_id and to_id are in valid_ids."""
    ids_list = sorted(valid_ids)
    return st.fixed_dictionaries({
        "from_id": st.sampled_from(ids_list),
        "to_id": st.sampled_from(ids_list),
        "dep_type": dep_type_strategy,
    })


# Strategy for an ID guaranteed NOT to be in a given set
def id_not_in(valid_ids: frozenset[str]) -> st.SearchStrategy[str]:
    """Generate an ID that is not in the valid_ids set."""
    return valid_id_strategy.filter(lambda x: x not in valid_ids)


# ---------------------------------------------------------------------------
# Property Tests
# ---------------------------------------------------------------------------

class TestDependencyReferentialIntegrityValid:
    """Property: Dependencies with both IDs in valid_ids pass validation."""

    @given(data=st.data())
    @settings(max_examples=50)
    def test_valid_dependencies_pass(self, data):
        """For any dependency where both from_id and to_id exist in valid_ids,
        validation SHALL pass.

        **Validates: Requirements 4.4**
        """
        valid_ids = data.draw(valid_id_set_strategy)
        dep = data.draw(dependency_with_valid_ids(valid_ids))

        reader = ProjectReader.__new__(ProjectReader)
        # Should not raise
        reader.validate_dependencies([dep], set(valid_ids))

    @given(data=st.data())
    @settings(max_examples=30)
    def test_multiple_valid_dependencies_pass(self, data):
        """Multiple dependencies all referencing valid IDs pass validation.

        **Validates: Requirements 4.4**
        """
        valid_ids = data.draw(valid_id_set_strategy)
        num_deps = data.draw(st.integers(min_value=1, max_value=5))
        deps = [
            data.draw(dependency_with_valid_ids(valid_ids))
            for _ in range(num_deps)
        ]

        reader = ProjectReader.__new__(ProjectReader)
        # Should not raise
        reader.validate_dependencies(deps, set(valid_ids))


class TestDependencyReferentialIntegrityInvalidFromId:
    """Property: Dependencies with from_id NOT in valid_ids raise ValueError."""

    @given(data=st.data())
    @settings(max_examples=50)
    def test_invalid_from_id_raises(self, data):
        """For any dependency where from_id does NOT exist in valid_ids,
        validation SHALL raise ValueError.

        **Validates: Requirements 4.4**
        """
        valid_ids = data.draw(valid_id_set_strategy)
        invalid_from = data.draw(id_not_in(valid_ids))
        ids_list = sorted(valid_ids)
        to_id = data.draw(st.sampled_from(ids_list))
        dep_type = data.draw(dep_type_strategy)

        dep = {"from_id": invalid_from, "to_id": to_id, "dep_type": dep_type}

        reader = ProjectReader.__new__(ProjectReader)
        with pytest.raises(ValueError) as exc_info:
            reader.validate_dependencies([dep], set(valid_ids))

        # The error message SHALL identify the source ID
        assert invalid_from in str(exc_info.value)


class TestDependencyReferentialIntegrityInvalidToId:
    """Property: Dependencies with to_id NOT in valid_ids raise ValueError."""

    @given(data=st.data())
    @settings(max_examples=50)
    def test_invalid_to_id_raises(self, data):
        """For any dependency where to_id does NOT exist in valid_ids,
        validation SHALL raise ValueError.

        **Validates: Requirements 4.4**
        """
        valid_ids = data.draw(valid_id_set_strategy)
        ids_list = sorted(valid_ids)
        from_id = data.draw(st.sampled_from(ids_list))
        invalid_to = data.draw(id_not_in(valid_ids))
        dep_type = data.draw(dep_type_strategy)

        dep = {"from_id": from_id, "to_id": invalid_to, "dep_type": dep_type}

        reader = ProjectReader.__new__(ProjectReader)
        with pytest.raises(ValueError) as exc_info:
            reader.validate_dependencies([dep], set(valid_ids))

        # The error message SHALL identify the source ID and unresolved target ID
        error_msg = str(exc_info.value)
        assert from_id in error_msg
        assert invalid_to in error_msg


class TestDependencyReferentialIntegrityErrorMessages:
    """Property: ValueError messages identify source and unresolved target."""

    @given(data=st.data())
    @settings(max_examples=30)
    def test_error_identifies_both_ids_when_both_invalid(self, data):
        """When both from_id and to_id are invalid, the error identifies
        the source ID (from_id is checked first).

        **Validates: Requirements 4.4**
        """
        valid_ids = data.draw(valid_id_set_strategy)
        invalid_from = data.draw(id_not_in(valid_ids))
        invalid_to = data.draw(id_not_in(valid_ids))
        assume(invalid_from != invalid_to)
        dep_type = data.draw(dep_type_strategy)

        dep = {"from_id": invalid_from, "to_id": invalid_to, "dep_type": dep_type}

        reader = ProjectReader.__new__(ProjectReader)
        with pytest.raises(ValueError) as exc_info:
            reader.validate_dependencies([dep], set(valid_ids))

        # from_id is checked first, so error should mention it
        assert invalid_from in str(exc_info.value)
