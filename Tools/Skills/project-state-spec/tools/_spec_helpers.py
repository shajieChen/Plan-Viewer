"""Pure utility functions for project-state-spec scaffold script.

These functions have NO side effects (other than ``safe_write``, which is
explicit) and are unit-tested in tests/test_spec_helpers.py.
"""

from __future__ import annotations

import re as _re
from pathlib import Path


def slugify(text: str) -> str:
    """Lowercase, replace non-ASCII alphanumerics with ``-``, collapse repeats.

    Raises ``ValueError`` if the result would be empty.
    """
    lowered = text.lower()
    # Replace every char that is not [a-z0-9] with a hyphen.
    replaced = _re.sub(r"[^a-z0-9]+", "-", lowered)
    # Collapse runs of hyphens, strip leading/trailing.
    collapsed = _re.sub(r"-+", "-", replaced).strip("-")
    if not collapsed:
        raise ValueError(f"slugify produced empty string from input: {text!r}")
    return collapsed
