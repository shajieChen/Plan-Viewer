你需要生成一个通用项目管理 Skill，名称建议为：

Project Research-Plan-Landing-Test State Skill

这个 Skill 的目标是帮助任何项目在预研阶段或迭代阶段管理以下四类资产：

1. Research
2. Plan
3. LandingPrompt
4. TestPrompt

并通过一个 status.yaml 作为项目状态数据库，维护 blocker、gate、PR/SP 状态、evidence labels、precondition 依赖图、artifact 状态、invalidated 状态和连锁影响关系。

这个 Skill 必须适用于所有项目，而不是只针对某个具体项目。

---

# 一、核心设计目标

生成的 Skill 必须解决以下问题：

当 Research 更新后，自动检测哪些 Plan 可能失效；
当 Plan 变化后，自动判断哪些 LandingPrompt 被阻塞或需要更新；
当 LandingPrompt 变化后，自动判断哪些 TestPrompt 需要更新；
当 TestPrompt 不完整时，自动阻止对应 LandingPrompt 进入 ready 状态；
所有状态必须集中记录在 status/status.yaml 中；
Research 只记录事实，不重复项目状态；
Plan 只记录执行方案，不混入大段调研原文；
LandingPrompt 只记录落地执行用 Prompt；
TestPrompt 只记录验证、回归、验收用 Prompt；
status.yaml 作为唯一状态数据库，负责状态、依赖、门禁和连锁反应。

---

# 二、Skill 的行为模式

当用户调用这个 Skill 时，Skill 必须先判断当前项目目录中是否存在以下结构：

research/
decisions/
plan/
prompts/landing/
prompts/test/
status/
tools/
views/

如果不存在，则将本次调用视为项目初始化，并创建缺失目录和配套 README。

如果部分存在，则只补齐缺失部分，不覆盖已有内容。

如果 status/status.yaml 不存在，则创建初始 status.yaml。

如果 status/schema.yaml 不存在，则创建 schema.yaml，用于描述 status.yaml 的结构约束。

如果 tools/render_status.py 不存在，则创建 render_status.py，用于根据 status.yaml 生成视图。

如果 tools/validate_status.py 不存在，则创建 validate_status.py，用于校验 status.yaml 基础结构。

如果 views/ 不存在或为空，则生成初始视图文件。

---

# 三、初始化时必须创建的目录结构

Skill 初始化项目时，需要创建如下结构：

project_root/
  research/
    README.md

  decisions/
    README.md

  plan/
    README.md

  prompts/
    README.md
    landing/
      README.md
    test/
      README.md

  status/
    README.md
    status.yaml
    schema.yaml

  tools/
    README.md
    render_status.py
    validate_status.py

  views/
    README.md
    status_report.md
    blocker_view.md
    landing_prompt_checklist.md
    dependency_graph.md
    change_impact_report.md

---

# 四、各目录 README 内容要求

每个 README 必须说明该目录的职责、禁止事项、推荐文件命名方式和与 status.yaml 的关系。

## research/README.md

必须表达以下规则：

Research 层只记录事实、发现、证据和调研结论。
Research 不记录当前状态。
Research 不直接决定 Plan、LandingPrompt 或 TestPrompt 是否 ready。
Research 中的每个重要发现都应该有 ID，例如 R-001。
每个重要证据都应该有 evidence label，例如 E-001。
如果 Research 推翻了旧假设，需要在内容中声明 invalidates。
如果 Research 影响某些模块，需要声明 affects。

推荐文件命名：

R-001-platform-limit.md
R-002-rendering-pipeline.md
R-003-ai-agent-capability.md

## decisions/README.md

必须表达以下规则：

Decision 层记录基于 Research 做出的工程选择。
Decision 是 Research 和 Plan 之间的桥梁。
Decision 不记录完整调研过程，只记录采用了什么方案、为什么采用、拒绝了哪些方案、依赖哪些 Research。
每个 Decision 必须有 ID，例如 D-001。

推荐文件命名：

D-001-rendering-strategy.yaml
D-002-prompt-generation-policy.yaml

## plan/README.md

必须表达以下规则：

Plan 层记录执行方案。
Plan 必须基于 Decision 或明确的 Research。
Plan 不应该复制 Research 的长文本。
Plan 可以被 Research 或 Decision 变更 invalidated。
每个 Plan artifact 需要在 status.yaml 中登记。

推荐文件命名：

plan.md
P-001-rendering-pipeline.md
P-002-implementation-milestone.md

## prompts/landing/README.md

必须表达以下规则：

LandingPrompt 是用于实际落地执行的 Prompt。
LandingPrompt 必须有 preconditions。
LandingPrompt 不能在依赖 Plan 未 approved、Gate 未 passed、TestPrompt 未 ready 时进入 ready 状态。
LandingPrompt 更新后，必须检查对应 TestPrompt 是否需要更新。

推荐文件命名：

LP-001-scene-implementation.md
LP-002-ui-generation.md

## prompts/test/README.md

必须表达以下规则：

TestPrompt 是用于验证、回归、验收的 Prompt。
TestPrompt 应该覆盖对应 LandingPrompt 的关键行为。
当 Plan 或 LandingPrompt 更新后，TestPrompt 可能需要进入 needs_update 状态。
TestPrompt ready 是 LandingPrompt ready 的前置条件之一。

