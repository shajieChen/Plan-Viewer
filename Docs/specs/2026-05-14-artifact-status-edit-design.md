# Design: Artifact Status 直接修改功能

## 概述

在 Artifact Details 侧边栏中，将静态的 status badge 替换为可操作的下拉选择器，允许用户直接修改 artifact 的状态。修改通过 API 持久化到项目的 `status/status.yaml` 文件，并触发 dashboard 重新生成。

## 前端交互

### UI 变更

在 DetailSidebar 组件的 STATUS 字段区域：
- 将当前的静态 `<span className="status-badge">` 替换为 `<select>` 下拉框
- 下拉框背景色跟随当前状态色（使用 STATUS_COLORS 映射）
- 选项列出全部 9 个合法状态：draft, reviewed, approved, ready, blocked, needs_update, invalidated, deprecated, archived
- 当前状态为默认选中值

### 交互流程

1. 用户在下拉框中选择新状态
2. 立即发起 `PATCH /api/artifact/status` 请求
3. 下拉框暂时 disabled（防止重复提交）
4. 请求成功 → auto-refresh 机制检测到 timestamp 变化后自动刷新页面
5. 请求失败 → 在下拉框下方显示红色错误文字，3 秒后自动消失

### 需要传递的数据

前端需要知道当前选中的 artifact 属于哪个 project。当前 App 组件已有 `selectedProject` 状态（项目名），直接传递给 DetailSidebar 即可。

## 后端 API

### 端点

`PATCH /api/artifact/status`

### 请求体

```json
{
  "project": "UE_Iris",
  "artifact_id": "Plan.Phase1-BitStream-NetSerializer",
  "new_status": "ready"
}
```

### 服务器逻辑

1. 解析 JSON body，验证 `project`、`artifact_id`、`new_status` 三个字段存在
2. 验证 `new_status` 是合法的 9 个状态之一
3. 在 `projects.json` 中找到匹配 project name 的项目路径（通过读取每个项目的 `status/status.yaml` 中的 `meta.project_name` 匹配）
4. 读取该项目的 `status/status.yaml`
5. 在 `artifacts` 列表中找到 `id` 匹配 `artifact_id` 的条目
6. 更新该条目的 `status` 字段为 `new_status`
7. 更新 `meta.last_updated` 为当前 UTC 时间（ISO-8601 格式）
8. 写回 YAML 文件（保持原有格式尽量不变）
9. 触发 `regenerate_dashboard()`
10. 返回 200 + `{"message": "Status updated", "artifact_id": "...", "new_status": "..."}`

### 合法状态列表

```python
VALID_STATUSES = [
    "draft", "reviewed", "approved", "ready", "blocked",
    "needs_update", "invalidated", "deprecated", "archived"
]
```

### 错误响应

| 场景 | HTTP 状态码 | 响应 |
|------|------------|------|
| 缺少必要字段 | 400 | `{"error": "Missing required field: xxx"}` |
| new_status 不合法 | 400 | `{"error": "Invalid status: xxx"}` |
| project 未找到 | 404 | `{"error": "项目未找到"}` |
| artifact_id 未找到 | 404 | `{"error": "Artifact 未找到"}` |
| YAML 读取/写入失败 | 500 | `{"error": "写入失败: xxx"}` |

## 数据流

```
用户选择新状态
  → fetch('PATCH /api/artifact/status', {project, artifact_id, new_status})
  → 服务器读取 status.yaml
  → 修改 artifact status + meta.last_updated
  → 写回 status.yaml
  → 调用 regenerate_dashboard()
  → 返回 200
  → auto-refresh 检测 timestamp 变化
  → 页面自动刷新（新状态生效）
```

## 修改的文件

| 文件 | 变更 |
|------|------|
| `dashboard_server.py` | 新增 `PATCH /api/artifact/status` 路由和 handler |
| `dashboard_template.html` | DetailSidebar 中 STATUS 字段改为 select 下拉框 + 错误提示 |

## 不做的事情

- 不做状态转换合法性校验（任何状态可以转到任何状态，不限制转换路径）
- 不记录 change_event（状态变更不自动写入 change_events 列表）
- 不做批量修改
- 不做撤销功能
