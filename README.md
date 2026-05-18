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
- **多项目支持** — 通过 `projects.json` 配置多个项目，顶部下拉切换

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
- **桌面版**：Tauri + Vite
- **主题**：暗色/亮色，跟随系统或手动切换

## 快速开始

### 启动 Dashboard 服务

双击 `serve.bat` 或手动运行：

```bash
python dashboard_server.py
```

浏览器会自动打开 `http://localhost:8000/dashboard.html`。

停止服务：双击 `stop.bat`。

### 生成 Dashboard HTML

```bash
python render_dashboard.py --project Q:\PortNotes\UE_Iris
```

输出 `views/dashboard.html`，浏览器打开即可。

### 构建桌面版（可选）

**一键构建**：双击 `build.bat`，脚本会自动检测并安装缺失的依赖（Node.js / Rust 工具链），无需手动准备环境。

```bash
build.bat               # 默认：只产出 .exe（速度快、无需联网下载 NSIS）
build.bat --installer   # 额外打包 NSIS 安装程序（需要联网）
```

构建产物：
- 根目录的 `plan-viewer-desktop.exe`（脚本自动从 target 复制）
- 原始路径：`plan-viewer-desktop\src-tauri\target\release\plan-viewer-desktop.exe`
- NSIS 安装包（仅 `--installer` 模式）：`plan-viewer-desktop\src-tauri\target\release\bundle\nsis\`

脚本特性：
- **Node.js 缺失** → 通过 winget 静默安装 LTS 版本
- **Rust 缺失** → 下载 rustup-init 静默安装 stable 工具链（minimal profile）
- **toolchain 损坏** → 自动卸载并重装 stable
- **PATH 注入** → 脚本会话内动态注入 `~/.cargo/bin`，无需重启终端
- **默认跳过 NSIS bundle** → 避免首次构建时 NSIS 工具下载超时

## 项目结构

```
Q:\Plan_Viewer\
├── README.md                       # 本文件
├── render_dashboard.py             # Dashboard 生成脚本（读取 status.yaml → HTML）
├── dashboard_template.html         # HTML 模板（React + Mermaid）
├── dashboard_server.py             # 本地 HTTP 服务器（自动打开浏览器）
├── project_store.py                # 多项目数据读取模块
├── projects.json                   # 多项目配置（路径 + 名称）
├── serve.bat                       # 一键启动服务
├── stop.bat                        # 一键停止服务
├── build.bat                       # 构建桌面版
├── generate_skill.bat              # 生成/分发 Skill 文件
├── requirements.txt                # Python 依赖
├── plan-viewer-desktop.exe         # 预编译桌面版
│
├── Prompt_project-state-tracker_生成项目使用的Workflow_State.md   # Skill 核心 Prompt (v4)
├── Prompt_project-state-tracker_appendix.md                      # Skill 伴随参考文件
│
├── tests/                          # 测试套件（pytest + hypothesis PBT）
├── views/                          # 生成的 Dashboard HTML 输出
├── plan-viewer-desktop/            # Tauri 桌面版源码
│
└── Docs/                           # 设计文档（project-state-tracker 标准结构）
    ├── AGENTS.md                   # AI agent 单页索引
    ├── research/                   # 调研文档
    ├── decisions/                  # 决策记录
    ├── plan/                       # 设计文档
    ├── plans/                      # 实施计划
    ├── specs/                      # 设计规格
    ├── prompts/                    # Landing/Test Prompts
    ├── status/                     # 状态管理（status.yaml）
    ├── tools/                      # 状态管理脚本（quality_check.py 等）
    ├── views/                      # 生成的视图
    └── PNG/                        # 截图/GIF 素材
```

## 设计文档

- 调研：`Docs/research/R-001-Dashboard-Visualization-Research.md`
- 决策：`Docs/decisions/D-001-single-html-react-cdn.yaml`
- 设计：`Docs/plan/2026-05-14-dashboard-visualization-design.md`
- Prompt v4 升级：`Docs/specs/2026-05-15-prompt-v4-structural-upgrade-design.md`

## 依赖

- Python 3.8+（PyYAML）
- 浏览器：Chrome / Edge 最新版本
- 网络：首次打开需要加载 CDN 资源（之后浏览器缓存）

```bash
pip install -r requirements.txt
```

## 测试

```bash
pytest tests/
```

包含单元测试、集成测试和基于 Hypothesis 的属性测试。

## Project State Tracker Skill

> Prompt 文件：`Prompt_project-state-tracker_生成项目使用的Workflow_State.md`
> 伴随参考：`Prompt_project-state-tracker_appendix.md`

Project State Tracker 是一个 AI Agent Skill，用于管理 Research → Decision → Plan → LandingPrompt → TestPrompt 工件的完整生命周期。通过中心化的 `status.yaml` 追踪所有工件的状态、依赖关系、前置条件和交接上下文。

核心能力是 **INFERENCE**（推理）：读取文档内容，自动提取 artifact ID、依赖关系、前置条件和 handoff context。

### 架构（v4）

- **核心 Prompt**（~1200 words）— SCL 合约 + 需求分页指针表
- **伴随参考文件**（~800 words）— 按需加载的详细规则（§6A-§6G）
- **quality_check.py** — 确定性质量验证（10 条规则）

### 运行模式

| 条件 | 模式 | 行为 |
|------|------|------|
| 无 status.yaml，有文档 | `INIT_FROM_DOCS` | 扫描所有文档，运行推理，生成 status.yaml |
| 无 status.yaml，无文档 | `INIT_EMPTY` | 创建目录结构 + 空 status.yaml |
| 有 status.yaml | `AUDIT` | SCL Pipeline: dirty_check → scan → propagate → review → apply → render |

### 使用方式

```
"init"              — 初始化项目
"audit"             — 完整审计
"regenerate views"  — 仅刷新视图
"rebuild graph"     — 重建依赖图
```

详细说明见 Prompt 文件本身。

---

## 最近更新

### 2026-05-18: Dwell Cancel via Immediate Cursor Signal

修复了窗口缩小后鼠标短暂进入又离开时窗口仍然错误放大的 Bug。

**根因**：`useWindowAutoShrink` 的 dwell-timer 取消逻辑依赖 3s 防抖后的 `hoverState` 信号，而 dwell timer 只有 2s，导致"离开"通知永远晚于 timer 到期。

**修复**：将 `useWindowHover` 拆分为双信号 hook：
- `cursorPresent: boolean` — 即时反映鼠标是否在窗口内（驱动 shrink/dwell）
- `opacityState: 'idle' | 'active'` — 3s 防抖（仅驱动 CSS 透明度）

详见：`Docs/specs/2026-05-18-dwell-cancel-cursor-signal-design.md`

---

## 许可证

MIT License - 详见 [LICENSE](LICENSE) 文件。
