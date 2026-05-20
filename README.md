# Plan Viewer

项目状态追踪的交互式可视化工具 — 桌面版 (Tauri) + 网页版。

## 功能概览

- 泳道图 / DAG 依赖图 / 状态机视图
- 节点详情面板（依赖、change_events、Markdown 预览）
- 多项目管理（添加/删除/切换）
- Glassmorphism 暗色主题 + 窗口自动缩放
- 状态点击交互（直接修改 artifact 状态）

## 快速开始

```bash
# 网页版
python dashboard_server.py

# 桌面版
build.bat
```

## 技术栈

Tauri · Preact · Vite · Python · PyYAML · Mermaid.js · marked.js

## 关联 Skill (submodules)

| Skill | 用途 |
|-------|------|
| [project-state-tracker](https://github.com/shajieChen/kiro-skill-project-state-tracker) | 工件生命周期管理 + 状态追踪 |
| [project-state-spec](https://github.com/shajieChen/kiro-skill-project-state-spec) | 三阶段 Spec 编写 (R→D→Task) |
| [Execute-LandingPrompt](https://github.com/shajieChen/kiro-skill-execute-landingprompt) | 执行 LP 并回流状态 |
| [module-quick-analysis](https://github.com/shajieChen/kiro-skill-module-quick-analysis) | 模块快速分析 |
| [OpenSpec](https://github.com/shajieChen/kiro-skill-OpenSpec) | Spec 打开/导航 |

## Skill 闭环

```
PSS (注册 draft) → PST (渲染 README) → ELP (执行 LP, 回流状态) → PST (审计推进) → 循环
```

## 测试

```bash
pip install -r requirements.txt
pytest tests/
```

## 许可证

MIT
