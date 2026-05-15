"""Property-based tests for distribute_skill.py.

Tests the YAML front-matter parsing and format conversion functions
used to distribute SKILL.md to Cursor MDC and Copilot formats.
"""

import string
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "Docs" / "tools"))

from hypothesis import given, settings
from hypothesis import strategies as st

from distribute_skill import parse_front_matter, convert_to_cursor_mdc


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _extract_mdc_description(mdc_content: str) -> str:
    """Extract the description value from Cursor MDC front-matter.

    The MDC format has description, globs, and alwaysApply fields (no name),
    so we parse the description line directly rather than using
    parse_front_matter which requires a name field.
    """
    lines = mdc_content.split("\n")
    assert lines[0] == "---", "MDC output must start with ---"

    # Find the description line
    for line in lines[1:]:
        if line.rstrip("\r") == "---":
            break
        if line.startswith("description:"):
            value = line[len("description:"):].strip()
            # Strip outer quotes if present (double quotes used for YAML safety)
            if len(value) >= 2 and value[0] == '"' and value[-1] == '"':
                # Unescape backslash-escaped characters
                inner = value[1:-1]
                inner = inner.replace('\\"', '"').replace('\\\\', '\\')
                return inner
            return value

    raise AssertionError("No description field found in MDC front-matter")


# ---------------------------------------------------------------------------
# Feature: skill-distribution-bat, Property 3: Metadata extraction round-trip
# ---------------------------------------------------------------------------


# --- Strategies ---

_name_alphabet = string.ascii_lowercase + string.digits + "-"

_name_strategy = st.text(
    alphabet=_name_alphabet,
    min_size=1,
    max_size=50,
)

# Description: avoid newlines (would break simple YAML parsing), leading
# "---" (would confuse front-matter delimiter detection), and strings
# with leading/trailing whitespace (stripped by the parser's .strip() call).
_description_strategy = st.text(
    min_size=1,
    max_size=200,
).filter(
    lambda s: "\n" not in s
    and "\r" not in s
    and not s.startswith("---")
    and s == s.strip()
    and len(s.strip()) > 0
)


@settings(max_examples=100)
@given(name=_name_strategy, description=_description_strategy)
def test_metadata_extraction_round_trip(name: str, description: str) -> None:
    """Property 3: Metadata extraction round-trip.

    For any valid name and description placed in SKILL.md YAML front-matter,
    parsing SHALL extract those exact values, and converting to Cursor MDC
    SHALL produce output whose front-matter contains the original description
    (semantically equal).

    **Validates: Requirements 7.2, 8.1**
    """
    # Compose a valid SKILL.md
    skill_content = f"---\nname: {name}\ndescription: {description}\n---\nbody content"

    # Parse front-matter
    metadata, body = parse_front_matter(skill_content)

    # Assert parsed metadata matches original values
    assert metadata["name"] == name
    assert metadata["description"] == description

    # Convert to Cursor MDC
    mdc_output = convert_to_cursor_mdc(metadata, body)

    # Parse the MDC output's front-matter to extract description
    mdc_description = _extract_mdc_description(mdc_output)

    # Assert the Cursor MDC front-matter description equals the original
    assert mdc_description == description


# ---------------------------------------------------------------------------
# Feature: skill-distribution-bat, Property 4: Missing field validation
# ---------------------------------------------------------------------------

# Strategy: generate random name/description values, then choose which to omit
_field_text = st.text(
    min_size=1,
    max_size=100,
    alphabet=st.characters(
        blacklist_characters="\x00\r\n",
        blacklist_categories=("Cs",),
    ),
).filter(lambda s: "---" not in s and ":" not in s)

_missing_mode = st.sampled_from(["missing_name", "missing_description", "missing_both"])


def _compose_skill_md_missing_field(name: str, description: str, mode: str) -> str:
    """Compose a SKILL.md with valid YAML but missing one or both required fields."""
    lines = ["---"]
    if mode == "missing_description":
        lines.append(f"name: {name}")
    elif mode == "missing_name":
        lines.append(f"description: {description}")
    # missing_both: no name or description lines
    lines.append("---")
    lines.append("# Body content")
    return "\n".join(lines)


