@echo off
cd /d %~dp0
if %errorlevel% neq 0 (
    echo ERROR: Cannot set working directory
    exit /b 1
)

echo ============================================================
echo   Skill Generation ^& Distribution
echo ============================================================

set "SOURCE_PROMPT=Prompt_project-state-tracker_生成项目使用的Workflow_State.md"
set "SKILL_MD=C:\Users\chenshajie\.kiro\skills\project-state-tracker\SKILL.md"

REM === Step 1: Clipboard loading and Kiro launch ===

REM -- Validate Source_Prompt exists --
if not exist "%SOURCE_PROMPT%" (
    echo ERROR: Source prompt not found: %SOURCE_PROMPT%
    exit /b 1
)

REM -- Validate Source_Prompt is non-empty --
for %%A in ("%SOURCE_PROMPT%") do if %%~zA==0 (
    echo ERROR: Source prompt is empty
    exit /b 1
)

REM -- Copy Source_Prompt to clipboard --
clip < "%SOURCE_PROMPT%"
if %errorlevel% neq 0 (
    echo ERROR: Clipboard copy failed
    exit /b 1
)
echo Prompt copied to clipboard successfully.

REM -- Launch Kiro IDE (non-blocking) --
start "" kiro
if %errorlevel% neq 0 (
    echo ERROR: Kiro IDE not found
    exit /b 1
)

echo.
echo ============================================================
echo   Instructions:
echo   1. Paste the clipboard content into Kiro
echo   2. Execute it to generate the Skill
echo   3. Press any key below once generation is complete
echo ============================================================
echo.

pause

REM === Step 2: Validation and distribution ===

REM -- Validate SKILL.md exists --
if not exist "%SKILL_MD%" (
    echo ERROR: SKILL.md not found or empty: %SKILL_MD%
    pause
    exit /b 1
)

REM -- Validate SKILL.md is non-empty --
for %%A in ("%SKILL_MD%") do if %%~zA==0 (
    echo ERROR: SKILL.md not found or empty: %SKILL_MD%
    pause
    exit /b 1
)

REM -- Invoke distribution script (try python, fallback to py) --
python Docs/tools/distribute_skill.py
if %errorlevel% equ 9009 goto :try_py
set "DIST_EXIT=%errorlevel%"
if %DIST_EXIT% neq 0 goto :dist_failed
goto :dist_success

:try_py
py Docs/tools/distribute_skill.py
if %errorlevel% equ 9009 goto :no_python
set "DIST_EXIT=%errorlevel%"
if %DIST_EXIT% neq 0 goto :dist_failed
goto :dist_success

:no_python
echo ERROR: No Python interpreter found
pause
exit /b 1

:dist_failed
echo ERROR: Distribution failed (exit code: %DIST_EXIT%)
pause
exit /b 1

:dist_success
echo Distribution completed successfully.
pause
exit /b 0
