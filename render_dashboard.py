"""
render_dashboard.py - Dashboard Visualization Generator

Reads project status data from one or more project directories and produces
a single-file HTML dashboard using React 18 + Mermaid.js via CDN.

Usage:
    python render_dashboard.py --project PATH [--project PATH ...] [--output FILE] [--template FILE]
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import yaml


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

STATUS_COLORS: dict[str, str] = {
    "draft":        "#6b7280",
    "reviewed":     "#3b82f6",
    "approved":     "#6366f1",
    "ready":        "#10b981",
    "blocked":      "#ef4444",
    "needs_update": "#f59e0b",
    "invalidated":  "#991b1b",
    "deprecated":   "#78716c",
    "archived":     "#d1d5db",
}

VALID_STATUSES: set[str] = {
    "draft",
    "reviewed",
    "approved",
    "ready",
    "blocked",
    "needs_update",
    "invalidated",
    "deprecated",
    "archived",
}

VALID_TYPES: set[str] = {
    "plan",
    "landing_prompt",
    "test_prompt",
    "research",
    "decision",
}

VALID_DEP_TYPES: set[str] = {
    "requires",
    "implements",
    "verifies",
}


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------

@dataclass
class MarkdownPreview:
    """Summary of a markdown file: title and first-paragraph excerpt."""
    title: str
    excerpt: str


@dataclass
class Artifact:
    """A tracked work item with lifecycle status."""
    id: str
    type: str
    status: str
    path: str
    depends_on: list[str] = field(default_factory=list)
    produces_handoffs: list[str] = field(default_factory=list)
    consumes_handoffs: list[str] = field(default_factory=list)
    last_checked: str = ""
    group: str = ""


@dataclass
class Dependency:
    """An explicit dependency edge between two artifacts."""
    from_id: str
    to_id: str
    dep_type: str


@dataclass
class ChangeEvent:
    """A recorded change event affecting one or more artifacts."""
    id: str
    time: str
    source: str
    event_type: str
    summary: str
    affected: list[str] = field(default_factory=list)
    transitions: list[dict] = field(default_factory=list)


@dataclass
class ProjectData:
    """Complete data structure for a single project."""
    meta: dict = field(default_factory=dict)
    artifacts: list[Artifact] = field(default_factory=list)
    dependencies: list[Dependency] = field(default_factory=list)
    research_findings: list[dict] = field(default_factory=list)
    decisions: list[dict] = field(default_factory=list)
    gates: list[dict] = field(default_factory=list)
    blockers: list[dict] = field(default_factory=list)
    change_events: list[ChangeEvent] = field(default_factory=list)
    markdown_previews: dict[str, MarkdownPreview] = field(default_factory=dict)


@dataclass
class DashboardData:
    """Top-level envelope for the serialized dashboard JSON."""
    projects: dict[str, ProjectData] = field(default_factory=dict)
    generated_at: str = ""
    generator_version: str = "1.0.0"


# ---------------------------------------------------------------------------
# Group Derivation
# ---------------------------------------------------------------------------

def derive_group(artifact: dict | str) -> str:
    """Derive group for an artifact.

    Accepts either a full artifact dict or a plain artifact ID string
    (for backward compatibility with existing callers/tests).

    Priority:
    1. Explicit 'group' field from status.yaml (if artifact is a dict)
    2. Fallback: keyword matching on artifact ID
    """
    if isinstance(artifact, str):
        # Backward compat: called with just an ID string
        return _derive_group_from_id(artifact)

    # Priority 1: explicit group field
    group = artifact.get("group", "")
    if group:
        return group

    # Priority 2: fallback to ID-based keyword matching
    return _derive_group_from_id(artifact.get("id", ""))


def _derive_group_from_id(artifact_id: str) -> str:
    """Legacy ID-based keyword matching (backward compat fallback).

    Priority order: phase1, phase2, phase3, phase4, phase5, codegen, then "Other".
    """
    id_lower = artifact_id.lower()
    if "phase1" in id_lower:
        return "Phase1"
    elif "phase2" in id_lower:
        return "Phase2"
    elif "phase3" in id_lower:
        return "Phase3"
    elif "phase4" in id_lower:
        return "Phase4"
    elif "phase5" in id_lower:
        return "Phase5"
    elif "codegen" in id_lower:
        return "CodeGen"
    else:
        return "Other"


def _extract_topic_from_plan_id(plan_id: str) -> str:
    """Extract group name from a Plan artifact ID.

    1. Strip 'Plan.' prefix
    2. If remainder matches Phase\\d+.* → return 'Phase{N}'
    3. If remainder contains 'codegen' → return 'CodeGen'
    4. Otherwise return remainder as-is (e.g. 'PR3_Runtime')
    """
    import re as _re

    # Strip Plan. prefix
    remainder = plan_id
    if remainder.startswith("Plan."):
        remainder = remainder[5:]

    # Check for PhaseN pattern
    phase_match = _re.match(r"[Pp]hase(\d+)", remainder)
    if phase_match:
        return f"Phase{phase_match.group(1)}"

    # Check for codegen
    if "codegen" in remainder.lower():
        return "CodeGen"

    # Return as-is (the topic name)
    return remainder if remainder else "Other"


def _find_root_plan(
    artifact: "Artifact",
    artifact_by_id: dict[str, "Artifact"],
    raw_artifacts: list[dict],
) -> "Artifact | None":
    """BFS walk through depends_on to find the nearest Plan ancestor.

    Max depth: 5. Returns the first Plan found, or None.
    """
    # Build a lookup from artifact id to its raw depends_on list
    raw_deps_by_id: dict[str, list[str]] = {}
    for a in raw_artifacts:
        aid = a.get("id", "")
        deps = a.get("depends_on", []) or []
        dep_ids = []
        for d in deps:
            if isinstance(d, str):
                dep_ids.append(d)
            elif isinstance(d, dict):
                dep_ids.append(d.get("id", ""))
        raw_deps_by_id[aid] = dep_ids

    # BFS
    from collections import deque
    queue: deque[tuple[str, int]] = deque()
    visited: set[str] = {artifact.id}

    for dep_id in raw_deps_by_id.get(artifact.id, []):
        if dep_id and dep_id not in visited:
            queue.append((dep_id, 1))
            visited.add(dep_id)

    while queue:
        current_id, depth = queue.popleft()
        if depth > 5:
            continue

        current = artifact_by_id.get(current_id)
        if current and current.type == "plan":
            return current

        # Continue BFS
        for dep_id in raw_deps_by_id.get(current_id, []):
            if dep_id and dep_id not in visited:
                queue.append((dep_id, depth + 1))
                visited.add(dep_id)

    return None


# ---------------------------------------------------------------------------
# Hotspot Action Mapping
# ---------------------------------------------------------------------------

def get_suggested_action(status: str) -> str:
    """Return the suggested action for a hotspot artifact based on its status.

    Args:
        status: The artifact status ("blocked" or "needs_update").

    Returns:
        "Resolve blocker" for "blocked", "Review and update" for "needs_update".
    """
    if status == "blocked":
        return "Resolve blocker"
    elif status == "needs_update":
        return "Review and update"
    return ""


def identify_hotspots(artifacts: list[Artifact]) -> list[Artifact]:
    """Return artifacts with status "blocked" or "needs_update".

    The result is ordered with all "blocked" artifacts first, then all
    "needs_update" artifacts. Within each group, artifacts are sorted
    alphabetically by ID.

    Args:
        artifacts: List of Artifact instances to filter.

    Returns:
        List of hotspot artifacts in the specified order.
    """
    blocked = sorted(
        [a for a in artifacts if a.status == "blocked"],
        key=lambda a: a.id,
    )
    needs_update = sorted(
        [a for a in artifacts if a.status == "needs_update"],
        key=lambda a: a.id,
    )
    return blocked + needs_update


# ---------------------------------------------------------------------------
# Markdown Preview Extraction
# ---------------------------------------------------------------------------

def extract_markdown_preview(file_path: Path) -> MarkdownPreview:
    """Extract title and first paragraph from a markdown file.

    Algorithm:
        1. Read up to 50 lines from the file.
        2. Use the first H1 heading (line starting with "# ") as the title,
           or fall back to the filename stem if no H1 is found.
        3. Find the first paragraph: consecutive non-empty lines that do not
           start with "```", ">", "##", "---", or "| ".
        4. Join paragraph lines with a space and truncate to 200 characters.

    If the file does not exist or is unreadable, returns a fallback preview
    with the filename stem as title and "[File not found]" as excerpt.
    """
    MAX_LINES_TO_SCAN = 50
    file_path = Path(file_path)
    title = file_path.stem  # Fallback title
    excerpt = ""
    paragraph_lines: list[str] = []
    found_title = False
    in_paragraph = False
    in_code_fence = False

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            for i, line in enumerate(f):
                if i >= MAX_LINES_TO_SCAN:
                    break

                stripped = line.strip()

                # Track code fence blocks
                if stripped.startswith("```"):
                    if in_paragraph:
                        break  # End of first paragraph
                    in_code_fence = not in_code_fence
                    continue

                # Skip lines inside code fences
                if in_code_fence:
                    continue

                # Extract title from first H1
                if not found_title and stripped.startswith("# "):
                    title = stripped[2:].strip()
                    found_title = True
                    continue

                # Skip empty lines before paragraph
                if not in_paragraph and not stripped:
                    continue

                # Skip blockquotes, other headings, horizontal rules, tables
                if stripped.startswith((">", "##", "---", "| ")):
                    if in_paragraph:
                        break  # End of first paragraph
                    continue

                # Accumulate paragraph lines
                if stripped:
                    in_paragraph = True
                    paragraph_lines.append(stripped)
                elif in_paragraph:
                    break  # Empty line ends paragraph

    except (OSError, IOError):
        return MarkdownPreview(title=file_path.stem, excerpt="[File not found]")

    excerpt = " ".join(paragraph_lines)[:200]
    return MarkdownPreview(title=title, excerpt=excerpt)


# ---------------------------------------------------------------------------
# JSON Serialization
# ---------------------------------------------------------------------------

def serialize_dashboard_data(dashboard_data: DashboardData) -> str:
    """Serialize DashboardData to a JSON string with HTML escape safety.

    Converts the dataclass hierarchy to a JSON-serializable dict, sets
    ``generated_at`` to the current UTC time in ISO-8601 format with a "Z"
    suffix, and escapes ``</`` as ``<\\/`` to prevent HTML injection when
    the JSON is embedded inside a ``<script>`` tag.

    Args:
        dashboard_data: The complete dashboard data envelope to serialize.

    Returns:
        A JSON string safe for embedding in HTML.
    """
    data_dict = asdict(dashboard_data)

    # Set generated_at to current UTC time in ISO-8601 with "Z" suffix
    data_dict["generated_at"] = (
        datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    )

    json_str = json.dumps(data_dict)

    # Escape </ as <\/ to prevent HTML injection (e.g. </script>)
    json_str = json_str.replace("</", r"<\/")

    return json_str


# ---------------------------------------------------------------------------
# Template Injection
# ---------------------------------------------------------------------------

def inject_into_template(
    template_path: Path, json_data: str, output_path: Path
) -> Path:
    """Read an HTML template, replace the {{APP_DATA}} placeholder, and write output.

    The function validates that the template contains exactly one ``{{APP_DATA}}``
    placeholder. It then replaces that placeholder with the provided *json_data*
    string (which should already be serialized and HTML-escaped), creates the
    output directory if needed, and writes the result as a UTF-8 encoded HTML file.

    Args:
        template_path: Path to the HTML template file containing ``{{APP_DATA}}``.
        json_data: The already-serialized (and HTML-escaped) JSON string to inject.
        output_path: Destination path for the generated HTML file.

    Returns:
        The *output_path* after successful write.

    Raises:
        ValueError: If the template does not contain exactly one ``{{APP_DATA}}``
            placeholder.
    """
    PLACEHOLDER = "{{APP_DATA}}"

    # Read template file
    template_content = template_path.read_text(encoding="utf-8")

    # Validate exactly one placeholder exists
    count = template_content.count(PLACEHOLDER)
    if count != 1:
        raise ValueError(
            f"Template must contain exactly 1 '{PLACEHOLDER}' placeholder, "
            f"found {count}"
        )

    # Replace placeholder with serialized JSON
    html_content = template_content.replace(PLACEHOLDER, json_data)

    # Extract generated_at from JSON and inject into meta tag for auto-refresh
    import re as _re
    generated_at_match = _re.search(r'"generated_at"\s*:\s*"([^"]*)"', json_data)
    if generated_at_match:
        timestamp = generated_at_match.group(1)
        html_content = html_content.replace(
            '<meta name="generation-timestamp" content="">',
            f'<meta name="generation-timestamp" content="{timestamp}">',
        )

    # Create output directory if needed
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Write UTF-8 encoded HTML file
    output_path.write_text(html_content, encoding="utf-8")

    return output_path


# ---------------------------------------------------------------------------
# Required top-level keys in status.yaml
# ---------------------------------------------------------------------------

REQUIRED_STATUS_KEYS: set[str] = {
    "meta",
    "artifacts",
}

# Keys that are used if present but not required for dashboard rendering
OPTIONAL_STATUS_KEYS: set[str] = {
    "research_findings",
    "decisions",
    "assumptions",
    "evidence",
    "blockers",
    "gates",
    "preconditions",
    "handoff_contexts",
    "change_events",
    "snapshots",
}


# ---------------------------------------------------------------------------
# Project Reader
# ---------------------------------------------------------------------------

class ProjectReader:
    """Reads and validates a single project's status.yaml and artifacts."""

    def __init__(self, project_path: Path):
        """Initialize with the project root directory path."""
        self.project_path = Path(project_path)

    def read_status_yaml(self) -> dict:
        """Read and validate the project's status/status.yaml file.

        Returns:
            Parsed dict from the YAML file.

        Raises:
            FileNotFoundError: If status/status.yaml does not exist.
            ValueError: If required top-level keys are missing or YAML is malformed.
        """
        status_file = self.project_path / "status" / "status.yaml"

        if not status_file.exists():
            raise FileNotFoundError(
                f"Status file not found: {status_file}"
            )

        try:
            content = status_file.read_text(encoding="utf-8")
            data = yaml.safe_load(content)
        except yaml.YAMLError as e:
            raise ValueError(
                f"Failed to parse YAML in {status_file}: {e}"
            )

        if data is None:
            data = {}

        # Validate required top-level keys
        present_keys = set(data.keys())
        missing_keys = REQUIRED_STATUS_KEYS - present_keys
        if missing_keys:
            sorted_missing = sorted(missing_keys)
            raise ValueError(
                f"Status file {status_file} is missing required keys: "
                f"{', '.join(sorted_missing)}"
            )

        return data

    def validate_artifacts(self, artifacts: list[dict]) -> None:
        """Validate artifact status and type fields against allowed values.

        Args:
            artifacts: List of artifact dicts, each with 'id', 'status', and 'type'.

        Raises:
            ValueError: If any artifact has an invalid status or type,
                identifying the artifact ID and the invalid field value.
        """
        for artifact in artifacts:
            artifact_id = artifact.get("id", "<unknown>")

            status = artifact.get("status", "")
            if status not in VALID_STATUSES:
                raise ValueError(
                    f"Artifact '{artifact_id}' has invalid status: '{status}'"
                )

            artifact_type = artifact.get("type", "")
            if artifact_type not in VALID_TYPES:
                raise ValueError(
                    f"Artifact '{artifact_id}' has invalid type: '{artifact_type}'"
                )

    def validate_dependencies(
        self, dependencies: list[dict], valid_ids: set[str]
    ) -> None:
        """Validate dependency types and referential integrity.

        Args:
            dependencies: List of dependency dicts with 'from_id', 'to_id', 'dep_type'.
            valid_ids: Combined set of artifact IDs, research finding IDs,
                and decision IDs that are valid reference targets.

        Raises:
            ValueError: If a dependency has an invalid dep_type, or if
                from_id/to_id references an ID not in valid_ids.
        """
        for dep in dependencies:
            from_id = dep.get("from_id", "<unknown>")
            to_id = dep.get("to_id", "<unknown>")
            dep_type = dep.get("dep_type", "")

            if dep_type not in VALID_DEP_TYPES:
                raise ValueError(
                    f"Dependency from '{from_id}' has invalid dep_type: '{dep_type}'"
                )

            if from_id not in valid_ids:
                raise ValueError(
                    f"Dependency from '{from_id}' references unresolved "
                    f"source ID: '{from_id}'"
                )

            if to_id not in valid_ids:
                raise ValueError(
                    f"Dependency from '{from_id}' references unresolved "
                    f"target ID: '{to_id}'"
                )

    def extract_markdown_previews(self, artifacts: list[dict]) -> dict[str, MarkdownPreview]:
        """Extract markdown previews for all artifacts that have a path field.

        For each artifact with a non-empty ``path`` field, resolves the path
        relative to the project directory and extracts the title and first
        paragraph using :func:`extract_markdown_preview`.

        Args:
            artifacts: List of artifact dicts, each optionally containing a 'path' field.

        Returns:
            Dict mapping artifact ID to its MarkdownPreview.
        """
        previews: dict[str, MarkdownPreview] = {}
        for artifact in artifacts:
            artifact_id = artifact.get("id", "")
            artifact_path = artifact.get("path", "")
            if artifact_id and artifact_path:
                full_path = self.project_path / artifact_path
                previews[artifact_id] = extract_markdown_preview(full_path)
        return previews

    def build_project_data(self, status_data: dict) -> ProjectData:
        """Assemble a complete ProjectData structure from parsed status.yaml data.

        This method validates artifacts and dependencies, derives groups,
        extracts markdown previews, and builds the full ProjectData dataclass.

        Args:
            status_data: The parsed dict from status.yaml (already validated
                for required top-level keys).

        Returns:
            A fully populated ProjectData instance.

        Raises:
            ValueError: If artifact or dependency validation fails.
        """
        raw_artifacts = status_data.get("artifacts", []) or []
        raw_research = status_data.get("research_findings", []) or []
        raw_decisions = status_data.get("decisions", []) or []
        raw_change_events = status_data.get("change_events", []) or []

        # Validate artifacts
        self.validate_artifacts(raw_artifacts)

        # Build valid IDs set for dependency validation
        valid_ids: set[str] = set()
        for a in raw_artifacts:
            valid_ids.add(a.get("id", ""))
        for r in raw_research:
            valid_ids.add(r.get("id", ""))
        for d in raw_decisions:
            valid_ids.add(d.get("id", ""))
        valid_ids.discard("")

        # Build dependency list from artifact depends_on fields
        dependencies_raw: list[dict] = []
        for a in raw_artifacts:
            artifact_id = a.get("id", "")
            depends_on = a.get("depends_on", []) or []
            for dep_entry in depends_on:
                if isinstance(dep_entry, dict):
                    dep_id = dep_entry.get("id", "")
                    dep_type = dep_entry.get("type", "requires")
                    dependencies_raw.append({
                        "from_id": artifact_id,
                        "to_id": dep_id,
                        "dep_type": dep_type,
                    })
                elif isinstance(dep_entry, str):
                    dependencies_raw.append({
                        "from_id": artifact_id,
                        "to_id": dep_entry,
                        "dep_type": "requires",
                    })

        # Validate dependencies
        self.validate_dependencies(dependencies_raw, valid_ids)

        # Build Artifact dataclass instances with derived groups
        artifacts: list[Artifact] = []
        for a in raw_artifacts:
            artifact = Artifact(
                id=a.get("id", ""),
                type=a.get("type", ""),
                status=a.get("status", ""),
                path=a.get("path", ""),
                depends_on=a.get("depends_on", []) or [],
                produces_handoffs=a.get("produces_handoffs", []) or [],
                consumes_handoffs=a.get("consumes_handoffs", []) or [],
                last_checked=a.get("last_checked", ""),
                group=derive_group(a),
            )
            artifacts.append(artifact)

        # --- Post-process: dependency-chain group inference ---
        # For artifacts with group="Other", try to infer group from Plan ancestors
        # via depends_on chain (BFS, max depth 5)
        artifact_by_id: dict[str, Artifact] = {a.id: a for a in artifacts}

        # Pass 1: For LP/TP with group="Other", walk depends_on to find a Plan ancestor
        # and use that Plan's topic as the group name
        for artifact in artifacts:
            if artifact.group != "Other":
                continue
            if artifact.type not in ("landing_prompt", "test_prompt", "research"):
                continue
            root_plan = _find_root_plan(artifact, artifact_by_id, raw_artifacts)
            if root_plan:
                topic = _extract_topic_from_plan_id(root_plan.id)
                if topic != "Other":
                    artifact.group = topic

        # Pass 2: For Plans with group="Other", check if any of their dependents
        # got assigned a non-"Other" group via Pass 1. If so, assign the same group
        # to the Plan so it appears in the same column.
        # Build reverse map: plan_id -> groups assigned to its dependents
        plan_dependent_groups: dict[str, set[str]] = {}
        for a in raw_artifacts:
            deps = a.get("depends_on", []) or []
            for d in deps:
                dep_id = d if isinstance(d, str) else d.get("id", "") if isinstance(d, dict) else ""
                if dep_id:
                    art = artifact_by_id.get(a.get("id", ""))
                    if art and art.group != "Other":
                        plan_dependent_groups.setdefault(dep_id, set()).add(art.group)

        for artifact in artifacts:
            if artifact.group == "Other" and artifact.type == "plan":
                topic = _extract_topic_from_plan_id(artifact.id)
                # Only assign if the topic matches a group that dependents use
                dep_groups = plan_dependent_groups.get(artifact.id, set())
                if topic in dep_groups:
                    artifact.group = topic

        # Build Dependency dataclass instances
        dependencies: list[Dependency] = [
            Dependency(
                from_id=d["from_id"],
                to_id=d["to_id"],
                dep_type=d["dep_type"],
            )
            for d in dependencies_raw
        ]

        # Build ChangeEvent dataclass instances
        change_events: list[ChangeEvent] = [
            ChangeEvent(
                id=ce.get("id", ""),
                time=ce.get("time", ""),
                source=ce.get("source", ""),
                event_type=ce.get("event_type", ""),
                summary=ce.get("summary", ""),
                affected=ce.get("affected", []) or [],
                transitions=ce.get("transitions", []) or [],
            )
            for ce in raw_change_events
        ]

        # Extract markdown previews
        markdown_previews = self.extract_markdown_previews(raw_artifacts)

        return ProjectData(
            meta=status_data.get("meta", {}),
            artifacts=artifacts,
            dependencies=dependencies,
            research_findings=raw_research,
            decisions=raw_decisions,
            gates=status_data.get("gates", []) or [],
            blockers=status_data.get("blockers", []) or [],
            change_events=change_events,
            markdown_previews=markdown_previews,
        )


