"""Property-based tests for invalid input error signaling.

**Validates: Requirements 1.2, 1.3**

Property 13: Invalid Input Error Signaling
- For any project path where status/status.yaml does not exist, the
  Dashboard_Generator SHALL raise FileNotFoundError.
- For any Status_YAML with missing required keys, the Dashboard_Generator
  SHALL raise ValueError listing the missing fields.
"""

import tempfile
from pathlib import Path

import pytest
import yaml
from hypothesis import given, settings
from hypothesis import strategies as st

from render_dashboard import ProjectReader, REQUIRED_STATUS_KEYS


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# Strategy for generating random directory names (safe filesystem chars)
random_dir_names = st.text(
    alphabet=st.characters(
        categories=("L", "N"),
        min_codepoint=ord("a"),
        max_codepoint=ord("z"),
    ),
    min_size=1,
    max_size=20,
)

# Strategy for generating non-empty proper subsets of REQUIRED_STATUS_KEYS
# (i.e., at least one key removed)
required_keys_list = sorted(REQUIRED_STATUS_KEYS)


def subsets_missing_keys() -> st.SearchStrategy[tuple[set[str], set[str]]]:
    """Generate (present_keys, missing_keys) where missing_keys is non-empty.

    Returns tuples of (keys_to_include, keys_that_are_missing) such that
    keys_to_include is a proper subset of REQUIRED_STATUS_KEYS.
    """
    n = len(required_keys_list)
    # max_value = (2**n) - 2 ensures at least one key is excluded
    return st.integers(min_value=0, max_value=(2**n) - 2).map(
        lambda mask: (
            {required_keys_list[i] for i in range(n) if mask & (1 << i)},
            {required_keys_list[i] for i in range(n) if not (mask & (1 << i))},
        )
    )


# ---------------------------------------------------------------------------
# Property Tests
# ---------------------------------------------------------------------------

class TestFileNotFoundProperty:
    """Property: For any project path where status/status.yaml does not exist,
    read_status_yaml() SHALL raise FileNotFoundError."""

    @given(subdir=random_dir_names)
    @settings(max_examples=30)
    def test_missing_status_yaml_raises_file_not_found(self, subdir: str):
        """Any project path without status/status.yaml raises FileNotFoundError.

        **Validates: Requirements 1.2**
        """
        with tempfile.TemporaryDirectory() as tmp:
            project_path = Path(tmp) / subdir
            project_path.mkdir(parents=True, exist_ok=True)

            reader = ProjectReader(project_path)
            with pytest.raises(FileNotFoundError):
                reader.read_status_yaml()

    @given(subdir=random_dir_names)
    @settings(max_examples=50)
    def test_empty_status_dir_raises_file_not_found(self, subdir: str):
        """A project with a status/ directory but no status.yaml raises FileNotFoundError.

        **Validates: Requirements 1.2**
        """
        with tempfile.TemporaryDirectory() as tmp:
            project_path = Path(tmp) / subdir
            status_dir = project_path / "status"
            status_dir.mkdir(parents=True, exist_ok=True)
            # status/ exists but status.yaml does not

            reader = ProjectReader(project_path)
            with pytest.raises(FileNotFoundError):
                reader.read_status_yaml()

    @given(subdir=random_dir_names)
    @settings(max_examples=50)
    def test_error_message_includes_path(self, subdir: str):
        """The FileNotFoundError message includes the expected file path.

        **Validates: Requirements 1.2**
        """
        with tempfile.TemporaryDirectory() as tmp:
            project_path = Path(tmp) / subdir
            project_path.mkdir(parents=True, exist_ok=True)

            reader = ProjectReader(project_path)
            with pytest.raises(FileNotFoundError) as exc_info:
                reader.read_status_yaml()

            error_msg = str(exc_info.value)
            assert "status.yaml" in error_msg


class TestMissingKeysProperty:
    """Property: For any Status_YAML with missing required keys,
    read_status_yaml() SHALL raise ValueError listing the missing fields."""

    @given(key_sets=subsets_missing_keys())
    @settings(max_examples=50)
    def test_missing_keys_raises_value_error(self, key_sets: tuple[set[str], set[str]]):
        """Any YAML with a proper subset of required keys raises ValueError.

        **Validates: Requirements 1.3**
        """
        present_keys, missing_keys = key_sets

        # Build a YAML dict with only the present keys
        data = {key: [] for key in present_keys}
        # meta needs to be a dict if present
        if "meta" in data:
            data["meta"] = {"project_name": "Test"}
        if "snapshots" in data:
            data["snapshots"] = {}

        with tempfile.TemporaryDirectory() as tmp:
            project_path = Path(tmp) / "proj"
            status_dir = project_path / "status"
            status_dir.mkdir(parents=True, exist_ok=True)
            (status_dir / "status.yaml").write_text(
                yaml.dump(data), encoding="utf-8"
            )

            reader = ProjectReader(project_path)
            with pytest.raises(ValueError):
                reader.read_status_yaml()

    @given(key_sets=subsets_missing_keys())
    @settings(max_examples=50)
    def test_error_lists_all_missing_keys(self, key_sets: tuple[set[str], set[str]]):
        """The ValueError message lists every missing key.

        **Validates: Requirements 1.3**
        """
        present_keys, missing_keys = key_sets

        # Build a YAML dict with only the present keys
        data = {key: [] for key in present_keys}
        if "meta" in data:
            data["meta"] = {"project_name": "Test"}
        if "snapshots" in data:
            data["snapshots"] = {}

        with tempfile.TemporaryDirectory() as tmp:
            project_path = Path(tmp) / "proj"
            status_dir = project_path / "status"
            status_dir.mkdir(parents=True, exist_ok=True)
            (status_dir / "status.yaml").write_text(
                yaml.dump(data), encoding="utf-8"
            )

            reader = ProjectReader(project_path)
            with pytest.raises(ValueError) as exc_info:
                reader.read_status_yaml()

            error_msg = str(exc_info.value)
            for key in missing_keys:
                assert key in error_msg, (
                    f"Missing key '{key}' not listed in error message: {error_msg}"
                )
