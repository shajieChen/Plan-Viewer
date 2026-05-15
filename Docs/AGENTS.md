# AGENTS.md — Project State Index

Project: **Plan_Viewer**  
Last updated: 2026-05-14T00:00:00Z

## Quick Stats

- Artifacts: 3 (1 Research, 1 Decision, 1 Plan)
- Research: 1
- Open blockers: 0

## Read X for Y

| Need | Read |
|------|------|
| Full project overview | `views/overview_view.md` |
| Blocker details | `views/blocker_view.md` |
| Prompt execution chain | `views/prompt_chain_view.md` |
| Handoff status | `views/handoff_view.md` |
| Recent changes | `views/change_log_view.md` |
| Authoritative state | `status/status.yaml` |

## Artifact Summary

| ID | Type | Status | Path |
|----|------|--------|------|
| R-001 | research | reviewed | `research/R-001-Dashboard-Visualization-Research.md` |
| D-001 | decision | accepted | `decisions/D-001-single-html-react-cdn.yaml` |
| Plan.dashboard-design | plan | draft | `plan/2026-05-14-dashboard-visualization-design.md` |

## Directory Map

```
research/           R-xxx-*.md     — 调研事实与证据
decisions/          D-xxx-*.yaml   — 基于调研的决策
plan/               P-xxx-*.md     — 执行计划与设计
prompts/landing/    LP-xxx-*.md    — 实施 Prompt
prompts/test/       TP-xxx-*.md    — 验证 Prompt
status/status.yaml                 — 状态单一真相源
views/                             — 只读派生视图
tools/                             — Python 状态管理脚本
```
