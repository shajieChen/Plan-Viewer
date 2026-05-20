# Module-Quick-Analysis Git Submodule Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 `module-quick-analysis` skill 创建私有 Git 仓库并在 Plan_Viewer 中以 submodule 引用。

**Architecture:** 在本地 skill 目录初始化 git 仓库，推送到 GitHub 私有仓库，然后在 Plan_Viewer 中添加 submodule 引用。

**Tech Stack:** Git, GitHub CLI (`gh`)

---

### Task 1: 初始化本地 Git 仓库

**Files:**
- Existing: `C:\Users\chenshajie\.kiro\skills\module-quick-analysis\SKILL.md`

- [ ] **Step 1: 初始化 git 仓库**

```bash
cd C:\Users\chenshajie\.kiro\skills\module-quick-analysis
git init
```

Expected: `Initialized empty Git repository in C:/Users/chenshajie/.kiro/skills/module-quick-analysis/.git/`

- [ ] **Step 2: 添加并提交 SKILL.md**

```bash
git add SKILL.md
git commit -m "feat: initial module-quick-analysis skill"
```

Expected: `1 file changed, X insertions(+)`

- [ ] **Step 3: 确认分支名为 main**

```bash
git branch -M main
```

---

### Task 2: 创建 GitHub 私有仓库并推送

**Files:**
- No file changes, remote operations only

- [ ] **Step 1: 使用 gh CLI 创建私有仓库并推送**

```bash
cd C:\Users\chenshajie\.kiro\skills\module-quick-analysis
gh repo create shajieChen/kiro-skill-module-quick-analysis --private --source=. --remote=origin --push
```

Expected: `✓ Created repository shajieChen/kiro-skill-module-quick-analysis on GitHub`

- [ ] **Step 2: 验证远程仓库已配置**

```bash
git remote -v
```

Expected:
```
origin  https://github.com/shajieChen/kiro-skill-module-quick-analysis.git (fetch)
origin  https://github.com/shajieChen/kiro-skill-module-quick-analysis.git (push)
```

- [ ] **Step 3: 验证推送成功**

```bash
git log --oneline -1
```

Expected: 显示 `feat: initial module-quick-analysis skill` 的 commit

---

### Task 3: 在 Plan_Viewer 中添加 submodule

**Files:**
- Modify: `Q:\Plan_Viewer\.gitmodules`
- Create: `Q:\Plan_Viewer\Tools\Skills\module-quick-analysis\` (submodule checkout)

- [ ] **Step 1: 添加 submodule**

```bash
cd Q:\Plan_Viewer
git submodule add -b main https://github.com/shajieChen/kiro-skill-module-quick-analysis.git Tools/Skills/module-quick-analysis
```

Expected: `Cloning into 'Q:/Plan_Viewer/Tools/Skills/module-quick-analysis'...`

- [ ] **Step 2: 验证 .gitmodules 已更新**

```bash
git diff --cached .gitmodules
```

Expected: 新增条目：
```ini
[submodule "Tools/Skills/module-quick-analysis"]
    path = Tools/Skills/module-quick-analysis
    url = https://github.com/shajieChen/kiro-skill-module-quick-analysis.git
    branch = main
```

- [ ] **Step 3: 验证 SKILL.md 已 checkout**

```bash
dir Tools\Skills\module-quick-analysis\SKILL.md
```

Expected: 文件存在

- [ ] **Step 4: 提交**

```bash
git add .gitmodules Tools/Skills/module-quick-analysis
git commit -m "feat: add module-quick-analysis as git submodule"
```

Expected: `2 files changed`

---

### Task 4: 验证最终状态

- [ ] **Step 1: 验证所有 submodule 状态正常**

```bash
cd Q:\Plan_Viewer
git submodule status
```

Expected: 5 个 submodule 全部显示（Execute-LandingPrompt, OpenSpec, module-quick-analysis, project-state-spec, project-state-tracker），无 `-` 前缀（表示已初始化）

- [ ] **Step 2: 验证 Plan_Viewer 工作区干净**

```bash
git status
```

Expected: `nothing to commit, working tree clean`
