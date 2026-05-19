# Plan Viewer

Project State Tracker 的交互式可视化 Dashboard — 桌面版 (Tauri) + 网页版。

## 功能

- DAG 依赖图 / 泳道图 / 状态机视图 / Hotspot 面板
- 点击节点查看详情、依赖、change_events
- 内置 Markdown 预览（README 导读 + artifact 文件）
- 类型 Filter（Plan / LP / TP / Research / Decision）
- 多项目切换（`projects.json`）
- Glassmorphism 暗色/亮色主题
- 窗口记忆尺寸 + 自动缩小/恢复（dwell 机制）

## 演示

| 桌面版 (Tauri) | 网页版 |
|:-:|:-:|
| ![桌面版](Docs/PNG/Plan_Viewer_Exe.gif) | ![网页版](Docs/PNG/Website_Exe.gif) |

## 快速开始

```bash
# 网页版
python dashboard_server.py          # 或双击 serve.bat

# 桌面版（一键构建，自动安装 Node/Rust）
build.bat
```

## 技术栈

Python (PyYAML) · React 18 (CDN) · Mermaid.js · marked.js · Tauri + Vite

## 关联 Skill (submodules)

| Skill | 用途 | 仓库 |
|-------|------|------|
| project-state-tracker | 工件生命周期管理 + 状态追踪 | [GitHub](https://github.com/shajieChen/kiro-skill-project-state-tracker) |
| project-state-spec | 三阶段 Spec 编写 (R→D→Task) | [GitHub](https://github.com/shajieChen/kiro-skill-project-state-spec) |
| Execute-LandingPrompt | 执行 LP 并回流状态 | [GitHub](https://github.com/shajieChen/kiro-skill-execute-landingprompt) |

## 测试

```bash
pip install -r requirements.txt
pytest tests/
```

## 许可证

MIT — 详见 [LICENSE](LICENSE)
