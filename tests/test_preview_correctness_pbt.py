"""Property-based tests for markdown preview extraction correctness.

**Validates: Requirements 2.1, 2.2**

Property 2: Markdown Preview Extraction Correctness
- For any markdown file containing an H1 heading (line starting with "# "),
  the extracted title SHALL equal the text of that H1 heading (without the
  "# " prefix, stripped).
- For any markdown file WITHOUT an H1 heading within the first 50 lines,
  the title SHALL equal the filename stem.
"""

import tempfile
from pathlib import Path

from hypothesis import given, assume, settings, HealthCheck
from hypothesis import strategies as st

from render_dashboard import extract_markdown_preview, MarkdownPreview


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# Strategy for valid H1 heading text: non-empty strings without newlines
h1_title_text = st.text(
    alphabet=st.characters(
        categories=("L", "N", "P", "S", "Z"),
        exclude_characters="\n\r",
    ),
    min_size=1,
    max_size=80,
).filter(lambda s: s.strip())  # Must have non-whitespace content after strip


# Strategy for markdown body lines that are NOT H1 headings
# These lines must not start with "# " when stripped
non_h1_line_content = st.text(
    alphabet=st.characters(
        categories=("L", "N", "P", "S"),
        exclude_characters="\n\r#",
    ),
    min_size=0,
    max_size=60,
)


# Windows reserved device names that cannot be used as file names
_WINDOWS_RESERVED = frozenset(
    ["CON", "PRN", "AUX", "NUL"]
    + [f"COM{i}" for i in range(1, 10)]
    + [f"LPT{i}" for i in range(1, 10)]
)

# Strategy for filenames (valid filename stems without extension)
filename_stems = st.text(
    alphabet=st.sampled_from(
        "abcdefghijklmnopqrstuvwxyz"
        "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        "0123456789_-"
    ),
    min_size=1,
    max_size=30,
).filter(lambda s: s.upper() not in _WINDOWS_RESERVED)


# Strategy for lines that cannot be mistaken for H1 headings
# Avoids lines starting with "# " after stripping
def safe_non_h1_lines():
    """Generate lines that are definitely not H1 headings."""
    return st.one_of(
        # Empty lines
        st.just(""),
        # Lines starting with ## (H2+)
        st.builds(lambda t: f"## {t}", non_h1_line_content),
        # Plain text lines (no leading #)
        non_h1_line_content.filter(
            lambda s: not s.strip().startswith("# ")
        ),
    )


def safe_prefix_lines_before_h1():
    """Generate lines that can appear before an H1 heading without causing
    the scanner to break early.

    The scanner breaks when a paragraph ends (empty line after non-empty
    non-skip content). Safe prefix lines are those that the scanner skips:
    - Empty lines (skipped before paragraph starts)
    - Lines starting with ">" after stripping (blockquotes)
    - Lines starting with "##" after stripping (other headings)
    - Lines that are exactly "---" after stripping (horizontal rules)
    - Lines starting with "| " after stripping (tables, must have space after |)

    We avoid code fences in prefix to keep things simple.
    """
    non_empty_content = st.text(
        alphabet=st.characters(categories=("L", "N"), exclude_characters="\n\r"),
        min_size=1,
        max_size=30,
    )
    return st.one_of(
        # Empty lines (skipped before paragraph)
        st.just(""),
        # Blockquotes: "> text" - stripped still starts with ">"
        st.builds(lambda t: f"> {t}", non_empty_content),
        # Other headings: "## text" - stripped still starts with "##"
        st.builds(lambda t: f"## {t}", non_empty_content),
        # Horizontal rules
        st.just("---"),
        # Table lines: "| text" - stripped still starts with "| "
        st.builds(lambda t: f"| {t}", non_empty_content),
    )


# ---------------------------------------------------------------------------
# Property Tests
# ---------------------------------------------------------------------------