推荐文件命名：

TP-001-scene-acceptance.md
TP-002-regression-check.md

## status/README.md

必须表达以下规则：

status.yaml 是项目状态数据库。
status.yaml 只记录状态、依赖、门禁、阻塞、证据引用和影响关系。
status.yaml 不复制 Research 正文。
status.yaml 中的状态是 Skill 判断连锁反应的基础。
所有 artifact 都应该在 status.yaml 中登记。

## tools/README.md

必须表达以下规则：

tools/ 放置状态校验、视图生成和依赖分析脚本。
工具脚本不能无提示覆盖用户手写内容。
render_status.py 负责根据 status.yaml 生成 views/ 下的视图。
validate_status.py 负责校验 status.yaml 是否符合基础结构。

## views/README.md

必须表达以下规则：

views/ 是由 status.yaml 派生出的只读视图目录。
用户可以阅读 views/，但不应该把 views/ 当作状态源。
如果 views/ 内容过期，应重新运行 render_status.py 或重新调用 Skill 生成视图。

---

# 五、status.yaml 初始结构

初始化时生成 status/status.yaml，结构必须包含以下部分：

project:
  name: unknown_project
  phase: pre_research
  version: 0.1.0

artifacts: []

research_findings: []

evidence: []

assumptions: []

decisions: []

blockers: []

gates: []

preconditions: []

dependencies: []

change_events: []

snapshots:
  enabled: true
  file_hashes: {}

rules:
  research_is_fact_only: true
  status_is_single_source_of_truth: true
  landing_requires_test_ready: true
  plan_invalidates_landing: true
  landing_invalidates_test: true

---

# 六、status.yaml 需要支持的 artifact 状态

Skill 必须支持以下 artifact 状态：

draft
reviewed
approved
ready
blocked
needs_update
invalidated
deprecated
archived

其中：

draft 表示草稿；
reviewed 表示已审阅；
approved 表示方案已批准；
ready 表示可以进入下一步；
blocked 表示被 blocker 或 gate 阻塞；
needs_update 表示依赖变化后需要更新；
invalidated 表示被新的 Research、Decision 或 Plan 变化推翻；
deprecated 表示不推荐继续使用；
archived 表示归档，仅保留历史记录。

---

# 七、status.yaml 中 artifact 推荐结构

Skill 生成或维护 artifact 时应使用如下结构：

artifacts:
  - id: Plan.rendering_pipeline
    type: plan
    path: plan/P-001-rendering-pipeline.md
    status: draft
    depends_on:
      - D-001
    affected_by:
      - R-001
    blocks: []
    blocked_by: []
    invalidated_by: []
    last_checked: null

  - id: LandingPrompt.scene_implementation
    type: landing_prompt
    path: prompts/landing/LP-001-scene-implementation.md
    status: blocked
    depends_on:
      - Plan.rendering_pipeline
      - TestPrompt.scene_acceptance
    blocked_by:
      - G-001
    preconditions:
      - PC-001
      - PC-002
    invalidated_by: []
    last_checked: null

  - id: TestPrompt.scene_acceptance
    type: test_prompt
    path: prompts/test/TP-001-scene-acceptance.md
    status: draft
    depends_on:
      - LandingPrompt.scene_implementation
    blocked_by: []
    invalidated_by: []
    last_checked: null

---

# 八、Research finding 推荐结构

Research finding 应该支持如下字段：

research_findings:
  - id: R-001
    title: Target platform rendering limitation
    path: research/R-001-platform-limit.md
    type: finding
    confidence: high
    evidence:
      - E-001
    affects:
      - Plan.rendering_pipeline
      - LandingPrompt.scene_implementation
    invalidates:
      - A-001
    status_effect:
      - target: Plan.rendering_pipeline
        set_status: invalidated
        reason: Research finding R-001 invalidated assumption A-001

---

# 九、Evidence 推荐结构

evidence:
  - label: E-001
    source: research/R-001-platform-limit.md
    confidence: high
    supports:
      - R-001
    notes: Evidence summary only. Do not copy the full research text here.

---

# 十、Decision 推荐结构

decisions:
  - id: D-001
    title: Use simplified rendering pipeline
    path: decisions/D-001-rendering-strategy.yaml
    status: draft
    based_on:
      - R-001
      - E-001
    rejects:
      - full_rendering_pipeline
    affects:
      - Plan.rendering_pipeline

---

# 十一、Blocker 推荐结构

blockers:
  - id: B-001
    title: Target platform capability is not confirmed
    severity: high
    status: open
    source:
      - R-001
    blocks:
      - Plan.rendering_pipeline
      - LandingPrompt.scene_implementation
    resolution_required_for:
      - G-001

---

# 十二、Gate 推荐结构

gates:
  - id: G-001
    name: LandingPrompt executable gate
    status: failed
    required:
      - no_high_open_blockers
      - plan_is_approved
      - test_prompt_is_ready
    checks:
      - id: GC-001
        description: No high severity blocker remains open
        status: failed
      - id: GC-002
        description: Required Plan artifact is approved
        status: failed
      - id: GC-003
        description: Required TestPrompt is ready
        status: failed

