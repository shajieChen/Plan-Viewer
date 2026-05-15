"""Unit tests for distribute_skill.py.

Example-based tests for edge cases and specific behaviors of the
YAML front-matter parsing, format conversion, and output reporting.
"""

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "Docs" / "tools"))

from distribute_skill import (
    convert_to_copilot,
    convert_to_cursor_mdc,
    main,
    parse_front_matter,
)


# ---------------------------------------------------------------------------
# 6.4 Unit tests for output reporting
# Requirements: 10.1, 10.2, 10.3
# ---------------------------------------------------------------------------


class TestOutputReporting:
    """Unit tests for output reporting behavior of main()."""

    def test_success_output_contains_ok_and_path(self, tmp_path, capsys, monkeypatch):
        """Success messages contain 'OK' and absolute path.

        **Validates: Requirements 10.1**
        """
        # Create a valid SKILL.md in tmp_path
        skill_file = tmp_path / "SKILL.md"
        skill_file.write_text(
            "---\nname: test-skill\ndescription: A test skill\n---\n# Body\n",
            encoding="utf-8",
        )

        # Redirect target paths to temp directories
        cursor_target = tmp_path / "cursor" / "test.mdc"
        copilot_target = tmp_path / "copilot" / "instructions.md"

        monkeypatch.setattr(
            "distribute_skill.CURSOR_MDC_PATH", cursor_target
        )
        monkeypatch.setattr(
            "distribute_skill.COPILOT_PATH", copilot_target
        )

        # Run main with --skill-path pointing to our temp SKILL.md
        monkeypatch.setattr(
            "sys.argv", ["distribute_skill.py", "--skill-path", str(skill_file)]
        )

        main()

        captured = capsys.readouterr()
        lines = [line for line in captured.out.strip().splitlines() if line.strip()]

        # Each OK line should contain "OK" and an absolute path
        ok_lines = [line for line in lines if "OK" in line]
        assert len(ok_lines) >= 2, (
            f"Expected at least 2 OK lines, got {len(ok_lines)}. stdout:\n{captured.out}"
        )
        for line in ok_lines:
            assert "OK" in line
            # Check that the line contains an absolute path
            # On Windows, absolute paths contain a drive letter like C:\ or a tmp path
            assert str(tmp_path) in line or Path(line.split()[-1]).is_absolute(), (
                f"Expected absolute path in line: {line!r}"
            )

    def test_success_summary_shows_targets_updated(self, tmp_path, capsys, monkeypatch):
        """Summary shows '2 targets updated'.

        **Validates: Requirements 10.2**
        """
        # Create a valid SKILL.md in tmp_path
        skill_file = tmp_path / "SKILL.md"
        skill_file.write_text(
            "---\nname: test-skill\ndescription: A test skill\n---\n# Body\n",
            encoding="utf-8",
        )

        # Redirect target paths to temp directories
        cursor_target = tmp_path / "cursor" / "test.mdc"
        copilot_target = tmp_path / "copilot" / "instructions.md"

        monkeypatch.setattr(
            "distribute_skill.CURSOR_MDC_PATH", cursor_target
        )
        monkeypatch.setattr(
            "distribute_skill.COPILOT_PATH", copilot_target
        )

        # Run main with --skill-path pointing to our temp SKILL.md
        monkeypatch.setattr(
            "sys.argv", ["distribute_skill.py", "--skill-path", str(skill_file)]
        )

        main()

        captured = capsys.readouterr()
        assert "2 targets updated" in captured.out, (
            f"Expected '2 targets updated' in stdout, got:\n{captured.out}"
        )

    def test_write_failure_reports_to_stderr(self, tmp_path, capsys, monkeypatch):
        """Write failure reports to stderr with path and reason.

        **Validates: Requirements 10.3**
        """
        # Create a valid SKILL.md in tmp_path
        skill_file = tmp_path / "SKILL.md"
        skill_file.write_text(
            "---\nname: test-skill\ndescription: A test skill\n---\n# Body\n",
            encoding="utf-8",
        )

        # Set up a target path that will fail
        bad_target = tmp_path / "readonly" / "test.mdc"
        copilot_target = tmp_path / "copilot" / "instructions.md"

        monkeypatch.setattr(
            "distribute_skill.CURSOR_MDC_PATH", bad_target
        )
        monkeypatch.setattr(
            "distribute_skill.COPILOT_PATH", copilot_target
        )

        # Mock write_target to raise OSError for the first target
        original_write_target = None

        def failing_write_target(path, content):
            if path == bad_target:
                err = OSError("Permission denied")
                err.strerror = "Permission denied"
                raise err
            # For other paths, write normally
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")

        monkeypatch.setattr(
            "distribute_skill.write_target", failing_write_target
        )

        # Run main with --skill-path pointing to our temp SKILL.md
        monkeypatch.setattr(
            "sys.argv", ["distribute_skill.py", "--skill-path", str(skill_file)]
        )

        with pytest.raises(SystemExit) as exc_info:
            main()

        assert exc_info.value.code == 1

        captured = capsys.readouterr()
        # stderr should contain the path and the error reason
        assert str(bad_target) in captured.err, (
            f"Expected path '{bad_target}' in stderr, got:\n{captured.err}"
        )
        assert "Permission denied" in captured.err, (
            f"Expected 'Permission denied' in stderr, got:\n{captured.err}"
        )


# ---------------------------------------------------------------------------
# Unit tests for convert_to_cursor_mdc
# Validates: Requirements 8.1, 8.2, 8.3, 8.4, 8.7
# ---------------------------------------------------------------------------


def test_mdc_contains_globs_empty() -> None:
    """Cursor MDC output contains globs: "" in front-matter.

    **Validates: Requirements 8.2**
    """
    metadata = {"name": "my-skill", "description": "A simple skill"}
    body = "# Hello\n"
    result = convert_to_cursor_mdc(metadata, body)
    assert 'globs: ""' in result


def test_mdc_contains_always_apply() -> None:
    """Cursor MDC output contains alwaysApply: true in front-matter.

    **Validates: Requirements 8.3**
    """
    metadata = {"name": "my-skill", "description": "A simple skill"}
    body = "# Hello\n"
    result = convert_to_cursor_mdc(metadata, body)
    assert "alwaysApply: true" in result


def test_mdc_description_special_chars_quoted() -> None:
    """Description with YAML-special characters is wrapped in quotes.

    **Validates: Requirements 8.7**
    """
    metadata = {"name": "my-skill", "description": "has: colon"}
    body = "# Hello\n"
    result = convert_to_cursor_mdc(metadata, body)
    # Find the description line and verify it uses quoting
    lines = result.split("\n")
    desc_line = next(line for line in lines if line.startswith("description:"))
    assert desc_line.startswith('description: "'), (
        f"Expected description to be quoted, got: {desc_line!r}"
    )


def test_mdc_body_preserved() -> None:
    """Body content appears exactly after the closing --- delimiter.

    **Validates: Requirements 8.4**
    """
    metadata = {"name": "my-skill", "description": "A simple skill"}
    body = "# Title\n\nParagraph\n"
    result = convert_to_cursor_mdc(metadata, body)
    # Body should appear after the closing ---
    assert result.endswith("---\n" + body)