class TestH1TitleExtraction:
    """Property: When a markdown file contains an H1 heading, the extracted
    title equals the H1 text (without '# ' prefix, stripped)."""

    @given(
        title_text=h1_title_text,
        prefix_lines=st.lists(safe_prefix_lines_before_h1(), min_size=0, max_size=5),
        suffix_lines=st.lists(safe_non_h1_lines(), min_size=0, max_size=10),
        filename=filename_stems,
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_title_equals_h1_text(
        self, title_text: str, prefix_lines: list, suffix_lines: list, filename: str
    ):
        """For any markdown file with an H1 heading within the first 50 lines,
        the extracted title SHALL equal the H1 text without the '# ' prefix,
        stripped of leading/trailing whitespace.

        The prefix lines before the H1 must be lines that the scanner skips
        (empty lines, blockquotes, other headings, horizontal rules, tables)
        so that the scanner reaches the H1 without breaking early.

        **Validates: Requirements 2.1**
        """
        # Ensure total lines stay within 50-line scan limit
        assume(len(prefix_lines) + 1 + len(suffix_lines) <= 50)

        # Build the markdown content with H1 heading
        lines = prefix_lines + [f"# {title_text}"] + suffix_lines
        content = "\n".join(lines)

        # Write to a temp file and verify
        with tempfile.TemporaryDirectory() as tmp_dir:
            file_path = Path(tmp_dir) / f"{filename}.md"
            file_path.write_text(content, encoding="utf-8")

            result = extract_markdown_preview(file_path)
            assert result.title == title_text.strip()

    @given(
        title_text=h1_title_text,
        body_text=st.text(
            alphabet=st.characters(
                categories=("L", "N", "P", "S"),
                exclude_characters="\n\r",
            ),
            min_size=1,
            max_size=100,
        ).filter(lambda s: not s.strip().startswith(("#", ">", "```", "---", "| "))),
        filename=filename_stems,
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_title_independent_of_body_content(
        self, title_text: str, body_text: str, filename: str
    ):
        """The extracted title depends only on the H1 heading text, not on
        subsequent body content.

        **Validates: Requirements 2.1**
        """
        content = f"# {title_text}\n\n{body_text}\n"

        with tempfile.TemporaryDirectory() as tmp_dir:
            file_path = Path(tmp_dir) / f"{filename}.md"
            file_path.write_text(content, encoding="utf-8")

            result = extract_markdown_preview(file_path)
            assert result.title == title_text.strip()

    @given(
        title_text=h1_title_text,
        filename=filename_stems,
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_h1_on_first_line(self, title_text: str, filename: str):
        """An H1 heading on the very first line is correctly extracted.

        **Validates: Requirements 2.1**
        """
        content = f"# {title_text}\n"

        with tempfile.TemporaryDirectory() as tmp_dir:
            file_path = Path(tmp_dir) / f"{filename}.md"
            file_path.write_text(content, encoding="utf-8")

            result = extract_markdown_preview(file_path)
            assert result.title == title_text.strip()


class TestFilenameStemFallback:
    """Property: When no H1 heading exists within the first 50 lines,
    the title equals the filename stem."""

    @given(
        lines=st.lists(safe_non_h1_lines(), min_size=0, max_size=48),
        filename=filename_stems,
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_no_h1_uses_filename_stem(
        self, lines: list, filename: str
    ):
        """For any markdown file without an H1 heading within the first 50
        lines, the title SHALL equal the filename stem.

        **Validates: Requirements 2.2**
        """
        # Ensure none of the generated lines are H1 headings
        for line in lines:
            assume(not line.strip().startswith("# "))

        content = "\n".join(lines)

        with tempfile.TemporaryDirectory() as tmp_dir:
            file_path = Path(tmp_dir) / f"{filename}.md"
            file_path.write_text(content, encoding="utf-8")

            result = extract_markdown_preview(file_path)
            assert result.title == filename

    @given(
        filename=filename_stems,
    )
    @settings(max_examples=30, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_empty_file_uses_filename_stem(self, filename: str):
        """An empty file always uses the filename stem as title.

        **Validates: Requirements 2.2**
        """
        with tempfile.TemporaryDirectory() as tmp_dir:
            file_path = Path(tmp_dir) / f"{filename}.md"
            file_path.write_text("", encoding="utf-8")

            result = extract_markdown_preview(file_path)
            assert result.title == filename

    @given(
        title_text=h1_title_text,
        filler_lines=st.lists(safe_non_h1_lines(), min_size=50, max_size=55),
        filename=filename_stems,
    )
    @settings(max_examples=30, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_h1_beyond_50_lines_uses_filename_stem(
        self, title_text: str, filler_lines: list, filename: str
    ):
        """If the H1 heading appears after line 50, the filename stem is used
        because the scanner only reads 50 lines.

        **Validates: Requirements 2.2**
        """
        # Ensure filler lines don't contain H1 headings
        for line in filler_lines:
            assume(not line.strip().startswith("# "))

        # Place H1 after the 50-line scan window
        lines = filler_lines[:50] + [f"# {title_text}"]
        content = "\n".join(lines)

        with tempfile.TemporaryDirectory() as tmp_dir:
            file_path = Path(tmp_dir) / f"{filename}.md"
            file_path.write_text(content, encoding="utf-8")

            result = extract_markdown_preview(file_path)
            assert result.title == filename

    @given(
        h2_text=st.text(
            alphabet=st.characters(categories=("L", "N"), exclude_characters="\n\r"),
            min_size=1,
            max_size=40,
        ),
        filename=filename_stems,
    )
    @settings(max_examples=30, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_h2_does_not_count_as_h1(self, h2_text: str, filename: str):
        """H2 headings (## ...) do not satisfy the H1 requirement; filename
        stem is used instead.

        **Validates: Requirements 2.2**
        """
        content = f"## {h2_text}\n\nSome body text.\n"

        with tempfile.TemporaryDirectory() as tmp_dir:
            file_path = Path(tmp_dir) / f"{filename}.md"
            file_path.write_text(content, encoding="utf-8")

            result = extract_markdown_preview(file_path)
            assert result.title == filename
