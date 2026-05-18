#!/usr/bin/env python3
"""Install all Skills under Tools/Skills/ to all supported AI Agents.

Source of truth: Q:\\Plan_Viewer\\Tools\\Skills\\<skill>\\SKILL.md (+ optional sub-folders).

Targets (per design 2026-05-18-skill-installer-multi-agent-design.md):
  - Kiro    : %USERPROFILE%\\.kiro\\skills\\<skill>\\           (folder copy)
  - Cursor  : %USERPROFILE%\\.cursor\\rules\\<skill>.mdc        (single MDC file)
  - Claude  : %USERPROFILE%\\.claude\\skills\\<skill>\\         (folder copy)
  - Copilot : %USERPROFILE%\\.github\\copilot-instructions.md   (shared, all skills concatenated)
  - Codex   : %USERPROFILE%\\.codex\\AGENTS.md                  (shared, all skills concatenated)

Usage:
    python Tools/install_skills.py
"""

from __future__ import annotations

import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

# ---------------------------------------------------------------------------
# Reuse parser / Cursor MDC converter from Docs/tools/distribute_skill.py
# ---------------------------------------------------------------------------

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "Docs" / "tools"))

try:
    from distribute_skill import (  # type: ignore  # noqa: E402
        convert_to_cursor_mdc,
        parse_front_matter,
    )
except ImportError as exc:  # pragma: no cover - environment failure
    print(
        f"ERROR: Cannot import distribute_skill from Docs/tools/: {exc}",
        file=sys.stderr,
    )
    sys.exit(1)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SKILLS_SOURCE_DIR = _ROOT / "Tools" / "Skills"
HOME = Path.home()

# Each Agent description is a plain dict so it's trivially overrideable in tests.
AGENTS: list[dict] = [
    {"id": "kiro",    "kind": "folder", "target": HOME / ".kiro" / "skills"},
    {"id": "cursor",  "kind": "mdc",    "target": HOME / ".cursor" / "rules"},
    {"id": "claude",  "kind": "folder", "target": HOME / ".claude" / "skills"},
    {"id": "copilot", "kind": "shared", "target": HOME / ".github" / "copilot-instructions.md"},
    {"id": "codex",   "kind": "shared", "target": HOME / ".codex" / "AGENTS.md"},
]

BEGIN_MARK = "<!-- BEGIN: {skill} -->"
END_MARK = "<!-- END: {skill} -->"

SEPARATOR = "=" * 60


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Skill:
    """A discovered, parsed Skill from Tools/Skills/<name>/."""

    name: str            # subdirectory name, canonical identifier
    source_dir: Path     # Tools/Skills/<name>/
    metadata: dict       # parsed YAML front-matter (must contain name + description)
    body: str            # SKILL.md content with front-matter stripped


@dataclass(frozen=True)
class InstallResult:
    """Outcome of a single (skill, agent) install attempt."""

    skill_name: str | None  # None for shared-file results that aggregate skills
    agent_id: str
    target_path: Path
    success: bool
    error: str | None = None


# ---------------------------------------------------------------------------
# Discovery / loading
# ---------------------------------------------------------------------------


def discover_skills(source_dir: Path) -> list[Path]:
    """Return sorted list of subdirectories of ``source_dir`` containing SKILL.md.

    Subdirectories without SKILL.md are skipped with a SKIP line on stdout.

    Raises:
        FileNotFoundError: if ``source_dir`` itself does not exist.
    """
    if not source_dir.exists():
        raise FileNotFoundError(f"Skills source directory does not exist: {source_dir}")

    discovered: list[Path] = []
    for entry in sorted(source_dir.iterdir(), key=lambda p: p.name):
        if not entry.is_dir():
            continue
        if (entry / "SKILL.md").is_file():
            discovered.append(entry)
        else:
            print(f"SKIP: {entry.name} (no SKILL.md)")
    return discovered


