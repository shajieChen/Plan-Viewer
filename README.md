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

## 许可证

MIT License - 详见 [LICENSE](LICENSE) 文件。
