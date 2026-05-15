@echo off
cd /d %~dp0

echo Starting Dashboard Server...
echo.

REM --- 强制清空端口 8000 上的占用进程 ---
echo Checking port 8000...
netstat -aon | findstr ":8000 " | findstr "LISTENING" > "_port_check.tmp" 2>nul
for /f "tokens=5" %%a in (_port_check.tmp) do (
    echo Killing process on port 8000, PID: %%a
    taskkill /F /PID %%a >nul 2>&1
)
del "_port_check.tmp" >nul 2>&1
echo Port 8000 is now free.
echo.

python dashboard_server.py
if %errorlevel% neq 0 (
    echo python not found, trying py launcher...
    py dashboard_server.py
)

echo.
echo Server stopped.
pause
