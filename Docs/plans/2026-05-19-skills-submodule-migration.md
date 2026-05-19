# Skills Submodule Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convert `Tools/Skills/` from inline file copies to Git Submodules pointing to their respective GitHub repos, eliminating manual sync.

**Architecture:** Remove tracked files from git index, delete directories, re-add as submodules with `branch = main` tracking. Update `install_skills.bat` to auto-init submodules before running the installer.

**Tech Stack:** Git (submodules), Windows batch scripting

---

### Task 1: Remove tracked files from git index

**Files:**
- Modify: git index (no file edits)

- [ ] **Step 1: Remove Execute-LandingPrompt from index**

```cmd
git rm -r --cached Tools/Skills/Execute-LandingPrompt
```

Expected: `rm 'Tools/Skills/Execute-LandingPrompt/SKILL.md'`

- [ ] **Step 2: Remove project-state-tracker from index**

```cmd
git rm -r --cached Tools/Skills/project-state-tracker
```

Expected: multiple `rm 'Tools/Skills/project-state-tracker/...'` lines (SKILL.md + templates/ + tools/)

- [ ] **Step 3: Remove project-state-spec from index**

```cmd
git rm -r --cached Tools/Skills/project-state-spec
```

Expected: multiple `rm 'Tools/Skills/project-state-spec/...'` lines (SKILL.md + templates/ + tools/)

- [ ] **Step 4: Verify index state**

```cmd
git status -- Tools/Skills/
```

Expected: all three directories shown as "deleted" in staged changes, and their contents shown as untracked files.

---

### Task 2: Delete directories from disk

Submodule add requires the target path to not exist.

**Files:**
- Delete: `Tools/Skills/Execute-LandingPrompt/`
- Delete: `Tools/Skills/project-state-tracker/`
- Delete: `Tools/Skills/project-state-spec/`

- [ ] **Step 1: Delete the three directories**

```cmd
rmdir /s /q Tools\Skills\Execute-LandingPrompt
rmdir /s /q Tools\Skills\project-state-tracker
rmdir /s /q Tools\Skills\project-state-spec
```

- [ ] **Step 2: Verify Tools/Skills/ is empty**

```cmd
dir Tools\Skills\
```

Expected: directory is empty (or does not exist — both are fine).

---

### Task 3: Add submodules

**Files:**
- Create: `.gitmodules`
- Create: `Tools/Skills/Execute-LandingPrompt` (submodule checkout)
- Create: `Tools/Skills/project-state-tracker` (submodule checkout)
- Create: `Tools/Skills/project-state-spec` (submodule checkout)

- [ ] **Step 1: Add Execute-LandingPrompt submodule**

```cmd
git submodule add -b main https://github.com/shajieChen/kiro-skill-execute-landingprompt.git Tools/Skills/Execute-LandingPrompt
```

Expected: Cloning into 'Tools/Skills/Execute-LandingPrompt'...

- [ ] **Step 2: Add project-state-tracker submodule**

```cmd
git submodule add -b main https://github.com/shajieChen/kiro-skill-project-state-tracker.git Tools/Skills/project-state-tracker
```

Expected: Cloning into 'Tools/Skills/project-state-tracker'...

- [ ] **Step 3: Add project-state-spec submodule**

```cmd
git submodule add -b main https://github.com/shajieChen/kiro-skill-project-state-spec.git Tools/Skills/project-state-spec
```

Expected: Cloning into 'Tools/Skills/project-state-spec'...

- [ ] **Step 4: Verify .gitmodules content**

```cmd
type .gitmodules
```

Expected output (order may vary):
```ini
[submodule "Tools/Skills/Execute-LandingPrompt"]
	path = Tools/Skills/Execute-LandingPrompt
	url = https://github.com/shajieChen/kiro-skill-execute-landingprompt.git
	branch = main
[submodule "Tools/Skills/project-state-tracker"]
	path = Tools/Skills/project-state-tracker
	url = https://github.com/shajieChen/kiro-skill-project-state-tracker.git
	branch = main
[submodule "Tools/Skills/project-state-spec"]
	path = Tools/Skills/project-state-spec
	url = https://github.com/shajieChen/kiro-skill-project-state-spec.git
	branch = main
```

