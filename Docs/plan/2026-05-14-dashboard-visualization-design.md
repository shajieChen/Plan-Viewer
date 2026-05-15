# Plan: Project State Tracker Dashboard 可视化设计

> 基于 D-001 决策，为 project-state-tracker 构建一个交互式单文件 HTML Dashboard。

## 1. 概述

### 目标
为 AI agent 驱动开发提供个人工作台，快速查看：
- 当前哪些 LandingPrompt 可以执行
- 哪些 artifact 被阻塞或需要更新
- 整体项目依赖关系和进度
- 各 artifact 的详细内容预览

### 生成方式
集成到现有 `render_status.py` 流程，每次执行时额外输出 `views/dashboard.html`。

## 2. 架构

### 生成流程

```
render_status.py 执行
  → 读取 status.yaml
  → 读取各 artifact 对应的 markdown 文件内容
  → 序列化为 JSON 数据
  → 注入到 dashboard_template.html 模板中
  → 输出 views/dashboard.html
```

### HTML 内部结构

```
dashboard.html
├── <style> 内联 CSS（暗色主题为主，支持亮色切换）
├── <script id="app-data" type="application/json"> 内嵌 JSON 数据
├── <script src="CDN"> React 18.2.0 + ReactDOM 18.2.0
├── <script src="CDN"> Babel standalone 7.24.0
├── <script src="CDN"> Mermaid 10.9.0
├── <script src="CDN"> marked 12.0.0
├── <div id="root"> React 挂载点
└── <script type="text/babel"> 内联 React 应用代码（JSX）
```

### 模板文件位置
`tools/dashboard_template.html`

## 3. 数据模型

Python 侧生成并注入 HTML 的 JSON 结构：

```json
{
  "project": { "name": "...", "phase": "...", "version": "..." },
  "meta": { "last_run": "...", "summary": {...}, "hotspots": [...] },
  "artifacts": [
    {
      "id": "Plan.Phase1-BitStream-NetSerializer",
      "type": "plan",
      "status": "approved",
      "path": "plan/Phase1-BitStream-NetSerializer.md",
      "depends_on": [],
      "produces_handoffs": [],
      "consumes_handoffs": [],
      "last_checked": "...",
      "group": "Phase1"
    }
  ],
  "dependencies": [
    { "from": "...", "to": "...", "type": "requires|implements|verifies" }
  ],
  "research_findings": [...],
  "decisions": [...],
  "gates": [...],
  "blockers": [...],
  "change_events": [...],
  "markdown_contents": {
    "plan/Phase1-BitStream-NetSerializer.md": "# Phase 1 ..."
  }
}
```

### group 字段推导规则（Python 侧）
- ID 包含 `Phase1` → "Phase1"
- ID 包含 `Phase2` → "Phase2"
- ID 包含 `Phase3` → "Phase3"
- ID 包含 `Phase4` → "Phase4"
- ID 包含 `Phase5` → "Phase5"
- ID 包含 `codegen` / `CodeGen` → "CodeGen"
- 其他 → "Other"

## 4. 页面布局

```
┌─────────────────────────────────────────────────────────┐
│ 顶部工具栏：项目名 | Filter 按钮组 | 暗/亮切换 | 视图切换 │
├────────────────────────────────────────┬────────────────┤
│                                        │                │
│         主视图区域（Tab 切换）           │   详情侧边栏    │
│                                        │                │
│  · DAG 依赖图                          │  · artifact 信息│
│  · 泳道图                              │  · 依赖列表     │
│  · 状态机视图                          │  · change_events│
│  · Hotspot 面板                        │  · MD 预览      │
│                                        │                │
└────────────────────────────────────────┴────────────────┘
```

### Filter
- 顶部工具栏 toggle 按钮组：Plan | LandingPrompt | TestPrompt | Research | Decision
- 默认全选，点击切换
- 影响所有视图（DAG 隐藏节点、泳道图隐藏行、Hotspot 过滤列表）

### 侧边栏
- 点击任意 artifact 节点触发
- 可折叠
- 包含详情 + markdown 预览

## 5. 视图详细设计

### 5.1 DAG 依赖图

渲染引擎：Mermaid `flowchart LR`

