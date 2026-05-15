# GitHub 上线设计 — Plan-Viewer

## 目标

将 Plan-Viewer 项目推送到 GitHub 作为个人备份和版本管理，仓库公开，MIT 许可证。

## 仓库信息

- **仓库地址**: https://github.com/shajieChen/Plan-Viewer
- **可见性**: Public
- **许可证**: MIT
- **主分支**: main

## 需要创建的文件

### 1. `.gitignore`

排除运行时产物和构建缓存，保留源码和 `views/dashboard.html`（作为生成示例）、`projects.json`（直接跟踪）。

```gitignore
# Python
__pycache__/
*.pyc
*.pyo

# Testing
.hypothesis/
.pytest_cache/

# Node / Desktop app
plan-viewer-desktop/node_modules/
plan-viewer-desktop/dist/

# Built binary
plan-viewer-desktop.exe

# IDE / Editor
.kiro/
```

### 2. `LICENSE`

MIT 许可证，版权人 shajieChen，年份 2025。

### 3. `requirements.txt`

```
PyYAML>=6.0
```

项目唯一的第三方 Python 依赖。

### 4. `build.bat`

一键构建 Tauri 桌面应用的脚本。前置条件：Node.js、npm、Rust 工具链。

```bat
@echo off
cd /d %~dp0\plan-viewer-desktop
echo Installing dependencies...
npm install
echo Building Tauri desktop app...
npm run tauri build
echo Done. Output in plan-viewer-desktop\src-tauri\target\release\
pause
```

### 5. README 追加内容

在现有 README.md 末尾追加"从源码构建"章节：

- Python 环境：`pip install -r requirements.txt`
- 桌面版构建：运行 `build.bat`（需要 Node.js + Rust 工具链）
- 启动服务：运行 `serve.bat`

## 执行步骤

1. ~~在 GitHub 创建 Plan-Viewer 仓库（Public，空仓库）~~ ✅ 已完成
2. `git init` — 初始化本地仓库
3. 创建 `.gitignore`、`LICENSE`、`requirements.txt`、`build.bat`
4. 追加 README 构建说明
5. `git add .` — 暂存所有文件
6. `git commit -m "Initial commit"`
7. `git remote add origin https://github.com/shajieChen/Plan-Viewer.git`
8. `git branch -M main`
9. `git push -u origin main`

## 保留在仓库中的文件

- `projects.json` — 直接跟踪（个人使用，不介意路径暴露）
- `views/dashboard.html` — 作为生成示例保留
- `package-lock.json` — 锁定 npm 依赖版本

## 排除出仓库的文件

- `__pycache__/`、`.hypothesis/`、`.pytest_cache/` — 运行时缓存
- `plan-viewer-desktop/node_modules/` — npm 依赖（`npm install` 还原）
- `plan-viewer-desktop/dist/` — Vite 构建产物
- `plan-viewer-desktop.exe` — 编译产物（将来可通过 Releases 发布）
- `.kiro/` — IDE 配置

## 不在本次范围内

- GitHub Actions / CI 自动化
- GitHub Releases 发布流程
- 分支策略（当前只用 main）