---

# 十三、Precondition 推荐结构

preconditions:
  - id: PC-001
    target: LandingPrompt.scene_implementation
    requires:
      - artifact: Plan.rendering_pipeline
        field: status
        equals: approved
    status: failed

  - id: PC-002
    target: LandingPrompt.scene_implementation
    requires:
      - artifact: TestPrompt.scene_acceptance
        field: status
        equals: ready
    status: failed

---

# 十四、依赖传播规则

Skill 每次被调用时，都必须执行依赖传播分析。

## 规则 1：Research 更新

当 Research 文件新增或内容变化时：

1. 识别新增或变化的 Research finding。
2. 检查该 Research 是否声明 affects。
3. 检查该 Research 是否声明 invalidates。
4. 如果 invalidates 某个 assumption 或 decision，则对应 Plan 进入 invalidated 或 needs_update。
5. 如果 Plan 进入 invalidated，则依赖该 Plan 的 LandingPrompt 进入 blocked 或 needs_update。
6. 如果 LandingPrompt 进入 needs_update，则对应 TestPrompt 进入 needs_update。
7. 更新 change_events。
8. 更新 views/change_impact_report.md。

## 规则 2：Plan 更新

当 Plan 文件新增或变化时：

1. 检查对应 artifact 是否存在于 status.yaml。
2. 如果不存在，则登记为 draft。
3. 检查它依赖的 Decision 或 Research 是否有效。
4. 如果 Plan 状态从 draft 进入 approved，需要重新检查依赖它的 LandingPrompt preconditions。
5. 如果 Plan 变化导致 LandingPrompt 输入条件变化，则 LandingPrompt 进入 needs_update。
6. 对应 TestPrompt 进入 needs_update。

## 规则 3：LandingPrompt 更新

当 LandingPrompt 文件新增或变化时：

1. 检查是否有对应 artifact。
2. 检查是否有 preconditions。
3. 如果没有 preconditions，则创建默认 preconditions。
4. 检查依赖 Plan 是否 approved。
5. 检查对应 TestPrompt 是否 ready。
6. 如果任一条件不满足，LandingPrompt 不能进入 ready。
7. 如果 LandingPrompt 内容变化，对应 TestPrompt 进入 needs_update。

## 规则 4：TestPrompt 更新

当 TestPrompt 文件新增或变化时：

1. 检查是否覆盖对应 LandingPrompt。
2. 如果 TestPrompt 内容完整，可以建议用户将其标记为 ready。
3. 如果 TestPrompt ready，则重新计算 LandingPrompt 的 preconditions。
4. 如果所有 LandingPrompt preconditions 通过，则 LandingPrompt 可以进入 ready。

## 规则 5：Blocker 更新

当 blocker 打开：

1. 所有被它 blocks 的 artifact 进入 blocked。
2. 相关 gate 进入 failed。
3. LandingPrompt 不允许 ready。

当 blocker 关闭：

1. 重新计算受影响 artifact。
2. 重新计算相关 gate。
3. 不要直接把 blocked artifact 改成 ready，除非所有 preconditions 通过。

---

# 十五、文件变化检测机制

Skill 必须支持下列文件变化检测方式：

1. 如果项目是 Git 仓库，优先使用 Git diff 或 Git status 判断变化文件。
2. 如果不是 Git 仓库，则使用 status.yaml 中 snapshots.file_hashes 记录的文件 hash 判断变化。
3. 每次分析完成后，更新 snapshots.file_hashes。
4. 不能只依赖文件修改时间，因为复制旧文件可能导致误判。

---

# 十六、每次调用 Skill 的标准流程

每次调用 Skill 时，必须按以下流程执行：

1. 定位项目根目录。
2. 检查目录结构是否存在。
3. 如果缺失目录或 README，则初始化或补齐。
4. 读取 status/status.yaml。
5. 校验 status.yaml 基础结构。
6. 扫描 research、decisions、plan、prompts/landing、prompts/test。
7. 检测新增、修改、删除的文件。
8. 根据变化文件分类。
9. 执行依赖传播分析。
10. 更新 status.yaml 中的 artifact、blocker、gate、precondition、change_events、snapshots。
11. 生成 views/ 下的视图。
12. 输出本次调用的摘要，包括：
    - 初始化了哪些文件
    - 检测到哪些变化
    - 哪些 artifact 被 invalidated
    - 哪些 LandingPrompt 被 blocked
    - 哪些 TestPrompt 需要更新
    - 哪些 gate failed
    - 下一步建议

---

# 十七、views 输出要求

render_status.py 或 Skill 自身需要生成以下视图。

## views/status_report.md

必须包含：

项目名称
当前阶段
artifact 总览
各状态数量统计
open blocker 列表
failed gate 列表
ready LandingPrompt 列表
blocked LandingPrompt 列表
needs_update TestPrompt 列表
最近 change_events

## views/blocker_view.md

必须包含：

所有 open blocker
severity
source
blocked artifacts
resolution_required_for
建议处理顺序

## views/landing_prompt_checklist.md

必须包含：

每个 LandingPrompt 的状态
依赖 Plan
依赖 TestPrompt
precondition 检查结果
是否允许执行
如果不允许，列出原因

