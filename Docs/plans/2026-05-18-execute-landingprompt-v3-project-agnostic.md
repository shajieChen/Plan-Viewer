# Execute-LandingPrompt v3 — Project-Agnostic Rewrite Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rewrite Execute-LandingPrompt SKILL.md to remove all project-specific hardcoding, making it a generic execution engine that reads project context from each project's `LandingPrompt/README.md`.

**Architecture:** Three deliverables — (1) rewrite SKILL.md as project-agnostic engine with README protocol + path derivation rules, (2) update Net Monitor README.md with front-matter + coding standards, (3) create UE_Iris README.md with front-matter + coding standards. The SKILL.md retains Phase A/B execution logic, constraints, handoff template, ID resolution, status mapping, and PST 回流 — but delegates all project-specific knowledge to README files.

**Tech Stack:** Markdown (SKILL.md format), YAML front-matter

**Design Doc:** `Docs/specs/2026-05-18-execute-landingprompt-v3-project-agnostic-design.md`

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `C:\Users\chenshajie\.kiro\skills\Execute-LandingPrompt\SKILL.md` | Replace | 通用执行引擎（README 协议 + 路径推导 + Phase A/B + Constraints + Handoff） |
| `Q:\PortNotes\RB_Net_Monitor\LandingPrompt\README.md` | Modify | 添加 YAML front-matter + `## Coding Standards` section |
| `Q:\PortNotes\UE_Iris\LandingPrompt\README.md` | Create | 完整 README（front-matter + LP 序列 + Coding Standards） |

---

### Task 1: Write the new project-agnostic SKILL.md

**Files:**
- Replace: `C:\Users\chenshajie\.kiro\skills\Execute-LandingPrompt\SKILL.md`

- [ ] **Step 1: Write the complete new SKILL.md**

Replace the entire file with the following content:

```markdown
---
name: Execute-LandingPrompt
description: "Execute exactly one LandingPrompt file from any project, then auto-sync execution results back to the project's status/status.yaml (PST回流). Project context (source root, coding standards, LP sequence) is read from the LandingPrompt directory's README.md. Use when the user says Skill + corresponding file, Skill + 对应文件, execute LandingPrompt, or asks to land one LandingPrompt step."
---

# Execute LandingPrompt

## Invocation

```text
Skill Execute-LandingPrompt + <path-to-any-landing-prompt-file>.md
```

Examples:
```text
Skill Execute-LandingPrompt + Q:\PortNotes\RB_Net_Monitor\LandingPrompt\CL_SubStep_Verify.md
Skill Execute-LandingPrompt + Q:\PortNotes\UE_Iris\LandingPrompt\Phase3-DescriptorRegistry.md
Skill Execute-LandingPrompt + prompts/landing/LP-001-some-task.md
```

If the user provides a folder, read that folder's `README.md` and ask which single prompt file to execute.

---

## § Path Derivation

Given user input `Skill Execute-LandingPrompt + <lp_file_path>`:

```
lp_dir       = dirname(lp_file_path)                           # LP 文件所在目录
readme_path  = lp_dir / README.md                              # README 位置
source_root  = README.front_matter.source_root                 # 必填，从 README 读取
scope        = README.front_matter.scope ?? [source_root, dirname(lp_dir)]
pst_root     = README.front_matter.pst_root ?? dirname(lp_dir)
```

**If `readme_path` does not exist:** Output error and STOP. Do not execute any LP without a README.

---

## § README Protocol

Every LandingPrompt directory MUST contain a `README.md` with this structure:

### YAML Front-matter (machine-readable config)

```yaml
---
source_root: "<absolute path>"     # REQUIRED: source code root directory
scope:                             # Optional: allowed file paths for ELP operations
  - "<path1>"                      # Default = [source_root, dirname(lp_dir)]
  - "<path2>"
pst_root: "<absolute path>"        # Optional: PST writeback target directory
                                   # Default = dirname(lp_dir)
                                   # ELP writes to <pst_root>/status/status.yaml
