@echo off
cd /d %~dp0

echo Stopping Dashboard Server on port 8000...
echo.

set "found=0"
netstat -aon | findstr ":8000 " | findstr "LISTENING" > "_port_stop.tmp" 2>nul
for /f "tokens=5" %%a in (_port_stop.tmp) do (
    echo Killing process PID: %%a
    taskkill /F /PID %%a >nul 2>&1
    set "found=1"
)
del "_port_stop.tmp" >nul 2>&1

if "%found%"=="0" (
    echo No process found listening on port 8000.
) else (
    echo Dashboard Server stopped.
)

echo.
pause
