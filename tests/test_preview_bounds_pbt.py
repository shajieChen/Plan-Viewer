"""Property-based tests for markdown preview bounds.

**Validates: Requirements 2.3, 2.4**

Property 1: Markdown Preview Bounds
- For ANY markdown file, the extracted excerpt SHALL have length <= 200 characters.
- For ANY markdown file, the title SHALL be a non-empty string.
- No content beyond the first 50 lines SHALL influence the preview.
"""

import tempfile
from pathlib import Path

from hypothesis import given, settings, assume
from hypothesis import strategies as st

from render_dashboard import extract_markdown_preview, MarkdownPreview


# --- Strategies ---

# Strategy for generating random markdown line content
_markdown_line = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N", "P", "S", "Z"), blacklist_characters="\r\x00"),
    min_size=0,
    max_size=120,
)

# Strategy for generating heading lines
_heading_line = st.builds(
    lambda text: f"# {text}",
    st.text(min_size=1, max_size=80, alphabet=st.characters(whitelist_categories=("L", "N", "P", "S"), blacklist_characters="\r\n\x00")),
)

# Strategy for generating blockquote lines
_blockquote_line = st.builds(
    lambda text: f"> {text}",
    st.text(min_size=0, max_size=80, alphabet=st.characters(whitelist_categories=("L", "N", "P", "S"), blacklist_characters="\r\n\x00")),
)

# Strategy for generating paragraph lines (non-empty, no special prefixes)
_paragraph_line = st.text(
    min_size=1,
    max_size=200,
    alphabet=st.characters(whitelist_categories=("L", "N", "P", "S", "Z"), blacklist_characters="\r\n\x00"),
).filter(lambda s: s.strip() and not s.strip().startswith(("#", ">", "```", "---", "| ")))

# Strategy for generating a markdown element (one of several types)
_markdown_element = st.one_of(
    _heading_line,
    _paragraph_line,
    _blockquote_line,
    st.just(""),  # empty line
    st.just("---"),  # horizontal rule
    st.builds(
        lambda h: f"## {h}",
        st.text(min_size=1, max_size=40, alphabet=st.characters(whitelist_categories=("L", "N"), blacklist_characters="\r\n\x00")),
    ),
)

# Strategy for generating a full markdown document (list of lines)
_markdown_document = st.builds(
    lambda elements: "\n".join(elements),
    st.lists(_markdown_element, min_size=0, max_size=80),
)


def _write_temp_md(content: str, suffix: str = ".md") -> Path:
    """Write content to a temporary markdown file and return its path."""
    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=suffix, encoding="utf-8", delete=False)
    tmp.write(content)
    tmp.close()
    return Path(tmp.name)


class TestMarkdownPreviewBounds:
    """Property 1: Markdown Preview Bounds.

    **Validates: Requirements 2.3, 2.4**

    For ANY markdown file:
    - The extracted excerpt SHALL have length <= 200 characters.
    - The title SHALL be a non-empty string.
    - No content beyond the first 50 lines SHALL influence the preview.
    """

    @given(content=_markdown_document)
    @settings(max_examples=50, deadline=None)
    def test_excerpt_length_never_exceeds_200(self, content: str) -> None:
        """For any markdown content, excerpt length is always <= 200 chars.

        **Validates: Requirements 2.3**
        """
        file_path = _write_temp_md(content)
        try:
            result = extract_markdown_preview(file_path)
            assert len(result.excerpt) <= 200, (
                f"Excerpt length {len(result.excerpt)} exceeds 200 chars: {result.excerpt!r}"
            )
        finally:
            file_path.unlink(missing_ok=True)

    @given(content=_markdown_document)
    @settings(max_examples=50, deadline=None)
    def test_title_is_always_non_empty(self, content: str) -> None:
        """For any markdown content, title is always a non-empty string.

        **Validates: Requirements 2.3**
        """
        file_path = _write_temp_md(content)
        try:
            result = extract_markdown_preview(file_path)
            assert isinstance(result.title, str)
            assert len(result.title) > 0, "Title must be non-empty"
        finally:
            file_path.unlink(missing_ok=True)

    @given(
        first_50_lines=st.lists(_markdown_element, min_size=50, max_size=50),
        extra_content=st.text(
            min_size=10,
            max_size=200,
            alphabet=st.characters(whitelist_categories=("L", "N"), blacklist_characters="\r\n\x00"),
        ),
    )
    @settings(max_examples=30, deadline=None)
    def test_content_beyond_50_lines_does_not_influence_preview(
        self, first_50_lines: list[str], extra_content: str
    ) -> None:
        """No content beyond line 50 SHALL influence the preview.

        **Validates: Requirements 2.4**

        Strategy: Generate exactly 50 lines of markdown, then append unique
        content on lines 51+. Verify that the unique content does NOT appear
        in either the title or the excerpt.
        """
        # Ensure extra_content is unique enough to detect if it leaks
        assume(len(extra_content.strip()) >= 5)
        # Make sure the extra content doesn't accidentally match something in first 50 lines
        joined_first_50 = "\n".join(first_50_lines)
        assume(extra_content not in joined_first_50)

        # Build file: exactly 50 lines, then extra content on line 51+
        lines_beyond = [extra_content] * 5  # Put unique content on lines 51-55
        full_content = joined_first_50 + "\n" + "\n".join(lines_beyond)

        file_path = _write_temp_md(full_content)
        try:
            result = extract_markdown_preview(file_path)

            # The unique extra_content should NOT appear in the preview
            assert extra_content not in result.title, (
                f"Content from beyond line 50 leaked into title: {extra_content!r} found in {result.title!r}"
            )
            assert extra_content not in result.excerpt, (
                f"Content from beyond line 50 leaked into excerpt: {extra_content!r} found in {result.excerpt!r}"
            )
        finally:
            file_path.unlink(missing_ok=True)
