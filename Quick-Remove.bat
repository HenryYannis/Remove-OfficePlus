@echo off
:: Keep this file pure ASCII with CRLF line endings.
:: cmd.exe reads .bat files in the system code page (GBK on Chinese Windows);
:: UTF-8 Chinese text or LF line endings can break parsing. The PowerShell
:: script prints all Chinese messages itself.
title Remove-OfficePlus

:: Check for administrative permissions
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo [!] Requesting administrator rights, please click "Yes" in the UAC prompt...
    set "ROP_SELF=%~f0"
    powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath $env:ROP_SELF -Verb RunAs" || (
        echo [!] Administrator rights were not granted. Right-click this file and choose "Run as administrator".
        pause
    )
    exit /b
)

:: Run core powershell script
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\Remove-OfficePlus.ps1"
pause