def load_skill(skill_dir: Path) -> Skill:
    """Read SKILL.md, parse front-matter, return a Skill instance.

    Raises:
        ValueError: if SKILL.md is missing required front-matter fields.
        OSError: if SKILL.md cannot be read.
    """
    skill_md = skill_dir / "SKILL.md"
    content = skill_md.read_text(encoding="utf-8")
    metadata, body = parse_front_matter(content)
    # parse_front_matter already validates name + description, but be defensive.
    if "name" not in metadata or "description" not in metadata:
        raise ValueError(
            f"SKILL.md at {skill_md} is missing required front-matter fields"
        )
    return Skill(
        name=skill_dir.name,
        source_dir=skill_dir,
        metadata=metadata,
        body=body,
    )


# ---------------------------------------------------------------------------
# Installers
# ---------------------------------------------------------------------------


def _install_folder(skill: Skill, agent: dict) -> InstallResult:
    """Copy the entire Skill folder into ``agent["target"]/<skill.name>/``.

    Excludes ``__pycache__/`` and ``*.pyc``. Overwrites existing content.
    """
    target = agent["target"] / skill.name
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(
            skill.source_dir,
            target,
            dirs_exist_ok=True,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
        )
    except OSError as exc:
        return InstallResult(
            skill_name=skill.name,
            agent_id=agent["id"],
            target_path=target,
            success=False,
            error=f"{type(exc).__name__}: {exc}",
        )
    return InstallResult(
        skill_name=skill.name,
        agent_id=agent["id"],
        target_path=target,
        success=True,
    )


def install_kiro(skill: Skill, agent: dict) -> InstallResult:
    return _install_folder(skill, agent)


def install_claude(skill: Skill, agent: dict) -> InstallResult:
    return _install_folder(skill, agent)


def install_cursor(skill: Skill, agent: dict) -> InstallResult:
    """Convert SKILL.md to Cursor MDC and write to ``agent["target"]/<name>.mdc``."""
    target = agent["target"] / f"{skill.name}.mdc"
    try:
        mdc_content = convert_to_cursor_mdc(skill.metadata, skill.body)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(mdc_content, encoding="utf-8")
    except OSError as exc:
        return InstallResult(
            skill_name=skill.name,
            agent_id=agent["id"],
            target_path=target,
            success=False,
            error=f"{type(exc).__name__}: {exc}",
        )
    return InstallResult(
        skill_name=skill.name,
        agent_id=agent["id"],
        target_path=target,
        success=True,
    )


def build_shared_content(skills: list[Skill]) -> str:
    """Concatenate all skills' bodies with BEGIN/END marker blocks.

    Each skill block:

        <!-- BEGIN: <name> -->

        <body>

        <!-- END: <name> -->

    Blocks are separated by a single blank line. Output uses LF line endings.
    The caller is responsible for sorting ``skills`` by name (this function does
    NOT re-sort). With an empty list, returns an empty string.
    """
    if not skills:
        return ""

    blocks: list[str] = []
    for skill in skills:
        # Strip trailing whitespace from body so we don't get accidental triple
        # blank lines, but preserve internal whitespace and Unicode byte-for-byte.
        body_normalized = skill.body.replace("\r\n", "\n").rstrip()
        block = (
            f"{BEGIN_MARK.format(skill=skill.name)}\n"
            f"\n"
            f"{body_normalized}\n"
            f"\n"
            f"{END_MARK.format(skill=skill.name)}"
        )
        blocks.append(block)
    return "\n\n".join(blocks) + "\n"


def install_shared(content: str, agent: dict) -> InstallResult:
    """Write shared-file content (Copilot / Codex) to ``agent["target"]``.

    Creates the parent directory if missing. Overwrites the file. Uses LF
    line endings (because ``content`` is already LF-only and we open the file
    with ``newline=""``).
    """
    target: Path = agent["target"]
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        with open(target, "w", encoding="utf-8", newline="") as fh:
            fh.write(content)
    except OSError as exc:
        return InstallResult(
            skill_name=None,
            agent_id=agent["id"],
            target_path=target,
            success=False,
            error=f"{type(exc).__name__}: {exc}",
        )
    return InstallResult(
        skill_name=None,
        agent_id=agent["id"],
        target_path=target,
        success=True,
    )


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------