## views/dependency_graph.md

必须用 Mermaid 语法输出依赖图。

格式示例：

graph TD
  R001[R-001 Research Finding] --> D001[D-001 Decision]
  D001 --> P001[Plan.rendering_pipeline]
  P001 --> LP001[LandingPrompt.scene_implementation]
  LP001 --> TP001[TestPrompt.scene_acceptance]

## views/change_impact_report.md

必须包含：

本次变化文件
直接影响对象
间接影响对象
状态变化前后对比
建议下一步动作

---

# 十八、Skill 不应该做的事情

Skill 不应该把 Research 正文复制进 status.yaml。
Skill 不应该在没有证据的情况下自动把 artifact 标记为 approved。
Skill 不应该在 preconditions failed 时把 LandingPrompt 标记为 ready。
Skill 不应该让 LandingPrompt 直接修改 Plan。
Skill 不应该把 views/ 当作状态源。
Skill 不应该静默覆盖用户已有文件。
Skill 不应该删除用户文件。
Skill 不应该把所有文件都标记为需要更新，而应该基于依赖图做最小影响传播。

---

# 十九、状态更新原则

Skill 修改 status.yaml 时必须遵循：

1. 保留已有 ID。
2. 保留用户手写字段。
3. 只补充缺失字段。
4. 只更新可推导状态。
5. 所有状态变化必须写入 change_events。
6. change_events 必须包含时间、原因、来源、影响对象、旧状态、新状态。

change_events 推荐结构：

change_events:
  - id: CE-001
    time: auto_generated_timestamp
    source: research/R-001-platform-limit.md
    event_type: research_updated
    affected:
      - Plan.rendering_pipeline
      - LandingPrompt.scene_implementation
      - TestPrompt.scene_acceptance
    transitions:
      - artifact: Plan.rendering_pipeline
        from: approved
        to: invalidated
        reason: Research R-001 invalidated assumption A-001
      - artifact: LandingPrompt.scene_implementation
        from: ready
        to: blocked
        reason: Dependent Plan became invalidated
      - artifact: TestPrompt.scene_acceptance
        from: ready
        to: needs_update
        reason: LandingPrompt dependency changed

---

# 二十、用户交互方式

当用户说：

“初始化这个项目”

Skill 应该创建缺失目录、README、status.yaml、schema.yaml、tools 和 views。

当用户说：

“我更新了 Research，检查影响”

Skill 应该扫描 Research 变化，更新 status.yaml，并输出 Plan、LandingPrompt、TestPrompt 的受影响情况。

当用户说：

“检查 LandingPrompt 是否可以执行”

Skill 应该读取 status.yaml，检查对应 LandingPrompt 的 preconditions、blockers、gates、依赖 Plan 和 TestPrompt 状态，并输出是否允许执行。

当用户说：

“生成状态视图”

Skill 应该根据 status.yaml 重新生成 views/ 下的所有视图。

当用户说：

“检查整个项目状态”

Skill 应该执行完整流程：
初始化补齐 -> 扫描变化 -> 校验状态 -> 依赖传播 -> 生成视图 -> 输出摘要。

---

# 二十一、输出风格要求

Skill 的回复必须结构化，优先使用以下格式：

## 本次处理结果

说明初始化、扫描或更新了什么。

## 检测到的变化

列出变化文件。

## 状态变化

用表格列出 artifact、旧状态、新状态、原因。

## 阻塞项

列出 blocker 和 failed gate。

## LandingPrompt 执行判断

列出每个 LandingPrompt 是否 ready。

## TestPrompt 更新判断

列出哪些 TestPrompt 需要更新。

## 下一步建议

只列出最关键的 3 到 5 个动作。

---

# 二十二、最终交付要求

请生成完整 Skill 文件内容，至少包括：

1. SKILL.md
2. 初始化目录结构说明
3. status.yaml 模板
4. schema.yaml 模板
5. research README 模板
6. decisions README 模板
7. plan README 模板
8. prompts README 模板
9. landing README 模板
10. test README 模板
11. status README 模板
12. tools README 模板
13. views README 模板
14. render_status.py
15. validate_status.py
16. views 模板文件

生成的 Skill 必须能够在下一次调用时读取已有 status.yaml，并根据 Research、Plan、LandingPrompt、TestPrompt 的变化执行连锁影响分析。

最终目标是让这个 Skill 成为所有项目通用的：

Research -> Decision -> Status -> Plan -> LandingPrompt -> TestPrompt

状态管理与落地控制系统。




###############################################
---

在上面的生产的Skill 追加一个独立特性：

HandoffContext Feature

该特性的目标是让不同 LandingPrompt、TestPrompt、Plan、Decision 之间能够通过中心状态层完成可靠交接。

已有 Skill 已经包含：

Research
Decision
Status
Plan
LandingPrompt
TestPrompt
status/status.yaml
tools/render_status.py
tools/validate_status.py
views/

现在请不要重写整个 Skill，而是在现有 Skill 基础上增量添加 HandoffContext 能力。

---

# 一、特性目标

当前 Skill 已经可以管理：

1. artifact 状态
2. blockers
3. gates
4. preconditions
5. evidence labels
6. Research 影响 Plan
7. Plan 影响 LandingPrompt
8. LandingPrompt 影响 TestPrompt
9. status.yaml 作为状态数据库

