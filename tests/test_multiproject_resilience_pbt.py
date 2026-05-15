"""Property-based tests for multi-project resilience.

**Validates: Requirements 1.4**

Property 14: Multi-Project Resilience
- For any batch of project paths where at least one project is valid and at least
  one is invalid, the DashboardGenerator output SHALL contain data for all valid
  projects and SHALL NOT contain data for invalid projects.
"""

import json
import tempfile
from pathlib import Path

import yaml
from hypothesis import given, settings, assume
from hypothesis import strategies as st

from render_dashboard import DashboardGenerator


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# Windows reserved device names that cannot be used as directory names
_WINDOWS_RESERVED = frozenset(
    ["CON", "PRN", "AUX", "NUL"]
    + [f"COM{i}" for i in range(1, 10)]
    + [f"LPT{i}" for i in range(1, 10)]
)

# Strategy for project names: simple alphanumeric names
project_names = st.text(
    alphabet=st.characters(categories=("L", "N")),
    min_size=3,
    max_size=20,
).filter(lambda s: s.isalnum() and s.upper() not in _WINDOWS_RESERVED)

# Strategy for number of valid projects (1-3)
valid_project_counts = st.integers(min_value=1, max_value=3)

# Strategy for number of invalid projects (1-3)
invalid_project_counts = st.integers(min_value=1, max_value=3)

# Strategy for invalid project type
invalid_project_types = st.sampled_from(["nonexistent", "no_status_yaml", "invalid_yaml"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_valid_status(project_name: str) -> dict:
    """Create a minimal valid status.yaml content for a project."""
    return {
        "meta": {"project_name": project_name},
        "artifacts": [
            {
                "id": f"plan-phase1-{project_name.lower()}",
                "type": "plan",
                "status": "draft",
                "path": "",
                "depends_on": [],
                "produces_handoffs": [],
                "consumes_handoffs": [],
                "last_checked": "2025-01-01T00:00:00Z",
            }
        ],
        "research_findings": [],
        "decisions": [],
        "assumptions": [],
        "evidence": [],
        "blockers": [],
        "gates": [],
        "preconditions": [],
        "handoff_contexts": [],
        "change_events": [],
        "snapshots": [],
    }


def create_valid_project(base_path: Path, name: str) -> Path:
    """Create a valid project directory with proper status.yaml."""
    project_dir = base_path / name
    status_dir = project_dir / "status"
    status_dir.mkdir(parents=True, exist_ok=True)
    status_file = status_dir / "status.yaml"
    status_file.write_text(yaml.dump(make_valid_status(name)), encoding="utf-8")
    return project_dir


def create_invalid_project(base_path: Path, name: str, invalid_type: str) -> Path:
    """Create an invalid project directory based on the invalid_type.

    Types:
        - nonexistent: directory does not exist
        - no_status_yaml: directory exists but no status.yaml
        - invalid_yaml: status.yaml exists but has missing required keys
    """
    project_dir = base_path / name
    if invalid_type == "nonexistent":
        # Don't create the directory at all
        return project_dir
    elif invalid_type == "no_status_yaml":
        project_dir.mkdir(parents=True, exist_ok=True)
        # No status/status.yaml created
        return project_dir
    elif invalid_type == "invalid_yaml":
        status_dir = project_dir / "status"
        status_dir.mkdir(parents=True, exist_ok=True)
        # Write YAML with missing required keys
        status_file = status_dir / "status.yaml"
        status_file.write_text("meta:\n  project_name: Invalid\n", encoding="utf-8")
        return project_dir
    else:
        raise ValueError(f"Unknown invalid_type: {invalid_type}")


def create_template(base_path: Path) -> Path:
    """Create a minimal HTML template with {{APP_DATA}} placeholder."""
    template = base_path / "template.html"
    template.write_text(
        '<html><script id="app-data">{{APP_DATA}}</script></html>',
        encoding="utf-8",
    )
    return template


def extract_json_from_output(output_path: Path) -> dict:
    """Extract and parse the JSON data from the generated HTML output."""
    content = output_path.read_text(encoding="utf-8")
    start = content.index(">", content.index("app-data")) + 1
    end = content.index("</script>")
    json_str = content[start:end].replace(r"<\/", "</")
    return json.loads(json_str)


# ---------------------------------------------------------------------------
# Property Tests
# ---------------------------------------------------------------------------

class TestMultiProjectResilience:
    """Property 14: Multi-Project Resilience.

    For any batch of project paths where at least one project is valid and at
    least one is invalid, the DashboardGenerator output SHALL contain data for
    all valid projects and SHALL NOT contain data for invalid projects.
    """

    @given(
        valid_names=st.lists(project_names, min_size=1, max_size=3, unique=True),
        invalid_names=st.lists(project_names, min_size=1, max_size=3, unique=True),
        invalid_types=st.lists(invalid_project_types, min_size=1, max_size=3),
    )
    @settings(max_examples=50, deadline=None)
    def test_output_contains_all_valid_projects_and_no_invalid(
        self, valid_names: list[str], invalid_names: list[str], invalid_types: list[str]
    ):
        """For any batch of project paths where at least one project is valid
        and at least one is invalid, the DashboardGenerator output SHALL contain
        data for all valid projects and SHALL NOT contain data for invalid projects.

        **Validates: Requirements 1.4**
        """
        # Ensure valid and invalid names don't overlap
        assume(not set(valid_names) & set(invalid_names))

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)

            # Pad invalid_types to match invalid_names length
            padded_invalid_types = [
                invalid_types[i % len(invalid_types)] for i in range(len(invalid_names))
            ]

            # Create valid projects
            valid_paths = []
            for name in valid_names:
                path = create_valid_project(tmp_path, name)
                valid_paths.append(path)

            # Create invalid projects
            invalid_paths = []
            for name, inv_type in zip(invalid_names, padded_invalid_types):
                path = create_invalid_project(tmp_path, name, inv_type)
                invalid_paths.append(path)

            # Create template and output path
            template = create_template(tmp_path)
            output = tmp_path / "output" / "dashboard.html"

            # Combine all project paths (mix valid and invalid)
            all_paths = valid_paths + invalid_paths

            # Generate dashboard
            gen = DashboardGenerator(
                project_paths=all_paths,
                output_path=output,
                template_path=template,
            )
            gen.generate()

            # Verify output was created
            assert output.exists()

            # Parse the output JSON
            data = extract_json_from_output(output)

            # Property: output contains ALL valid projects
            for name in valid_names:
                assert name in data["projects"], (
                    f"Valid project '{name}' missing from output"
                )

            # Property: output does NOT contain invalid projects
            # The key check is that only valid project names appear
            project_keys = set(data["projects"].keys())
            assert project_keys == set(valid_names), (
                f"Expected exactly valid projects {set(valid_names)}, "
                f"got {project_keys}"
            )
