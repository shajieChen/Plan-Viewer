# Design: Plan Viewer Desktop Floating Widget

## Overview

将 Plan Viewer 转换为一个基于 Tauri 的桌面浮窗应用。常驻置顶，支持窗口透明和自适应缩放，聚焦于泳道图（SwimLane）和 artifact 详情查看。通过文件监听实时感知项目状态变化。

## 技术选型

| 维度 | 选择 | 理由 |
|------|------|------|
| 桌面框架 | Tauri v2 | 轻量（5-15MB exe），原生支持置顶/透明/无边框，Windows WebView2 |
| 前端框架 | Preact + Vite | 与 React 写法兼容，打包仅 ~3KB，适合精简视图 |
| 泳道渲染 | CSS Grid + JSX | 不依赖 Mermaid.js，定制性强，体积小 |
| Markdown | marked (~7KB) | 轻量，用于 artifact 文件预览 |
| 文件监听 | Rust notify crate | 业界标准，性能好，支持 debounce |
| YAML 解析 | serde_yaml | Rust 生态标准选择 |

## Architecture

```
plan-viewer-desktop/
├── src-tauri/                  # Rust 后端
│   ├── src/
│   │   ├── main.rs            # Tauri 入口，窗口配置，托盘
│   │   ├── watcher.rs         # 文件监听（notify crate, 500ms debounce）
│   │   ├── project_reader.rs  # 读取 status.yaml → ProjectData
│   │   └── commands.rs        # Tauri commands
│   ├── Cargo.toml
│   └── tauri.conf.json
├── src/                        # Preact 前端
│   ├── index.html
│   ├── main.jsx               # 入口
│   ├── SwimLane.jsx           # 泳道组件
│   ├── DetailPanel.jsx        # 详情面板
│   ├── styles.css             # 样式（透明/毛玻璃）
│   └── data.js                # Tauri invoke 封装
├── vite.config.js
└── package.json
```

## 窗口行为

### 配置

- `alwaysOnTop: true` — 始终置顶
- `transparent: true` — 允许背景透明
- `decorations: false` — 无系统标题栏
- 默认尺寸：400×300
- 最小尺寸：200×150

### 透明度状态机

```
Idle（鼠标不在窗口上）
  - 背景完全透明（rgba 0,0,0,0）
  - 内容半透明（opacity: 0.6）
  - 只显示精简内容
        │
        │ 鼠标进入窗口
        ▼
Active（鼠标悬停/聚焦）
  - 背景渐变为半透明毛玻璃（backdrop-filter: blur）
  - 内容完全不透明（opacity: 1.0）
  - 显示完整交互界面
        │
        │ 鼠标离开窗口（延迟 1.5s）
        ▼
      回到 Idle
```

### 自定义标题栏

- 顶部窄条（20px），`data-tauri-drag-region` 拖拽
- 按钮：📌 取消置顶 / 🔒 锁定透明度 / ✕ 最小化到托盘
- 关闭 = 最小化到托盘，不退出进程

### 系统托盘

- 关闭窗口 → 最小化到托盘
- 左键单击托盘图标 → 显示/隐藏窗口
- 右键菜单：显示窗口 / 退出

## 功能范围

### 包含

1. **泳道图（SwimLane）** — 按 Phase 分列展示 artifact 状态流转，节点带状态色
2. **详情面板** — 点击节点查看：artifact ID、状态、类型、依赖列表、最近 change events、Markdown 预览
3. **项目切换** — 顶部下拉框切换已注册项目
4. **实时刷新** — 文件监听 status.yaml 变更，自动更新视图

### 不包含

- DAG 依赖图
- 状态机视图
- Hotspot 面板
- 项目管理 UI（添加/移除项目）
- 类型 Filter

## 响应式断点

| 窗口宽度 | 模式 | 显示内容 |
|----------|------|----------|
| < 400px | Compact | 泳道压缩为竖向列表，每 Phase 一行显示完成比例 |
| 400-599px | Full | 完整泳道图 + 点击节点后详情面板从底部弹出 |
| ≥ 600px | Full+Side | 完整泳道图 + 详情面板在右侧滑出 |

## Rust 后端

### Tauri Commands

```rust
#[tauri::command]
fn get_projects() -> Result<Vec<ProjectEntry>, String>

#[tauri::command]
fn get_dashboard_data() -> Result<DashboardData, String>

#[tauri::command]
fn set_always_on_top(enabled: bool) -> Result<(), String>

#[tauri::command]
fn set_opacity(level: f64) -> Result<(), String>
```

### 事件推送（Rust → 前端）

```rust
app_handle.emit_all("project-updated", ProjectUpdatePayload {
    project_path: String,
    timestamp: String,
});
```

### 文件监听策略

- 启动时为每个已注册项目的 `status/status.yaml` 创建 watcher
- 使用 debounce（500ms）避免连续写入触发多次刷新
- 监听 Modify 和 Create 事件
- 项目列表变更时动态增减 watcher

### Rust 依赖

| crate | 用途 |
|-------|------|
| `tauri` | 框架核心 |
| `serde` + `serde_json` | JSON 序列化 |
| `serde_yaml` | YAML 解析 |
| `notify` | 文件系统监听 |
| `tauri-plugin-system-tray` | 系统托盘 |

### 数据模型

与现有 Python 版 `render_dashboard.py` 中的 dataclass 对齐：

- `ProjectData` — 项目完整数据
- `Artifact` — 含 id, type, status, path, depends_on, group
- `Dependency` — from_id, to_id, dep_type
- `ChangeEvent` — id, time, source, event_type, summary, affected

`derive_group()` 逻辑（从 artifact ID 推导 Phase）同样在 Rust 端实现。

## 打包与分发

- `cargo tauri build` → `plan-viewer-desktop.exe`（单文件，~5-15MB）
- exe 放置于 `Q:\Plan_Viewer\plan-viewer-desktop.exe`
- 运行时依赖 WebView2（Windows 10 21H2+ / Windows 11 自带）

## 与浏览器版的关系

| 维度 | 桌面版 | 浏览器版 |
|------|--------|----------|
| 数据源 | `projects.json` + `status.yaml`（只读） | 同（可读写） |
| 项目管理 | 无（读取 projects.json） | 有（添加/移除/初始化） |
| 视图 | 泳道 + 详情 | 完整 Dashboard |
| 运行方式 | 独立 exe，常驻托盘 | Python server + 浏览器 |
| 可同时运行 | 是 | 是 |

两者完全独立，互不干扰，共享 `projects.json` 和各项目的 `status.yaml`。

## 前置条件

开发环境需要：
- Rust 工具链（rustup）
- Node.js 18+（前端构建）
- Tauri CLI（`cargo install tauri-cli`）

用户运行只需：
- Windows 10 21H2+ 或 Windows 11（自带 WebView2）
- 双击 exe 即可
