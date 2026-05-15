#!/usr/bin/env python3
"""Distribute SKILL.md to Cursor MDC and Copilot formats.

Reads the project-state-tracker SKILL.md file, parses its YAML front-matter,
and converts/distributes the content to:
  - Cursor .mdc format (with description, globs, alwaysApply front-matter)
  - Copilot markdown format (pure body, no front-matter)

Usage:
    python distribute_skill.py [--skill-path PATH]
"""

import argparse
import re
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SKILL_MD_PATH = Path(r"C:\Users\chenshajie\.kiro\skills\project-state-tracker\SKILL.md")
CURSOR_MDC_PATH = Path(r"C:\Users\chenshajie\.cursor\rules\project-state-tracker.mdc")
COPILOT_PATH = Path(r"C:\Users\chenshajie\.github\copilot-instructions.md")


# ---------------------------------------------------------------------------
# Functions
# ---------------------------------------------------------------------------

def parse_front_matter(content: str) -> tuple[dict, str]:
    """Parse YAML front-matter from SKILL.md content.

    Args:
        content: Raw file content as a string.

    Returns:
        A tuple of (metadata_dict, body_str) where metadata_dict contains
        the 'name' and 'description' fields, and body_str is everything
        after the closing '---' delimiter.

    Raises:
        ValueError: If no front-matter is found, required fields are missing,
                    or the YAML content is invalid.
    """
    # Split content into lines preserving line endings
    # Check that file starts with --- on line 1
    lines = content.split("\n")
    if not lines or lines[0].rstrip("\r") != "---":
        raise ValueError(
            "No YAML front-matter found (file must start with ---)"
        )

    # Find closing --- delimiter (next line that is exactly ---)
    closing_idx = None
    for i in range(1, len(lines)):
        if lines[i].rstrip("\r") == "---":
            closing_idx = i
            break

    if closing_idx is None:
        raise ValueError(
            "No YAML front-matter found (file must start with ---)"
        )

    # Extract YAML content between delimiters
    yaml_lines = lines[1:closing_idx]

    # Parse key-value pairs from YAML content
    metadata: dict[str, str] = {}
    for line in yaml_lines:
        stripped = line.rstrip("\r")
        # Skip empty lines and comment lines
        if not stripped or stripped.startswith("#"):
            continue
        # Match key: value pattern
        match = re.match(r"^([a-zA-Z_][a-zA-Z0-9_]*)\s*:\s*(.*)", stripped)
        if match is None:
            raise ValueError(
                f"YAML parse failure: invalid line '{stripped}'"
            )
        key = match.group(1)
        value = match.group(2).strip()
        # Strip outer quotes if present (single or double)
        if len(value) >= 2:
            if value[0] == '"' and value[-1] == '"':
                value = value[1:-1]
                # Unescape YAML double-quote escape sequences
                value = value.replace('\\"', '"').replace("\\\\", "\\")
            elif value[0] == "'" and value[-1] == "'":
                value = value[1:-1]
        metadata[key] = value

    # Validate required fields
    if "name" not in metadata:
        raise ValueError("Required field 'name' missing from front-matter")
    if "description" not in metadata:
        raise ValueError(
            "Required field 'description' missing from front-matter"
        )

    # Body is everything after the closing delimiter
    # Rejoin remaining lines with \n to preserve original content
    body = "\n".join(lines[closing_idx + 1 :])

    return (metadata, body)


def convert_to_cursor_mdc(metadata: dict, body: str) -> str:
    """Convert parsed SKILL.md data to Cursor MDC format.

    Args:
        metadata: Dict with 'name' and 'description' keys.
        body: Markdown body content.

    Returns:
        Formatted string with Cursor MDC front-matter and body.
    """
    description = metadata["description"]

    # Characters that require YAML quoting
    yaml_special_chars = set(':#{["\'')

    if any(ch in yaml_special_chars for ch in description):
        # Escape backslashes first, then double quotes with backslash escape
        escaped = description.replace("\\", "\\\\").replace('"', '\\"')
        desc_value = f'"{escaped}"'
    else:
        desc_value = description

    # Build the MDC output
    front_matter = (
        f"---\n"
        f"description: {desc_value}\n"
        f'globs: ""\n'
        f"alwaysApply: true\n"
        f"---\n"
    )

    return front_matter + body


def convert_to_copilot(body: str) -> str:
    """Convert body content to Copilot instructions format.

    Args:
        body: Markdown body content.

    Returns:
        Body content as-is (no front-matter).
    """
    return body


def write_target(path: Path, content: str) -> None:
    """Write content to a target file, creating directories as needed.

    Args:
        path: Target file path.
        content: Content to write.

    Raises:
        OSError: If the file cannot be written due to permission or path errors.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def main() -> None:
    """Main entry point: parse args, read SKILL.md, convert, and distribute."""
    parser = argparse.ArgumentParser(
        description="Distribute SKILL.md to Cursor MDC and Copilot formats."
    )
    parser.add_argument(
        "--skill-path",
        type=Path,
        default=SKILL_MD_PATH,
        help="Path to SKILL.md (default: %(default)s)",
    )
    args = parser.parse_args()

    # Step 1: Read SKILL.md file
    skill_path: Path = args.skill_path
    try:
        content = skill_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        print(
            f"ERROR: Cannot read {skill_path}: No such file or directory",
            file=sys.stderr,
        )
        sys.exit(1)
    except PermissionError:
        print(
            f"ERROR: Cannot read {skill_path}: Permission denied",
            file=sys.stderr,
        )
        sys.exit(1)

    # Step 2: Parse front-matter
    try:
        metadata, body = parse_front_matter(content)
    except ValueError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    # Step 3: Convert to target formats
    cursor_content = convert_to_cursor_mdc(metadata, body)
    copilot_content = convert_to_copilot(body)

    # Step 4: Write targets and report
    targets = [
        (CURSOR_MDC_PATH, cursor_content),
        (COPILOT_PATH, copilot_content),
    ]

    for target_path, target_content in targets:
        try:
            write_target(target_path, target_content)
        except OSError as e:
            print(
                f"ERROR: Cannot write {target_path}: {e.strerror}",
                file=sys.stderr,
            )
            sys.exit(1)
        print(f"OK  {target_path.resolve()}")

    print(f"{len(targets)} targets updated")


if __name__ == "__main__":
    main()
