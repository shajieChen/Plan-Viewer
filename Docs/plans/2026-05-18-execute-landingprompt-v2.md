# Execute-LandingPrompt v2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rewrite the Execute-LandingPrompt SKILL.md to include PST回流能力，使执行结果自动写入 workspace 的 status.yaml。

**Architecture:** 单文件 SKILL.md 替换。Phase A（执行）保留原有逻辑，Phase B（回流）追加 scaffold + 数据写入指令。

**Tech Stack:** Markdown (SKILL.md format), YAML (status.yaml schema knowledge embedded in prompt)

**Design Doc:** `Docs/specs/2026-05-18-execute-landingprompt-v2-design.md`

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `C:\Users\chenshajie\.kiro\skills\Execute-LandingPrompt\SKILL.md` | Replace | 完整的 skill prompt（Phase A + Phase B） |

---

### Task 1: Write the new SKILL.md

**Files:**
- Replace: `C:\Users\chenshajie\.kiro\skills\Execute-LandingPrompt\SKILL.md`

- [ ] **Step 1: Write the complete new SKILL.md**

The file must contain these sections in order:

1. YAML front-matter (`name`, `description` — updated to mention PST回流)
2. `# Execute LandingPrompt` title
3. `## Invocation` — unchanged
4. `## Project Detection` — unchanged
5. `## Scope` — updated (added Local PST workspace-local LP support)
6. `## Execution Flow` — updated to 12 steps (Phase A 1-8 + Phase B 9-12)
7. `## § ID Resolution` — NEW section (PST-registered > filename pattern > fallback)
8. `## § Status Mapping` — NEW section (completed→ready, partial→needs_update, blocked→blocked)
9. `## Constraints` — unchanged
10. `## Coding Standards` — unchanged (Baseline + UE_Iris + Net Monitor)
11. `## LandingPrompt Sequence` — unchanged
12. `## Handoff Template` — unchanged
13. `## § PST 回流` — NEW section with:
    - Phase B 触发条件
    - 写入方式（优先 apply_changes.py 管道）
    - Scaffold 规则（含 .cache/ 和 prompts/ 目录）
    - 数据映射表（使用 ready 而非 archived）
    - HC 管理（条件性 version bump）
    - 幂等性规则
    - change_event 格式
    - 错误处理（Phase B 失败不影响 Phase A）
14. `## Safety Checks` — updated (追加 Phase B 多项检查)

Complete content follows:

```markdown
---
name: Execute-LandingPrompt
description: "Execute exactly one LandingPrompt file from a supported project (RB_Net_Monitor or UE_Iris), then auto-sync execution results back to the workspace's status/status.yaml (PST回流). Use when the user says Skill + corresponding file, Skill + 对应文件, execute LandingPrompt, or asks to land one LandingPrompt step."
---

# Execute LandingPrompt

## Invocation

```text
Skill Execute-LandingPrompt + Q:\PortNotes\RB_Net_Monitor\LandingPrompt\CL_SubStep_Verify.md
Skill Execute-LandingPrompt + Q:\PortNotes\UE_Iris\LandingPrompt\Phase3-DescriptorRegistry.md
```

If the user provides a folder, read that folder's `README.md` and ask which single prompt file to execute.

---

## Project Detection

| Path prefix | Project | Source root | Prompt root |
|---|---|---|---|
| `Q:\PortNotes\RB_Net_Monitor\` | Net Monitor | `Q:\1.55.0_Net_Monitor\Source` | `Q:\PortNotes\RB_Net_Monitor\LandingPrompt` |
| `Q:\PortNotes\UE_Iris\` | UE_Iris (Replication) | `Q:\1.47\Source` | `Q:\PortNotes\UE_Iris\LandingPrompt` |

---

## Scope

- **Net Monitor**: `Q:\PortNotes\RB_Net_Monitor` + `Q:\1.55.0_Net_Monitor\Source`
- **UE_Iris**: `Q:\PortNotes\UE_Iris` + `Q:\1.47\Source` (primary target: `Core\RainbowEngine\Engine\System\Network\ReplicationSystem\`)

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

### Phase B — PST 回流 (Steps 9–11)

9. Detect `status/status.yaml` in workspace root. If missing → scaffold (see § PST 回流).
10. Write/update: LP artifact entry + handoff_context + change_event.
11. Set LP artifact status: completed→`archived`, partial→`needs_update`, blocked→`blocked`.

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

## § PST 回流

### 触发条件

Phase A 完成后（无论结果是 completed/partial/blocked），立即执行 Phase B。

### Scaffold 规则

如果 workspace 根目录下不存在 `status/status.yaml`，创建：

```
<workspace_root>/
└── status/
    └── status.yaml
