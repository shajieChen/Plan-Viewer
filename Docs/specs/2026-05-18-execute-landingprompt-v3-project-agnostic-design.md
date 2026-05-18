# Execute-LandingPrompt v3 — 项目无关化设计

## Overview

将 Execute-LandingPrompt 从"硬编码项目路径和规则"的执行器，重构为"读取项目自描述配置"的通用执行引擎。所有项目特有信息（source root、coding standards、LP 序列、scope）从 SKILL.md 中移除，改由每个项目的 `LandingPrompt/README.md` 自行声明。

## 决策记录

| # | 问题 | 决策 |
|---|------|------|
| 1 | 项目特有信息放哪里 | 放在 `LandingPrompt/README.md` 中 |
| 2 | 配置格式 | YAML front-matter（机器可读）+ Markdown 正文（人可读） |
| 3 | Coding standards 存放方式 | 直接写在 README.md 的 `## Coding Standards` section 中 |
| 4 | ELP 如何定位 README | 取 LP 文件的父目录，在该目录下找 README.md |
| 5 | PST root 定位 | 默认取 LP 父目录的上级；README 中可用 `pst_root` 字段覆盖 |
| 6 | README 不存在时的行为 | 报错，不执行（无 fallback） |

## 从 SKILL.md 中删除的内容

| 原有 section | 原因 |
|---|---|
| `## Project Detection` 硬编码表 | 被路径推导规则替代 |
| `## Scope` 硬编码定义 | 被 README front-matter 的 `scope` 字段替代 |
| `## Coding Standards` 全部（Baseline + UE_Iris + Net Monitor） | 被 README 的 `## Coding Standards` section 替代 |
| `## LandingPrompt Sequence` fallback | 被 README 的 `## LP 序列` section 替代 |

## 保留不变的内容

- Phase A 执行流程（Steps 1-8）
- Phase B PST 回流（Steps 9-12）
- `## Constraints`（通用约束）
- `## Handoff Template`
- `## § ID Resolution`
- `## § Status Mapping`
- `## § PST 回流`（scaffold、数据映射、HC 管理、幂等性、错误处理）
- `## Safety Checks`

## § README 协议

每个 LandingPrompt 目录下必须有一个 `README.md`，格式如下：

### YAML Front-matter Schema

```yaml
---
source_root: "<绝对路径>"          # 必填：源码根目录，ELP 在此目录下读/改代码
scope:                             # 可选：允许操作的路径列表
  - "<path1>"                      # 默认 = [source_root, lp_dir 的父目录]
  - "<path2>"
pst_root: "<绝对路径>"             # 可选：PST 回流目标目录
                                   # 默认 = lp_dir 的父目录
                                   # ELP 写入 <pst_root>/status/status.yaml
---
```

### Markdown 正文约定

| Section heading | 用途 | 必填 |
|---|---|---|
| `## LP 序列` | 声明 LP 执行顺序，ELP 用来确定"下一个 prompt" | 是 |
| `## Coding Standards` | 项目编码规范，ELP 执行代码修改时遵循 | 否 |

正文其余部分为自由格式，供人阅读。

### 完整示例

```markdown
---
source_root: "Q:\\1.55.0_Net_Monitor\\Source"
scope:
  - "Q:\\PortNotes\\RB_Net_Monitor"
  - "Q:\\1.55.0_Net_Monitor\\Source"
pst_root: "Q:\\PortNotes\\RB_Net_Monitor"
---

# Net Monitor LandingPrompt

## LP 序列

CollectionLayer_Phase -> CL_SubStep_Verify -> CL_SubStep_Structures -> CL_SubStep_Instrumentation -> CL_SubStep_Lifecycle
TelemetryProcessingLayer_Phase -> TPL_SubStep_Framework -> TPL_SubStep_Snapshot -> TPL_SubStep_SinkAndTick
PresentationLayer_Phase -> PL_SubStep_Verify -> PL_SubStep_Sinks -> PL_SubStep_Integration

## Coding Standards

Follow existing code style in source root. Match surrounding file style.
```

## § 路径推导规则