但它还缺少一个明确能力：

不同 LandingPrompt / TestPrompt / Plan 之间的交接事实、交接结果、交接约束、交接版本和消费状态。

因此需要新增 HandoffContext，使 status.yaml 不只是状态数据库，也成为跨 Prompt 协作的交接索引中心。

---

# 二、核心设计

新增中心概念：

HandoffContext

HandoffContext 用于记录一个上游 artifact 产出的可交接内容。

它必须回答以下问题：

1. 谁生产了这个交接内容？
2. 这个交接内容来自哪些 Research / Decision / Plan / LandingPrompt / TestPrompt？
3. 它包含哪些下游需要知道的事实？
4. 它包含哪些结果文件或结果目录？
5. 它包含哪些下游必须遵守的约束？
6. 哪些下游 artifact 需要消费它？
7. 下游是否已经消费？
8. 下游消费的是哪个版本？
9. 当前 handoff 是否 stale、invalidated、deprecated 或 archived？
10. 如果 handoff 过期，哪些 LandingPrompt / TestPrompt 需要更新？

---

# 三、status.yaml 结构扩展

请在现有 status/status.yaml 中新增顶级字段：

handoff_contexts: []

如果 status.yaml 中不存在该字段，则自动补齐。

不得删除或重写现有字段。

不得破坏已有 status.yaml 的用户内容。

---

# 四、handoff_contexts 推荐结构

请支持以下结构：

handoff_contexts:
  - id: HC-001
    title: Rendering pipeline implementation handoff
    producer: LandingPrompt.rendering_pipeline_design
    producer_type: landing_prompt
    produced_from:
      - Plan.rendering_pipeline
      - Decision.rendering_strategy
    status: available
    version: 1
    facts:
      - id: HF-001
        statement: "The rendering pipeline uses a simplified forward-rendering path."
        source: prompts/landing/LP-001-rendering-pipeline-design.md
        confidence: high
      - id: HF-002
        statement: "Deferred rendering is rejected for the current milestone."
        source: decisions/D-001-rendering-strategy.yaml
        confidence: high
    results:
      - id: HR-001
        type: design_result
        path: outputs/rendering_pipeline_design.md
        summary: "Defines the selected rendering path, required components, and implementation boundaries."
    constraints:
      - id: HCST-001
        statement: "Do not introduce a deferred-rendering dependency in downstream prompts."
        source: Decision.rendering_strategy
    consumed_by:
      - LandingPrompt.scene_implementation
      - TestPrompt.scene_acceptance
    consumed_status:
      - consumer: LandingPrompt.scene_implementation
        status: pending
        consumed_version: null
        consumed_at: null
      - consumer: TestPrompt.scene_acceptance
        status: pending
        consumed_version: null
        consumed_at: null
    invalidated_by: []
    last_verified: null

---

# 五、HandoffContext 状态

HandoffContext 必须支持以下状态：

draft
available
consumed
partially_consumed
stale
invalidated
deprecated
archived

状态含义：

draft:
交接内容还未确认。

available:
交接内容可供下游使用。

consumed:
所有声明的下游都已经消费当前版本。

partially_consumed:
部分下游已经消费当前版本。

stale:
上游发生变化，交接内容可能过期。

invalidated:
交接内容已经被新的 Research、Decision、Plan 或 Prompt 结果推翻。

deprecated:
不推荐继续使用。

archived:
历史归档，仅保留记录。

---

# 六、artifact 结构扩展

请为 status.yaml 中的 artifacts 添加两个可选字段：

produces_handoffs
consumes_handoffs

示例：

artifacts:
  - id: LandingPrompt.rendering_pipeline_design
    type: landing_prompt
    path: prompts/landing/LP-001-rendering-pipeline-design.md
    status: ready
    produces_handoffs:
      - HC-001
    consumes_handoffs: []
    depends_on:
      - Plan.rendering_pipeline
    blocked_by: []
    invalidated_by: []

  - id: LandingPrompt.scene_implementation
    type: landing_prompt
    path: prompts/landing/LP-002-scene-implementation.md
    status: blocked
    produces_handoffs:
      - HC-002
    consumes_handoffs:
      - HC-001
    depends_on:
      - Plan.scene_implementation
      - TestPrompt.scene_acceptance
    blocked_by:
      - PC-003
    invalidated_by: []

要求：

1. 如果 artifact 不存在 produces_handoffs，则补为空数组。
2. 如果 artifact 不存在 consumes_handoffs，则补为空数组。
3. 不要删除已有 artifact 字段。
4. 不要覆盖用户手写字段。
5. 如果 artifact 声明 consumes_handoffs，则必须检查对应 handoff 是否存在。

---

# 七、preconditions 扩展

preconditions 必须支持 handoff 检查。

示例：

preconditions:
  - id: PC-003
    target: LandingPrompt.scene_implementation
    requires:
      - handoff: HC-001
        field: status
        in:
          - available
          - consumed
      - handoff: HC-001
        field: version
        min: 1
    status: failed

规则：

