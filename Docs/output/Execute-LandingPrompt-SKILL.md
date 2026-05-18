---
name: Execute-LandingPrompt
description: "Execute exactly one LandingPrompt file from a supported project (RB_Net_Monitor or UE_Iris) OR from the current workspace's prompts/landing/ directory, then auto-sync execution results back to the workspace's status/status.yaml (PST回流). Use when the user says Skill + corresponding file, Skill + 对应文件, execute LandingPrompt, or asks to land one LandingPrompt step."
---

# Execute LandingPrompt

## Invocation

```text
Skill Execute-LandingPrompt + Q:\PortNotes\RB_Net_Monitor\LandingPrompt\CL_SubStep_Verify.md
Skill Execute-LandingPrompt + Q:\PortNotes\UE_Iris\LandingPrompt\Phase3-DescriptorRegistry.md
Skill Execute-LandingPrompt + prompts/landing/LP-001-some-task.md
```

If the user provides a folder, read that folder's `README.md` and ask which single prompt file to execute.

---

## Project Detection

| Path prefix | Project | Source root | Prompt root |
|---|---|---|---|
| `Q:\PortNotes\RB_Net_Monitor\` | Net Monitor | `Q:\1.55.0_Net_Monitor\Source` | `Q:\PortNotes\RB_Net_Monitor\LandingPrompt` |
| `Q:\PortNotes\UE_Iris\` | UE_Iris (Replication) | `Q:\1.47\Source` | `Q:\PortNotes\UE_Iris\LandingPrompt` |
| `prompts/landing/` (workspace-local) | Local PST | workspace root | `<workspace>/prompts/landing/` |

For workspace-local LPs, the source root is the workspace root itself.

---

## Scope

- **Net Monitor**: `Q:\PortNotes\RB_Net_Monitor` + `Q:\1.55.0_Net_Monitor\Source`
- **UE_Iris**: `Q:\PortNotes\UE_Iris` + `Q:\1.47\Source` (primary target: `Core\RainbowEngine\Engine\System\Network\ReplicationSystem\`)
- **Local PST**: workspace root (LP files in `prompts/landing/`, source in workspace)

---

## Execution Flow

### Phase A — Execute (Steps 1–8)

1. Read `LandingPrompt\README.md` for the detected project.
2. Read the user-specified current LandingPrompt file.
3. Read prerequisite prompts only when needed for safe execution.
4. Execute only the current prompt (summarize goal/mode/allowed files/gates first).
5. Run relevant verification; compare against acceptance criteria.
6. Mark as `completed` / `partial` / `blocked`.
7. Read the next prompt for handoff context — do NOT execute it.
8. Produce the handoff section (Markdown).

### Phase B — PST 回流 (Steps 9–12)

9. Detect `status/status.yaml` in workspace root. If missing → scaffold (see § PST 回流).
10. Resolve LP artifact ID (see § ID Resolution).
11. Write/update: LP artifact entry + handoff_context + change_event via `approved_transitions.json → apply_changes.py` pipeline when tools exist, or direct write when scaffold-only.
12. Set LP artifact status per § Status Mapping.

Phase B is best-effort. If YAML write fails, report the error in the handoff footer but do NOT alter Phase A results.

---

## Constraints

- **Single Prompt Rule**: Do not execute sibling prompts, do not widen scope, do not start the next prompt. If blocked, hand off the blocker.
- **Verify-only prompts**: Do not modify source files.
- **Missing anchors**: Stop and report, do not guess nonexistent functions/paths.
- **Allowed files only**: Keep edits inside the current prompt's file list.
- **Preserve `禁止修改` / `不应改动` rules**.
- **`confirmed` = reusable facts; `unresolved` = gates to verify first**.
- **If an unresolved gate fails**: Stop, write handoff note, do not force code.

---

## Coding Standards

### Baseline

All code written by this skill MUST follow the workspace steering rules (`.kiro/steering/rules.md`), which are always loaded into context. Key points already covered there:

- 无注释、函数体内无空行、显式类型、变量必须初始化
- 容器/智能指针使用引擎 Utilities 实现（`DynamicArray` 优先）
- 内存分配使用引擎接口 + MemLabel 标签
- 静态对象使用 `RuntimeStatic<T>` + `s_` 前缀 + `Get` 暴露
- CRLF、4 空格缩进、连续行局部对齐
- 禁止 `std::vector/map/shared_ptr/unique_ptr/new/delete/malloc/free`

**Do not repeat these rules in code review — they are enforced by steering.**

### UE_Iris — ReplicationSystem 特有规则

These are the rules SPECIFIC to the Replication System that go beyond the general steering:

| Rule | Correct | Forbidden |
|------|---------|-----------|
| Macro header | `NetReplication.h` | IrisReplication.h |
| Macro prefix | `NET_REPLICATED_STRUCT`, `NET_FIELD`, `NET_ARRAY_FIELD` | IRIS_* |
| Generated suffix | `.net.generated.h` / `.net.generated.cpp` | .iris.generated.* |
| Tool directory | `Source/Tools/NetCodeGen/` | IrisCodeGen |
| Comments | "replication" / "net replication" | "Iris replication" |
| "Iris" in source | NEVER | Only in `PortNotes/UE_Iris/Research/` |

Additional ReplicationSystem conventions:
- Namespaces: `namespace Rainbow { ... } // namespace Rainbow`
- DLL export: `EXPORT_ENGINEMODULE` on classes crossing DLL boundaries (not on templates).
- Naming: PascalCase types/methods, `m_PascalCase` members, `k` prefix constants, `UPPER_SNAKE` macros.
- Enum: `enum class` + explicit underlying type + `ENUM_FLAGS_8` for flags + `k` prefix values.
- Reflection: `DECLARE_REFLECT()`, `DECLARE_CLASS()`, `DECLARE_OBJECT_SERIALIZE()`.
- Object ctors: first param `MemLabelId label`.
- Threading: `ASSERT_RUNNING_ON_MAIN_THREAD` for gameplay state writes.
- Serialization: Network = `NetSerialize`/`NetDeserialize`; Object = `Transfer(TransferFunction&)`. Never mix.
- Dependency: `Core/RainbowEngine <- SandboxEngine <- SandboxGame <- MiniGame`. No upward deps.

