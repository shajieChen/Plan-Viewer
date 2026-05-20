# ELP Result 持久化设计

**Date:** 2026-05-20
**Scope:** Execute-LandingPrompt Skill (C:\Users\chenshajie\.kiro\skills\Execute-LandingPrompt\)
**Status:** Draft

---

## 目标

在 Execute-LandingPrompt 执行完成后，将 Handoff Markdown（完整执行结果）持久化为独立文件，保存在 PST 根目录下的 `Result/` 目录中。每次执行保留历史记录，不覆盖。

## 动机

当前 ELP 的执行结果仅存在于：
1. 会话输出（临时，关闭即丢失）
2. status.yaml 中的 change_event（仅记录状态变更摘要，不含完整 Handoff 内容）
3. handoff_contexts 中的 facts/constraints（结构化摘要，非原始输出）

缺少一个可回溯的、完整的执行结果归档。`Result/` 目录填补这个空白。

## 设计

### 写入时机

Phase A Step 9（Handoff Markdown 生成）完成后，Phase B 开始前。新增 **Step 9.5**。

Phase B 失败不影响 Result 文件——Result 是 Phase A 的产物，独立于 PST 回流。

### 文件路径

```
<pst_root>/Result/<LP-artifact-id>-<YYYYMMDD-HHmmss>.md
```

示例：
```
Q:\PortNotes\RB_Net_Monitor\Result\LP-001-init-20260520-143022.md
Q:\PortNotes\UE_Iris\Result\CL_SubStep_Verify-20260520-160511.md
```

### 文件内容

完整的 Handoff Markdown，即从 `## 当前 Prompt 执行结果` 到 `## 给下一个 Prompt 的交接` 末尾的全部内容（与会话输出一致）。

### 目录创建

- Step 9.5 检查 `<pst_root>/Result/` 是否存在
- 不存在则创建
- Phase B Scaffold Rules 中也追加 `Result/` 到创建列表（确保 scaffold 场景覆盖）

### 错误处理

- 写入失败（权限、磁盘满等）→ 在 Handoff footer 追加 `⚠️ Result 写入失败: <error>`
- 不阻塞 Phase B，不改变 Phase A 执行状态判定
- 不入队 pending_writebacks（Result 不是 PST 状态数据）

### Handoff Template 变更

在 `## 当前 Prompt 执行结果` section 中新增一行：

```markdown
- Result 文件: <pst_root>/Result/<artifact-id>-<timestamp>.md
```

### PST 兼容性

- `scan_changes.py` IGNORE 列表追加 `Result/**`（PST SKILL.md §10）
- `render_status.py` 不涉及 Result 目录
- status.yaml schema 不变

---

## 改动文件清单

| 文件 | 改动 |
|------|------|
| `SKILL.md` § Execution Flow | 新增 Step 9.5 描述 |
| `SKILL.md` § Handoff Template | 新增 `Result 文件:` 行 |
| `phase_b.md` § Scaffold Rules | 目录列表追加 `Result/` |
| PST `SKILL.md` §10 | IGNORE 列表追加 `Result/**` |

## 不改动的部分

- Phase B 回流逻辑
- status.yaml schema
- approved_transitions.json 格式
- Dependency Gate 逻辑
- HC Management 逻辑
- PST views/render 流程

## 时间戳格式

`YYYYMMDD-HHmmss`，使用本地时间（与 LP 执行环境一致）。不使用 ISO 8601 带冒号格式，因为冒号在 Windows 文件名中非法。

## 幂等性

同一 LP 多次执行 → 每次生成独立文件（时间戳不同）。不存在覆盖或去重逻辑。用户可手动清理历史 Result 文件。