1. 如果 LandingPrompt 声明 consumes_handoffs，则必须存在对应 precondition。
2. 如果 handoff 不存在，则 precondition failed。
3. 如果 handoff status 是 stale、invalidated、deprecated 或 archived，则 precondition failed。
4. 如果 handoff version 小于要求版本，则 precondition failed。
5. 如果 consumed_version 小于 handoff 当前 version，则 consumer 状态 stale。
6. LandingPrompt 不能在所需 handoff 不可用时进入 ready。

---

# 八、handoff consumption tracking

HandoffContext 必须跟踪下游消费状态。

consumed_status 示例：

consumed_status:
  - consumer: LandingPrompt.scene_implementation
    status: consumed
    consumed_version: 1
    consumed_at: auto_generated_timestamp
  - consumer: TestPrompt.scene_acceptance
    status: pending
    consumed_version: null
    consumed_at: null

消费状态支持：

pending
consumed
stale
rejected

含义：

pending:
下游尚未消费。

consumed:
下游已消费当前版本。

stale:
下游消费的是旧版本。

rejected:
下游明确拒绝该 handoff。

如果 rejected，必须支持记录 reason：

consumed_status:
  - consumer: LandingPrompt.scene_implementation
    status: rejected
    consumed_version: null
    consumed_at: auto_generated_timestamp
    reason: "The handoff conflicts with the current implementation plan."

---

# 九、handoff versioning

每个 HandoffContext 必须有 version。

规则：

1. version 必须是整数。
2. 新建 handoff 时 version 为 1。
3. producer 文件发生实质变化时，对应 handoff version 加 1。
4. handoff version 增加后，所有 consumed_version 小于当前 version 的 consumer 状态进入 stale。
5. 如果 producer 被 invalidated，则对应 handoff 进入 invalidated。
6. 如果 producer 只是被修改但尚未确认，则 handoff 进入 stale。
7. 如果 handoff 重新确认，则可以进入 available。
8. version 变化必须写入 change_events。

---

# 十、handoff 与 Research facts 的关系

请明确区分：

Research facts:
完整事实来源，保存在 research/ 中。

Handoff facts:
面向下游交接的事实摘要，保存在 status.yaml 的 handoff_contexts 中。

规则：

1. Research 中保留完整事实、调研过程和证据。
2. HandoffContext 中只保留下游需要消费的事实摘要。
3. Handoff facts 必须有 source。
4. Handoff facts 不应复制 Research 的长正文。
5. Handoff facts 可以引用 Research、Decision、Plan、LandingPrompt 或 TestPrompt。
6. 如果 Handoff fact 引用了不存在的 source，应在 validate_status.py 中报 warning 或 error。

---

# 十一、handoff results

HandoffContext 必须支持 results 字段，用于登记上游产出的文件、目录或结果。

示例：

results:
  - id: HR-001
    type: design_doc
    path: outputs/rendering_pipeline_design.md
    summary: "Rendering pipeline design result."

  - id: HR-002
    type: generated_code
    path: src/rendering/pipeline/
    summary: "Initial rendering pipeline implementation."

规则：

1. results 只记录索引、摘要和路径。
2. 不要把完整结果内容复制进 status.yaml。
3. 如果 path 不存在，应在 validate_status.py 中给出 warning。
4. 如果 result 被下游消费，应在 handoff_view.md 中展示。

---

# 十二、handoff constraints

HandoffContext 必须支持 constraints 字段，用于登记下游必须遵守的约束。

示例：

constraints:
  - id: HCST-001
    statement: "Do not introduce deferred rendering in the current milestone."
    source: Decision.rendering_strategy

  - id: HCST-002
    statement: "The implementation must stay compatible with the current mobile target."
    source: Research.platform_limit

规则：

1. 下游 LandingPrompt 生成前，必须读取 consumes_handoffs 中的 constraints。
2. 如果下游 Prompt 明确违反 constraints，应标记为 needs_update 或 blocked。
3. constraints 必须有 source。
4. constraints 不应包含长篇解释，只记录可执行约束。

---

# 十三、连锁传播规则扩展

请在现有依赖传播逻辑中加入 handoff propagation。

## Research changed

Research changed
  -> affected Decision check
  -> affected Plan invalidation check
  -> related HandoffContext stale / invalidated check
  -> downstream LandingPrompt needs_update / blocked check
  -> downstream TestPrompt needs_update check
  -> gate recalculation
  -> views regeneration

## Plan changed

Plan changed
  -> produced or dependent HandoffContext stale check
  -> downstream LandingPrompt needs_update check
  -> downstream TestPrompt needs_update check
  -> gate recalculation
  -> views regeneration

## LandingPrompt changed

LandingPrompt changed
  -> produced HandoffContext stale check
  -> downstream LandingPrompt needs_update check
  -> downstream TestPrompt needs_update check
  -> handoff consumption status recalculation
  -> views regeneration

## TestPrompt changed

TestPrompt changed
  -> related HandoffContext consumption check
  -> LandingPrompt precondition recalculation
  -> gate recalculation
  -> views regeneration

## HandoffContext invalidated

HandoffContext invalidated
  -> all consumers enter needs_update or blocked
  -> related gates enter failed
  -> related TestPrompt enter needs_update
  -> change_events updated
  -> views regenerated

---

# 十四、新增 views