- [ ] **Step 5: Verify submodule directories have content**

```cmd
dir Tools\Skills\Execute-LandingPrompt\SKILL.md
dir Tools\Skills\project-state-tracker\SKILL.md
dir Tools\Skills\project-state-spec\SKILL.md
```

Expected: all three files exist.

---

### Task 4: Update install_skills.bat

**Files:**
- Modify: `install_skills.bat`

- [ ] **Step 1: Add submodule init before Python call**

Insert after the `echo` banner and before the Python invocation:

```bat
@echo off
cd /d %~dp0
if %errorlevel% neq 0 (
    echo ERROR: Cannot set working directory
    exit /b 1
)

echo ============================================================
echo   Skill Installer
echo ============================================================

REM -- Ensure submodules are initialized and up-to-date --
git submodule update --init --remote
if %errorlevel% neq 0 (
    echo WARNING: git submodule update failed, continuing with existing state...
)

REM -- Try python first; on 9009 (command not found) fall back to py --
python Tools\install_skills.py
if %errorlevel% equ 9009 goto :try_py
set "INST_EXIT=%errorlevel%"
if %INST_EXIT% neq 0 goto :inst_failed
goto :inst_success

:try_py
py Tools\install_skills.py
if %errorlevel% equ 9009 goto :no_python
set "INST_EXIT=%errorlevel%"
if %INST_EXIT% neq 0 goto :inst_failed
goto :inst_success

:no_python
echo ERROR: No Python interpreter found
pause
exit /b 1

:inst_failed
echo ERROR: Installation failed (exit code: %INST_EXIT%)
pause
exit /b 1

:inst_success
echo Installation completed successfully.
pause
exit /b 0
```

Note: submodule failure is a WARNING not a hard error — allows the installer to still work with whatever version is currently checked out.

---

### Task 5: Commit and verify

**Files:**
- Commit: `.gitmodules`, `Tools/Skills/Execute-LandingPrompt`, `Tools/Skills/project-state-tracker`, `Tools/Skills/project-state-spec`, `install_skills.bat`

- [ ] **Step 1: Stage all changes**

```cmd
git add .gitmodules Tools/Skills/Execute-LandingPrompt Tools/Skills/project-state-tracker Tools/Skills/project-state-spec install_skills.bat
```

- [ ] **Step 2: Review staged changes**

```cmd
git status
```

Expected:
- `.gitmodules` — new file
- `Tools/Skills/Execute-LandingPrompt` — new file (submodule reference)
- `Tools/Skills/project-state-tracker` — new file (submodule reference)
- `Tools/Skills/project-state-spec` — new file (submodule reference)
- `install_skills.bat` — modified
- Many "deleted" entries for the old inline files

- [ ] **Step 3: Commit**

```cmd
git commit -m "refactor: convert Tools/Skills to git submodules

Replaces inline file copies of Execute-LandingPrompt, project-state-tracker,
and project-state-spec with git submodules tracking their respective GitHub
repos on the main branch. install_skills.bat now auto-inits submodules."
```

- [ ] **Step 4: Verify install_skills.py still discovers all skills**

```cmd
python Tools\install_skills.py --dry-run
```

If `--dry-run` is not supported, just run:
```cmd
python -c "import sys; sys.path.insert(0,'Tools'); from pathlib import Path; skills = [d.name for d in (Path('Tools/Skills')).iterdir() if d.is_dir() and (d/'SKILL.md').exists()]; print(f'Found {len(skills)} skills:', skills)"
```

Expected: `Found 3 skills: ['Execute-LandingPrompt', 'project-state-spec', 'project-state-tracker']`

- [ ] **Step 5: Verify submodule update works**

```cmd
git submodule update --remote
git submodule status
```

Expected: three submodules listed with their current SHA, no `+` prefix (meaning they're at the expected commit).
