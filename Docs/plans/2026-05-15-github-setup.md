# GitHub 上线实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 Plan-Viewer 项目初始化为 git 仓库并推送到 https://github.com/shajieChen/Plan-Viewer

**Architecture:** 创建必要的项目管理文件（.gitignore、LICENSE、requirements.txt、build.bat），补充 README 构建说明，然后 git init + commit + push。

**Tech Stack:** Git, GitHub, Batch scripting

---

## File Structure

| 操作 | 文件路径 | 职责 |
|------|----------|------|
| Create | `.gitignore` | 排除缓存和构建产物 |
| Create | `LICENSE` | MIT 开源许可证 |
| Create | `requirements.txt` | Python 依赖声明 |
| Create | `build.bat` | 一键构建 Tauri 桌面应用 |
| Modify | `README.md` | 追加"从源码构建"章节 |

---

### Task 1: 创建 .gitignore

**Files:**
- Create: `.gitignore`

- [ ] **Step 1: 创建 .gitignore 文件**

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

---

### Task 2: 创建 LICENSE

**Files:**
- Create: `LICENSE`

- [ ] **Step 1: 创建 MIT LICENSE 文件**

```
MIT License

Copyright (c) 2025 shajieChen

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

---

### Task 3: 创建 requirements.txt

**Files:**
- Create: `requirements.txt`

- [ ] **Step 1: 创建 requirements.txt**

```
PyYAML>=6.0
```

---

### Task 4: 创建 build.bat

**Files:**
- Create: `build.bat`

- [ ] **Step 1: 创建 build.bat**

```bat
@echo off
cd /d %~dp0\plan-viewer-desktop

echo ============================================
echo   Plan Viewer Desktop - Build Script
echo ============================================
echo.
echo Prerequisites:
echo   - Node.js (v18+)
echo   - Rust toolchain (rustup)
echo   - npm
echo.

echo [1/2] Installing npm dependencies...
call npm install
if %errorlevel% neq 0 (
    echo ERROR: npm install failed.
    pause
    exit /b 1
)

echo.
echo [2/2] Building Tauri desktop app...
call npm run tauri build
if %errorlevel% neq 0 (
    echo ERROR: Tauri build failed.
    pause
    exit /b 1
)

echo.
echo ============================================
echo   Build complete!
echo   Output: plan-viewer-desktop\src-tauri\target\release\
echo ============================================
pause
```

---

### Task 5: 追加 README 构建说明

**Files:**
- Modify: `README.md`（在文件末尾追加）

- [ ] **Step 1: 在 README.md 末尾追加以下内容**

```markdown

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
```

---

### Task 6: Git 初始化并推送

**Files:**
- 无新文件，纯 git 操作

- [ ] **Step 1: 初始化 git 仓库**

Run: `git init`
Expected: `Initialized empty Git repository in Q:/Plan_Viewer/.git/`

- [ ] **Step 2: 暂存所有文件**

Run: `git add .`
Expected: 无输出（成功）

- [ ] **Step 3: 检查暂存状态，确认排除项生效**

Run: `git status`
Expected: 不应出现 `__pycache__/`、`.hypothesis/`、`.pytest_cache/`、`node_modules/`、`plan-viewer-desktop.exe`、`.kiro/`

- [ ] **Step 4: 首次提交**

Run: `git commit -m "Initial commit: Plan-Viewer dashboard tool"`
Expected: 提交成功，显示文件数量

- [ ] **Step 5: 添加远程仓库**

Run: `git remote add origin https://github.com/shajieChen/Plan-Viewer.git`
Expected: 无输出（成功）

- [ ] **Step 6: 重命名分支为 main**

Run: `git branch -M main`
Expected: 无输出（成功）

- [ ] **Step 7: 推送到 GitHub**

Run: `git push -u origin main`
Expected: 推送成功，显示 `Branch 'main' set up to track remote branch 'main' from 'origin'.`

---

### Task 7: 验证

- [ ] **Step 1: 验证远程仓库**

Run: `git log --oneline -1`
Expected: 显示 `Initial commit: Plan-Viewer dashboard tool`

- [ ] **Step 2: 浏览器验证**

打开 https://github.com/shajieChen/Plan-Viewer 确认文件已上传，README 正常渲染。
