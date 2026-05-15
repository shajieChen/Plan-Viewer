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