节点样式映射：
| 状态 | 颜色 | 说明 |
|------|------|------|
| draft | #6b7280 灰 | 圆角矩形 |
| reviewed | #3b82f6 蓝 | 圆角矩形 |
| approved | #6366f1 靛蓝 | 加粗边框 |
| ready | #10b981 绿 | 双边框 |
| blocked | #ef4444 红 | 虚线边框 |
| needs_update | #f59e0b 黄 | 波浪边框 |
| invalidated | #991b1b 深红 | 删除线 |
| deprecated | #78716c 棕灰 | 淡化 |
| archived | #d1d5db 浅灰 | 淡化 |

边样式：
- `requires` → 实线箭头
- `implements` → 虚线箭头
- `verifies` → 点线箭头

Filter 生效时：前端动态重新生成 Mermaid 代码并 re-render。

### 5.2 泳道图

CSS Grid 布局：
- 列 = Phase 分组（Phase1-5, CodeGen, Other）
- 行 = 类型层级（Plan → LandingPrompt → TestPrompt）
- 每个格子 = 状态色块卡片，显示短名称
- 点击触发侧边栏

### 5.3 状态机视图

Mermaid `stateDiagram-v2`：
- 展示 9 个状态之间的合法转换
- 每个状态节点旁标注当前 artifact 数量（如 `draft (18)`）
- 全局概览，不随 Filter 变化

合法转换：
```
draft --> reviewed
reviewed --> approved
approved --> ready
ready --> needs_update
ready --> blocked
needs_update --> draft
needs_update --> reviewed
blocked --> draft
blocked --> reviewed
any --> invalidated
any --> deprecated
any --> archived
```

### 5.4 Hotspot 面板

卡片列表，每张卡片：
- artifact ID + 类型图标
- 当前状态（色块）
- 原因（最近 change_event 提取）
- 建议操作

### 5.5 详情侧边栏

选中 artifact 后展示：
- 基本信息：ID、类型、状态、路径、last_checked
- 上游依赖（depends_on）
- 下游依赖（被谁依赖，从 dependencies[] 反查）
- Handoff：produces / consumes
- 关联 Gate
- 最近 3 条 change_events

### 5.6 Markdown 预览

侧边栏底部区域：
- marked.js 渲染选中 artifact 的 markdown 内容
- 支持滚动
- 代码块语法高亮（marked 默认支持）

## 6. CDN 依赖

| 库 | 版本 | 用途 |
|---|---|---|
| React | 18.2.0 | UI 框架 |
| ReactDOM | 18.2.0 | DOM 渲染 |
| Babel standalone | 7.24.0 | 浏览器端 JSX 编译 |
| Mermaid | 10.9.0 | DAG + 状态机图 |
| marked | 12.0.0 | Markdown 渲染 |

全部使用 pinned 版本，通过 unpkg 或 cdnjs 引入。

## 7. 主题

- 默认跟随系统 `prefers-color-scheme`
- 右上角手动切换按钮
- CSS 变量控制所有颜色
- 暗色主题为主要设计目标

## 8. 文件结构

```
Q:\Plan_Viewer\
├── README.md                          # 工程说明
├── Docs/
│   ├── research/R-001-...md           # 调研文档
│   ├── decisions/D-001-...yaml        # 决策记录
│   ├── plan/2026-05-14-dashboard-...  # 本设计文档
│   └── ...                            # project-state-tracker 标准结构
└── src/
    ├── render_dashboard.py            # 生成脚本（独立于 UE_Iris 的 render_status.py）
    └── dashboard_template.html        # HTML 模板
```

### 与 UE_Iris 的关系
- `render_dashboard.py` 接受 `--project` 参数指向任意 project-state-tracker 项目
- 默认指向 `Q:\PortNotes\UE_Iris`
- 读取目标项目的 `status/status.yaml` 和 artifact 文件
- 输出到目标项目的 `views/dashboard.html`

## 9. 使用方式

```bash
python Q:\Plan_Viewer\src\render_dashboard.py --project Q:\PortNotes\UE_Iris
# 输出: Q:\PortNotes\UE_Iris\views\dashboard.html
# 浏览器打开即可
```

也可集成到 UE_Iris 的 `render_status.py` 末尾调用。

## 10. 约束

- 单文件 HTML 输出，零构建步骤
- 不修改 UE_Iris 现有的任何文件（只新增 dashboard.html）
- Python 3.8+ 兼容（与现有 tools 一致）
- 浏览器兼容：Chrome/Edge 最新版本
