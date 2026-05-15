# Design: Build Exe Output to Project Root

**Date:** 2026-05-15  
**Scope:** `build.bat` only

## Problem

`build.bat` 构建完成后，exe 产物留在深层目录 `plan-viewer-desktop\src-tauri\target\release\`，用户需要手动找到并复制到根目录才能方便使用。

## Solution

在 `build.bat` 构建成功后增加一步 `copy` 命令，将 exe 自动复制到项目根目录并命名为 `plan-viewer-desktop.exe`。

## Changes

修改 `build.bat`：

1. 步骤编号从 `[1/2]` `[2/2]` 改为 `[1/3]` `[2/3]`
2. 在 Tauri 构建成功后、"Build complete!" 提示前，新增步骤 `[3/3]`：
   - 使用 `copy /Y` 将 `src-tauri\target\release\Plan Viewer.exe` 复制到 `..\plan-viewer-desktop.exe`
   - 复制失败时报错并暂停退出
3. 更新最终 Output 提示行，指向根目录 `plan-viewer-desktop.exe`

## Behavior

- 如果根目录已存在旧 exe，直接覆盖（`/Y` 参数）
- 如果复制失败（文件被占用等），显示错误信息并暂停
- `.gitignore` 已包含 `plan-viewer-desktop.exe`，无需修改

## Files Affected

- `build.bat` — 唯一修改文件