# ---------------------------------------------------------------------------
# Dashboard Generator
# ---------------------------------------------------------------------------

class DashboardGenerator:
    """Orchestrates reading multiple projects and generating the HTML dashboard.

    Handles multi-project batch processing: reads each project, skips failures
    with stderr logging, and exits with non-zero code if all projects fail.
    """

    def __init__(
        self,
        project_paths: list[Path],
        output_path: Path,
        template_path: Path,
    ):
        """Initialize with project paths, output path, and template path.

        Args:
            project_paths: One or more project root directory paths.
            output_path: Destination path for the generated HTML file.
            template_path: Path to the HTML template containing {{APP_DATA}}.
        """
        self.project_paths = [Path(p) for p in project_paths]
        self.output_path = Path(output_path)
        self.template_path = Path(template_path)

    def generate(self) -> Path:
        """Generate the dashboard HTML and return the output path.

        For each project path:
            1. Create a ProjectReader and read/validate status.yaml
            2. Build the ProjectData structure
            3. On failure (FileNotFoundError, ValueError, yaml errors),
               log to stderr and skip

        If ALL projects fail, exit with non-zero code and print error summary.

        Returns:
            The output path after successful generation.
        """
        all_projects: dict[str, ProjectData] = {}
        errors: list[str] = []

        for project_path in self.project_paths:
            try:
                reader = ProjectReader(project_path)
                status_data = reader.read_status_yaml()
                project_data = reader.build_project_data(status_data)
                project_name = status_data.get("meta", {}).get(
                    "project_name", project_path.name
                )
                all_projects[project_name] = project_data
            except (FileNotFoundError, ValueError) as e:
                error_msg = f"[{project_path}] {e}"
                print(error_msg, file=sys.stderr)
                errors.append(error_msg)

        # If all projects failed, exit with non-zero code
        if not all_projects:
            print(
                f"\nAll {len(errors)} project(s) failed:",
                file=sys.stderr,
            )
            for err in errors:
                print(f"  - {err}", file=sys.stderr)
            sys.exit(1)

        # Build DashboardData envelope
        dashboard_data = DashboardData(
            projects=all_projects,
            generated_at="",  # Will be set by serialize_dashboard_data
            generator_version="1.0.0",
        )

        # Serialize to JSON
        json_str = serialize_dashboard_data(dashboard_data)

        # Inject into template and write output
        inject_into_template(self.template_path, json_str, self.output_path)

        return self.output_path


