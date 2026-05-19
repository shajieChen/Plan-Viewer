# Skills Submodule Migration Design

**Date:** 2026-05-19  
**Status:** Approved  
**Scope:** Convert `Tools/Skills/` from inline file copies to Git Submodules

---

## Problem

`Tools/Skills/` 下的三个 skill 目录（Execute-LandingPrompt、project-state-tracker、project-state-spec）以普通文件形式提交在 Plan_Viewer 仓库中。每次在 `~/.kiro/skills/` 的独立仓库里更新 skill 后，还需要手动把最新内容同步回 `Tools/Skills/` 并再次提交，产生重复劳动和版本漂移风险。

## Solution

将这三个目录转为 Git Submodule，指向各自的 GitHub 仓库并跟踪 `main` 分支。`install_skills.py` 的路径逻辑不变，submodule checkout 后目录结构与之前一致。

## Submodule Mapping

| Local Path | Remote URL | Branch |
|---|---|---|
| `Tools/Skills/Execute-LandingPrompt` | `https://github.com/shajieChen/kiro-skill-execute-landingprompt.git` | main |
| `Tools/Skills/project-state-tracker` | `https://github.com/shajieChen/kiro-skill-project-state-tracker.git` | main |
| `Tools/Skills/project-state-spec` | `https://github.com/shajieChen/kiro-skill-project-state-spec.git` | main |

## Execution Steps

1. **Remove tracked files from index** (keep on disk temporarily):
   ```
   git rm -r --cached Tools/Skills/Execute-LandingPrompt
   git rm -r --cached Tools/Skills/project-state-tracker
   git rm -r --cached Tools/Skills/project-state-spec
   ```

2. **Delete the directories from disk** (submodule add requires empty target):
   ```
   rmdir /s /q Tools\Skills\Execute-LandingPrompt
   rmdir /s /q Tools\Skills\project-state-tracker
   rmdir /s /q Tools\Skills\project-state-spec
   ```

3. **Add submodules** with branch tracking:
   ```
   git submodule add -b main https://github.com/shajieChen/kiro-skill-execute-landingprompt.git Tools/Skills/Execute-LandingPrompt
   git submodule add -b main https://github.com/shajieChen/kiro-skill-project-state-tracker.git Tools/Skills/project-state-tracker
   git submodule add -b main https://github.com/shajieChen/kiro-skill-project-state-spec.git Tools/Skills/project-state-spec
   ```

4. **Update `install_skills.bat`** — prepend submodule init:
   ```bat
   git submodule update --init --remote
   ```

5. **Commit**:
   ```
   git add .gitmodules Tools/Skills/Execute-LandingPrompt Tools/Skills/project-state-tracker Tools/Skills/project-state-spec install_skills.bat
   git commit -m "refactor: convert Tools/Skills to git submodules"
   ```

## What Does NOT Change

- `install_skills.py` — path logic unchanged; it reads `Tools/Skills/<name>/SKILL.md` as before
- `~/.kiro/skills/` — independent repos continue to work normally for Kiro
- Distribution targets (Cursor MDC, Copilot, Codex) — still populated by `install_skills.py`

## Update Workflow (Post-Migration)

When a skill is updated in its own repo:

```bash
# In Plan_Viewer repo
git submodule update --remote
git add Tools/Skills/<name>
git commit -m "chore: bump <name> submodule"
```

Or update all at once:

```bash
git submodule update --remote
git add Tools/Skills/
git commit -m "chore: bump all skill submodules"
```

## Risks & Mitigations

| Risk | Mitigation |
|---|---|
| Fresh clone has empty skill dirs if `--recurse-submodules` forgotten | `install_skills.bat` runs `git submodule update --init --remote` first |
| Submodule SHA drift (forgot to commit after update) | Low impact — only affects Cursor/Copilot/Codex distribution, Kiro uses its own copy |
| GitHub repo unavailable | Submodule stays at last fetched commit; local work unaffected |

## Out of Scope

- Changing `install_skills.py` source directory logic
- Moving skills to a different path
- Modifying the skill content itself