---
```

### Markdown Body (human-readable + ELP-parsed sections)

| Section heading | Purpose | Required |
|---|---|---|
| `## LP 序列` | Declares LP execution order; ELP uses this to determine "next prompt" | Yes |
| `## Coding Standards` | Project coding conventions; ELP follows these when modifying code | No |

Remaining body content is free-form for human readers.

---

## § Coding Standards Resolution

ELP does NOT contain any built-in coding standards. Resolution priority:

1. README.md `## Coding Standards` section → if present, follow those rules
2. If README has no such section → follow workspace `.kiro/steering/` rules (if any)
3. If neither exists → follow general best practices

---

## Execution Flow

### Phase A — Execute (Steps 1–8)

1. Derive `lp_dir` from LP file path. Read `lp_dir/README.md`.
   - Parse YAML front-matter → extract `source_root`, `scope`, `pst_root`
   - Parse body → extract LP sequence, Coding Standards
   - If README.md missing → error and STOP
2. Read the user-specified current LandingPrompt file.
3. Read prerequisite prompts only when needed for safe execution.
4. Execute only the current prompt (summarize goal/mode/allowed files/gates first).
5. Run relevant verification; compare against acceptance criteria.
6. Mark as `completed` / `partial` / `blocked`.
7. Read the next prompt (determined from LP sequence) for handoff context — do NOT execute it.
8. Produce the handoff section (Markdown).

### Phase B — PST 回流 (Steps 9–12)

9. Check if `<pst_root>/status/status.yaml` exists. If missing → scaffold (see § PST 回流).
10. Resolve LP artifact ID (see § ID Resolution).
11. Write/update: LP artifact entry + handoff_context + change_event.
12. Set LP artifact status (see § Status Mapping).

Phase B is best-effort. If YAML write fails, report the error in the handoff footer but do NOT alter Phase A results.

---

## Constraints

- **Single Prompt Rule**: Do not execute sibling prompts, do not widen scope, do not start the next prompt. If blocked, hand off the blocker.
- **Verify-only prompts**: Do not modify source files.
- **Missing anchors**: Stop and report, do not guess nonexistent functions/paths.
- **Allowed files only**: Keep edits inside the current prompt's file list AND within `scope`.
- **Preserve `禁止修改` / `不应改动` rules**.
- **`confirmed` = reusable facts; `unresolved` = gates to verify first**.
- **If an unresolved gate fails**: Stop, write handoff note, do not force code.

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

1. **PST-registered ID**: If `status/status.yaml` already contains an artifact whose `path` matches the LP file → use that artifact's `id`.
2. **Filename pattern**: If filename matches `LP-\d{3}-*.md` → extract `LP-001` etc.
3. **Fallback slug**: `LP.<stem>` (filename without `.md`).

### LP Path in status.yaml

| Source | `artifacts[].path` value |
|--------|--------------------------|
| Workspace-local (`prompts/landing/`) | `prompts/landing/<filename>.md` (relative to pst_root) |
| External (any other absolute path) | `external:<project_dir_name>/<filename>.md` |

The `external:` prefix tells PST dirty_check to skip this artifact during file-based scanning.

---

## § Status Mapping

| ELP Result | PST status | Semantics |
|----------|-----------|------|
| completed | `ready` | LP executed successfully, outputs available for downstream |
| partial | `needs_update` | LP partially completed, needs re-execution |
| blocked | `blocked` | LP blocked, needs external resolution |

**Valid re-execution transitions:**
- `ready → ready` (re-executed, still completed — HC version bumps if content changed)
- `ready → needs_update` / `ready → blocked`
- `needs_update → ready` / `needs_update → needs_update`
- `blocked → ready` / `blocked → needs_update`

---

## § PST 回流

### Trigger

After Phase A completes (regardless of completed/partial/blocked), immediately execute Phase B.

### Write Method