class TestMissingFieldValidation:
    """Property 4: Missing field validation.

    **Validates: Requirements 7.3**

    For any SKILL.md file with valid YAML front-matter that is missing either
    the `name` field, the `description` field, or both, the parser SHALL reject
    the input with a ValueError and an error message identifying which specific
    field is missing.
    """

    @given(
        name=_field_text,
        description=_field_text,
        mode=_missing_mode,
    )
    @settings(max_examples=100, deadline=None)
    def test_missing_field_raises_valueerror(
        self, name: str, description: str, mode: str
    ) -> None:
        """Parse SKILL.md with missing required field(s) and assert ValueError
        is raised with a message identifying the missing field.

        **Validates: Requirements 7.3**
        """
        content = _compose_skill_md_missing_field(name, description, mode)

        import pytest

        with pytest.raises(ValueError) as exc_info:
            parse_front_matter(content)

        error_msg = str(exc_info.value)

        if mode == "missing_name":
            assert "'name'" in error_msg, (
                f"Expected error message to contain \"'name'\" but got: {error_msg!r}"
            )
        elif mode == "missing_description":
            assert "'description'" in error_msg, (
                f"Expected error message to contain \"'description'\" but got: {error_msg!r}"
            )
        elif mode == "missing_both":
            # name is checked first, so error should mention 'name'
            assert "'name'" in error_msg, (
                f"Expected error message to contain \"'name'\" when both fields "
                f"are missing but got: {error_msg!r}"
            )


# ---------------------------------------------------------------------------
# Feature: skill-distribution-bat, Property 5: YAML escaping produces valid output
# ---------------------------------------------------------------------------

import yaml

# Strategy: generate description strings that MUST contain at least one
# YAML-special character from : " ' # [ {
# Avoid newlines (they would break the single-line YAML value) and
# control characters that YAML readers reject.
_yaml_special_chars = ':"\'#[{'

# Safe printable characters for surrounding text
_printable_no_newline = st.characters(
    blacklist_characters="\x00\r\n",
    blacklist_categories=("Cs", "Cc"),
)

# Build descriptions by combining normal text with at least one special char
_description_with_yaml_special = st.builds(
    lambda prefix, special, suffix: prefix + special + suffix,
    prefix=st.text(min_size=0, max_size=80, alphabet=_printable_no_newline),
    special=st.text(
        min_size=1,
        max_size=20,
        alphabet=st.sampled_from(list(_yaml_special_chars)),
    ),
    suffix=st.text(min_size=0, max_size=80, alphabet=_printable_no_newline),
)


class TestYamlEscapingProducesValidOutput:
    """Property 5: YAML escaping produces valid output.

    **Validates: Requirements 8.7**

    For any description string containing YAML-special characters
    (`:`, `"`, `'`, `#`, `[`, `{`), the Cursor MDC conversion SHALL produce
    output where the front-matter block is parseable as valid YAML and the
    parsed description value is semantically equal to the original input.
    """

    @given(desc=_description_with_yaml_special)
    @settings(max_examples=100, deadline=None)
    def test_yaml_escaping_produces_parseable_output(self, desc: str) -> None:
        """Convert description with YAML-special chars to MDC format,
        parse the front-matter as YAML, and verify the description round-trips.

        **Validates: Requirements 8.7**
        """
        # Convert to Cursor MDC format
        metadata = {"name": "test", "description": desc}
        result = convert_to_cursor_mdc(metadata, "body")

        # Extract front-matter block (between first and second ---)
        lines = result.split("\n")
        assert lines[0] == "---", f"Expected opening --- but got: {lines[0]!r}"

        closing_idx = None
        for i in range(1, len(lines)):
            if lines[i] == "---":
                closing_idx = i
                break

        assert closing_idx is not None, "No closing --- found in MDC output"

        # Parse the front-matter as YAML
        front_matter_text = "\n".join(lines[1:closing_idx])
        try:
            parsed = yaml.safe_load(front_matter_text)
        except yaml.YAMLError as e:
            raise AssertionError(
                f"Front-matter is not valid YAML.\n"
                f"Input description: {desc!r}\n"
                f"Front-matter text:\n{front_matter_text}\n"
                f"YAML error: {e}"
            ) from e

        # Assert parsed description equals original
        assert parsed is not None, "YAML parsed to None"
        assert "description" in parsed, (
            f"Parsed YAML missing 'description' key. Got keys: {list(parsed.keys())}"
        )
        assert parsed["description"] == desc, (
            f"Description mismatch after YAML round-trip.\n"
            f"Original:  {desc!r}\n"
            f"Parsed:    {parsed['description']!r}"
        )


