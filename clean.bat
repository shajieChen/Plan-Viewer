@echo off
cd /d %~dp0

set TARGET_DIR=plan-viewer-desktop\src-tauri\target

if exist "%TARGET_DIR%" (
    echo Removing build cache: %TARGET_DIR% ...
    rmdir /s /q "%TARGET_DIR%"
    echo Done. Build cache cleaned.
) else (
    echo Nothing to clean. %TARGET_DIR% does not exist.
)
