# Plan Viewer

Project State Tracker 的交互式可视化 Dashboard 工具。

## 概述

为 AI agent 驱动开发提供个人工作台，将 `status.yaml` 中的项目状态数据渲染为一个可交互的单文件 HTML Dashboard。支持：

- **DAG 依赖图** — 所有 artifact 之间的依赖关系，节点颜色标注状态
- **泳道图** — 按 Phase 分列，展示 Plan → LandingPrompt → TestPrompt 层级
- **状态机视图** — 9-state 流转规则 + 当前分布统计
- **Hotspot 面板** — needs_update / blocked 的 artifact + 建议操作
- **详情侧边栏** — 点击节点查看依赖、change_events、关联 Gate
- **Markdown 预览** — 直接在 Dashboard 内阅读 artifact 对应的文件内容
- **类型 Filter** — 按 Plan / LandingPrompt / TestPrompt / Research / Decision 筛选

## 演示效果

### 桌面版 (Tauri)

![桌面版执行效果](Docs/PNG/Plan_Viewer_Exe.gif)

### 网页版 (Browser Dashboard)

![网页版执行效果](Docs/PNG/Website_Exe.gif)

## 技术栈

- **生成方式**：Python 脚本读取 status.yaml → 注入 JSON 数据 → 输出单文件 HTML
- **前端**：React 18 + Babel standalone（CDN，浏览器端 JSX 编译）
- **图表**：Mermaid.js（DAG + 状态机）
- **Markdown**：marked.js
- **主题**：暗色/亮色，跟随系统或手动切换

## 使用方式

```bash
python src/render_dashboard.py --project Q:\PortNotes\UE_Iris
```

输出 `<project>/views/dashboard.html`，浏览器打开即可。

## 项目结构

```
Q:\Plan_Viewer\
├── README.md                 # 本文件
├── Docs/                     # 设计文档（project-state-tracker 标准结构）
│   ├── AGENTS.md
│   ├── research/             # 调研文档
│   ├── decisions/            # 决策记录
│   ├── plan/                 # 设计文档
│   ├── status/               # 状态管理
│   ├── tools/                # 状态管理脚本
│   └── views/                # 生成的视图
└── src/                      # Dashboard 源码
    ├── render_dashboard.py   # 生成脚本
    └── dashboard_template.html  # HTML 模板
```

## 设计文档

- 调研：`Docs/research/R-001-Dashboard-Visualization-Research.md`
- 决策：`Docs/decisions/D-001-single-html-react-cdn.yaml`
- 设计：`Docs/plan/2026-05-14-dashboard-visualization-design.md`

## 依赖

- Python 3.8+（PyYAML）
- 浏览器：Chrome / Edge 最新版本
- 网络：首次打开需要加载 CDN 资源（之后浏览器缓存）


## 从源码构建

### Python 环境

```bash
pip install -r requirements.txt
```

### 启动 Dashboard 服务

双击 `serve.bat` 或手动运行：

```bash
python dashboard_server.py
```

浏览器会自动打开 `http://localhost:8000/dashboard.html`。

### 构建桌面版（可选）