# ---------------------------------------------------------------------------
# Feature: skill-distribution-bat, Property 2: Front-matter boundary detection
# ---------------------------------------------------------------------------


# Unicode characters including emoji, CJK, accented, symbols — no null bytes
_unicode_chars_p2 = st.characters(
    whitelist_categories=("L", "N", "P", "S", "Z", "So"),
    blacklist_characters="\x00",
)


# Strategy for body content that always contains at least one `---` line
@st.composite
def _body_with_separator_lines(draw):
    """Generate body content containing one or more lines that are exactly `---`.

    Ensures the body always has at least one `---` line to test that the parser
    does NOT treat it as a front-matter delimiter.
    """
    num_lines = draw(st.integers(min_value=3, max_value=20))
    lines = []
    for _ in range(num_lines):
        lines.append(
            draw(
                st.one_of(
                    st.text(min_size=0, max_size=60, alphabet=_unicode_chars_p2),
                    st.just(""),
                )
            )
        )

    # Insert at least one `---` line at a random position
    num_separators = draw(st.integers(min_value=1, max_value=3))
    for _ in range(num_separators):
        insert_pos = draw(st.integers(min_value=0, max_value=len(lines)))
        lines.insert(insert_pos, "---")

    return "\n".join(lines)


class TestFrontMatterBoundaryDetection:
    """Property 2: Front-matter boundary detection.

    # Feature: skill-distribution-bat, Property 2: Front-matter boundary detection

    **Validates: Requirements 7.1, 11.3**

    For any SKILL.md file where the body content contains one or more lines
    that are exactly `---`, the parser SHALL treat only the first `---`-delimited
    block (starting at line 1) as YAML front-matter, and all subsequent `---`
    occurrences SHALL be preserved as part of the body content.
    """

    @given(body=_body_with_separator_lines())
    @settings(max_examples=100, deadline=None)
    def test_only_first_block_treated_as_front_matter(self, body: str) -> None:
        """Parser treats only the first `---` block as front-matter.

        **Validates: Requirements 7.1, 11.3**
        """
        # Compose valid SKILL.md with known front-matter and body containing ---
        skill_md = f"---\nname: test-skill\ndescription: test desc\n---\n{body}"

        # Parse front-matter
        metadata, extracted_body = parse_front_matter(skill_md)

        # Assert the parsed metadata has the expected name and description
        assert metadata["name"] == "test-skill", (
            f"Expected name='test-skill', got name={metadata['name']!r}"
        )
        assert metadata["description"] == "test desc", (
            f"Expected description='test desc', got description={metadata['description']!r}"
        )

    @given(body=_body_with_separator_lines())
    @settings(max_examples=100, deadline=None)
    def test_all_separator_lines_preserved_in_body(self, body: str) -> None:
        """All `---` lines in the body are preserved after parsing.

        **Validates: Requirements 7.1, 11.3**
        """
        # Compose valid SKILL.md with known front-matter and body containing ---
        skill_md = f"---\nname: test-skill\ndescription: test desc\n---\n{body}"

        # Parse front-matter
        metadata, extracted_body = parse_front_matter(skill_md)

        # Count --- lines in original body
        original_separator_count = body.split("\n").count("---")

        # Count --- lines in extracted body
        extracted_separator_count = extracted_body.split("\n").count("---")

        # All --- occurrences in the body must be preserved
        assert extracted_separator_count == original_separator_count, (
            f"Expected {original_separator_count} '---' lines in body, "
            f"got {extracted_separator_count}.\n"
            f"Original body repr: {body!r}\n"
            f"Extracted body repr: {extracted_body!r}"
        )

    @given(body=_body_with_separator_lines())
    @settings(max_examples=100, deadline=None)
    def test_body_is_exactly_the_generated_content(self, body: str) -> None:
        """Extracted body is exactly the generated body content.

        **Validates: Requirements 7.1, 11.3**
        """
        # Compose valid SKILL.md with known front-matter and body containing ---
        skill_md = f"---\nname: test-skill\ndescription: test desc\n---\n{body}"

        # Parse front-matter
        metadata, extracted_body = parse_front_matter(skill_md)

        # Assert body is exactly the generated body content
        assert extracted_body == body, (
            f"Extracted body differs from generated body.\n"
            f"Generated body repr: {body!r}\n"
            f"Extracted body repr: {extracted_body!r}"
        )