### Net Monitor — Project Standards

Follow existing code style in `Q:\1.55.0_Net_Monitor\Source`. Match surrounding file style.

---

## LandingPrompt Sequence (Net Monitor fallback)

Only if README is unavailable:

```
CollectionLayer_Phase -> CL_SubStep_Verify -> CL_SubStep_Structures -> CL_SubStep_Instrumentation -> CL_SubStep_Lifecycle
TelemetryProcessingLayer_Phase -> TPL_SubStep_Framework -> TPL_SubStep_Snapshot -> TPL_SubStep_SinkAndTick
PresentationLayer_Phase -> PL_SubStep_Verify -> PL_SubStep_Sinks -> PL_SubStep_Integration
```

---

## Handoff Template

```markdown
## 当前 Prompt 执行结果

- 当前文件:
- 执行状态: completed / partial / blocked
- 已完成:
- 未完成:
- 修改文件:
- 验证结果:

## confirmed

- ...

## unresolved

- ...

## 给下一个 Prompt 的交接

- 下一个文件:
- 已预读但未执行:
- 下一个 Prompt 的入口条件:
- 当前阶段提供给它的可复用事实:
- 必须避免重复做的事:
- 必须先验证的风险:
```

---

## § ID Resolution

### LP Artifact ID

Resolution order (first match wins):

1. **PST-registered ID**: If `status/status.yaml` already contains an artifact whose `path` matches the LP file → use that artifact's `id` (e.g., `LP-001`).
2. **Filename pattern**: If filename matches `LP-\d{3}-*.md` → extract `LP-001` etc.
3. **Fallback slug**: `LP.<stem>` (filename without `.md`).

This ensures ELP respects IDs assigned by PST's §6A extraction rules. When PST has already registered an LP as `LP-001`, ELP will update that same record rather than creating a duplicate `LP.<stem>`.

### LP Path in status.yaml

| Source | `artifacts[].path` value |
|--------|--------------------------|
| Workspace-local (`prompts/landing/`) | `prompts/landing/<filename>.md` (relative to workspace) |
| External (Net Monitor / UE_Iris) | `external:<project>/<filename>.md` (prefixed to signal non-local) |

The `external:` prefix tells PST's dirty_check to skip this artifact during file-based scanning (it cannot resolve external paths). PST AUDIT treats `external:*` artifacts as "agent-managed" — state transitions come only from ELP, not from file change detection.

---

## § Status Mapping

### LP 状态流转（PST 状态机兼容）

ELP execution results map to PST states as follows:

| ELP 结果 | PST status | 语义 |
|----------|-----------|------|
| completed | `ready` | LP 已成功执行，产出可用，下游可消费 |
| partial | `needs_update` | LP 部分完成，需要重新执行 |
| blocked | `blocked` | LP 被阻塞，需要外部解决 |

**Why `ready` instead of `archived`:**
- `archived` is a terminal state in PST's state machine (no outgoing transitions). Using it would make re-execution impossible.
- `ready` means "this artifact has been processed and its outputs are available for consumption" — which is exactly what a completed LP is.
- If the user later wants to permanently close an LP (no more re-execution expected), PST AUDIT can transition `ready → archived` through the normal pipeline.

**Valid re-execution transitions:**
- `ready → ready` (re-executed, still completed — HC version bumps)
- `ready → needs_update` (re-executed, now partial)
- `ready → blocked` (re-executed, now blocked)
- `needs_update → ready` (re-executed, now completed)
- `needs_update → needs_update` (re-executed, still partial)
- `blocked → ready` (blocker resolved, re-executed successfully)
- `blocked → needs_update` (partially unblocked)

