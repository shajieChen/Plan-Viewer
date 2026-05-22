# Plan Viewer

**中文** | [English](README.md)

项目状态追踪的交互式可视化工具 — 桌面版 (Tauri) + 网页版。

将 [project-state-tracker](https://github.com/shajieChen/kiro-skill-project-state-tracker) 管理的 `status.yaml` 转化为可交互的泳道图 / DAG 依赖图，让你随时掌握工件进度、依赖关系和阻塞点。

---

## 演示

### 桌面版 (exe)

![桌面版演示](Docs/PNG/Plan_Viewer_Exe.gif)

> Always-on-Top 悬浮窗，鼠标离开自动缩小，一键聚焦绑定进程。

### 网页版 (web)

![网页版演示](Docs/PNG/Website_Exe.gif)

> 浏览器直接访问，Mermaid 图表 + Markdown 预览，REST API 支持外部集成。

---

## Skill 联动架构

Plan Viewer 不是孤立工具，它是 Skill 闭环工作流的**可视化终端**。以下 ASCII 图展示了各 Skill 如何协作：

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         Skill 闭环工作流                                 │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌───────────────┐   注册 draft    ┌───────────────────┐               │
│  │  PSS          │ ──────────────▶ │  PST              │               │
│  │  (Spec 编写)  │                 │  (状态追踪/渲染)  │               │
│  │               │◀── 读取依赖 ──  │                   │               │
│  └───────┬───────┘                 └─────────┬─────────┘               │
│          │                                   │                          │
│          │ 生成 LandingPrompt                │ 生成 views/ + README     │
│          ▼                                   ▼                          │
│  ┌───────────────┐                 ┌───────────────────┐               │
│  │  ELP          │   回流状态      │  Plan Viewer      │               │
│  │  (执行 LP)    │ ──────────────▶ │  (可视化展示)     │               │
│  └───────┬───────┘                 └───────────────────┘               │
│          │                                   ▲                          │
│          │ Result 持久化                     │ 读取 status.yaml         │
│          ▼                                   │                          │
│  ┌───────────────┐                           │                          │
│  │  Result/      │ ─── 历史归档 ─────────────┘                          │
│  └───────────────┘                                                      │
│                                                                         │
│  循环: PSS → PST → ELP → PST(审计推进) → 循环                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### 数据流说明

```
status.yaml ──读取──▶ Plan Viewer (exe/web) ──展示──▶ 泳道图 / DAG
     ▲                                                      │
     │                                                      │ 点击修改状态
     └──────────────── 写回 ────────────────────────────────┘
```

---

## 各 Skill 职责

| Skill | 全称 | 触发方式 | 职责 |
|-------|------|----------|------|
| **PST** | project-state-tracker | `"init"` / `"audit"` | 9-state 状态机、依赖图构建、SCL Pipeline、视图渲染 |
| **PSS** | project-state-spec | `Skill PSS + new <topic>` | 三阶段 Spec 编写 (R→D→Task)，生成 Plan + LP + TP |
| **ELP** | Execute-LandingPrompt | `Skill ELP + <LP文件>` | 执行 LP 实施任务，自动回流状态到 status.yaml |
| **MQA** | module-quick-analysis | `Skill MQA + <模块名>` | 5 分钟快速理解陌生模块的设计与职责 |

### Skill 安装

所有 Skill 源码位于 `Tools/Skills/`，通过统一安装脚本分发到各 AI Agent：

```bash
python Tools/install_skills.py
```

支持的 Agent 目标：

| Agent | 安装形式 | 目标路径 |
|-------|----------|----------|
| Kiro | 文件夹复制 | `~/.kiro/skills/<skill>/` |
| Cursor | MDC 单文件 | `~/.cursor/rules/<skill>.mdc` |
| Claude | 文件夹复制 | `~/.claude/skills/<skill>/` |
| Copilot | 合并文件 | `~/.github/copilot-instructions.md` |
| Codex | 合并文件 | `~/.codex/AGENTS.md` |

---

## 功能对照：桌面版 vs 网页版

| 功能 | 桌面版 (exe) | 网页版 (web) |
|------|:---:|:---:|
| 泳道图 / DAG 依赖图 | ✅ | ✅ |
| 节点详情面板（依赖、change_events） | ✅ | ✅ |
| Markdown 预览 | ✅ | ✅ |
| 多项目管理（添加/删除/切换） | ✅ | ✅ |
| 状态点击修改（直接写回 status.yaml） | ✅ | ✅ |
| Smart Group Derivation（依赖链聚类分组） | ✅ | ✅ |
| Always-on-Top 悬浮窗 | ✅ | ❌ |
| 窗口自动缩放（鼠标离开缩小） | ✅ | ❌ |
| 进程绑定 + 一键聚焦 | ✅ | ❌ |
| Glassmorphism 透明暗色主题 | ✅ | ❌ |
| 窗口尺寸记忆（per-project） | ✅ | ❌ |
| 无需安装，浏览器直接访问 | ❌ | ✅ |
| Mermaid 图表渲染 | ❌ | ✅ |
| REST API（项目增删/状态修改） | ❌ | ✅ |
| 启动时自动打开浏览器 | ❌ | ✅ |

---

## 典型工作流（从 0 到 1）

以下场景展示一个完整的项目管理循环，帮助你理解各组件如何串联：

```
步骤 1 ─ 初始化项目结构
         $ cd my-project
         对 AI 说: "init"
         → PST 创建 status/ 目录 + status.yaml + schema.yaml
                                                          │
步骤 2 ─ 编写 Spec                                       │
         对 AI 说: "Skill PSS + new user-auth"            │
         → PSS 引导需求收集 → 生成 Research + Decision    │
         → 生成 Plan + LandingPrompt + TestPrompt         │
         → 自动注册到 status.yaml (draft)                 │
                                                          │
步骤 3 ─ PST 审计 + 渲染视图                             │
         对 AI 说: "audit"                                │
         → PST 运行 SCL Pipeline                          │
         → 生成 views/ (泳道图、DAG、统计)                │
         → 更新 README                                    │
                                                          │
步骤 4 ─ 执行 LandingPrompt                              │
         对 AI 说: "Skill ELP + prompts/landing/LP-001.md"│
         → ELP 按步骤执行实施任务                         │
         → 完成后自动回流状态 (draft → ready)             │
         → Handoff 归档到 Result/                         │
                                                          │
步骤 5 ─ 查看进度                                        │
         桌面版: 运行 build.bat → 悬浮窗实时显示          │
         网页版: python dashboard_server.py → 浏览器打开  │
         → 泳道图展示所有工件状态                         │
         → 点击节点查看详情 / 修改状态                    │
                                                          │
步骤 6 ─ 循环                                            │
         → PST audit 发现下一批 ready 工件                │
         → 回到步骤 2，继续下一轮 Spec                    │
```

---

## 快速开始

### 前置条件

- Python 3.9+ (网页版)
- Rust + Node.js (桌面版编译)
- `pip install -r requirements.txt`

### 网页版

```bash
python dashboard_server.py
# 自动打开 http://localhost:8000/dashboard.html
```

或使用快捷脚本：

```bash
serve.bat
```

### 桌面版

```bash
cd plan-viewer-desktop
npm install
npm run tauri build
# 产物在 src-tauri/target/release/
```

开发模式：

```bash
npm run tauri dev
```

---

## 项目结构

```
Plan_Viewer/
├── dashboard_server.py      # 网页版 HTTP 服务器 + REST API
├── dashboard_template.html  # 网页版 HTML 模板（React CDN + Mermaid）
├── render_dashboard.py      # Dashboard 生成器（读取 status.yaml → HTML）
├── project_store.py         # 项目列表持久化 (projects.json)
├── serve.bat                # 一键启动网页版
├── build.bat                # 一键编译桌面版
│
├── plan-viewer-desktop/     # 桌面版 (Tauri + Preact + Vite)
│   ├── src/
│   │   ├── App.jsx          # 主应用（泳道图、详情面板、进程绑定）
│   │   ├── components/      # UI 组件（TitleBar, SwimLane, DetailPanel...）
│   │   └── hooks/           # 自定义 Hooks（useProjects, useWindowAutoShrink...）
│   └── src-tauri/
│       └── src/             # Rust 后端（进程枚举、窗口聚焦、文件操作）
│
├── Tools/
│   ├── Skills/              # Skill 源码 (git submodules)
│   │   ├── project-state-tracker/
│   │   ├── project-state-spec/
│   │   ├── Execute-LandingPrompt/
│   │   ├── module-quick-analysis/
│   │   └── OpenSpec/
│   └── install_skills.py    # 统一 Skill 安装脚本（→ Kiro/Cursor/Claude/Copilot/Codex）
│
├── Docs/
│   ├── PNG/                 # 演示 GIF
│   ├── specs/               # 设计文档
│   ├── plans/               # 实施计划
│   └── research/            # 调研文档
│
├── views/                   # 生成的 Dashboard HTML
└── tests/                   # pytest 测试
```

---

## 技术栈

| 层 | 技术 |
|----|------|
| 桌面框架 | Tauri 2.x (Rust backend) |
| 桌面前端 | Preact + Vite |
| 网页前端 | React 18 CDN + Tailwind CSS + Mermaid.js + marked.js |
| 网页后端 | Python stdlib `http.server` + PyYAML |
| 数据格式 | YAML (status.yaml) + JSON (projects.json) |
| 测试 | pytest + Hypothesis (property-based testing) |
| Skill 分发 | Python 脚本 → 5 种 Agent 格式 |

---

## REST API（网页版）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/projects` | 获取项目列表 |
| POST | `/api/projects` | 添加项目 |
| POST | `/api/projects/initialize` | 初始化项目结构 |
| DELETE | `/api/projects` | 删除项目 |
| PATCH | `/api/artifact/status` | 修改工件状态 |
| POST | `/api/regenerate` | 手动触发 Dashboard 重新生成 |
| GET | `/api/file?path=<rel>` | 获取项目源文件内容 |

---

## 测试

```bash
pip install -r requirements.txt
pytest tests/
```

使用 [Hypothesis](https://hypothesis.readthedocs.io/) 进行 property-based testing，确保状态机流转和数据解析的正确性。

---

## 关联仓库

| Skill | 仓库 | 用途 |
|-------|------|------|
| project-state-tracker | [GitHub](https://github.com/shajieChen/kiro-skill-project-state-tracker) | 工件生命周期管理 + 状态追踪 |
| project-state-spec | [GitHub](https://github.com/shajieChen/kiro-skill-project-state-spec) | 三阶段 Spec 编写 (R→D→Task) |
| Execute-LandingPrompt | [GitHub](https://github.com/shajieChen/kiro-skill-execute-landingprompt) | 执行 LP 并回流状态 |
| module-quick-analysis | [GitHub](https://github.com/shajieChen/kiro-skill-module-quick-analysis) | 模块快速分析 |
| OpenSpec | [GitHub](https://github.com/Fission-AI/OpenSpec) | Spec 打开/导航 |

---

## 许可证

MIT