# ---------------------------------------------------------------------------
# CLI Argument Parsing
# ---------------------------------------------------------------------------

def build_arg_parser() -> argparse.ArgumentParser:
    """Build and return the CLI argument parser."""
    parser = argparse.ArgumentParser(
        description="Generate an interactive HTML dashboard from project status data.",
    )
    parser.add_argument(
        "--project",
        action="append",
        required=True,
        metavar="PATH",
        help="Path to a project directory (repeatable, at least one required).",
    )
    parser.add_argument(
        "--output",
        default="views/dashboard.html",
        metavar="FILE",
        help="Output HTML file path (default: views/dashboard.html, relative to cwd).",
    )
    parser.add_argument(
        "--template",
        default=None,
        metavar="FILE",
        help="HTML template file path (default: dashboard_template.html relative to script dir).",
    )
    return parser


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments and resolve default paths.

    --output is resolved relative to the current working directory.
    --template defaults to dashboard_template.html relative to the script directory.
    """
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    # Resolve --template default relative to script directory
    if args.template is None:
        script_dir = Path(__file__).resolve().parent
        args.template = str(script_dir / "dashboard_template.html")

    return args


# ---------------------------------------------------------------------------
# Main Entry Point
# ---------------------------------------------------------------------------

def main() -> None:
    """Main entry point for the dashboard generator CLI."""
    args = parse_args()

    project_paths = [Path(p) for p in args.project]
    output_path = Path(args.output)
    template_path = Path(args.template)

    generator = DashboardGenerator(
        project_paths=project_paths,
        output_path=output_path,
        template_path=template_path,
    )

    result = generator.generate()
    print(f"Dashboard generated: {result}")


if __name__ == "__main__":
    main()
