@echo off
chcp 65001 >nul
title Remove-OfficePlus

:: Check for administrative permissions
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo [!] 正在请求管理员权限，请在弹出的 UAC 窗口中点击【是】...
    powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process '%~0' -Verb RunAs"
    exit /b
)

:: Run core powershell script
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\Remove-OfficePlus.ps1"
pause
