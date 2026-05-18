@echo off
setlocal enabledelayedexpansion
cd /d %~dp0\plan-viewer-desktop

echo ============================================
echo   Plan Viewer Desktop - Build Script
echo ============================================
echo.

rem ---------- Parse arguments ----------
set BUILD_INSTALLER=0
if /I "%~1"=="--installer" set BUILD_INSTALLER=1
if /I "%~1"=="-i" set BUILD_INSTALLER=1

if %BUILD_INSTALLER%==1 (
    set BUNDLE_FLAG=--bundles nsis
    set BUILD_MODE=exe + NSIS installer
) else (
    set BUNDLE_FLAG=--no-bundle
    set BUILD_MODE=exe only ^(use --installer for NSIS package^)
)
echo Build mode: !BUILD_MODE!
echo.

rem ---------- [1/4] Ensure Node.js ----------
echo [1/4] Checking Node.js...
where node >nul 2>&1
if !errorlevel! neq 0 (
    echo   Node.js not found. Installing via winget...
    where winget >nul 2>&1
    if !errorlevel! neq 0 (
        echo ERROR: winget is not available. Install Node.js manually from https://nodejs.org
        pause
        exit /b 1
    )
    winget install -e --id OpenJS.NodeJS.LTS --accept-package-agreements --accept-source-agreements --silent
    if !errorlevel! neq 0 (
        echo ERROR: Failed to install Node.js via winget.
        echo Please install manually from https://nodejs.org and re-run this script.
        pause
        exit /b 1
    )
    rem Refresh PATH from registry so node/npm become visible in this session
    for /f "tokens=2*" %%A in ('reg query "HKCU\Environment" /v PATH 2^>nul ^| findstr /I "PATH"') do set "USER_PATH=%%B"
    for /f "tokens=2*" %%A in ('reg query "HKLM\SYSTEM\CurrentControlSet\Control\Session Manager\Environment" /v PATH 2^>nul ^| findstr /I "PATH"') do set "SYS_PATH=%%B"
    set "PATH=!SYS_PATH!;!USER_PATH!"
    where node >nul 2>&1
    if !errorlevel! neq 0 (
        echo ERROR: Node.js installed but not visible. Please restart this terminal and re-run.
        pause
        exit /b 1
    )
)
for /f "delims=" %%V in ('node --version') do set NODE_VER=%%V
echo   Node.js !NODE_VER! OK
echo.

rem ---------- [2/4] Ensure Rust ----------
echo [2/4] Checking Rust toolchain...
rem Inject ~/.cargo/bin so cargo is visible even right after rustup install
set "PATH=%USERPROFILE%\.cargo\bin;%PATH%"

where cargo >nul 2>&1
if !errorlevel! neq 0 (
    echo   Rust not found. Installing via rustup...
    set "RUSTUP_INIT=%TEMP%\rustup-init.exe"
    powershell -NoProfile -Command "try { Invoke-WebRequest -Uri 'https://win.rustup.rs/x86_64' -OutFile '%TEMP%\rustup-init.exe' -UseBasicParsing } catch { exit 1 }"
    if !errorlevel! neq 0 (
        echo ERROR: Failed to download rustup-init.exe. Check your network.
        pause
        exit /b 1
    )
    "!RUSTUP_INIT!" -y --default-toolchain stable --profile minimal --no-modify-path
    if !errorlevel! neq 0 (
        echo ERROR: rustup-init failed.
        pause
        exit /b 1
    )
    set "PATH=%USERPROFILE%\.cargo\bin;%PATH%"
)

rem Heal corrupted toolchain manifest if rustup show fails
rustup show >nul 2>&1
if !errorlevel! neq 0 (
    echo   Toolchain manifest issue detected. Reinstalling stable...
    rustup toolchain uninstall stable >nul 2>&1
    rustup toolchain install stable
    if !errorlevel! neq 0 (
        echo ERROR: Failed to install stable toolchain.
        pause
        exit /b 1
    )
    rustup default stable >nul 2>&1
)

cargo --version >nul 2>&1
if !errorlevel! neq 0 (
    echo ERROR: cargo still not available after install.
    pause
    exit /b 1
)
for /f "delims=" %%V in ('cargo --version') do set CARGO_VER=%%V
for /f "delims=" %%V in ('rustc --version') do set RUSTC_VER=%%V
echo   !RUSTC_VER!
echo   !CARGO_VER!
echo.

rem ---------- [3/4] Install npm dependencies ----------
echo [3/4] Installing npm dependencies...
call npm install
if !errorlevel! neq 0 (
    echo ERROR: npm install failed.
    pause
    exit /b 1
)
echo.

rem ---------- [4/4] Build Tauri app ----------
echo [4/4] Building Tauri desktop app...
call npm run tauri -- build !BUNDLE_FLAG!
if !errorlevel! neq 0 (
    echo ERROR: Tauri build failed.
    pause
    exit /b 1
)
echo.

rem ---------- Copy exe to project root ----------
echo Copying exe to project root...
copy /Y "src-tauri\target\release\plan-viewer-desktop.exe" "..\plan-viewer-desktop.exe" >nul
if !errorlevel! neq 0 (
    echo ERROR: Failed to copy exe to project root.
    pause
    exit /b 1
)

echo.
echo ============================================
echo   Build complete!
echo   Output: plan-viewer-desktop.exe (project root)
if %BUILD_INSTALLER%==1 (
    echo   NSIS installer: src-tauri\target\release\bundle\nsis\
)
echo ============================================
pause