All of these are legal in PST's state machine (`ready → needs_update | blocked` is defined; `needs_update → ready` goes through the implicit `needs_update → reviewed → approved → ready` semantic, which ELP collapses because it IS the reviewer+approver+executor).

---

## § PST 回流

### 触发条件

Phase A 完成后（无论结果是 completed/partial/blocked），立即执行 Phase B。

### 写入方式

**Priority order:**

1. If `tools/apply_changes.py` exists in workspace → write `status/.cache/approved_transitions.json` then invoke `python tools/apply_changes.py --project <workspace_root>`. This respects PST §1 write boundaries.
2. If tools/ does not exist (scaffold-only workspace) → direct-write status.yaml. This is acceptable because no PST pipeline exists yet to conflict with.

### Scaffold 规则

如果 workspace 根目录下不存在 `status/status.yaml`，创建完整 PST 结构：

```
<workspace_root>/
├── status/
│   ├── status.yaml
│   └── .cache/
├── prompts/
│   ├── landing/
│   └── test/
└── (views/ and tools/ are NOT created — PST INIT handles those)
```

最小 status.yaml 内容：

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
- id: <resolved per § ID Resolution>
  type: landing_prompt
  path: <resolved per § ID Resolution path rules>
  status: <ready|needs_update|blocked>
  depends_on: []
  produces_handoffs: [HC-001]
  consumes_handoffs: []

handoff_contexts:
- id: HC-001
  producer: <artifact id>
  version: 1
  status: available
  facts:
  - "<confirmed item 1>"
  - "<confirmed item 2>"
  constraints:
  - "<unresolved item 1>"
  consumed_by: [<next LP id>]
  consumed_status: []

change_events:
- id: CE-001
  time: "<ISO>"
  source: Execute-LandingPrompt
  event_type: scaffold_and_execute
  affected: [<artifact id>]
  transitions:
  - artifact: <artifact id>
    from: null
    to: <ready|needs_update|blocked>
    reason: "ELP execution: <one-line summary>"
```

### 数据映射

| ELP 产出 | PST 字段 | 规则 |
|----------|----------|------|
| LP 文件名 | `artifacts[].id` | 按 § ID Resolution 解析 |
| completed | `artifacts[].status` | → `ready` |
| partial | `artifacts[].status` | → `needs_update` |
| blocked | `artifacts[].status` | → `blocked` |
| confirmed 每条 | `handoff_contexts[].facts[]` | 原文 |
| unresolved 每条 | `handoff_contexts[].constraints[]` | 原文 |
| 下一个 LP | `handoff_contexts[].consumed_by[]` | `[<next LP id>]` |
| 修改文件列表 | `change_events[].summary` | 仅记录 |

### HC 管理

**ID 分配:**
- status.yaml 中已有该 LP 的 HC → 更新 facts/constraints，**不 bump version**（遵守 PST §7 "Never auto-bump HC versions"）
- 没有 → 分配下一个顺序 ID（HC-001, HC-002...，基于已有最大值）
- 新创建的 HC 标记 `status: available`

**Version bump 条件（仅当以下全部满足时 +1）:**
- HC 已存在
- facts 或 constraints 内容实际发生了变化（与上次不同）
- 这确保只有"新信息"才触发 version bump，纯重复执行不会无意义递增

### 幂等性

- 同一 LP 重复执行：更新已有 artifact status，按条件 bump HC version，追加新 change_event
- 不产生重复 artifact 或 HC 条目
- change_events 永远追加（审计日志）
- 如果执行结果与当前 status.yaml 中的状态完全相同且 HC 内容无变化 → 仍追加 change_event（记录执行事实），但不修改 artifact/HC

### change_event 格式

```yaml
- id: CE-<next>
  time: "<ISO>"
  source: Execute-LandingPrompt
  event_type: lp_execution
  affected: [<artifact id>]
  transitions:
  - artifact: <artifact id>
    from: <previous_status or null>
    to: <ready|needs_update|blocked>
    reason: "ELP: <one-line summary>"
```

### 错误处理

如果 Phase B 任何步骤失败（YAML 解析错误、文件写入失败等）：
1. 不修改 Phase A 的执行状态判定
2. 在 handoff 末尾追加一行：`⚠️ PST 回流失败: <error description>`
3. 继续正常输出 handoff

---

## Safety Checks (before final response)

- README was read first; current prompt was read and only it was executed.
- Next prompt was read but not executed; handoff section exists.
- No forbidden scope modified; no unresolved reported as confirmed.
- All code conforms to steering rules + project-specific standards above.
- Phase B: artifact ID resolved correctly (PST-registered > filename pattern > fallback).
- Phase B: status mapping uses `ready`/`needs_update`/`blocked` (never `archived`).
- Phase B: write method matches workspace state (apply_changes.py if exists, else direct).
- Phase B: HC version only bumped if facts/constraints actually changed.
- Phase B 回流完成或失败已报告.