Priority order:
1. If `tools/apply_changes.py` exists in pst_root → write `status/.cache/approved_transitions.json` then invoke pipeline.
2. If tools/ does not exist → direct-write status.yaml.

### Scaffold Rules

If `<pst_root>/status/status.yaml` does not exist, create minimal structure:

```
<pst_root>/
├── status/
│   ├── status.yaml
│   └── .cache/
├── prompts/
│   ├── landing/
│   └── test/
└── (views/ and tools/ are NOT created — PST INIT handles those)
```

Minimal status.yaml:

```yaml
meta:
  project_name: "<pst_root folder name>"
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

### Data Mapping

| ELP Output | PST Field | Rule |
|----------|----------|------|
| LP filename | `artifacts[].id` | Per § ID Resolution |
| completed | `artifacts[].status` | → `ready` |
| partial | `artifacts[].status` | → `needs_update` |
| blocked | `artifacts[].status` | → `blocked` |
| Each confirmed item | `handoff_contexts[].facts[]` | Verbatim |
| Each unresolved item | `handoff_contexts[].constraints[]` | Verbatim |
| Next LP | `handoff_contexts[].consumed_by[]` | `[<next LP id>]` |
| Modified files list | `change_events[].summary` | Record only |

### HC Management

**ID assignment:**
- Existing HC for this LP in status.yaml → update facts/constraints
- No existing HC → assign next sequential ID (HC-001, HC-002... based on max existing)
- New HC marked `status: available`

**Version bump (only when ALL of these are true):**
- HC already exists
- facts or constraints content actually changed (differs from previous)

### Idempotency

- Same LP re-executed: update existing artifact status, conditionally bump HC version, append new change_event
- Never create duplicate artifact or HC entries
- change_events always append (audit log)
- If result identical to current status.yaml state AND HC content unchanged → still append change_event (record execution fact), but don't modify artifact/HC

### change_event Format

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

### Error Handling

If Phase B fails at any step (YAML parse error, file write failure, etc.):
1. Do NOT alter Phase A status determination
2. Append to handoff footer: `⚠️ PST 回流失败: <error description>`
3. Continue normal handoff output

---

## Safety Checks (before final response)

- README.md was read and front-matter parsed successfully.
- source_root path exists and is accessible.
- Current prompt was read and only it was executed.
- Next prompt was read but not executed; handoff section exists.
- All code modifications are within declared scope.
- Code follows Coding Standards declared in README (or steering fallback).
- No forbidden scope modified; no unresolved reported as confirmed.
- Phase B: artifact ID resolved correctly (PST-registered > filename pattern > fallback).
- Phase B: status mapping uses `ready`/`needs_update`/`blocked` (never `archived`).
- Phase B: write method matches pst_root state (apply_changes.py if exists, else direct).
- Phase B: HC version only bumped if facts/constraints actually changed.
- Phase B 回流完成或失败已报告.
```

- [ ] **Step 2: Verify the file structure**

Read back the file and confirm:
- YAML front-matter has updated `description` mentioning "any project" and README.md
- No `## Project Detection` table exists
- No `## Scope` hardcoded section exists
- No `## Coding Standards` with project-specific rules exists
- No `## LandingPrompt Sequence` fallback exists
- New sections present: `§ Path Derivation`, `§ README Protocol`, `§ Coding Standards Resolution`
- All retained sections present: Execution Flow, Constraints, Handoff Template, § ID Resolution, § Status Mapping, § PST 回流, Safety Checks

- [ ] **Step 3: Commit**

```bash
git add "C:\Users\chenshajie\.kiro\skills\Execute-LandingPrompt\SKILL.md"
git commit -m "feat: Execute-LandingPrompt v3 — project-agnostic rewrite"
```

---

### Task 2: Update Net Monitor LandingPrompt README.md

**Files:**
- Modify: `Q:\PortNotes\RB_Net_Monitor\LandingPrompt\README.md`

- [ ] **Step 1: Add YAML front-matter and Coding Standards to existing README**

