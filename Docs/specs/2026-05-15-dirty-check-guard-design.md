# Dirty Check 启动守卫设计

> 为 project-state-tracker Skill 增加前置脏变化检测能力，使 Skill 在每次被调用时能快速感知文件变更，自动刷新视图和传播状态。

## 背景

当前 project-state-tracker 的 AUDIT 模式是被动的——只有用户显式说 "audit" 时才会扫描变更。如果用户在两次调用之间编辑了 research/plan/decision 文件，Skill 下次启动时看到的 views/ 和 status.yaml 可能是过时的。

## 决策摘要

| 决策点 | 选择 |
|--------|------|
| 触发时机 | Skill 被调用时前置检查（启动守卫） |
| 响应范围 | 刷新视图 + 标记受影响 artifact 为 needs_update（跳过 agent_review 项） |
| 检测策略 | 两级：mtime 快筛 → hash 确认 |
| 集成方式 | 独立 Python 脚本 `tools/dirty_check.py` |
| 快照存储 | `status/.cache/file_snapshot.json` |

## 架构

```
Agent 调用 Skill
       │
       ▼
┌─────────────────┐
│ dirty_check.py  │  ← 前置守卫
│  mtime 快筛     │
│  hash 确认      │
└────────┬────────┘
         │
    ┌────┴────┐
    │ clean?  │
    └────┬────┘
     yes │    no
         │     │
         │     ▼
         │  scan_changes.py
         │     │
         │     ▼
         │  propagate.py
         │     │
         │     ▼
         │  apply_changes.py (auto-approve non-review only)
         │     │
         │     ▼
         │  render_status.py
         │     │
         ▼     ▼
    正常 Skill 路由（INIT / AUDIT / 用户指令）
```

## 组件：`tools/dirty_check.py`

### 输入

```
python tools/dirty_check.py --project <project_root>
```

### 执行流程

1. 读取 `status/.cache/file_snapshot.json`
   - 若不存在 → 视为首次运行，所有 tracked 文件标记为 dirty
2. 遍历 tracked 目录（`research/`, `decisions/`, `plan/`, `prompts/`），收集每个文件的 `os.path.getmtime()`
3. **第一级 — mtime 快筛**：对比快照中的 mtime，筛选出 mtime 变化的候选文件
4. **第二级 — hash 确认**：对候选文件计算 SHA-256，对比快照中的 hash
   - hash 相同 → 假阳性（文件被 touch 但内容未变），跳过
   - hash 不同 → 确认为真正变更
5. 检测删除：快照中有但磁盘上不存在的文件 → 标记为 `deleted`
6. 检测新增：磁盘上有但快照中没有的文件 → 标记为 `new`
7. 输出判定结果到 stdout
8. 更新 `file_snapshot.json` 为当前状态

### 输出格式

```json
{
  "status": "dirty|clean",
  "dirty_files": [
    {"path": "research/R-001-xxx.md", "change_type": "modified"},
    {"path": "plan/new-file.md", "change_type": "new"},
    {"path": "decisions/old.yaml", "change_type": "deleted"}
  ],
  "checked_files": 12,
  "elapsed_ms": 45
}
```

### 退出码

- `0` — 正常执行（无论 clean 或 dirty）
- `1` — `status.yaml` 不存在（交给 INIT 模式处理）
- `2` — 其他错误

## 快照文件：`status/.cache/file_snapshot.json`

```json
{
  "last_check": "2026-05-15T10:30:00Z",
  "files": {
    "research/R-001-Dashboard-Visualization-Research.md": {
      "mtime": 1747312200.0,
      "hash": "a3f2b8c4e5d6..."
    },
    "decisions/D-001-single-html-react-cdn.yaml": {
      "mtime": 1747312100.0,
      "hash": "b4c3d2e1f0a9..."
    }
  }
}
```

## Prompt 集成点

在现有 Prompt 的 `Execution Pipeline` 部分，步骤 1 之前插入步骤 0：

```
0. PRE-CHECK: Run `python tools/dirty_check.py --project <project>`
   - If status == "clean" → skip to step 1 (normal routing)
   - If status == "dirty" → auto-execute pipeline:
     a. scan_changes.py (using dirty_files as input)
     b. propagate.py (generate candidates)
     c. Filter: auto-approve candidates where requires_agent_review == false
     d. apply_changes.py (apply approved transitions only)
     e. render_status.py (regenerate views/ + AGENTS.md)
   - Then proceed to step 1 with fresh state
```

## 自动应用规则

| 候选项类型 | 处理方式 |
|-----------|---------|
| `requires_agent_review: false` | 自动写入 `approved_transitions.json`，立即应用 |
| `requires_agent_review: true` | 写入 `candidate_transitions.json`，不自动应用，留待正常流程 |

## 边界条件

| 场景 | 行为 |
|------|------|
| 首次运行（无 file_snapshot.json） | 生成完整快照，标记所有文件为 dirty，触发一次完整刷新 |
| 文件被删除 | 快照中有但磁盘上无 → change_type: "deleted" |
| 文件新增 | 磁盘上有但快照中无 → change_type: "new" |
| status.yaml 不存在 | dirty_check 退出码 1，不做任何操作，交给 INIT 模式 |
| 所有候选项都需要 agent_review | 仅刷新视图，不改 status.yaml 状态 |
| tracked 目录不存在 | 跳过该目录，不报错 |

## 性能预期

- 典型项目（< 50 个 tracked 文件）：mtime 扫描 < 10ms
- Hash 计算仅对 mtime 变化的文件执行，通常 0-3 个文件
- 总体 dirty_check 耗时目标：< 100ms

## 不做的事

- 不引入文件系统监听（watchdog）——过重，且 Skill 是按需调用的
- 不修改 status.yaml 的 snapshots.file_hashes 字段——快照独立存储在 .cache
- 不对 views/ 目录做脏检查——views 是派生输出，永远从 status.yaml 重新生成
- 不自动应用 requires_agent_review 的候选项——保持人工审核门控
