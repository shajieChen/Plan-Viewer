# Skill Installer (Multi-Agent) Implementation Plan

> **For agentic workers:** Use checkbox (`- [ ]`) syntax to track progress task-by-task. Each task lists the files it touches plus its acceptance criteria.

**Goal:** Make `Q:\Plan_Viewer\Tools\Skills\` the source of truth for AI Agent Skills, and provide `install_skills.bat` (double-click) to install every Skill into Kiro / Cursor / Claude Code (folder targets) and Copilot / Codex (shared concatenated files).

**Architecture (one-paragraph):** A thin batch entry script (`install_skills.bat`) shells into a Python orchestrator (`Tools/install_skills.py`) that discovers every subdirectory of `Tools/Skills/` containing a `SKILL.md`, parses its YAML front-matter via the existing `Docs/tools/distribute_skill.py`, performs format-specific install per Agent (folder copy via `shutil.copytree` for Kiro/Claude, MDC conversion for Cursor, BEGIN/END marker concatenation for Copilot/Codex), reports per-target status to stdout, and exits 0 on full success or 1 on any failure.

**Tech Stack:** Windows batch (`install_skills.bat`), Python 3.8+ stdlib only (`pathlib`, `shutil`, `dataclasses`, `sys`), pytest + hypothesis (existing test stack).

**Design Doc:** `Docs/specs/2026-05-18-skill-installer-multi-agent-design.md`

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `Q:\Plan_Viewer\Tools\Skills\Execute-LandingPrompt\` | Create (seed copy) | Source-of-truth copy of `~/.kiro/skills/Execute-LandingPrompt/` |
| `Q:\Plan_Viewer\Tools\Skills\project-state-tracker\` | Create (seed copy) | Source-of-truth copy of `~/.kiro/skills/project-state-tracker/`, excluding `tools/__pycache__/` |
| `Q:\Plan_Viewer\Tools\install_skills.py` | Create | Multi-Skill × multi-Agent orchestrator (discovery, conversion, install, reporting) |
| `Q:\Plan_Viewer\install_skills.bat` | Create | Project-root double-click entry point; `python` → `py` fallback |
| `Q:\Plan_Viewer\tests\test_install_skills.py` | Create | Unit + property-based tests for the orchestrator |

`Docs/tools/distribute_skill.py` is **read-only** — used via `sys.path.insert` import to reuse `parse_front_matter` and `convert_to_cursor_mdc`.

---

## Phase 1 — Seed `Tools/Skills/` source-of-truth folder

Goal: create `Q:\Plan_Viewer\Tools\Skills\` and populate it with the two existing Skills so the installer has something to install.

### Task 1.1: Create `Tools/Skills/Execute-LandingPrompt/`

**Files:**
- Create: `Q:\Plan_Viewer\Tools\Skills\Execute-LandingPrompt\SKILL.md`

**Steps:**
- [ ] Copy `C:\Users\chenshajie\.kiro\skills\Execute-LandingPrompt\SKILL.md` to `Q:\Plan_Viewer\Tools\Skills\Execute-LandingPrompt\SKILL.md` byte-for-byte.

**Acceptance:** `Tools/Skills/Execute-LandingPrompt/SKILL.md` exists; first line is `---`; file size matches the source.

### Task 1.2: Create `Tools/Skills/project-state-tracker/`

**Files:**
- Create: `Q:\Plan_Viewer\Tools\Skills\project-state-tracker\` (recursive)

**Steps:**
- [ ] Recursively copy the entire `C:\Users\chenshajie\.kiro\skills\project-state-tracker\` tree (`SKILL.md` + `templates/` + `tools/`) to `Q:\Plan_Viewer\Tools\Skills\project-state-tracker\`.
- [ ] Exclude `tools/__pycache__/` and any `*.pyc` files from the copy.

**Acceptance:** Target tree contains `SKILL.md`, `templates/` (with all subfolders), and `tools/` (without `__pycache__/` or `.pyc`); the `SKILL.md` first line is `---`.

### Task 1.3: Verify seed integrity

**Steps:**
- [ ] Run a recursive byte-comparison between `Tools/Skills/<skill>/` and the corresponding source `~/.kiro/skills/<skill>/`, ignoring `__pycache__/` and `*.pyc`. All other files must match byte-for-byte.

**Acceptance:** Zero diff (apart from excluded patterns).

---

## Phase 2 — Implement `Tools/install_skills.py`

Goal: complete, tested Python orchestrator. Build it bottom-up: pure functions first, then I/O, then orchestration.

### Task 2.1: Module skeleton, constants, data classes

**Files:**
- Create: `Q:\Plan_Viewer\Tools\install_skills.py`

**Steps:**
- [ ] Add module docstring explaining purpose.
- [ ] Standard imports: `from __future__ import annotations`, `from dataclasses import dataclass`, `from pathlib import Path`, `import shutil`, `import sys`.
- [ ] Compute `_ROOT = Path(__file__).resolve().parent.parent`.
- [ ] Define `SKILLS_SOURCE_DIR = _ROOT / "Tools" / "Skills"`.
- [ ] Define `HOME = Path.home()`.
- [ ] Define `AGENTS` list (5 dicts; `id`, `kind`, `target` as per design §2 Install Targets).
- [ ] Define `BEGIN_MARK = "<!-- BEGIN: {skill} -->"` and `END_MARK = "<!-- END: {skill} -->"`.
- [ ] Define frozen dataclasses `Skill(name, source_dir, metadata, body)` and `InstallResult(skill_name, agent_id, target_path, success, error=None)`.
- [ ] Insert `Docs/tools` into `sys.path` and `from distribute_skill import parse_front_matter, convert_to_cursor_mdc`. Wrap import in try/except — on `ImportError`, print error to stderr and `sys.exit(1)`.
- [ ] Stub `def main(): ...` and `if __name__ == "__main__": main()`.

**Acceptance:** Module imports cleanly when run as `python Tools/install_skills.py` (will exit since `main` is empty). No syntax errors. `parse_front_matter` and `convert_to_cursor_mdc` are accessible.

### Task 2.2: Implement `discover_skills(source_dir) -> list[Path]`

**Files:**
- Modify: `Q:\Plan_Viewer\Tools\install_skills.py`

**Steps:**
- [ ] Iterate `source_dir.iterdir()`; keep only directories.
- [ ] For each directory, check if `SKILL.md` exists. If yes, append. If no, print `SKIP: <name> (no SKILL.md)` to stdout.
- [ ] Sort the resulting list by `path.name` (ASCII lex).
- [ ] If `source_dir` does not exist, raise `FileNotFoundError` (caller handles fatal exit).

**Acceptance:** Returns `list[Path]`, sorted lex, only includes dirs with `SKILL.md`. Skipped dirs produce a SKIP line on stdout.

### Task 2.3: Implement `load_skill(skill_dir) -> Skill`

**Files:**
- Modify: `Q:\Plan_Viewer\Tools\install_skills.py`

**Steps:**
- [ ] Read `skill_dir / "SKILL.md"` as UTF-8 text.
- [ ] Call `parse_front_matter(content)` to get `(metadata, body)`.
- [ ] Validate `metadata` contains `name` and `description` (re-check, even though `parse_front_matter` checks too).
- [ ] Return `Skill(name=skill_dir.name, source_dir=skill_dir, metadata=metadata, body=body)`.

**Acceptance:** For `Tools/Skills/Execute-LandingPrompt/`, returns a Skill whose `name == "Execute-LandingPrompt"` and `body` starts with the markdown body content (no front-matter).

### Task 2.4: Implement folder installers (`install_kiro`, `install_claude`)

**Files:**
- Modify: `Q:\Plan_Viewer\Tools\install_skills.py`

**Steps:**
- [ ] Define `_install_folder(skill, agent) -> InstallResult` helper.
- [ ] Compute `target = agent["target"] / skill.name`.
- [ ] Try `shutil.copytree(skill.source_dir, target, dirs_exist_ok=True, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))`.
- [ ] On success, return `InstallResult(skill_name=skill.name, agent_id=agent["id"], target_path=target, success=True)`.
- [ ] On any `OSError`, return `InstallResult(..., success=False, error=str(exc))`.
- [ ] Define `install_kiro = _install_folder` and `install_claude = _install_folder` (or thin wrappers).

**Acceptance:** Calling `install_kiro(skill, agent)` on a Skill folder copies its content (excluding `__pycache__` / `*.pyc`) to the agent's target subdirectory. Re-running overwrites cleanly.

### Task 2.5: Implement `install_cursor(skill, agent) -> InstallResult`

**Files:**
- Modify: `Q:\Plan_Viewer\Tools\install_skills.py`

**Steps:**
- [ ] Compute `mdc_content = convert_to_cursor_mdc(skill.metadata, skill.body)`.
- [ ] Compute `target = agent["target"] / f"{skill.name}.mdc"`.
- [ ] Ensure parent dir: `target.parent.mkdir(parents=True, exist_ok=True)`.
- [ ] Write `mdc_content` to `target` with UTF-8 encoding.
- [ ] Return `InstallResult(success=True, ...)` on success, or `InstallResult(success=False, error=...)` on `OSError`.

**Acceptance:** A `.mdc` file appears at `<target>/<skill_name>.mdc` containing valid Cursor MDC front-matter (`description`, `globs: ""`, `alwaysApply: true`) followed by the original body.

### Task 2.6: Implement `build_shared_content(skills) -> str`

**Files:**
- Modify: `Q:\Plan_Viewer\Tools\install_skills.py`

**Steps:**
- [ ] If `skills` is empty, return empty string.
- [ ] Skills are assumed already sorted by name (caller invariant); do not re-sort here.
- [ ] For each skill, build a block of the form:
  ```
  <!-- BEGIN: <name> -->

  <body>

  <!-- END: <name> -->
  ```
  Strip trailing whitespace from `body` before insertion to avoid double blank lines, but preserve the body's internal whitespace and Unicode characters byte-for-byte.
- [ ] Join blocks with one blank line between them (`"\n\n"`).
- [ ] Normalize all line endings to LF (`"\n"`) in the final output.
- [ ] Return the resulting string.

**Acceptance:** For 2 sorted skills, output contains exactly 2 BEGIN markers and 2 END markers; their pair-name-substitution matches each skill's name; the text between matched markers reproduces the skill's body byte-for-byte.

### Task 2.7: Implement `install_shared(content, agent) -> InstallResult`

**Files:**
- Modify: `Q:\Plan_Viewer\Tools\install_skills.py`

**Steps:**
- [ ] Compute `target = agent["target"]` (this is the **file path**, not a directory).
- [ ] `target.parent.mkdir(parents=True, exist_ok=True)`.
- [ ] Open `target` in write mode with `encoding="utf-8"`, `newline=""` (to keep our LF endings literal), and write `content`.
- [ ] Return `InstallResult(skill_name=None, agent_id=agent["id"], target_path=target, success=True)`. On `OSError` return failure.

**Acceptance:** File is created at the exact target path with UTF-8 bytes, LF line endings, no BOM, no extra trailing newline beyond what `content` contains.

### Task 2.8: Implement `print_summary(results) -> None`

**Files:**
- Modify: `Q:\Plan_Viewer\Tools\install_skills.py`

**Steps:**
- [ ] Count successes and failures.
- [ ] Print the closing summary banner:
  ```
  ============================================================
    Summary: <N> target(s) updated, <M> failed
  ============================================================
  ```
- [ ] If any failures, print each failure's `agent_id`, `skill_name` (if set), and `error` to stderr.

**Acceptance:** Output matches design §8 examples (success + partial-failure variants).

### Task 2.9: Implement `main()` orchestration

**Files:**
- Modify: `Q:\Plan_Viewer\Tools\install_skills.py`

**Steps:**
- [ ] Print start banner (separator + "Skill Installer" + separator).
- [ ] Call `discover_skills(SKILLS_SOURCE_DIR)`. On `FileNotFoundError`, print fatal message to stderr and `sys.exit(1)`.
- [ ] If empty list, print `No SKILL.md found in Tools/Skills/` to stderr and `sys.exit(1)`.
- [ ] Print `Discovered N skill(s) in Tools/Skills/:` and the list.
- [ ] Initialize `results: list[InstallResult] = []`.
- [ ] Build `loaded_skills: list[Skill] = []`. For each discovered path: try `load_skill`; on `ValueError`, print FAIL line to stdout + detail to stderr, append a synthetic `InstallResult(success=False, ...)` for each non-shared agent so the failure shows in the summary, and skip this skill from `loaded_skills`.
- [ ] For each `(idx, skill)` in `loaded_skills` (1-indexed):
  - Print `[idx/total] <skill.name>`.
  - Run `install_kiro`, `install_cursor`, `install_claude`, append each result, print `OK <agent_id> <target>` or `FAIL <agent_id> <error>`.
- [ ] After the per-skill loop, build shared content via `build_shared_content(loaded_skills)`.
- [ ] Print `Shared files (<N> skills concatenated):`.
- [ ] For each shared agent (copilot, codex), call `install_shared`, append result, print OK / FAIL.
- [ ] Call `print_summary(results)`.
- [ ] `sys.exit(0 if all(r.success for r in results) else 1)`.

**Acceptance:** Running `python Tools/install_skills.py` with the seeded `Tools/Skills/` produces stdout matching design §8 (success path) and writes the 5 target paths.

---

## Phase 3 — Implement `install_skills.bat`

Goal: thin entry point matching `generate_skill.bat` style.

### Task 3.1: Create `install_skills.bat`

**Files:**
- Create: `Q:\Plan_Viewer\install_skills.bat`

**Steps:**
- [ ] First line: `@echo off`.
- [ ] `cd /d %~dp0` with `if %errorlevel% neq 0` guard that prints error and `exit /b 1`.
- [ ] Print start banner (3 separator lines + "Skill Installer").
- [ ] Try `python Tools\install_skills.py`. Capture exit code.
- [ ] If exit code is `9009`, retry with `py Tools\install_skills.py`.
- [ ] If second attempt is also `9009`, print `ERROR: No Python interpreter found`, `pause`, `exit /b 1`.
- [ ] If Python exit code is non-zero (other than 9009), print `ERROR: Installation failed (exit code: %DIST_EXIT%)`, `pause`, `exit /b 1`.
- [ ] On success, print `Installation completed successfully.`, `pause`, `exit /b 0`.

**Acceptance:** Double-clicking `install_skills.bat` runs end-to-end and produces the expected stdout from `install_skills.py`. Renaming `python.exe` (or testing in a shell without Python) triggers the `py` fallback. With neither available, the "No Python interpreter found" error appears.

---

## Phase 4 — Tests

Goal: validate correctness properties from design §9 plus key edge cases. **No test writes to `%USERPROFILE%`**; all use `tmp_path`.

### Task 4.1: Create test scaffolding

**Files:**
- Create: `Q:\Plan_Viewer\tests\test_install_skills.py`

**Steps:**
- [ ] Add module docstring referencing the design doc.
- [ ] Imports: `pytest`, `hypothesis` (`given`, `strategies as st`, `settings`), `pathlib.Path`, the functions under test from `Tools.install_skills` (adjust `sys.path` if needed in a `conftest.py` or directly in the test file).
- [ ] Define a helper `make_skill_dir(tmp_path, name, body, *, description="A test skill")` that writes a valid `SKILL.md` and returns the path.

**Acceptance:** `pytest tests/test_install_skills.py --collect-only` lists tests with no import errors.

### Task 4.2: Unit tests for `discover_skills`

**Steps:**
- [ ] Test: returns sorted list of subdirs containing `SKILL.md`.
- [ ] Test: skips subdirs without `SKILL.md` and prints SKIP line (capture stdout via `capsys`).
- [ ] Test: raises `FileNotFoundError` when `source_dir` doesn't exist.
- [ ] Test: returns empty list when `source_dir` exists but has no qualifying subdirs.

**Acceptance:** All four cases pass.

### Task 4.3: Unit tests for `build_shared_content`

**Steps:**
- [ ] Test: empty list → empty string.
- [ ] Test: single skill → exactly one BEGIN/END pair surrounding body.
- [ ] Test: multiple skills → blocks appear in input order; blank line between blocks.
- [ ] Test: body with internal `---` lines is preserved (not treated as a delimiter).
- [ ] Test: output uses LF line endings only (no `\r\n`).

**Acceptance:** All five cases pass.

### Task 4.4: Property test P2 (concatenation round-trip)

**Steps:**
- [ ] Use `hypothesis` with `@settings(max_examples=100)`.
- [ ] Strategy: list of 1–8 unique skill names (lowercase + digits + hyphen, length 1–32) paired with arbitrary text bodies (Unicode + emoji + mixed line endings + lines starting with `---`).
- [ ] Build `Skill` objects, sort by name, call `build_shared_content`.
- [ ] For each skill, locate its `BEGIN: <name>` / `END: <name>` marker pair via string search; assert the slice between them (after trimming the leading/trailing blank lines added by the marker formatting) equals the input body byte-for-byte.

**Acceptance:** Property passes 100 examples.

### Task 4.5: Property test P3 (sort order)

**Steps:**
- [ ] Generator: same skill list as P2, intentionally unsorted.
- [ ] After sorting and calling `build_shared_content`, assert that the order in which `BEGIN:` markers appear in the output matches `sorted(names)`.

**Acceptance:** Property passes 100 examples.

### Task 4.6: Property test P4 (folder copy fidelity)

**Steps:**
- [ ] Generate a synthetic Skill folder at `tmp_path/source/<name>/` containing arbitrary nested files (and a `__pycache__/` directory with junk content + a `.pyc` file).
- [ ] Call `install_kiro(skill, agent_with_target=tmp_path/"target")` (or the underlying `_install_folder`).
- [ ] Assert that for every file in the source tree (excluding `__pycache__/` and `*.pyc`), a corresponding file exists in the target with byte-identical content.
- [ ] Assert that no `__pycache__/` directory or `.pyc` file exists in the target.

**Acceptance:** Property passes 50 examples (kept lower because each example builds a folder tree).

### Task 4.7: Property test P5 (idempotence)

**Steps:**
- [ ] Generate one or more synthetic Skills in `tmp_path/source/`.
- [ ] Run the full install pipeline twice in a row (call the same per-Agent install functions, plus `install_shared` for the shared targets) into `tmp_path/target_*` paths.
- [ ] Hash all output files after run 1 and after run 2 with `hashlib.sha256`; assert hash sets are equal.

**Acceptance:** Property passes 50 examples.

### Task 4.8: Unit tests for I/O helpers

**Steps:**
- [ ] `install_cursor` writes a file containing `description:`, `globs: ""`, `alwaysApply: true` and the body, and creates the parent dir if missing.
- [ ] `install_shared` creates the parent dir if missing, then writes the exact content with LF endings.
- [ ] `install_kiro` overwrites pre-existing target content (write a stale file at the target before the call; assert it is replaced).

**Acceptance:** All three cases pass.

---

## Phase 5 — Manual integration & checkpoint

Goal: end-to-end smoke test on the actual machine.

### Task 5.1: Run the bat once

**Steps:**
- [ ] Double-click `install_skills.bat` at `Q:\Plan_Viewer\`.
- [ ] Confirm stdout shows: discovery (2 skills), 3 `OK` lines per skill, 2 `OK` lines for shared files, summary `Summary: 8 target(s) updated, 0 failed`.

**Acceptance:** Exit code 0; the output matches the design §8 success example (with the actual paths).

### Task 5.2: Verify all 5 target paths

**Steps:**
- [ ] `~/.kiro/skills/Execute-LandingPrompt/SKILL.md` exists and matches source.
- [ ] `~/.kiro/skills/project-state-tracker/SKILL.md` and subfolders exist and match source (excluding `__pycache__`).
- [ ] `~/.cursor/rules/Execute-LandingPrompt.mdc` and `~/.cursor/rules/project-state-tracker.mdc` exist and contain valid MDC front-matter (`description`, `globs: ""`, `alwaysApply: true`).
- [ ] `~/.claude/skills/Execute-LandingPrompt/` and `~/.claude/skills/project-state-tracker/` exist with the same content as Kiro counterparts.
- [ ] `~/.github/copilot-instructions.md` exists with two BEGIN/END marker blocks in alphabetical order (Execute-LandingPrompt first).
- [ ] `~/.codex/AGENTS.md` exists and is byte-identical to `copilot-instructions.md`.

**Acceptance:** All six checks pass.

### Task 5.3: Run the bat a second time (idempotence)

**Steps:**
- [ ] Take SHA-256 hashes of every file at the 5 target paths.
- [ ] Re-run `install_skills.bat`.
- [ ] Re-take hashes; compare.

**Acceptance:** All hashes match before/after.

### Task 5.4: Failure mode — missing source

**Steps:**
- [ ] Temporarily rename `Q:\Plan_Viewer\Tools\Skills\` → `Tools\Skills_bak\`.
- [ ] Run the bat.
- [ ] Confirm stderr message matches design §7.1 fatal pattern; exit code 1.
- [ ] Restore the folder name.

**Acceptance:** Fatal exit observed; restoration leaves project in original state.

---

## Dependencies

- Python 3.8+ (already a project dependency).
- pytest + hypothesis (already in `requirements.txt` based on `tests/` and `.hypothesis/` presence).
- No new third-party packages.

## Success Criteria

1. `Tools/Skills/` exists at `Q:\Plan_Viewer\` and contains both Skill folders.
2. Double-clicking `install_skills.bat` writes content to all 5 Agent paths and prints the summary banner.
3. Re-running the bat is idempotent (zero diff in target files).
4. `pytest tests/test_install_skills.py` passes (unit + property tests).
5. `Docs/tools/distribute_skill.py` is unchanged.
6. `generate_skill.bat` is unchanged.

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "1.2"] },
    { "id": 1, "tasks": ["1.3"] },
    { "id": 2, "tasks": ["2.1"] },
    { "id": 3, "tasks": ["2.2", "2.3", "2.6"] },
    { "id": 4, "tasks": ["2.4", "2.5", "2.7", "2.8"] },
    { "id": 5, "tasks": ["2.9"] },
    { "id": 6, "tasks": ["3.1"] },
    { "id": 7, "tasks": ["4.1"] },
    { "id": 8, "tasks": ["4.2", "4.3", "4.4", "4.5", "4.6", "4.7", "4.8"] },
    { "id": 9, "tasks": ["5.1", "5.2", "5.3", "5.4"] }
  ]
}
```

## Notes

- The plan installs **content from `Tools/Skills/`** to the user's global Agent paths. The first run will overwrite the existing `~/.kiro/skills/<skill>/` folders with byte-identical content (since they were just seeded from there) — no risk.
- After implementation, future Skill edits should be made in `Tools/Skills/` and re-run the bat to propagate.
- Tests must never touch `%USERPROFILE%`. Use `tmp_path` exclusively.
- All file I/O is UTF-8. Source `SKILL.md` files contain Chinese characters; bytes must round-trip cleanly.
