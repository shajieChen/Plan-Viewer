"""Tests for DashboardGenerator class with multi-project support."""

import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from render_dashboard import DashboardGenerator, ProjectReader


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

MINIMAL_STATUS = {
    "meta": {"project_name": "TestProject"},
    "artifacts": [
        {
            "id": "plan-phase1-test",
            "type": "plan",
            "status": "draft",
            "path": "plan/Phase1-Test.md",
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


def create_project(tmp_path: Path, name: str, status_data: dict) -> Path:
    """Create a minimal project directory with status.yaml."""
    project_dir = tmp_path / name
    status_dir = project_dir / "status"
    status_dir.mkdir(parents=True)
    status_file = status_dir / "status.yaml"
    status_file.write_text(yaml.dump(status_data), encoding="utf-8")
    return project_dir


def create_template(tmp_path: Path) -> Path:
    """Create a minimal HTML template with {{APP_DATA}} placeholder."""
    template = tmp_path / "template.html"
    template.write_text(
        '<html><script id="app-data">{{APP_DATA}}</script></html>',
        encoding="utf-8",
    )
    return template


# ---------------------------------------------------------------------------
# Tests: DashboardGenerator.__init__
# ---------------------------------------------------------------------------

class TestDashboardGeneratorInit:
    def test_stores_paths(self, tmp_path):
        gen = DashboardGenerator(
            project_paths=[tmp_path / "p1", tmp_path / "p2"],
            output_path=tmp_path / "out.html",
            template_path=tmp_path / "tmpl.html",
        )
        assert len(gen.project_paths) == 2
        assert gen.output_path == tmp_path / "out.html"
        assert gen.template_path == tmp_path / "tmpl.html"

    def test_converts_strings_to_paths(self, tmp_path):
        gen = DashboardGenerator(
            project_paths=[str(tmp_path / "p1")],
            output_path=tmp_path / "out.html",
            template_path=tmp_path / "tmpl.html",
        )
        assert isinstance(gen.project_paths[0], Path)


# ---------------------------------------------------------------------------
# Tests: DashboardGenerator.generate - single project
# ---------------------------------------------------------------------------

class TestDashboardGeneratorSingleProject:
    def test_generates_output_for_valid_project(self, tmp_path):
        project = create_project(tmp_path, "proj1", MINIMAL_STATUS)
        template = create_template(tmp_path)
        output = tmp_path / "views" / "dashboard.html"

        gen = DashboardGenerator(
            project_paths=[project],
            output_path=output,
            template_path=template,
        )
        result = gen.generate()

        assert result == output
        assert output.exists()
        content = output.read_text(encoding="utf-8")
        assert "TestProject" in content

    def test_output_contains_valid_json(self, tmp_path):
        project = create_project(tmp_path, "proj1", MINIMAL_STATUS)
        template = create_template(tmp_path)
        output = tmp_path / "out.html"

        gen = DashboardGenerator(
            project_paths=[project],
            output_path=output,
            template_path=template,
        )
        gen.generate()

        content = output.read_text(encoding="utf-8")
        # Extract JSON between script tags
        start = content.index(">", content.index("app-data")) + 1
        end = content.index("</script>")
        json_str = content[start:end].replace(r"<\/", "</")
        data = json.loads(json_str)

        assert "projects" in data
        assert "TestProject" in data["projects"]
        assert "generated_at" in data
        assert "generator_version" in data
        assert data["generator_version"] == "1.0.0"

    def test_creates_output_directory(self, tmp_path):
        project = create_project(tmp_path, "proj1", MINIMAL_STATUS)
        template = create_template(tmp_path)
        output = tmp_path / "deep" / "nested" / "dir" / "dashboard.html"

        gen = DashboardGenerator(
            project_paths=[project],
            output_path=output,
            template_path=template,
        )
        gen.generate()

        assert output.exists()


# ---------------------------------------------------------------------------
# Tests: DashboardGenerator.generate - multi-project
# ---------------------------------------------------------------------------

class TestDashboardGeneratorMultiProject:
    def test_processes_multiple_valid_projects(self, tmp_path):
        status1 = {**MINIMAL_STATUS, "meta": {"project_name": "Alpha"}}
        status2 = {**MINIMAL_STATUS, "meta": {"project_name": "Beta"}}
        proj1 = create_project(tmp_path, "p1", status1)
        proj2 = create_project(tmp_path, "p2", status2)
        template = create_template(tmp_path)
        output = tmp_path / "out.html"

        gen = DashboardGenerator(
            project_paths=[proj1, proj2],
            output_path=output,
            template_path=template,
        )
        gen.generate()

        content = output.read_text(encoding="utf-8")
        assert "Alpha" in content
        assert "Beta" in content

    def test_skips_failed_project_continues_with_valid(self, tmp_path, capsys):
        valid_status = {**MINIMAL_STATUS, "meta": {"project_name": "GoodProject"}}
        valid_proj = create_project(tmp_path, "good", valid_status)
        bad_proj = tmp_path / "bad"  # No status.yaml
        bad_proj.mkdir()
        template = create_template(tmp_path)
        output = tmp_path / "out.html"

        gen = DashboardGenerator(
            project_paths=[bad_proj, valid_proj],
            output_path=output,
            template_path=template,
        )
        gen.generate()

        # Output should contain only the valid project
        content = output.read_text(encoding="utf-8")
        assert "GoodProject" in content

        # Error should be logged to stderr
        captured = capsys.readouterr()
        assert "bad" in captured.err

    def test_skips_project_with_invalid_yaml(self, tmp_path, capsys):
        valid_status = {**MINIMAL_STATUS, "meta": {"project_name": "ValidProj"}}
        valid_proj = create_project(tmp_path, "valid", valid_status)

        # Create project with missing keys
        bad_proj = tmp_path / "bad_yaml"
        (bad_proj / "status").mkdir(parents=True)
        (bad_proj / "status" / "status.yaml").write_text(
            "meta:\n  project_name: Bad\n", encoding="utf-8"
        )
        template = create_template(tmp_path)
        output = tmp_path / "out.html"

        gen = DashboardGenerator(
            project_paths=[bad_proj, valid_proj],
            output_path=output,
            template_path=template,
        )
        gen.generate()

        content = output.read_text(encoding="utf-8")
        assert "ValidProj" in content
        captured = capsys.readouterr()
        assert "missing required keys" in captured.err


# ---------------------------------------------------------------------------
# Tests: DashboardGenerator.generate - all projects fail
# ---------------------------------------------------------------------------

class TestDashboardGeneratorAllFail:
    def test_exits_nonzero_when_all_projects_fail(self, tmp_path, capsys):
        bad1 = tmp_path / "bad1"
        bad1.mkdir()
        bad2 = tmp_path / "bad2"
        bad2.mkdir()
        template = create_template(tmp_path)
        output = tmp_path / "out.html"

        gen = DashboardGenerator(
            project_paths=[bad1, bad2],
            output_path=output,
            template_path=template,
        )

        with pytest.raises(SystemExit) as exc_info:
            gen.generate()

        assert exc_info.value.code == 1

        captured = capsys.readouterr()
        assert "All 2 project(s) failed" in captured.err

    def test_exits_nonzero_single_project_fails(self, tmp_path, capsys):
        bad = tmp_path / "bad"
        bad.mkdir()
        template = create_template(tmp_path)
        output = tmp_path / "out.html"

        gen = DashboardGenerator(
            project_paths=[bad],
            output_path=output,
            template_path=template,
        )

        with pytest.raises(SystemExit) as exc_info:
            gen.generate()

        assert exc_info.value.code == 1


# ---------------------------------------------------------------------------
# Tests: ProjectReader.extract_markdown_previews
# ---------------------------------------------------------------------------

class TestProjectReaderExtractMarkdownPreviews:
    def test_extracts_previews_for_artifacts_with_paths(self, tmp_path):
        project = tmp_path / "proj"
        (project / "plan").mkdir(parents=True)
        md_file = project / "plan" / "Phase1-Test.md"
        md_file.write_text("# My Title\n\nSome content here.\n", encoding="utf-8")

        artifacts = [
            {"id": "art1", "path": "plan/Phase1-Test.md"},
        ]

        reader = ProjectReader(project)
        previews = reader.extract_markdown_previews(artifacts)

        assert "art1" in previews
        assert previews["art1"].title == "My Title"
        assert previews["art1"].excerpt == "Some content here."

    def test_handles_missing_file(self, tmp_path):
        project = tmp_path / "proj"
        project.mkdir()

        artifacts = [
            {"id": "art1", "path": "nonexistent.md"},
        ]

        reader = ProjectReader(project)
        previews = reader.extract_markdown_previews(artifacts)

        assert "art1" in previews
        assert previews["art1"].title == "nonexistent"
        assert previews["art1"].excerpt == "[File not found]"

    def test_skips_artifacts_without_path(self, tmp_path):
        project = tmp_path / "proj"
        project.mkdir()

        artifacts = [
            {"id": "art1", "path": ""},
            {"id": "art2"},
        ]

        reader = ProjectReader(project)
        previews = reader.extract_markdown_previews(artifacts)

        assert len(previews) == 0


# ---------------------------------------------------------------------------
# Tests: ProjectReader.build_project_data
# ---------------------------------------------------------------------------

class TestProjectReaderBuildProjectData:
    def test_builds_complete_project_data(self, tmp_path):
        project = create_project(tmp_path, "proj", MINIMAL_STATUS)
        reader = ProjectReader(project)
        status_data = reader.read_status_yaml()
        project_data = reader.build_project_data(status_data)

        assert project_data.meta == {"project_name": "TestProject"}
        assert len(project_data.artifacts) == 1
        assert project_data.artifacts[0].id == "plan-phase1-test"
        assert project_data.artifacts[0].group == "Phase1"

    def test_raises_on_invalid_artifact_status(self, tmp_path):
        bad_status = {**MINIMAL_STATUS}
        bad_status["artifacts"] = [
            {"id": "art1", "type": "plan", "status": "invalid_status", "path": ""}
        ]
        project = create_project(tmp_path, "proj", bad_status)
        reader = ProjectReader(project)
        status_data = reader.read_status_yaml()

        with pytest.raises(ValueError, match="invalid status"):
            reader.build_project_data(status_data)

    def test_builds_dependencies_from_depends_on(self, tmp_path):
        status = {**MINIMAL_STATUS}
        status["artifacts"] = [
            {
                "id": "art1",
                "type": "plan",
                "status": "draft",
                "path": "",
                "depends_on": [{"id": "art2", "type": "requires"}],
                "produces_handoffs": [],
                "consumes_handoffs": [],
                "last_checked": "",
            },
            {
                "id": "art2",
                "type": "plan",
                "status": "draft",
                "path": "",
                "depends_on": [],
                "produces_handoffs": [],
                "consumes_handoffs": [],
                "last_checked": "",
            },
        ]
        project = create_project(tmp_path, "proj", status)
        reader = ProjectReader(project)
        status_data = reader.read_status_yaml()
        project_data = reader.build_project_data(status_data)

        assert len(project_data.dependencies) == 1
        assert project_data.dependencies[0].from_id == "art1"
        assert project_data.dependencies[0].to_id == "art2"
        assert project_data.dependencies[0].dep_type == "requires"


# ---------------------------------------------------------------------------
# Tests: main() integration
# ---------------------------------------------------------------------------

class TestMainIntegration:
    def test_main_generates_dashboard(self, tmp_path, monkeypatch):
        project = create_project(tmp_path, "proj", MINIMAL_STATUS)
        template = create_template(tmp_path)
        output = tmp_path / "out.html"

        monkeypatch.setattr(
            sys,
            "argv",
            [
                "render_dashboard.py",
                "--project", str(project),
                "--output", str(output),
                "--template", str(template),
            ],
        )

        from render_dashboard import main
        main()

        assert output.exists()