def _format_target(path: Path, is_folder: bool) -> str:
    """Render a target path with a trailing separator for folders."""
    suffix = "\\" if is_folder else ""
    return f"{path}{suffix}"


def print_summary(results: list[InstallResult]) -> None:
    """Print closing summary banner; emit per-failure details to stderr."""
    successes = sum(1 for r in results if r.success)
    failures = sum(1 for r in results if not r.success)
    print()
    print(SEPARATOR)
    print(f"  Summary: {successes} target(s) updated, {failures} failed")
    print(SEPARATOR)
    if failures:
        for r in results:
            if r.success:
                continue
            label = (
                f"{r.agent_id} / {r.skill_name}" if r.skill_name else r.agent_id
            )
            print(f"ERROR: {label}: {r.error}", file=sys.stderr)


def _agent_by_id(agent_id: str) -> dict:
    for a in AGENTS:
        if a["id"] == agent_id:
            return a
    raise KeyError(agent_id)  # pragma: no cover


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    """Discover skills, install them to all Agents, print summary, exit 0/1."""
    print(SEPARATOR)
    print("  Skill Installer")
    print(SEPARATOR)
    print()

    try:
        discovered = discover_skills(SKILLS_SOURCE_DIR)
    except FileNotFoundError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)

    if not discovered:
        print(
            f"ERROR: No SKILL.md found in {SKILLS_SOURCE_DIR}",
            file=sys.stderr,
        )
        sys.exit(1)

    print(f"Discovered {len(discovered)} skill(s) in Tools/Skills/:")
    for d in discovered:
        print(f"  - {d.name}")
    print()

    results: list[InstallResult] = []
    loaded_skills: list[Skill] = []

    # Per-skill, non-shared agents
    folder_agents = [a for a in AGENTS if a["kind"] in ("folder", "mdc")]
    folder_kinds = {"kiro", "cursor", "claude"}

    for idx, skill_dir in enumerate(discovered, start=1):
        print(f"[{idx}/{len(discovered)}] {skill_dir.name}")

        # Load (parse front-matter)
        try:
            skill = load_skill(skill_dir)
        except (ValueError, OSError) as exc:
            for agent_id in folder_kinds:
                agent = _agent_by_id(agent_id)
                target = agent["target"] / skill_dir.name
                if agent_id == "cursor":
                    target = agent["target"] / f"{skill_dir.name}.mdc"
                fail = InstallResult(
                    skill_name=skill_dir.name,
                    agent_id=agent_id,
                    target_path=target,
                    success=False,
                    error=f"load_skill failed: {exc}",
                )
                results.append(fail)
                print(f"  FAIL {agent_id:8s} {fail.error}")
            print()
            continue
        loaded_skills.append(skill)

        for agent in folder_agents:
            if agent["id"] == "kiro":
                r = install_kiro(skill, agent)
                is_folder = True
            elif agent["id"] == "claude":
                r = install_claude(skill, agent)
                is_folder = True
            elif agent["id"] == "cursor":
                r = install_cursor(skill, agent)
                is_folder = False
            else:  # pragma: no cover - guarded by AGENTS shape
                continue
            results.append(r)
            tag = "OK  " if r.success else "FAIL"
            if r.success:
                print(
                    f"  {tag} {agent['id']:8s} {_format_target(r.target_path, is_folder)}"
                )
            else:
                print(f"  {tag} {agent['id']:8s} {r.error}")
        print()

    # Shared files (one write per shared agent, content built from all loaded skills)
    print(f"Shared files ({len(loaded_skills)} skills concatenated):")
    shared_content = build_shared_content(loaded_skills)
    for agent in AGENTS:
        if agent["kind"] != "shared":
            continue
        r = install_shared(shared_content, agent)
        results.append(r)
        tag = "OK  " if r.success else "FAIL"
        if r.success:
            print(f"  {tag} {agent['id']:8s} {r.target_path}")
        else:
            print(f"  {tag} {agent['id']:8s} {r.error}")

    print_summary(results)

    sys.exit(0 if all(r.success for r in results) else 1)


if __name__ == "__main__":
    main()