```
输入: Skill Execute-LandingPrompt + <lp_file_path>

lp_dir       = dirname(lp_file_path)                    # LP 文件所在目录
readme_path  = lp_dir / README.md                       # README 位置
source_root  = README.front_matter.source_root          # 必填，从 README 读取
scope        = README.front_matter.scope ?? [source_root, dirname(lp_dir)]
pst_root     = README.front_matter.pst_root ?? dirname(lp_dir)
```

如果 `readme_path` 不存在：ELP 输出错误信息并停止，不执行任何 LP。

## § Coding Standards 处理

ELP 不再内置任何编码规范。行为优先级：

1. 读 README.md 的 `## Coding Standards` section → 如果存在，遵循其中规则
2. 如果 README 中无该 section → 遵循当前 workspace 的 `.kiro/steering/` 规则（如果有）
3. 如果都没有 → 按通用最佳实践写代码

## § 更新后的 Execution Flow

### Phase A — Execute (Steps 1-8)

1. 从 LP 文件路径推导 `lp_dir`，读取 `lp_dir/README.md`。
   - 解析 YAML front-matter → 获取 `source_root`、`scope`、`pst_root`
   - 解析正文 → 获取 LP 序列、Coding Standards
   - 如果 README.md 不存在 → 报错停止
2. 读取用户指定的当前 LandingPrompt 文件。
3. 按需读取前置 prompt（仅当安全执行需要时）。
4. 执行当前 prompt（先摘要 goal/mode/allowed files/gates）。
5. 运行相关验证；对比 acceptance criteria。
6. 判定状态：`completed` / `partial` / `blocked`。
7. 读取下一个 prompt（从 LP 序列确定）用于 handoff 上下文 — 不执行。
8. 产出 handoff section（Markdown）。

### Phase B — PST 回流 (Steps 9-12)

9. 检测 `<pst_root>/status/status.yaml` 是否存在。不存在则 scaffold。
10. 解析 LP artifact ID（按 § ID Resolution 规则）。
11. 写入/更新：LP artifact 条目 + handoff_context + change_event。
12. 设置 LP artifact 状态（按 § Status Mapping）。

Phase B 是 best-effort。如果 YAML 写入失败，在 handoff 末尾报告但不影响 Phase A 结果。

## § 对现有项目的迁移

现有两个项目需要更新各自的 `LandingPrompt/README.md`，将原来 SKILL.md 中的项目特有规则迁移过去：

### Net Monitor (`Q:\PortNotes\RB_Net_Monitor\LandingPrompt\README.md`)

- front-matter: `source_root`, `scope`, `pst_root`
- `## Coding Standards`: "Follow existing code style in source root. Match surrounding file style."
- `## LP 序列`: 现有的 CollectionLayer → TelemetryProcessing → Presentation 序列

### UE_Iris (`Q:\PortNotes\UE_Iris\LandingPrompt\README.md`)

- front-matter: `source_root: "Q:\1.47\Source"`, `scope`, `pst_root`
- `## Coding Standards`: 完整的 ReplicationSystem 特有规则（宏前缀、命名空间、DLL export 等）
- `## LP 序列`: 现有的 Phase 序列

## § Safety Checks（更新后）

- README.md 已读取且 front-matter 解析成功。
- source_root 路径存在且可访问。
- 当前 prompt 已读取且仅执行了它。
- 下一个 prompt 已读取但未执行；handoff section 存在。
- 所有代码修改在 scope 范围内。
- 代码遵循 README 中声明的 Coding Standards。
- 无 forbidden scope 被修改；无 unresolved 被报告为 confirmed。
- Phase B: artifact ID 正确解析。
- Phase B: status mapping 使用 `ready`/`needs_update`/`blocked`。
- Phase B: 写入方式匹配 workspace 状态。
- Phase B: HC version 仅在 facts/constraints 实际变化时 bump。
- Phase B 回流完成或失败已报告。

## 交付物

1. `C:\Users\chenshajie\.kiro\skills\Execute-LandingPrompt\SKILL.md` — 重写（删除所有项目特有内容，新增 README 协议和路径推导规则）
2. `Q:\PortNotes\RB_Net_Monitor\LandingPrompt\README.md` — 更新（添加 front-matter + Coding Standards section）
3. `Q:\PortNotes\UE_Iris\LandingPrompt\README.md` — 更新（添加 front-matter + Coding Standards section）