```

不创建 tools/、views/、.cache/ 等目录。

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
  facts:
  - "<confirmed item 1>"
  - "<confirmed item 2>"
  constraints:
  - "<unresolved item 1>"
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
    reason: "ELP execution: <one-line summary>"
```

### 数据映射

| ELP 产出 | PST 字段 | 规则 |
|----------|----------|------|
| LP 文件名 | `artifacts[].id` | `LP.<stem>`（去 .md） |
| completed | `artifacts[].status` | → `archived` |
| partial | `artifacts[].status` | → `needs_update` |
| blocked | `artifacts[].status` | → `blocked` |
| confirmed 每条 | `handoff_contexts[].facts[]` | 原文 |
| unresolved 每条 | `handoff_contexts[].constraints[]` | 原文 |
| 下一个 LP | `handoff_contexts[].consumed_by[]` | `[LP.<next_stem>]` |
| 修改文件列表 | `change_events[].summary` | 仅记录 |

### HC ID 分配

- 已有该 LP 的 HC → version +1，覆盖 facts/constraints
- 没有 → 分配 `HC-<next>`（基于已有最大数字 +1）

### 幂等性

- 同一 LP 重复执行：更新 artifact status，HC version +1，追加 change_event
- 不产生重复 artifact 或 HC 条目
- change_events 永远追加

### change_event 格式

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
- Phase B 回流完成或失败已报告.
```

- [ ] **Step 2: Verify the file was written correctly**

Read back the file and confirm:
- YAML front-matter has updated `description` mentioning PST回流
- Execution Flow shows 11 steps (Phase A 1-8 + Phase B 9-11)
- `§ PST 回流` section exists with scaffold template, data mapping table, HC ID rules, idempotency rules, change_event format, error handling
- Safety Checks has the new Phase B line
- All original sections (Project Detection, Scope, Constraints, Coding Standards, LandingPrompt Sequence, Handoff Template) are preserved verbatim

- [ ] **Step 3: Commit**

```bash
git add "C:\Users\chenshajie\.kiro\skills\Execute-LandingPrompt\SKILL.md"
git commit -m "feat: Execute-LandingPrompt v2 — add PST回流 (status.yaml auto-sync)"
```

---

### Task 2: Validate by dry-run mental model

- [ ] **Step 1: Trace a completed execution**

Mentally trace: ELP executes `CL_SubStep_Verify.md` → completed → Phase B:
- workspace = `Q:\PortNotes\RB_Net_Monitor`
- No `status/status.yaml` → scaffold
- artifact: `LP.CL_SubStep_Verify`, status: `archived`
- HC-001: producer `LP.CL_SubStep_Verify`, consumed_by `[LP.CL_SubStep_Structures]`
- CE-001: from null → archived

Confirm this matches the spec's expected behavior.

- [ ] **Step 2: Trace a repeated execution**

Same LP executed again (partial this time):
- status.yaml exists → no scaffold
- artifact `LP.CL_SubStep_Verify` already exists → update status to `needs_update`
- HC-001 exists → version becomes 2, facts/constraints overwritten
- CE-002 appended

Confirm idempotency rules hold.

- [ ] **Step 3: Trace a blocked execution**

ELP executes `Phase3-DescriptorRegistry.md` → blocked:
- workspace = `Q:\PortNotes\UE_Iris`
- scaffold if needed
- artifact: `LP.Phase3-DescriptorRegistry`, status: `blocked`
- HC: facts from confirmed, constraints from unresolved
- Handoff footer: no error (Phase B succeeded)

Confirm blocked path works.
