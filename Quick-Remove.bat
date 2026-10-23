@echo off
:: Keep this file pure ASCII with CRLF line endings.
:: cmd.exe reads .bat files in the system code page (GBK on Chinese Windows);
:: UTF-8 Chinese text or LF line endings can break parsing. The PowerShell
:: script prints all Chinese messages itself.
title Remove-OfficePlus

:: Check for administrative permissions.
:: fltmc only succeeds as admin and, unlike "net session", does not depend on the
:: Server service (when it is disabled, net session always fails and UAC loops).
fltmc >nul 2>&1
if %errorlevel% neq 0 (
    echo [!] Requesting administrator rights, please click "Yes" in the UAC prompt...
    set "ROP_SELF=%~f0"
    powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath $env:ROP_SELF -Verb RunAs" || (
        echo [!] Administrator rights were not granted. Right-click this file and choose "Run as administrator".
        pause
    )
    exit /b
)

:: Run core powershell script. It waits for a key press itself before exiting,
:: so only pause here when PowerShell failed to run the script at all
:: (exit code 0 = clean, 1 = leftovers remain; both were already shown).
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\Remove-OfficePlus.ps1"
set "ROP_RC=%errorlevel%"
if %ROP_RC% gtr 1 pause
if %ROP_RC% lss 0 pause
exit /b %ROP_RC%