前置条件：
- [Node.js](https://nodejs.org/) v18+
- [Rust](https://rustup.rs/) 工具链
- npm

运行：

```bash
build.bat
```

输出的 `.exe` 文件位于 `plan-viewer-desktop\src-tauri\target\release\`。

## Project State Tracker — Prompt 参考手册

> 文件位置：`Prompt_project-state-tracker_生成项目使用的Workflow_State.md`

### 功能概述

Project State Tracker 是一个 AI Agent Skill Prompt，用于管理 Research → Decision → Plan → LandingPrompt → TestPrompt 工件的完整生命周期。它通过一个中心化的 `status.yaml` 数据库追踪所有工件的状态、依赖关系、前置条件和交接上下文，并在检测到变更时自动传播影响。

核心能力是 **INFERENCE**（推理）：读取文档内容，自动提取 artifact ID、依赖关系、前置条件和 handoff context——而不仅仅是把文件归档到目录。

### 运行模式

Prompt 根据项目状态自动选择模式：

| 条件 | 模式 | 行为 |
|------|------|------|
| 无 status.yaml，无文档 | `INIT_EMPTY` | 创建目录结构、空 status.yaml、工具模板 |
| 无 status.yaml，有文档 | `INIT_FROM_DOCS` | 扫描所有文档，运行完整推理，生成 status.yaml |
| 有 status.yaml，有文档 | `AUDIT` | 扫描变更，传播影响，验证质量，输出报告 |
| 有 status.yaml，无文档 | `INIT_EMPTY` | 视 status.yaml 为孤立文件，重新初始化 |

#### User-Intent Routing Table

| 用户说的话 | 触发模式 | 范围 |
|-----------|---------|------|
| "init" / "initialize this project" | INIT_* | 完整初始化 + 推理 |
| "audit" / "check status" / "full check" | AUDIT | scan → propagate → validate → report |
| "research updated" / "I changed R-*" | AUDIT | 仅 Research 范围的传播 |
| "can LP-* execute" / "check landing prompt" | AUDIT | 仅前置条件评估 |
| "regenerate views" | — | 从 status.yaml 重新渲染视图，不改状态 |
| "improve quality" / "check completeness" | AUDIT | 运行质量检查清单，报告缺口 |
| "infer dependencies" / "rebuild graph" | AUDIT | 对所有已注册文档重新运行推理引擎 |
| "create handoff for LP-*" | AUDIT | 为指定 LP 生成 HandoffContext |
| "check handoff status" | AUDIT | 渲染 handoff_view，报告过期/无效项 |

### Execution Pipeline

```
Step 0: PRE-CHECK (Dirty Guard)
  └─ dirty_check.py → clean? → skip to Step 1
                     → dirty? → scan → propagate → apply (auto) → render → Step 1

Step 1: Detect project state → select mode
Step 2: Scaffold missing directories (INIT only)
Step 3: Run Inference Engine (Phase 1-5)
Step 4: Execute propagation rules (AUDIT)
Step 5: Write approved_transitions.json → apply_changes.py
Step 6: render_status.py → regenerate views/ + AGENTS.md
Step 7: Emit structured report
```

#### Step 0: PRE-CHECK (Dirty Guard)

每次 Skill 被调用时，先运行 `dirty_check.py` 进行两级脏检测：

1. **Level 1 — mtime 快筛**：对比 `status/.cache/file_snapshot.json` 中记录的文件修改时间
2. **Level 2 — hash 确认**：仅对 mtime 变化的文件计算 SHA-256，排除"只是 touch 但内容未变"的假阳性

如果检测到脏文件，自动执行 scan → propagate → apply（仅 `requires_agent_review: false` 的候选项）→ render，确保 Agent 看到的状态始终是最新的。

### Inference Engine

推理引擎分 5 个阶段，优先级：Smart inference > Dependency completeness > Gate coverage。

#### Phase 1: Document Scanning & ID Extraction

扫描 `research/`、`decisions/`、`plan/`、`prompts/landing/`、`prompts/test/` 下的文件，提取：

- **ID**：从文件名模式（`R-001-*.md`）、YAML front-matter、H1 标题、或 fallback slugify
- **Title**：从 YAML `title:` 字段、H1 标题、或文件名
- **Type**：从所在目录推断（research → research_finding, plan → plan, etc.）

#### Phase 2: Dependency Inference from Content

读取文档内容，通过 4 步提取依赖关系：

| 步骤 | 方法 | 示例 |
|------|------|------|
| A. Reference Scan | 正则匹配已知 ID 模式 | `R-\d{3}`, `D-\d{3}`, `LP-\d{3}` |
| B. Semantic Markers | 关键词 + ID 组合 | "based on R-001" → depends_on |
| C. Structural Inference | 目录层级推断 | Decision 提到 R-* → based_on |
| D. Confidence Scoring | high/medium/low 分级 | high → 自动注册, low → 仅建议 |

#### Phase 3: Preconditions & Gates 自动生成

为每个 LandingPrompt 自动生成前置条件：
- 上游 Plan 必须 approved/ready
- 关联 TestPrompt 必须 ready
- 消费的 HandoffContext 必须 available 且 version ≥ 1

#### Phase 4: Handoff Context Inference

为被下游引用的 LP 自动建议 HandoffContext：
- 提取 facts（LP 文件中 Summary/Output/Results 下的要点）
- 提取 constraints（含 "must not"/"required"/"constraint" 的句子）
- 标记 `requires_agent_review: true`

#### Phase 5: Quality Validation Checklist

| # | 检查项 | 严重度 |
|---|--------|--------|
| Q1 | 无孤立 artifact（每个都有 depends_on 或是根节点） | warning |
| Q2 | 无断裂引用（depends_on 中的 ID 都存在） | error |
| Q3 | 无循环依赖（拓扑排序成功） | error |
| Q4 | 每个 LP 至少有一个 precondition | warning |
| Q5 | LP 的 consumes_handoffs 都有对应 PC | error |
| Q6 | 每个 TP 至少引用一个 LP | warning |
| Q7 | 无 artifact 在上游 needs_update 时仍为 ready | error |
| Q8 | Handoff chain 连通性：每个 HC 有 producer + ≥1 consumer | warning |
| Q9 | 所有 gate 至少有一个 check | warning |
| Q10 | 无重复 artifact ID | error |

### Propagation Rules

变更传播遵循 6 条规则，严格限制在依赖图范围内：

```
Rule 1: Research changed    → dependent Decisions → dependent Plans → needs_update
Rule 2: Plan changed        → dependent LPs → needs_update; dependent TPs → needs_update
Rule 3: LP changed          → dependent TPs → needs_update; LP's produced HCs → stale
Rule 4: TP becomes ready    → re-evaluate LP preconditions referencing this TP
Rule 5: Blocker open/close  → recompute affected artifacts + gates
Rule 6: HC stale/invalidated → consumers with ready/approved → needs_update | blocked
```

### State Machine (9 states)

```
draft → reviewed → approved → ready
ready → needs_update | blocked
needs_update → draft | reviewed
blocked → draft | reviewed
Any non-terminal → invalidated | deprecated | archived
```

所有状态：`draft`, `reviewed`, `approved`, `ready`, `blocked`, `needs_update`, `invalidated`, `deprecated`, `archived`

### 工具链

| 脚本 | 职责 |
|------|------|
| `tools/dirty_check.py` | 前置守卫：两级 mtime+hash 脏检测，输出 clean/dirty JSON |
| `tools/scan_changes.py` | 扫描 tracked 目录，通过 git status 或 hash 对比检测变更文件 |
| `tools/propagate.py` | 读取 changed_files.json，沿依赖图生成 candidate_transitions.json |
| `tools/validate_status.py` | 验证 status.yaml 结构是否符合 schema.yaml |
| `tools/apply_changes.py` | 读取 approved_transitions.json，原子写入 status.yaml |
| `tools/render_status.py` | 从 status.yaml 生成 views/*.md + AGENTS.md |

所有工具通过 `--project <path>` 参数指定项目根目录。

### Directory Layout

```
<project>/
  research/           R-xxx-*.md          （调研事实与证据）
  decisions/          D-xxx-*.yaml        （基于调研的决策）
  plan/               P-xxx-*.md          （执行计划与设计）
  prompts/landing/    LP-xxx-*.md         （实施 Prompt）
  prompts/test/       TP-xxx-*.md         （验证 Prompt）
  status/
    status.yaml                           （权威状态源——仅 apply_changes.py 写入）
    schema.yaml                           （结构约束，供 validate_status.py 使用）
    .cache/                               （中间分析产物：changed_files / candidates / approved）
  tools/                                  （Python 状态管理脚本）
  views/                                  （只读派生视图，每次运行重新生成）
  AGENTS.md                               （AI agent 单页索引，每次运行重新生成）
```

### 使用方式

#### 作为 AI Agent Skill 使用

将 Prompt 文件内容作为 System Prompt 或 Skill 注入 AI Agent，然后用自然语言指令触发：

```
# 初始化新项目
"init this project"

# 审计当前状态
"audit" / "full check"

# 告知某个文件已更新
"research updated — I changed R-001"

# 检查 LP 是否可执行
"can LP-001 execute?"

# 仅刷新视图
"regenerate views"

# 重建依赖图
"rebuild graph"
```

#### 手动调用工具链

```bash
# 脏检测（快速判断是否有变更）
python tools/dirty_check.py --project .

# 完整扫描
python tools/scan_changes.py --project .

# 传播变更
python tools/propagate.py --project .

# 验证结构
python tools/validate_status.py --project .

# 应用已批准的状态转换
python tools/apply_changes.py --project .

# 重新生成视图
python tools/render_status.py --project .
```

### status.yaml Canonical Fields

```yaml
meta: {project_name, created, last_updated, total_artifacts, total_research, total_blockers, hotspots}
artifacts: [{id, type, path, status, depends_on, produces_handoffs?, consumes_handoffs?}]
research_findings: [{id, title, path, status, evidence?, affects?, invalidates?}]
decisions: [{id, title, path, status, based_on, rejects?, affects?}]
assumptions: [{id, statement, status, source?}]
evidence: [{label, source, confidence, supports}]
blockers: [{id, title, severity, status, source, blocks}]
gates: [{id, name, status, required, checks}]
preconditions: [{id, target, requires, status}]
handoff_contexts: [{id, producer, version, status, facts, results, constraints, consumed_by, consumed_status}]
change_events: [{id, time, source, event_type, affected, transitions}]
snapshots: {git_baseline, file_hashes}
```

### Hard Constraints

**DO:**
- 更新 status.yaml 时保留所有用户编写的字段
- 每次状态变更都记录到 change_events（含时间戳、来源、原因）
- 对 medium/low confidence 的推理标记 `requires_agent_review: true`
- 为每个 LP 自动生成 preconditions
- 每次推理后运行 quality checklist
- 优先使用 Python 工具执行机械性工作
- 使用顺序 ID（CE-001, PC-001, G-001, HC-001...）

**DON'T:**
- 把 research 正文复制到 status.yaml（只存 ID、路径、一行摘要）
- 在 preconditions 未全部通过时将 artifact 设为 ready
- 覆盖或删除用户编写的文件（research/, decisions/, plan/, prompts/）
- 传播超出依赖图的范围
- 把 views/ 当作数据源（它是派生输出）
- 未经确认就自动 bump handoff version
- 直接编辑 status.yaml（必须通过 approved_transitions.json → apply_changes.py）
- 注册 confidence=low 的 artifact 而不经过 agent review

### Session Memory

跨调用持久化推理结果到 `status/.cache/session_memory.json`，避免重复工作：

- 跳过 hash 未变的文件
- 重新展示未被批准/拒绝的 pending_suggestions
- 用上次的 quality_score 优先排序检查项

在 INIT 模式或用户说 "full check" 时删除此文件。

### Output Format

每次调用结束时输出结构化报告：

```markdown
## Processing Summary
## Changes Detected
## State Transitions
## Quality Issues
## Handoff Status
## Blocked Items
## Recommended Next Actions (max 5)
```

---

## 许可证

MIT License - 详见 [LICENSE](LICENSE) 文件。