请新增两个视图：

views/handoff_view.md
views/prompt_chain_view.md

如果 views/ 不存在，则创建。
如果这两个文件不存在，则创建。
如果已存在，则根据 status.yaml 重新生成，但不得删除用户自定义 section，除非原 Skill 已经定义 views/ 为完全派生目录。

---

## views/handoff_view.md 内容要求

必须包含：

1. 所有 HandoffContext。
2. 每个 handoff 的 producer。
3. 每个 handoff 的 consumers。
4. 每个 handoff 的 status。
5. 每个 handoff 的 version。
6. 每个 handoff 的 facts。
7. 每个 handoff 的 results。
8. 每个 handoff 的 constraints。
9. 哪些 consumer 尚未消费。
10. 哪些 consumer 使用了过期版本。
11. 哪些 LandingPrompt 因 handoff 失效而 blocked。
12. 哪些 TestPrompt 因 handoff 失效而 needs_update。

建议表格：

| Handoff | Producer | Status | Version | Consumers | Issues |
|---|---|---|---|---|---|

---

## views/prompt_chain_view.md 内容要求

必须包含：

1. LandingPrompt 链路。
2. 每个 LandingPrompt 消费哪些 handoff。
3. 每个 LandingPrompt 生产哪些 handoff。
4. 每个 TestPrompt 消费哪些 handoff。
5. 每个 TestPrompt 验证哪些 LandingPrompt。
6. 链路中断点。
7. stale handoff。
8. invalidated handoff。
9. 下一个建议执行的 Prompt。
10. 不能执行的 Prompt 及原因。

需要输出 Mermaid 图。

示例：

graph TD
  LP001[LandingPrompt.rendering_pipeline_design] --> HC001[HC-001 Rendering Handoff]
  HC001 --> LP002[LandingPrompt.scene_implementation]
  HC001 --> TP001[TestPrompt.scene_acceptance]

---

# 十五、render_status.py 修改要求

请修改已有 tools/render_status.py，而不是新建重复脚本。

新增能力：

1. 读取 handoff_contexts。
2. 生成 views/handoff_view.md。
3. 生成 views/prompt_chain_view.md。
4. 检查 consumes_handoffs 是否存在。
5. 检查 produces_handoffs 是否存在。
6. 检查 handoff version 和 consumed_version 是否一致。
7. 检查 stale / invalidated handoff 是否阻塞下游 LandingPrompt。
8. 把 handoff 问题写入 views/change_impact_report.md。
9. 在 views/status_report.md 中增加 handoff summary。
10. 在 views/landing_prompt_checklist.md 中增加 handoff precondition 检查结果。

代码要求：

1. 注释使用英文。
2. 不引入复杂外部依赖。
3. 优先使用 Python 标准库。
4. 如果需要 YAML，沿用现有项目中的 YAML 解析方式。
5. 不要破坏已有 render_status.py 的旧功能。
6. 保持函数职责清晰，例如：
   - load_status
   - render_handoff_view
   - render_prompt_chain_view
   - analyze_handoff_issues
   - check_handoff_consumption

---

# 十六、validate_status.py 修改要求

请修改已有 tools/validate_status.py，而不是新建重复脚本。

新增校验：

1. 每个 handoff_contexts.id 必须唯一。
2. 每个 handoff producer 必须指向存在的 artifact。
3. 每个 consumed_by 必须指向存在的 artifact。
4. 每个 produces_handoffs 必须指向存在的 handoff_context。
5. 每个 consumes_handoffs 必须指向存在的 handoff_context。
6. 每个 consumed_status.consumer 必须存在于 consumed_by。
7. 每个 handoff 必须有 version。
8. version 必须是整数。
9. 每个 handoff fact 必须有 source。
10. 每个 handoff constraint 必须有 source。
11. 每个 handoff result 必须有 path 或 summary。
12. invalidated handoff 不能被 ready artifact 消费。
13. stale handoff 不能让下游 LandingPrompt 保持 ready。
14. archived handoff 不应该被新的 artifact 消费。
15. deprecated handoff 应输出 warning。

代码要求：

1. 注释使用英文。
2. 不破坏已有 validate_status.py 的旧校验逻辑。
3. 新增 handoff 校验最好独立成函数，例如：
   - validate_handoff_contexts
   - validate_handoff_references
   - validate_handoff_consumption
   - validate_handoff_preconditions

---

# 十七、change_events 扩展

当 handoff 发生变化时，必须写入 change_events。

示例：

change_events:
  - id: CE-010
    time: auto_generated_timestamp
    event_type: handoff_version_changed
    source: LandingPrompt.rendering_pipeline_design
    affected:
      - HC-001
      - LandingPrompt.scene_implementation
      - TestPrompt.scene_acceptance
    transitions:
      - artifact: HC-001
        from: available
        to: stale
        reason: Producer LandingPrompt.rendering_pipeline_design changed.
      - artifact: LandingPrompt.scene_implementation
        from: ready
        to: needs_update
        reason: Consumed handoff HC-001 is stale.
      - artifact: TestPrompt.scene_acceptance
        from: ready
        to: needs_update
        reason: TestPrompt consumed old handoff version.

要求：

