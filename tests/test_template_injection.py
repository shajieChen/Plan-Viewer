"""Unit tests for inject_into_template function.

Tests cover:
- Reading HTML template file
- Validating exactly one {{APP_DATA}} placeholder exists
- Replacing placeholder with serialized JSON
- Creating output directory if needed
- Writing UTF-8 encoded HTML file

Requirements: 3.2, 3.3, 3.6, 3.7
"""

from pathlib import Path

import pytest

from render_dashboard import inject_into_template


@pytest.fixture
def template_file(tmp_path):
    """Helper to create a temporary template file with given content."""
    def _create(content: str, filename: str = "template.html") -> Path:
        file_path = tmp_path / filename
        file_path.write_text(content, encoding="utf-8")
        return file_path
    return _create


class TestPlaceholderValidation:
    """Tests for {{APP_DATA}} placeholder validation (Requirement 3.3)."""

    def test_raises_when_no_placeholder(self, template_file, tmp_path):
        template = template_file("<html><body>No placeholder here</body></html>")
        output = tmp_path / "output" / "dashboard.html"
        with pytest.raises(ValueError, match="exactly 1"):
            inject_into_template(template, '{"data": true}', output)

    def test_raises_when_multiple_placeholders(self, template_file, tmp_path):
        content = "<html>{{APP_DATA}} and {{APP_DATA}}</html>"
        template = template_file(content)
        output = tmp_path / "output" / "dashboard.html"
        with pytest.raises(ValueError, match="found 2"):
            inject_into_template(template, '{"data": true}', output)

    def test_raises_when_three_placeholders(self, template_file, tmp_path):
        content = "{{APP_DATA}}{{APP_DATA}}{{APP_DATA}}"
        template = template_file(content)
        output = tmp_path / "output" / "dashboard.html"
        with pytest.raises(ValueError, match="found 3"):
            inject_into_template(template, '{"data": true}', output)

    def test_succeeds_with_exactly_one_placeholder(self, template_file, tmp_path):
        content = '<script id="app-data">{{APP_DATA}}</script>'
        template = template_file(content)
        output = tmp_path / "dashboard.html"
        result = inject_into_template(template, '{"key": "value"}', output)
        assert result == output


class TestPlaceholderReplacement:
    """Tests for replacing {{APP_DATA}} with JSON data (Requirement 3.2)."""

    def test_replaces_placeholder_with_json(self, template_file, tmp_path):
        content = '<script id="app-data">{{APP_DATA}}</script>'
        template = template_file(content)
        output = tmp_path / "dashboard.html"
        json_data = '{"projects": {}, "generated_at": "2024-01-01T00:00:00Z"}'

        inject_into_template(template, json_data, output)

        result = output.read_text(encoding="utf-8")
        assert json_data in result
        assert "{{APP_DATA}}" not in result

    def test_preserves_surrounding_content(self, template_file, tmp_path):
        content = '<html><head></head><body><script>{{APP_DATA}}</script></body></html>'
        template = template_file(content)
        output = tmp_path / "dashboard.html"
        json_data = '{"test": 1}'

        inject_into_template(template, json_data, output)

        result = output.read_text(encoding="utf-8")
        assert result == '<html><head></head><body><script>{"test": 1}</script></body></html>'

    def test_handles_empty_json(self, template_file, tmp_path):
        content = '<script>{{APP_DATA}}</script>'
        template = template_file(content)
        output = tmp_path / "dashboard.html"

        inject_into_template(template, '{}', output)

        result = output.read_text(encoding="utf-8")
        assert result == '<script>{}</script>'


class TestOutputDirectory:
    """Tests for creating output directory if needed (Requirement 3.7)."""

    def test_creates_parent_directory(self, template_file, tmp_path):
        content = '<script>{{APP_DATA}}</script>'
        template = template_file(content)
        output = tmp_path / "nested" / "deep" / "dashboard.html"

        assert not output.parent.exists()
        inject_into_template(template, '{"data": true}', output)
        assert output.exists()

    def test_works_with_existing_directory(self, template_file, tmp_path):
        content = '<script>{{APP_DATA}}</script>'
        template = template_file(content)
        output = tmp_path / "dashboard.html"

        inject_into_template(template, '{"data": true}', output)
        assert output.exists()


class TestFileOutput:
    """Tests for UTF-8 encoded HTML file output (Requirement 3.6)."""

    def test_writes_utf8_encoded_file(self, template_file, tmp_path):
        content = '<html>{{APP_DATA}}</html>'
        template = template_file(content)
        output = tmp_path / "dashboard.html"
        json_data = '{"name": "tëst üñîcödé"}'

        inject_into_template(template, json_data, output)

        result = output.read_text(encoding="utf-8")
        assert "tëst üñîcödé" in result

    def test_returns_output_path(self, template_file, tmp_path):
        content = '<script>{{APP_DATA}}</script>'
        template = template_file(content)
        output = tmp_path / "views" / "dashboard.html"

        result = inject_into_template(template, '{}', output)
        assert result == output

    def test_overwrites_existing_file(self, template_file, tmp_path):
        content = '<script>{{APP_DATA}}</script>'
        template = template_file(content)
        output = tmp_path / "dashboard.html"

        # Write initial file
        output.write_text("old content", encoding="utf-8")

        inject_into_template(template, '{"new": true}', output)

        result = output.read_text(encoding="utf-8")
        assert "old content" not in result
        assert '{"new": true}' in result
