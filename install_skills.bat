@echo off
cd /d %~dp0
if %errorlevel% neq 0 (
    echo ERROR: Cannot set working directory
    exit /b 1
)

echo ============================================================
echo   Skill Installer
echo ============================================================

REM -- Ensure submodules are initialized and up-to-date --
git submodule update --init --remote
if %errorlevel% neq 0 (
    echo WARNING: git submodule update failed, continuing with existing state...
)

REM -- Try python first; on 9009 (command not found) fall back to py --
python Tools\install_skills.py
if %errorlevel% equ 9009 goto :try_py
set "INST_EXIT=%errorlevel%"
if %INST_EXIT% neq 0 goto :inst_failed
goto :inst_success

:try_py
py Tools\install_skills.py
if %errorlevel% equ 9009 goto :no_python
set "INST_EXIT=%errorlevel%"
if %INST_EXIT% neq 0 goto :inst_failed
goto :inst_success

:no_python
echo ERROR: No Python interpreter found
pause
exit /b 1

:inst_failed
echo ERROR: Installation failed (exit code: %INST_EXIT%)
pause
exit /b 1

:inst_success
echo Installation completed successfully.
pause
exit /b 0