1. HandoffContext 状态变化必须记录。
2. Handoff version 变化必须记录。
3. Consumer consumed_status 变化必须记录。
4. 因 handoff 导致 artifact 状态变化必须记录。
5. 不要删除旧 change_events。

---

# 十八、README 更新

请更新以下 README：

status/README.md
prompts/landing/README.md
prompts/test/README.md
views/README.md
tools/README.md

## status/README.md 追加内容

说明 status.yaml 现在同时承担：

1. 状态数据库
2. 依赖数据库
3. 交接索引中心

说明 handoff_contexts 用于记录跨 Prompt 的事实、结果、约束和消费状态。

## prompts/landing/README.md 追加内容

说明 LandingPrompt 可以：

1. consumes_handoffs
2. produces_handoffs

LandingPrompt 执行前必须检查 consumes_handoffs 的状态。

LandingPrompt 产出重要结果后，必须登记或更新 HandoffContext。

## prompts/test/README.md 追加内容

说明 TestPrompt 可以消费 HandoffContext。

TestPrompt 应验证对应 LandingPrompt 是否正确使用了 handoff facts、results 和 constraints。

## views/README.md 追加内容

说明：

handoff_view.md 展示交接状态。
prompt_chain_view.md 展示 Prompt 链路和断点。

## tools/README.md 追加内容

说明：

render_status.py 会生成 handoff 相关视图。
validate_status.py 会校验 handoff 结构和引用完整性。

---

# 十九、Skill 说明更新

请更新 Skill 的 SKILL.md，新增一节：

## HandoffContext Feature

内容必须说明：

1. HandoffContext 的目的。
2. 什么时候需要创建 HandoffContext。
3. LandingPrompt 如何生产 handoff。
4. LandingPrompt 如何消费 handoff。
5. TestPrompt 如何验证 handoff。
6. handoff stale / invalidated 后如何连锁影响下游。
7. status.yaml 是 handoff 的中心索引，不是结果正文仓库。
8. Handoff facts / results / constraints 必须引用来源。
9. 不允许跨 Prompt 靠隐式上下文交接。

---

# 二十、用户调用语义

请让 Skill 支持以下用户请求语义：

“为这个 LandingPrompt 创建交接上下文”
-> 新建 HandoffContext，登记 producer、facts、results、constraints、consumers。

“检查这个 LandingPrompt 是否消费了上游结果”
-> 检查 consumes_handoffs、consumed_status、preconditions 和 handoff version。

“我更新了 LP-001，检查下游影响”
-> 找到 LP-001 produces_handoffs，标记 stale 或 version +1，传播到 consumers。

“检查 Prompt 链路”
-> 生成 prompt_chain_view.md，列出链路断点。

“检查交接状态”
-> 生成 handoff_view.md，列出 stale、invalidated、pending、rejected、version mismatch。

“把 HC-001 标记为已被 LP-002 消费”
-> 更新 consumed_status 中 LP-002 的状态为 consumed，并记录 consumed_version 和 consumed_at。

---

# 二十一、输出格式扩展

每次调用 Skill 后，输出摘要必须新增：

## 交接状态

包含：

1. 新增 handoff。
2. stale handoff。
3. invalidated handoff。
4. 未消费 handoff。
5. 使用旧版本 handoff 的消费者。
6. 因 handoff 阻塞的 LandingPrompt。
7. 因 handoff 需要更新的 TestPrompt。
8. 建议下一个处理的 Prompt。

表格示例：

| Handoff | Producer | Status | Version | Consumers | Issue |
|---|---|---|---|---|---|
| HC-001 | LandingPrompt.rendering_pipeline_design | stale | 2 | LandingPrompt.scene_implementation | Consumer used version 1 |

---

# 二十二、重要约束

请遵守以下约束：

1. 不要重写整个 Skill。
2. 不要删除已有功能。
3. 不要删除已有 status.yaml 字段。
4. 不要覆盖用户手写内容。
5. 新增字段必须向后兼容。
6. views/ 可以重新生成，但 status.yaml 必须谨慎修改。
7. 不要把完整 Research 或完整输出结果复制到 status.yaml。
8. status.yaml 中只保存交接摘要、索引、路径、状态和引用。
9. HandoffContext 是跨 Prompt 协作的中心层。
10. LandingPrompt 之间不能只靠隐式上下文交接。
11. 下游 Prompt 必须通过 consumes_handoffs 显式声明输入。
12. 上游 Prompt 必须通过 produces_handoffs 显式声明输出。
13. stale 或 invalidated handoff 必须阻止下游默认保持 ready。
14. 所有代码注释使用英文。
15. 如果生成或修改带花括号的代码，花括号另起一行。

---

# 二十三、最终交付要求

请在已有 Skill 基础上完成增量修改，并输出：

1. 修改了哪些文件。
2. 新增了哪些文件。
3. status.yaml 新增字段说明。
4. HandoffContext 示例。
5. render_status.py 中新增的函数或逻辑。
6. validate_status.py 中新增的函数或逻辑。
7. 新增 views 的内容结构。
8. SKILL.md 的新增章节。
9. README 的新增章节。
10. 如何测试该特性。

不要只给概念说明，必须给出可以直接合并到现有 Skill 的具体文件内容或补丁。