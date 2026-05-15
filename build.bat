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

echo [1/3] Installing npm dependencies...
call npm install
if %errorlevel% neq 0 (
    echo ERROR: npm install failed.
    pause
    exit /b 1
)

echo.
echo [2/3] Building Tauri desktop app...
call npm run tauri build
if %errorlevel% neq 0 (
    echo ERROR: Tauri build failed.
    pause
    exit /b 1
)

echo.
echo [3/3] Copying exe to project root...
copy /Y "src-tauri\target\release\Plan Viewer.exe" "..\plan-viewer-desktop.exe"
if %errorlevel% neq 0 (
    echo ERROR: Failed to copy exe to project root.
    pause
    exit /b 1
)

echo.
echo ============================================
echo   Build complete!
echo   Output: plan-viewer-desktop.exe (project root)
echo ============================================
pause
