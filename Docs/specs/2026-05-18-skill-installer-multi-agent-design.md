# Skill Installer (Multi-Agent) Design

**Date:** 2026-05-18
**Status:** Approved (brainstorming complete; ready for plan)
**Owner:** chenshajie

## 1. Overview

Distribute Skills authored under `Q:\Plan_Viewer\Tools\Skills\` to five AI Agent platforms in their **native formats** by double-clicking a single batch file at the project root.

`Tools/Skills/` is the **source of truth**: the user edits Skills there. `install_skills.bat` reads every Skill subdirectory and installs each one into the correct global path for each Agent, performing format conversion where the target Agent expects a single file.

The workflow complements the existing `generate_skill.bat`: that tool generates a Skill's `SKILL.md` content via Kiro; this new installer takes the curated `Tools/Skills/` tree and pushes it out to all Agents. The two tools are independent.

### Goals

- Single-action install for all Skills × all supported Agents.
- Idempotent: running the installer twice with the same `Tools/Skills/` content produces identical files.
- No data backup or branching needed — `Tools/Skills/` is the canonical source.
- Reuse the existing `Docs/tools/distribute_skill.py` parsing/conversion functions.

### Non-Goals

- Generating new Skills (handled by `generate_skill.bat`).
- Selective install (always installs all Skills to all Agents).
- Backup of pre-existing Agent files.
- Uninstall / removal of Skills.

## 2. Architecture

### Layout

```
Q:\Plan_Viewer\
├── Tools/
│   ├── Skills/                              ← Source of truth
│   │   ├── Execute-LandingPrompt/
│   │   │   └── SKILL.md
│   │   └── project-state-tracker/
│   │       ├── SKILL.md
│   │       ├── templates/...
│   │       └── tools/...                    (excludes __pycache__)
│   └── install_skills.py                    ← Main install logic
├── install_skills.bat                       ← Entry point (double-click)
└── Docs/tools/distribute_skill.py           ← Reused (parse_front_matter, convert_to_cursor_mdc)
```

### Install Targets

| Agent | Kind | Target Path | Format |
|---|---|---|---|
| Kiro | folder | `%USERPROFILE%\.kiro\skills\<skill>\` | Folder copy (SKILL.md + subfolders) |
| Cursor | mdc | `%USERPROFILE%\.cursor\rules\<skill>.mdc` | YAML front-matter (`description`, `globs: ""`, `alwaysApply: true`) + body |
| Claude Code | folder | `%USERPROFILE%\.claude\skills\<skill>\` | Folder copy (SKILL.md + subfolders) |
| GitHub Copilot | shared | `%USERPROFILE%\.github\copilot-instructions.md` | All skills concatenated into one file with BEGIN/END marker blocks |
| Codex (OpenAI) | shared | `%USERPROFILE%\.codex\AGENTS.md` | All skills concatenated into one file with BEGIN/END marker blocks |

### Data Flow

```
install_skills.bat
  └─ python Tools/install_skills.py            (fallback: py)

