# Execute-LandingPrompt v2 — PST 回流集成设计

## Overview

重写 Execute-LandingPrompt skill，在保留原有"单 prompt 执行引擎"核心的基础上，追加 Phase B 回流阶段，使执行结果自动写入 workspace 的 `status/status.yaml`，与 project-state-tracker 体系对齐。

## 决策记录

| # | 问题 | 决策 |
|---|------|------|
| 1 | 回流目标 | 回流到 ELP 所在 workspace 自身的 status.yaml |
| 2 | 目标项目无 PST 结构 | ELP 首次回流时自动 scaffold（含 status/.cache/ 和 prompts/ 目录） |
| 3 | LP artifact ID 规则 | 优先使用 PST 已注册 ID → 文件名模式 `LP-001` → fallback `LP.<stem>` |
| 4 | 写入方式 | 优先 apply_changes.py 管道（如存在）；scaffold-only 时直接写 |
| 5 | Handoff 映射 | confirmed→facts[], unresolved→constraints[] |
| 6 | LP 状态流转 | completed→`ready`, partial→`needs_update`, blocked→`blocked`（不使用 archived） |
| 7 | 回流架构 | 内联回流（Phase A 末尾写，优先走 PST 管道） |
| 8 | 外部 LP 路径 | `external:<project>/<filename>.md` 前缀标记，PST dirty_check 跳过 |
| 9 | HC version bump | 仅当 facts/constraints 内容实际变化时 +1（遵守 PST §7） |
| 10 | workspace-local LP | 支持 `prompts/landing/` 目录下的 LP，与 PST §6A 完全兼容 |

## 架构

```
Phase A: 执行（Steps 1-8，与现有 ELP 一致）
Phase B: 回流（Steps 9-11，新增）
```

### Phase A — 执行

1. 读 README.md → 确定序列
2. 读当前 LP 文件
3. 按需读前置 prompt
4. 摘要 goal/mode/allowed files/gates
5. 执行当前 prompt（代码修改或验证）
6. 验证 + 对比 acceptance criteria
7. 判定状态：completed / partial / blocked
8. 读下一个 prompt（不执行）→ 产出 Markdown handoff

### Phase B — PST 回流

9. 检测 workspace 是否有 `status/status.yaml`；没有则 scaffold
10. 写入/更新：LP artifact 条目 + handoff_context + change_event
11. 更新 LP artifact 状态

Phase B 是"尽力而为"——如果 YAML 写入失败，在 handoff 末尾报告但不影响 Phase A 的结果判定。

## Scaffold 规则

当 workspace 下没有 `status/status.yaml` 时，创建最小结构：

```
<workspace_root>/
└── status/
    └── status.yaml
```

不创建 tools/、views/、.cache/、research/、decisions/ 等目录。

最小 status.yaml 模板：

```yaml
meta:
  project_name: "<workspace folder name>"
  created: "<ISO timestamp>"
  last_updated: "<ISO timestamp>"
  total_artifacts: 1
  total_research: 0
  total_blockers: 0
  hotspots: []

artifacts:
- id: LP.<stem>
  type: landing_prompt
  path: "LandingPrompt/<filename>.md"
  status: <archived|needs_update|blocked>
  depends_on: []
  produces_handoffs: [HC-001]

handoff_contexts:
- id: HC-001
  producer: LP.<stem>
  version: 1
  status: available
  facts: [<confirmed items>]
  constraints: [<unresolved items>]
  consumed_by: [LP.<next_stem>]
  consumed_status: []

change_events:
- id: CE-001
  time: "<ISO>"
  source: Execute-LandingPrompt
  event_type: scaffold_and_execute
  affected: [LP.<stem>]
  transitions:
  - artifact: LP.<stem>
    from: null
    to: <archived|needs_update|blocked>
    reason: "ELP execution result: <status>"
```

## 数据映射

| ELP 产出 | PST 字段 | 规则 |
|----------|----------|------|
| 当前 LP 文件名 | artifacts[].id | `LP.<stem>` |
| completed | artifacts[].status | → archived |
| partial | artifacts[].status | → needs_update |
| blocked | artifacts[].status | → blocked |
| confirmed 列表每条 | handoff_contexts[].facts[] | 原文保留 |
| unresolved 列表每条 | handoff_contexts[].constraints[] | 原文保留 |
| 下一个 LP（README 序列） | handoff_contexts[].consumed_by[] | [LP.<next_stem>] |
| 修改文件列表 | change_events[].summary | 仅记录 |

## HC ID 分配

- status.yaml 中已有该 LP 的 HC → 更新（version +1，覆盖 facts/constraints）
- 没有 → 分配下一个顺序 ID（HC-001, HC-002...，基于已有最大值）

## 幂等性

- 同一 LP 重复执行：更新已有 artifact status，HC version +1，追加新 change_event
- 不产生重复 artifact 或 HC 条目
- change_events 永远追加，不覆盖（审计日志）

## change_event 格式

```yaml
- id: CE-<next>
  time: "<ISO>"
  source: Execute-LandingPrompt
  event_type: lp_execution
  affected: [LP.<stem>]
  transitions:
  - artifact: LP.<stem>
    from: <previous_status or null>
    to: <archived|needs_update|blocked>
    reason: "ELP: <one-line summary>"
```

## 保留不变的部分

- Project Detection 表（Net Monitor / UE_Iris 路径映射）
- Scope 定义
- Constraints 全部
- Coding Standards 全部（Baseline + UE_Iris + Net Monitor）
- LandingPrompt Sequence fallback
- Handoff Template（Markdown 格式不变）

## Safety Checks（更新）

原有检查全部保留，追加一条：

- Phase B 回流完成或失败已报告

## 交付物

单文件：`C:\Users\chenshajie\.kiro\skills\Execute-LandingPrompt\SKILL.md`（替换现有文件）
