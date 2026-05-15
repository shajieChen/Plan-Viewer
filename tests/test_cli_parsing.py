"""Unit tests for CLI argument parsing in render_dashboard.py.

Validates: Requirements 1.7
"""

import pytest
from pathlib import Path

from render_dashboard import parse_args, build_arg_parser


class TestProjectArgument:
    """Tests for the --project CLI argument."""

    def test_project_is_required(self):
        """Calling without --project should raise SystemExit."""
        with pytest.raises(SystemExit):
            parse_args([])

    def test_project_is_repeatable(self):
        """--project A --project B should give args.project == ['A', 'B']."""
        args = parse_args(["--project", "A", "--project", "B"])
        assert args.project == ["A", "B"]

    def test_single_project(self):
        """A single --project value is stored as a one-element list."""
        args = parse_args(["--project", "myproject"])
        assert args.project == ["myproject"]


class TestOutputArgument:
    """Tests for the --output CLI argument."""

    def test_output_defaults_to_views_dashboard_html(self):
        """--output defaults to 'views/dashboard.html' when not specified."""
        args = parse_args(["--project", "X"])
        assert args.output == "views/dashboard.html"

    def test_output_can_be_overridden(self):
        """--output custom.html should give args.output == 'custom.html'."""
        args = parse_args(["--project", "X", "--output", "custom.html"])
        assert args.output == "custom.html"


class TestTemplateArgument:
    """Tests for the --template CLI argument."""

    def test_template_defaults_to_script_dir(self):
        """--template defaults to dashboard_template.html relative to the script directory."""
        args = parse_args(["--project", "X"])
        expected = str(Path(__file__).resolve().parent.parent / "render_dashboard.py")
        # The default template is relative to the script (render_dashboard.py) directory
        script_dir = Path(expected).resolve().parent
        expected_template = str(script_dir / "dashboard_template.html")
        assert args.template == expected_template

    def test_template_can_be_overridden(self):
        """--template custom_template.html should give args.template == 'custom_template.html'."""
        args = parse_args(["--project", "X", "--template", "custom_template.html"])
        assert args.template == "custom_template.html"