install_skills.py:
  1. Discover Skills:   Tools/Skills/*/SKILL.md          → list[Skill]
  2. Load metadata:     parse YAML front-matter           → Skill(name, source_dir, metadata, body)
  3. Per-skill install:
       Kiro    → shutil.copytree(...)
       Claude  → shutil.copytree(...)
       Cursor  → convert_to_cursor_mdc(metadata, body) → write .mdc
  4. Shared file build (after loop):
       build_shared_content(skills) → write Copilot + Codex files
  5. Print summary, exit 0/1.
```

## 3. Components and Interfaces

### 3.1 `install_skills.bat` (entry point)

Thin shell that handles environment setup and Python invocation.

**Behavior:**
- `@echo off`, `cd /d %~dp0`, fail-fast on `cd` error.
- Print start banner.
- Run `python Tools\install_skills.py`. If exit code is `9009` (command not found), retry with `py Tools\install_skills.py`. If both fail with `9009`, print "No Python interpreter found" and exit 1.
- Forward Python exit code: 0 → "Installation completed", non-zero → "Installation failed (exit code: X)".
- `pause` before returning so output stays visible after double-click.

**No CLI arguments.**

### 3.2 `Tools/install_skills.py` (main logic)

**Module skeleton:**

```python
"""Install all Skills under Tools/Skills/ to all supported AI Agents."""

from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import shutil
import sys

# Reuse existing module by adding Docs/tools to sys.path
_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "Docs" / "tools"))
from distribute_skill import parse_front_matter, convert_to_cursor_mdc  # noqa: E402

SKILLS_SOURCE_DIR = _ROOT / "Tools" / "Skills"
HOME = Path.home()

AGENTS = [
    {"id": "kiro",    "kind": "folder", "target": HOME / ".kiro" / "skills"},
    {"id": "cursor",  "kind": "mdc",    "target": HOME / ".cursor" / "rules"},
    {"id": "claude",  "kind": "folder", "target": HOME / ".claude" / "skills"},
    {"id": "copilot", "kind": "shared", "target": HOME / ".github" / "copilot-instructions.md"},
    {"id": "codex",   "kind": "shared", "target": HOME / ".codex" / "AGENTS.md"},
]
```

**Function signatures:**

| Function | Signature | Responsibility |
|---|---|---|
| `discover_skills(source_dir)` | `Path → list[Path]` | Return sorted (lex by dir name) list of subdirs containing `SKILL.md`. Subdirs without `SKILL.md` print SKIP and are excluded. |
| `load_skill(skill_dir)` | `Path → Skill` | Read `SKILL.md`, call `parse_front_matter`, return `Skill` dataclass. Raises `ValueError` on parse failure. |
| `install_kiro(skill, agent)` | `(Skill, dict) → InstallResult` | `shutil.copytree(skill.source_dir, agent["target"]/skill.name, dirs_exist_ok=True, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))` |
| `install_claude(skill, agent)` | `(Skill, dict) → InstallResult` | Identical to `install_kiro`, different target. |
| `install_cursor(skill, agent)` | `(Skill, dict) → InstallResult` | `convert_to_cursor_mdc(skill.metadata, skill.body)`, write to `agent["target"]/<name>.mdc`. |
| `build_shared_content(skills)` | `list[Skill] → str` | Concatenate skills using BEGIN/END markers (see §4.5). Pure function. |
| `install_shared(content, agent)` | `(str, dict) → InstallResult` | Create parent dir if missing, write `content` to `agent["target"]` (overwrite). |
| `print_summary(results)` | `list[InstallResult] → None` | Render the summary block. |
| `main()` | `() → None` | Orchestrate steps, exit 0 on full success else 1. |

**Data classes:**

```python
@dataclass(frozen=True)
class Skill:
    name: str            # subdirectory name, e.g. "project-state-tracker"
    source_dir: Path     # Tools/Skills/<name>/
    metadata: dict       # parsed front-matter (must contain "name", "description")
    body: str            # SKILL.md content with front-matter stripped

@dataclass(frozen=True)
class InstallResult:
    skill_name: str | None  # None for shared-file results that aggregate skills
    agent_id: str
    target_path: Path
    success: bool
    error: str | None = None
```

### 3.3 Reuse of `Docs/tools/distribute_skill.py`

`install_skills.py` does not modify or relocate `distribute_skill.py`. It uses `sys.path.insert` at module load time to make the `Docs/tools/` directory importable, then imports `parse_front_matter` and `convert_to_cursor_mdc`. The existing CLI behavior of `distribute_skill.py` is unaffected.

## 4. Data Formats

### 4.1 Source `SKILL.md`

Standard YAML front-matter delimited by `---`:

```markdown
---
name: project-state-tracker
description: "Manage Research → Decision → Plan → LandingPrompt → TestPrompt artifacts"
---

# Project State Tracker

[body...]
```

Required front-matter fields: `name`, `description`.

### 4.2 Kiro / Claude (folder targets)

Entire source `Tools/Skills/<skill>/` tree copied verbatim, except `__pycache__/` and `*.pyc` are excluded. Existing target content with the same path is overwritten (`dirs_exist_ok=True`).

### 4.3 Cursor `.mdc` (single file)

```markdown
---
description: "<from front-matter>"
globs: ""
alwaysApply: true
---

[body byte-for-byte from SKILL.md]
```

Generated by the existing `convert_to_cursor_mdc` function.

### 4.4 Copilot / Codex (shared files)

Both targets receive an **identical** string produced by `build_shared_content(skills)`. Each Skill contributes one block, ordered by Skill name (lex). Blocks are separated by a single blank line.

```markdown
<!-- BEGIN: Execute-LandingPrompt -->

[Execute-LandingPrompt body byte-for-byte]

<!-- END: Execute-LandingPrompt -->

<!-- BEGIN: project-state-tracker -->

[project-state-tracker body byte-for-byte]

<!-- END: project-state-tracker -->
```

### 4.5 Build rules for shared content

1. Skills sorted by `name` ASCII lex order before concatenation.
2. Each block: opening marker line → blank line → skill body → blank line → closing marker line.
3. Blocks separated by a single blank line.
4. Output written with LF line endings (avoids cross-platform git noise).
5. No YAML front-matter at file level (Copilot and Codex do not parse one).

## 5. Discovery and Skill Identification

1. Enumerate **direct** subdirectories of `Tools/Skills/`.
2. For each subdirectory:
   - If `SKILL.md` exists → include as Skill.
   - Otherwise → print `SKIP: <dir> (no SKILL.md)` and exclude. Not an error.
3. Sort the included list by directory name (ASCII lex).
4. Subdirectory name is the canonical Skill name; used for:
   - Folder name under Kiro / Claude target.
   - Filename prefix for Cursor `.mdc`.
   - Marker block name in shared files.
5. The YAML `name` field inside `SKILL.md` is **not** required to match the directory name. The directory name is authoritative for filenames and markers; the YAML `name` is preserved as-is in folder targets (it lives inside `SKILL.md`) and ignored for filename / marker derivation. No warning is emitted on mismatch.

## 6. Encoding and Path Handling

| Concern | Rule |
|---|---|
| File read | UTF-8, `errors="strict"` |
| File write (single skill files) | UTF-8; preserve source line endings (LF or CRLF) for `.mdc` |
| File write (shared files) | UTF-8 with LF line endings |
| `%USERPROFILE%` | `Path.home()` |
| Missing parent directory | `path.parent.mkdir(parents=True, exist_ok=True)` |
| Folder copy | `shutil.copytree(..., dirs_exist_ok=True, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))` |

## 7. Error Handling

### 7.1 Fatal (early exit, code 1)

- `Tools/Skills/` directory does not exist.
- `Tools/Skills/` contains zero subdirectories with a `SKILL.md`.
- `distribute_skill.py` cannot be imported.

### 7.2 Per-skill (continue with rest)

- A `SKILL.md` is missing front-matter or required fields. Skip that Skill, log error, mark all its target results as failed.

### 7.3 Per-target (continue with rest)

- A target write fails (permission, disk, path). Wrap exception in `InstallResult(success=False, error=str(exc))`, continue with other targets.

### 7.4 Final exit code

- All `InstallResult`s have `success=True` → exit 0.
- Any failure → exit 1.

### 7.5 Output streams

- Progress and OK lines → stdout.
- Errors and FAIL lines → stderr (with full exception detail).
- Summary block → stdout.

## 8. Output Format

Successful run:

```
============================================================
  Skill Installer
============================================================

Discovered 2 skill(s) in Tools/Skills/:
  - Execute-LandingPrompt
  - project-state-tracker

[1/2] Execute-LandingPrompt
  OK   kiro     C:\Users\chenshajie\.kiro\skills\Execute-LandingPrompt\
  OK   cursor   C:\Users\chenshajie\.cursor\rules\Execute-LandingPrompt.mdc
  OK   claude   C:\Users\chenshajie\.claude\skills\Execute-LandingPrompt\

[2/2] project-state-tracker
  OK   kiro     C:\Users\chenshajie\.kiro\skills\project-state-tracker\
  OK   cursor   C:\Users\chenshajie\.cursor\rules\project-state-tracker.mdc
  OK   claude   C:\Users\chenshajie\.claude\skills\project-state-tracker\

Shared files (2 skills concatenated):
  OK   copilot  C:\Users\chenshajie\.github\copilot-instructions.md
  OK   codex    C:\Users\chenshajie\.codex\AGENTS.md

============================================================
  Summary: 8 target(s) updated, 0 failed
============================================================
```

Partial failure:

```
[1/2] Execute-LandingPrompt
  OK   kiro     ...
  FAIL cursor   PermissionError: [WinError 5] Access is denied
  OK   claude   ...
...
============================================================
  Summary: 7 target(s) updated, 1 failed
============================================================
```

## 9. Correctness Properties

| ID | Property | Validates |
|---|---|---|
| **P1** | For any valid SKILL.md, the body in the Cursor `.mdc` output is byte-for-byte identical to the source body. | §4.3 (already covered by `distribute_skill.py` tests; not re-tested) |
| **P2** | For any list of N≥1 Skills, `build_shared_content` output contains exactly N pairs of `BEGIN: <name>` / `END: <name>` markers, and the text between each pair is the corresponding Skill's body byte-for-byte. | §4.5 |
| **P3** | The order of marker blocks in `build_shared_content` output matches the input list sorted by Skill name (ASCII lex). | §5.3 |
| **P4** | After folder install, every file under the source Skill directory (excluding `__pycache__`, `*.pyc`) has a counterpart at the target with byte-for-byte identical content. | §4.2 |
| **P5** | Running `install_skills.py` twice in succession with unchanged `Tools/Skills/` produces target files whose contents are byte-for-byte identical between the two runs. | Idempotence |

## 10. Testing Strategy

### 10.1 Unit tests (pytest)

Test file: `tests/test_install_skills.py`.

- `discover_skills` returns subdirs with `SKILL.md` only, sorted lex.
- `discover_skills` skips subdirs lacking `SKILL.md` (logs but does not fail).
- `build_shared_content` with 0 skills returns empty string.
- `build_shared_content` with 1 skill produces 1 block with correct markers.
- `build_shared_content` with multiple skills sorts by name.
- `install_kiro` overwrites existing target folder content.
- `install_kiro` excludes `__pycache__/` and `*.pyc`.
- `install_cursor` writes valid MDC structure.
- `install_shared` creates missing parent directory.

### 10.2 Property-based tests (hypothesis)

Validate P2, P3, P4, P5. Generators:
- Skill names: lowercase + digits + hyphen (POSIX-safe), length 1–32.
- Bodies: arbitrary text including Unicode, emoji, CRLF/LF mix, lines starting with `---`.
- Skill counts: 1–8.

All tests use `tmp_path` fixtures; **no test ever writes to `%USERPROFILE%`**.

### 10.3 Manual integration

- Double-click `install_skills.bat` end-to-end on a clean machine.
- Verify all 5 target paths contain expected content.
- Verify second double-click is idempotent (no diff in target files).
- Manually delete `~/.cursor` and re-run; confirm parent directory auto-created.

### 10.4 Out of scope

- The batch entry script's correctness (kept thin enough for smoke testing only).
- The reused `distribute_skill.py` functions (covered by existing tests).
- Backup / rollback behavior (none implemented).

## 11. Initialization Step (one-time)

`Tools/Skills/` does not yet exist in the repository. As part of implementation:

1. Create `Q:\Plan_Viewer\Tools\Skills\`.
2. Copy `C:\Users\chenshajie\.kiro\skills\Execute-LandingPrompt\` → `Tools/Skills/Execute-LandingPrompt\`.
3. Copy `C:\Users\chenshajie\.kiro\skills\project-state-tracker\` → `Tools/Skills/project-state-tracker\`. Exclude `tools/__pycache__/`.

After this seed, the first run of `install_skills.bat` writes the same content back to `~/.kiro/skills/` (idempotent) plus the four other Agent paths.

## 12. Relationship to Existing Tools

| Tool | Role | Touched in this spec |
|---|---|---|
| `generate_skill.bat` | Generates SKILL.md content via Kiro | No |
| `Docs/tools/distribute_skill.py` | Reused for YAML parse + Cursor MDC conversion | No |
| `Tools/install_skills.py` | New: orchestrates multi-Agent install | Yes (new file) |
| `install_skills.bat` | New: entry point at project root | Yes (new file) |
| `Tools/Skills/` | New: source-of-truth Skill folder | Yes (new directory + initial seed) |

The two BAT files are independent: `generate_skill.bat` produces Skill content, `install_skills.bat` distributes whatever is in `Tools/Skills/`.
