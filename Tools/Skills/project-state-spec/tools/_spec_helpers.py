"""Pure utility functions for project-state-spec scaffold script.

These functions have NO side effects (other than ``safe_write``, which is
explicit) and are unit-tested in tests/test_spec_helpers.py.
"""

from __future__ import annotations

import datetime as _dt
import re as _re
from pathlib import Path

import yaml  # PyYAML, already in requirements.txt


class StatusYamlMissingError(FileNotFoundError):
    """Raised when ``<pst_root>/status/status.yaml`` does not exist."""


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


def today_iso() -> str:
    """Return current UTC date as ``YYYY-MM-DD``."""
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%d")


def load_status(pst_root: Path | str) -> dict:
    """Load and return ``<pst_root>/status/status.yaml`` as a dict.

    Raises ``StatusYamlMissingError`` if the file does not exist.
    """
    pst_root = Path(pst_root)
    status_path = pst_root / "status" / "status.yaml"
    if not status_path.is_file():
        raise StatusYamlMissingError(
            f"status.yaml not found at {status_path}. "
            "Run PST INIT first."
        )
    with status_path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    if not isinstance(data, dict):
        raise ValueError(f"status.yaml at {status_path} must be a mapping at top level")
    return data


_VALID_PREFIXES = {"R", "D", "LP", "TP"}


def next_id(status: dict, prefix: str) -> str:
    """Return the next sequential id for ``prefix`` (one of R, D, LP, TP).

    Scans ``status`` for any string id matching ``<prefix>-<NNN>`` across the
    sections that may contain it (``artifacts``, plus the dedicated
    ``research_findings`` / ``decisions`` lists). Returns the next number
    zero-padded to 3 digits.
    """
    if prefix not in _VALID_PREFIXES:
        raise ValueError(
            f"Unknown id prefix: {prefix!r}. Expected one of {sorted(_VALID_PREFIXES)}."
        )

    pattern = _re.compile(rf"^{_re.escape(prefix)}-(\d+)$")
    seen: list[int] = []

    sections = ["artifacts"]
    if prefix == "R":
        sections.append("research_findings")
    if prefix == "D":
        sections.append("decisions")

    for section in sections:
        for entry in status.get(section, []) or []:
            if not isinstance(entry, dict):
                continue
            entry_id = entry.get("id")
            if not isinstance(entry_id, str):
                continue
            m = pattern.match(entry_id)
            if m:
                seen.append(int(m.group(1)))

    next_num = (max(seen) + 1) if seen else 1
    return f"{prefix}-{next_num:03d}"
