# Module-Quick-Analysis Git Submodule Design

**Date:** 2026-05-20  
**Status:** Approved  
**Scope:** 为 `module-quick-analysis` skill 创建私有 Git 仓库并在 Plan_Viewer 中以 submodule 引用

---

## Problem

`C:\Users\chenshajie\.kiro\skills\module-quick-analysis` 目前只是一个本地目录，没有版本控制。需要：
1. 为其建立独立 Git 仓库并推送到 GitHub（私有）
2. 在 `Q:\Plan_Viewer\Tools\Skills` 中以 submodule 方式引用，与其他 skill 保持一致的管理模式

## Solution

### Step 1: 初始化本地 Git 仓库

在 `C:\Users\chenshajie\.kiro\skills\module-quick-analysis` 中：
```bash
git init
git add SKILL.md
git commit -m "feat: initial module-quick-analysis skill"
```

### Step 2: 创建 GitHub 私有仓库

使用 GitHub CLI：
```bash
gh repo create shajieChen/kiro-skill-module-quick-analysis --private --source=. --remote=origin --push
```

或手动创建后添加 remote：
```bash
git remote add origin https://github.com/shajieChen/kiro-skill-module-quick-analysis.git
git branch -M main
git push -u origin main
```

### Step 3: 在 Plan_Viewer 中添加 submodule

在 `Q:\Plan_Viewer` 中：
```bash
git submodule add -b main https://github.com/shajieChen/kiro-skill-module-quick-analysis.git Tools/Skills/module-quick-analysis
```

### Step 4: 提交

```bash
git add .gitmodules Tools/Skills/module-quick-analysis
git commit -m "feat: add module-quick-analysis as git submodule"
```

## Final State

`.gitmodules` 新增条目：
```ini
[submodule "Tools/Skills/module-quick-analysis"]
    path = Tools/Skills/module-quick-analysis
    url = https://github.com/shajieChen/kiro-skill-module-quick-analysis.git
    branch = main
```

`Tools/Skills/` 目录结构：
```
Tools/Skills/
├── Execute-LandingPrompt/   (submodule)
├── OpenSpec/                 (submodule)
├── module-quick-analysis/    (submodule) ← 新增
├── project-state-spec/       (submodule)
└── project-state-tracker/    (submodule)
```

## What Does NOT Change

- `~/.kiro/skills/module-quick-analysis` 继续作为 Kiro 本地 skill 正常工作
- `install_skills.py` 路径逻辑不变
- 其他 submodule 不受影响

## Update Workflow (Post-Migration)

与其他 skill 一致：
```bash
# 在 Plan_Viewer 仓库中
git submodule update --remote Tools/Skills/module-quick-analysis
git add Tools/Skills/module-quick-analysis
git commit -m "chore: bump module-quick-analysis submodule"
```

## Risks & Mitigations

| Risk | Mitigation |
|---|---|
| GitHub 私有仓库需要认证才能 clone | 使用 gh CLI 或已配置的 credential helper |
| Fresh clone 缺少 submodule 内容 | `install_skills.bat` 已有 `git submodule update --init --remote` |
