@echo off
cd /d %~dp0

echo Starting Dashboard Server...
echo.

python dashboard_server.py
if %errorlevel% neq 0 (
    echo python not found, trying py launcher...
    py dashboard_server.py
)

echo.
echo Server stopped.
pause
