# PST §11 REVIEW Mode — 落地质量审计

**Date:** 2026-05-21
**Scope:** project-state-tracker Skill (`C:\Users\chenshajie\.kiro\skills\project-state-tracker\`)
**Status:** Draft

---

## 目标

为 project-state-tracker 新增 §11 REVIEW Mode，用于审计已落地（`ready` 状态）的 LandingPrompt 实现质量。核心逻辑：从 ready LP 倒推找到对应的 Plan 和 Decision，再从需求层面（AC + 架构选型）对实际代码进行事实倒推审计。

## 动机

当前 PST 的 §4 AUDIT 关注的是**状态一致性**（文件变更 → 状态转换是否正确），但不关注**实现质量**（LP 标记 ready 后，代码是否真正满足了 Plan 的 Acceptance Criteria 和架构设计意图）。

ELP 执行时的 Dependency Gate 只检查前置条件是否满足，不回溯验证已完成的工作质量。Result 文件记录了执行过程，但没有机制将其与 Plan AC 做系统性比对。

§11 REVIEW 填补这个空白：提供一个只读的、基于文档推理的质量审计机制。

## 核心约束

- **只读操作** — 不修改 status.yaml，不触发 propagate / apply_changes
- **仅审计 ready LP** — 聚焦已完成的落地质量
- **基于文档推理** — 读 Plan AC + Result 文件 + 代码快照，用 agent 推理判定
- **不运行测试** — 不执行 TP，不跑任何代码

---

## 架构

```
用户触发 "review" / "审计质量" / "quality check"
        │
        ▼
§2 Mode Detection → §11 REVIEW
        │
        ▼
┌─────────────────────────────────┐
│  review_quality.py --project <p> │  ← 新增 Python 工具
│  输出: review_context.json       │
│  (ready LP 列表 + Plan AC +     │
│   Decision 架构选型 +            │
│   Result 路径 + 代码文件列表)    │
└─────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────┐
│  Phase 1: AC 满足度审计          │
│  - 逐 AC 读 Result + 代码       │
│  - 判定: pass / partial / fail   │
└─────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────┐
│  Phase 2: 架构符合度审计         │
│  - 读 Plan 架构描述              │
│  - 读 Decision 架构选型/约束     │
│  - 对比实际代码结构              │
└─────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────┐
│  Phase 3: 综合判定               │
│  - AC 满足度 + 架构符合度        │
│  - 整体质量等级 + 改进建议       │
└─────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────┐
│  输出                            │
│  - 会话摘要                      │
│  - views/review_report.md        │
└─────────────────────────────────┘
```

---

## review_quality.py 工具设计

### 接口

```bash
python tools/review_quality.py --project <pst_root>
```

### 输出

写入 `status/.cache/review_context.json`：

```json
{
  "generated_at": "2026-05-21T10:00:00Z",
  "project_name": "Plan_Viewer",
  "ready_lps": [
    {
      "id": "LP-001",
      "title": "初始化核心模块",
      "path": "prompts/landing/LP-001-init-core.md",
      "plan_id": "Plan.topic",
      "plan_path": "plan/2026-05-14-topic-design.md",
      "decision_id": "D-001",
      "decision_path": "decisions/D-001-architecture.yaml",
      "acceptance_criteria": [
        {
          "id": "AC-1",
          "statement": "THE system SHALL provide...",
          "validates_property": "P-1"
        }
      ],
      "result_files": [
        "Result/LP-001-init-core-20260520-143022.md"
      ],
      "modified_files": ["src/core.py", "src/utils.py"]
    }
  ],
  "architecture": {
    "decision_summary": "选择方案 1: 单文件 HTML + React CDN",
    "plan_architecture_section": "## Architecture\n...",
    "key_constraints": [
      "单文件部署",
      "CDN 依赖不超过 3 个",
      "无构建步骤"
    ]
  }
}
```

### 工具内部逻辑

1. **读取 status.yaml** — 加载 artifacts、decisions、handoff_contexts
2. **筛选 ready LP** — `artifacts WHERE type == "landing_prompt" AND status == "ready"`
3. **倒推 Plan** — 通过 LP 的 `depends_on[]` 找到 `type == "plan"` 的 artifact（若多个 Plan，取 depends_on 列表中第一个匹配的；若无直接 Plan 依赖，BFS 向上查找，max depth 3）
4. **倒推 Decision** — 通过 Plan 的 `depends_on[]` 找到 `type == "decision"` 的 artifact（同样取第一个匹配；若 Plan 无 Decision 依赖，跳过 Decision 相关审计）
5. **提取 AC** — 读取 Decision YAML 文件，解析 `acceptance_criteria` 段落；若 Decision 无 AC，则从 Plan 文件中解析 `## Acceptance Criteria` 或 `## Properties` section
6. **匹配 Result 文件** — 在 `<pst_root>/Result/` 目录中查找文件名以 LP artifact ID 开头的文件，取最新（按时间戳排序）
7. **提取修改文件列表** — 从 Result 文件中解析 `- 修改文件:` 行
8. **提取架构信息** — 从 Plan 文件中提取 `## Architecture` / `## 架构` section；从 Decision 文件中提取选型摘要和约束

### 工具不做的事

- 不读代码文件内容（agent 负责）
- 不做任何质量判定（agent 负责）
- 不修改 status.yaml
- 不触发任何状态转换

### 错误处理

| 场景 | 行为 |
|------|------|
| 无 ready LP | 输出空 `ready_lps: []`，agent 报告"无可审计对象" |
| LP 无法倒推到 Plan | `plan_id: null, plan_path: null`，agent 标记为"无法审计" |
| Result 目录不存在 | `result_files: []`，agent 基于代码快照判定 |
| Decision 文件缺失 | `decision_id: null`，Phase 2 跳过 Decision 约束检查 |
| AC 解析失败 | `acceptance_criteria: []`，agent 标记为"AC 不可解析" |

---

## Agent 判定协议

### Phase 1 — AC 满足度

对 `review_context.json` 中每个 ready LP 的每个 AC：

1. 读对应 Result 文件中的相关段落（`## confirmed` + `## 当前 Prompt 执行结果`）
2. 读 `modified_files` 中的代码快照（关键函数签名、类定义、核心逻辑）
3. 判定：
   - `pass` — Result 和代码明确满足 AC 的 SHALL 语句
   - `partial` — 部分满足，有遗漏或边界情况未覆盖
   - `fail` — 未实现或实现与 AC 矛盾
4. 给出一句话理由（引用具体代码位置或 Result 段落）

**Token 优化：** 当 `modified_files` 超过 5 个时，优先读与 AC 语义最相关的文件（基于文件名和 AC 关键词匹配）。

### Phase 2 — 架构符合度

1. 读 `architecture.plan_architecture_section`（Plan 的架构描述）
2. 读 `architecture.decision_summary` + `architecture.key_constraints`（Decision 的选型和约束）
3. 读实际代码的文件结构（目录树 + 关键模块的 import 关系）
4. 判定维度：
   - **模块边界** — 实际文件/类划分是否与设计一致
   - **数据流** — 数据传递方向是否符合设计
   - **职责分离** — 每个模块是否只做设计中声明的事
   - **约束遵循** — Decision 中的约束条件是否被违反
   - **拒绝方案检查** — Decision 中被拒绝的方案是否意外引入
5. 每个维度给出：
   - `conformant` — 完全符合设计意图
   - `deviation` — 有偏离但不影响核心设计
   - `violation` — 违反设计意图或约束

### Phase 3 — 综合判定

| 等级 | 条件 |
|------|------|
| A (优秀) | 所有 AC pass + 架构全部 conformant |
| B (良好) | ≥80% AC pass，无 fail + 架构无 violation |
| C (合格) | ≥60% AC pass + 架构无 violation |
| D (不合格) | <60% AC pass 或 架构存在 violation |

综合判定还需列出：
- **关键风险** — 最可能导致问题的 partial/fail AC 或 deviation
- **改进建议** — 具体可操作的修复方向（max 5 条）

---

## 报告模板

### views/review_report.md

```markdown
# Quality Review Report

**Project:** <project_name>
**Date:** <ISO timestamp>
**Scope:** <N> ready LPs reviewed
**Overall Grade:** <A/B/C/D>

---

## Summary

| Metric | Value |
|--------|-------|
| Ready LPs Reviewed | <N> |
| AC Total | <N> |
| AC Pass | <N> (<percent>%) |
| AC Partial | <N> (<percent>%) |
| AC Fail | <N> (<percent>%) |
| Architecture Conformance | <conformant/deviation/violation> |

---

## AC Satisfaction Detail

### LP-001: <title>
**Plan:** <plan_id> | **Result:** <result_file>

| AC | Statement | Verdict | Reason |
|----|-----------|---------|--------|
| AC-1 | THE system SHALL... | pass | 代码中 xxx 函数实现了... |
| AC-2 | WHEN user... | partial | 主流程实现，但边界情况... |

### LP-002: <title>
...

---

## Architecture Conformance

### Design Intent
<Plan 架构描述摘要>

### Decision Constraints
- 选型: <decision_summary>
- 约束: <key_constraints 列表>
- 拒绝方案: <rejects 列表>

### Findings

| Dimension | Verdict | Detail |
|-----------|---------|--------|
| 模块边界 | conformant | 文件划分与设计一致 |
| 数据流 | deviation | xxx 模块直接调用了 yyy，设计中应通过 zzz |
| 职责分离 | conformant | 各模块职责清晰 |
| 约束遵循 | conformant | 单文件部署、CDN 数量均满足 |
| 拒绝方案 | conformant | 未引入被拒绝的方案 |

---

## Risks & Recommendations

1. [HIGH] AC-2 partial: 边界情况未覆盖 → 建议补充 xxx 逻辑
2. [MEDIUM] 数据流 deviation: xxx 直接调用 yyy → 建议引入中间层
3. ...

---

## Audit Trail

- Tool version: review_quality.py v1.0
- Context file: status/.cache/review_context.json
- Status.yaml snapshot: <last_updated from meta>
```

### 会话摘要格式

```markdown
## Review Summary

Overall Grade: **B (良好)**

AC Pass Rate: 8/10 (80%)
Architecture: conformant (1 minor deviation)

Key Findings:
- ✓ 8 AC fully satisfied
- △ 2 AC partially satisfied (边界情况)
- ✓ 架构整体符合设计意图

Top Recommendations:
1. LP-002 AC-3: 补充空值处理逻辑
2. 数据流: 考虑将 xxx 调用改为通过事件总线

Full report: views/review_report.md
```

---

## §2 路由扩展

在 SKILL.md §2 User-intent routing 表中新增：

| Pattern | Route | Scope |
|---------|-------|-------|
| "review" / "审计质量" / "quality check" / "review landing quality" / "review quality" | §11 | Ready LP quality audit |

---

## §11 REVIEW Mode 流程定义

### 前置条件

- `status/status.yaml` 存在
- `tools/review_quality.py` 存在
- 至少一个 `status == "ready"` 的 LP artifact

### 步骤

| Step | Action | Input | Output | Fail |
|------|--------|-------|--------|------|
| 1 | `review_quality.py --project <p>` | project path | `review_context.json` | 无 ready LP → 报告"无可审计对象"并退出 |
| 2 | Agent 读 review_context.json | JSON | 审计计划 | — |
| 3 | Phase 1: 逐 AC 判定 | Result + 代码 | AC verdicts | 单个 AC 不可判定 → 标记 `inconclusive` |
| 4 | Phase 2: 架构符合度 | Plan + Decision + 代码结构 | Architecture verdicts | Decision 缺失 → 跳过约束检查 |
| 5 | Phase 3: 综合判定 | Phase 1 + 2 结果 | Grade + Recommendations | — |
| 6 | 写入 `views/review_report.md` | 全部结果 | 持久化报告 | 写入失败 → 仅输出会话摘要 |
| 7 | 输出会话摘要 | 全部结果 | 格式化摘要 | — |

### Token 预算控制

| LP 数量 | 策略 |
|---------|------|
| 1-3 | 完整读取所有 Result + 所有 modified_files |
| 4-8 | 每个 LP 读最新 Result + 最相关的 3 个代码文件 |
| >8 | 分批处理（每批 5 个 LP），中间结果缓存到 `status/.cache/` |

---

## 与现有系统的交互

| 组件 | 交互方式 |
|------|----------|
| status.yaml | 只读 — 读取 artifacts、decisions 信息 |
| Result/ | 只读 — 读取 ELP 执行结果 |
| Plan 文件 | 只读 — 提取 AC 和架构描述 |
| Decision 文件 | 只读 — 提取选型和约束 |
| 源代码 | 只读 — 读取快照用于判定 |
| views/ | 写入 — review_report.md |
| status/.cache/ | 写入 — review_context.json |
| scan_changes.py | 无影响 — views/ 和 status/ 已在 IGNORE 列表 |
| render_status.py | 无影响 — 不涉及 review_report.md |
| propagate.py | 不触发 |
| apply_changes.py | 不触发 |

---

## 改动文件清单

| 文件 | 改动 |
|------|------|
| `SKILL.md` §2 | 路由表新增 "review" 模式 |
| `SKILL.md` 新增 §11 | REVIEW Mode 完整定义 |
| `tools/review_quality.py` | 新增工具文件 |
| `companion.md` | 无改动（§11 不依赖 companion 规则） |

## 不改动的部分

- §4 AUDIT 流程
- status.yaml schema
- apply_changes.py / propagate.py / scan_changes.py / render_status.py
- Execute-LandingPrompt Skill
- project-state-spec Skill
- Handoff Context 管理逻辑

---

## 幂等性

多次运行 review：
- `review_context.json` 每次覆盖（最新快照）
- `review_report.md` 每次覆盖（最新审计结果）
- 不产生累积副作用

## 未来扩展点

- 支持指定单个 LP 审计（`review LP-001`）
- 支持审计后可选降级（需要用户确认 + apply_changes）
- 支持与 TP 执行结果交叉验证
- 支持历史 review 报告对比（时间序列质量趋势）