The existing README already contains LP sequence information. Prepend YAML front-matter and append a `## Coding Standards` section. The final file should have this structure (preserve existing body content):

```markdown
---
source_root: "Q:\\1.55.0_Net_Monitor\\Source"
scope:
  - "Q:\\PortNotes\\RB_Net_Monitor"
  - "Q:\\1.55.0_Net_Monitor\\Source"
pst_root: "Q:\\PortNotes\\RB_Net_Monitor"
---

<... existing README content preserved as-is ...>

## Coding Standards

Follow existing code style in `Q:\1.55.0_Net_Monitor\Source`. Match surrounding file style.

Additional rules enforced by workspace steering (`.kiro/steering/rules.md`):
- 无注释、函数体内无空行、显式类型、变量必须初始化
- 容器/智能指针使用引擎 Utilities 实现（`DynamicArray` 优先）
- 内存分配使用引擎接口 + MemLabel 标签
- 静态对象使用 `RuntimeStatic<T>` + `s_` 前缀 + `Get` 暴露
- CRLF、4 空格缩进、连续行局部对齐
- 禁止 `std::vector/map/shared_ptr/unique_ptr/new/delete/malloc/free`
```

Note: If the existing README already has a section that serves as `## LP 序列`, rename it to exactly `## LP 序列` so ELP can parse it. If it uses a different heading (like `## Execution Order` or `## Sequence`), rename to `## LP 序列`.

- [ ] **Step 2: Verify the README**

Read back and confirm:
- YAML front-matter is valid (3 fields: source_root, scope, pst_root)
- `## LP 序列` section exists (or equivalent renamed)
- `## Coding Standards` section exists
- Original content preserved

- [ ] **Step 3: Commit**

```bash
cd Q:\PortNotes\RB_Net_Monitor
git add LandingPrompt/README.md
git commit -m "feat: add ELP v3 front-matter and coding standards to README"
```

---

### Task 3: Create UE_Iris LandingPrompt README.md

**Files:**
- Create: `Q:\PortNotes\UE_Iris\LandingPrompt\README.md`

- [ ] **Step 1: Write the complete README.md**

Note: UE_Iris currently has `EXECUTE_ORDER.md` but no `README.md`. Create `README.md` with full content. The LP sequence should be extracted from `EXECUTE_ORDER.md` (read it first to get the actual sequence).

```markdown
---
source_root: "Q:\\1.47\\Source"
scope:
  - "Q:\\PortNotes\\UE_Iris"
  - "Q:\\1.47\\Source"
pst_root: "Q:\\PortNotes\\UE_Iris"
---

# UE_Iris (Replication System) LandingPrompt

Primary target: `Core\RainbowEngine\Engine\System\Network\ReplicationSystem\`

## LP 序列

<Extract the execution order from EXECUTE_ORDER.md and place here.>
<Format: Phase1-NetSerializer-Interface -> Phase1-ScalarSerializers -> Phase1-ComplexSerializers -> Phase2-NetObjectHandle-Registry -> Phase3-DescriptorRegistry -> ... >

## Coding Standards

### ReplicationSystem 特有规则

| Rule | Correct | Forbidden |
|------|---------|-----------|
| Macro header | `NetReplication.h` | IrisReplication.h |
| Macro prefix | `NET_REPLICATED_STRUCT`, `NET_FIELD`, `NET_ARRAY_FIELD` | IRIS_* |
| Generated suffix | `.net.generated.h` / `.net.generated.cpp` | .iris.generated.* |
| Tool directory | `Source/Tools/NetCodeGen/` | IrisCodeGen |
| Comments | "replication" / "net replication" | "Iris replication" |
| "Iris" in source | NEVER | Only in `PortNotes/UE_Iris/Research/` |

### General Conventions

- Namespaces: `namespace Rainbow { ... } // namespace Rainbow`
- DLL export: `EXPORT_ENGINEMODULE` on classes crossing DLL boundaries (not on templates).
- Naming: PascalCase types/methods, `m_PascalCase` members, `k` prefix constants, `UPPER_SNAKE` macros.
- Enum: `enum class` + explicit underlying type + `ENUM_FLAGS_8` for flags + `k` prefix values.
- Reflection: `DECLARE_REFLECT()`, `DECLARE_CLASS()`, `DECLARE_OBJECT_SERIALIZE()`.
- Object ctors: first param `MemLabelId label`.
- Threading: `ASSERT_RUNNING_ON_MAIN_THREAD` for gameplay state writes.
- Serialization: Network = `NetSerialize`/`NetDeserialize`; Object = `Transfer(TransferFunction&)`. Never mix.
- Dependency: `Core/RainbowEngine <- SandboxEngine <- SandboxGame <- MiniGame`. No upward deps.

