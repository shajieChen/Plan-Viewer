"""Unit tests for extract_markdown_preview function.

Tests cover:
- Title extraction from H1 heading
- Fallback to filename stem when no H1
- Paragraph extraction (skipping code fences, blockquotes, headings, rules, tables)
- Truncation to 200 characters
- 50-line scan limit
- Missing/unreadable file fallback
- Files with no paragraph (empty excerpt)

Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6
"""

import os
from pathlib import Path

import pytest

from render_dashboard import extract_markdown_preview, MarkdownPreview


@pytest.fixture
def tmp_md(tmp_path):
    """Helper to create a temporary markdown file with given content."""
    def _create(content: str, filename: str = "test_file.md") -> Path:
        file_path = tmp_path / filename
        file_path.write_text(content, encoding="utf-8")
        return file_path
    return _create


class TestTitleExtraction:
    """Tests for title extraction from H1 heading (Requirement 2.1)."""

    def test_extracts_title_from_h1(self, tmp_md):
        content = "# My Document Title\n\nSome paragraph text here."
        result = extract_markdown_preview(tmp_md(content))
        assert result.title == "My Document Title"

    def test_extracts_title_with_extra_spaces(self, tmp_md):
        content = "#   Spaced Title   \n\nParagraph."
        result = extract_markdown_preview(tmp_md(content))
        assert result.title == "Spaced Title"

    def test_fallback_to_filename_stem_when_no_h1(self, tmp_md):
        content = "## Only H2 heading\n\nSome text."
        result = extract_markdown_preview(tmp_md(content, "my_document.md"))
        assert result.title == "my_document"

    def test_fallback_to_filename_stem_empty_file(self, tmp_md):
        content = ""
        result = extract_markdown_preview(tmp_md(content, "empty_doc.md"))
        assert result.title == "empty_doc"

    def test_uses_first_h1_only(self, tmp_md):
        content = "# First Title\n\n# Second Title\n\nParagraph."
        result = extract_markdown_preview(tmp_md(content))
        assert result.title == "First Title"


class TestParagraphExtraction:
    """Tests for first paragraph extraction (Requirement 2.2)."""

    def test_extracts_simple_paragraph(self, tmp_md):
        content = "# Title\n\nThis is the first paragraph."
        result = extract_markdown_preview(tmp_md(content))
        assert result.excerpt == "This is the first paragraph."

    def test_joins_multiline_paragraph(self, tmp_md):
        content = "# Title\n\nLine one of paragraph.\nLine two of paragraph."
        result = extract_markdown_preview(tmp_md(content))
        assert result.excerpt == "Line one of paragraph. Line two of paragraph."

    def test_skips_code_fences(self, tmp_md):
        content = "# Title\n\n```python\ncode here\n```\n\nActual paragraph."
        result = extract_markdown_preview(tmp_md(content))
        assert result.excerpt == "Actual paragraph."

    def test_skips_blockquotes(self, tmp_md):
        content = "# Title\n\n> This is a quote\n\nActual paragraph."
        result = extract_markdown_preview(tmp_md(content))
        assert result.excerpt == "Actual paragraph."

    def test_skips_h2_headings(self, tmp_md):
        content = "# Title\n\n## Section\n\nActual paragraph."
        result = extract_markdown_preview(tmp_md(content))
        assert result.excerpt == "Actual paragraph."

    def test_skips_horizontal_rules(self, tmp_md):
        content = "# Title\n\n---\n\nActual paragraph."
        result = extract_markdown_preview(tmp_md(content))
        assert result.excerpt == "Actual paragraph."

    def test_skips_tables(self, tmp_md):
        content = "# Title\n\n| Col1 | Col2 |\n| --- | --- |\n\nActual paragraph."
        result = extract_markdown_preview(tmp_md(content))
        assert result.excerpt == "Actual paragraph."

    def test_paragraph_ends_at_empty_line(self, tmp_md):
        content = "# Title\n\nFirst paragraph.\n\nSecond paragraph."
        result = extract_markdown_preview(tmp_md(content))
        assert result.excerpt == "First paragraph."

    def test_paragraph_ends_at_code_fence(self, tmp_md):
        content = "# Title\n\nParagraph start.\n```\ncode\n```"
        result = extract_markdown_preview(tmp_md(content))
        assert result.excerpt == "Paragraph start."

    def test_paragraph_without_title(self, tmp_md):
        content = "This is a paragraph without any heading."
        result = extract_markdown_preview(tmp_md(content, "no_heading.md"))
        assert result.title == "no_heading"
        assert result.excerpt == "This is a paragraph without any heading."


class TestTruncation:
    """Tests for 200-character truncation (Requirement 2.3)."""

    def test_truncates_at_200_chars(self, tmp_md):
        long_text = "A" * 300
        content = f"# Title\n\n{long_text}"
        result = extract_markdown_preview(tmp_md(content))
        assert len(result.excerpt) == 200
        assert result.excerpt == "A" * 200

    def test_no_truncation_under_200(self, tmp_md):
        text = "Short paragraph."
        content = f"# Title\n\n{text}"
        result = extract_markdown_preview(tmp_md(content))
        assert result.excerpt == text

    def test_exactly_200_chars_not_truncated(self, tmp_md):
        text = "B" * 200
        content = f"# Title\n\n{text}"
        result = extract_markdown_preview(tmp_md(content))
        assert len(result.excerpt) == 200


class TestScanLimit:
    """Tests for 50-line scan limit (Requirement 2.4)."""

    def test_does_not_read_beyond_50_lines(self, tmp_md):
        # Put 49 empty lines, then a paragraph on line 51 (index 50)
        lines = ["# Title\n"] + ["\n"] * 49 + ["This should not be found.\n"]
        content = "".join(lines)
        result = extract_markdown_preview(tmp_md(content))
        assert result.excerpt == ""

    def test_reads_paragraph_within_50_lines(self, tmp_md):
        # Title on line 0, empty on line 1, paragraph on line 2
        lines = ["# Title\n", "\n", "Found within limit.\n"]
        content = "".join(lines)
        result = extract_markdown_preview(tmp_md(content))
        assert result.excerpt == "Found within limit."


class TestMissingFile:
    """Tests for missing/unreadable file fallback (Requirement 2.5)."""

    def test_missing_file_returns_fallback(self):
        path = Path("nonexistent_document.md")
        result = extract_markdown_preview(path)
        assert result.title == "nonexistent_document"
        assert result.excerpt == "[File not found]"

    def test_missing_file_uses_stem_not_extension(self):
        path = Path("/some/path/my-plan.md")
        result = extract_markdown_preview(path)
        assert result.title == "my-plan"
        assert result.excerpt == "[File not found]"


class TestNoParagraph:
    """Tests for files with no paragraph (Requirement 2.6)."""

    def test_only_headings_returns_empty_excerpt(self, tmp_md):
        content = "# Title\n\n## Section 1\n\n## Section 2\n"
        result = extract_markdown_preview(tmp_md(content))
        assert result.title == "Title"
        assert result.excerpt == ""

    def test_only_code_fences_returns_empty_excerpt(self, tmp_md):
        content = "# Title\n\n```python\nprint('hello')\n```\n"
        result = extract_markdown_preview(tmp_md(content))
        assert result.title == "Title"
        assert result.excerpt == ""

    def test_empty_file_returns_empty_excerpt(self, tmp_md):
        content = ""
        result = extract_markdown_preview(tmp_md(content, "blank.md"))
        assert result.title == "blank"
        assert result.excerpt == ""