### Baseline (from workspace steering)

- 无注释、函数体内无空行、显式类型、变量必须初始化
- 容器/智能指针使用引擎 Utilities 实现（`DynamicArray` 优先）
- 内存分配使用引擎接口 + MemLabel 标签
- 静态对象使用 `RuntimeStatic<T>` + `s_` 前缀 + `Get` 暴露
- CRLF、4 空格缩进、连续行局部对齐
- 禁止 `std::vector/map/shared_ptr/unique_ptr/new/delete/malloc/free`
```

- [ ] **Step 2: Read EXECUTE_ORDER.md and fill in the LP 序列**

Read `Q:\PortNotes\UE_Iris\LandingPrompt\EXECUTE_ORDER.md`, extract the execution sequence, and write it into the `## LP 序列` section of the new README.md.

- [ ] **Step 3: Verify the README**

Read back and confirm:
- YAML front-matter is valid (3 fields)
- `## LP 序列` section has the complete sequence from EXECUTE_ORDER.md
- `## Coding Standards` section has all ReplicationSystem rules + General Conventions + Baseline
- No mention of "Iris" in coding standards (only in the project title which is in PortNotes context)

- [ ] **Step 4: Commit**

```bash
cd Q:\PortNotes\UE_Iris
git add LandingPrompt/README.md
git commit -m "feat: create ELP v3 README with front-matter and coding standards"
```

---

### Task 4: Update the Kiro skill description (front-matter trigger)

**Files:**
- Verify: `C:\Users\chenshajie\.kiro\skills\Execute-LandingPrompt\SKILL.md` (already done in Task 1)

- [ ] **Step 1: Verify skill discovery still works**

The skill's YAML front-matter `description` field is what Kiro uses for skill matching. Confirm the new description includes trigger phrases:
- "execute LandingPrompt"
- "Skill + corresponding file"
- "Skill + 对应文件"
- "land one LandingPrompt step"

These were preserved in Task 1. No additional action needed unless Task 1 verification found issues.

- [ ] **Step 2: Final integration check**

Mentally trace a full execution:
1. User says: `Skill Execute-LandingPrompt + Q:\PortNotes\RB_Net_Monitor\LandingPrompt\CL_SubStep_Verify.md`
2. ELP derives: `lp_dir = Q:\PortNotes\RB_Net_Monitor\LandingPrompt\`
3. ELP reads: `Q:\PortNotes\RB_Net_Monitor\LandingPrompt\README.md`
4. ELP parses front-matter: `source_root = Q:\1.55.0_Net_Monitor\Source`, `pst_root = Q:\PortNotes\RB_Net_Monitor`
5. ELP reads LP sequence from `## LP 序列`
6. ELP reads coding standards from `## Coding Standards`
7. ELP executes CL_SubStep_Verify.md following those standards
8. ELP writes to `Q:\PortNotes\RB_Net_Monitor\status\status.yaml`

Confirm this matches the design spec's expected behavior.

- [ ] **Step 3: Commit plan document**

```bash
cd Q:\Plan_Viewer
git add "Docs\plans\2026-05-18-execute-landingprompt-v3-project-agnostic.md"
git commit -m "plan: Execute-LandingPrompt v3 project-agnostic implementation"
```
