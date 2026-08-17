<#
.SYNOPSIS
    Remove-OfficePlus: 一键彻底根除「微软 OfficePLUS」及同类顽固 Office 加载项。

.DESCRIPTION
    本脚本用于扫描、诊断并彻底清除「微软 OfficePLUS」插件。
    包括停止并注销后台守护服务、清理系统全局 (HKLM) 与用户级 (HKCU) 注册表强载项、删除应用与缓存目录、清理计划任务。

.PARAMETER Scan
    仅执行系统诊断与残留扫描，不进行任何修改操作。

.PARAMETER Nuke
    执行彻底清理根除操作。

.PARAMETER NoBackup
    跳过注册表自动备份。

.PARAMETER Force
    跳过交互确认提示，直接执行。

.EXAMPLE
    .\Remove-OfficePlus.ps1 -Scan
    .\Remove-OfficePlus.ps1 -Nuke
#>

[CmdletBinding(DefaultParameterSetName = "Default")]
param(
    [Parameter(ParameterSetName = "Scan")]
    [switch]$Scan,

    [Parameter(ParameterSetName = "Nuke")]
    [switch]$Nuke,

    [switch]$NoBackup,
    [switch]$Force
)

# 确保控制台输出使用 UTF-8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

# ==========================================
# 0. 自动提权检测 (UAC Elevation)
# ==========================================
function Test-IsAdmin {
    $currentPrincipal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
    return $currentPrincipal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Elevate-Privileges {
    if (-not (Test-IsAdmin)) {
        Write-Host "`n[!] 检测到当前非管理员权限，正在请求 UAC 管理员提权..." -ForegroundColor Yellow
        $scriptPath = $MyInvocation.MyCommand.Definition
        
        # 判断是否为本地文件运行还是 irm 在线管道运行
        if ($scriptPath -and (Test-Path $scriptPath)) {
            $argList = "-NoProfile -ExecutionPolicy Bypass -File `"$scriptPath`""
            if ($Scan) { $argList += " -Scan" }
            if ($Nuke) { $argList += " -Nuke" }
            if ($NoBackup) { $argList += " -NoBackup" }
            if ($Force) { $argList += " -Force" }
        } else {
            # 在线 Web 执行模式下的提权
            $onlineCmd = "irm https://raw.githubusercontent.com/HenryYannis/Remove-OfficePlus/main/scripts/Remove-OfficePlus.ps1 | iex"
            $argList = "-NoProfile -ExecutionPolicy Bypass -Command `"$onlineCmd`""
        }

        try {
            Start-Process powershell -Verb RunAs -ArgumentList $argList
            exit
        } catch {
            Write-Error "提权失败或用户取消了 UAC 授权。请右键以管理员身份运行 PowerShell。"
            exit 1
        }
    }
}

# ==========================================
# 1. 目标组件定义
# ==========================================
$TargetProcesses = @(
    "MSOfficePLUSService",
    "OfficePLUS.AgentLauncher",
    "DeepLink",
    "OfficePLUS",
    "WINWORD",
    "EXCEL",
    "POWERPNT",
    "OUTLOOK"
)

$TargetServices = @(
    "OfficePLUS Service"
)

$TargetRegistryKeys = @(
    "HKLM:\Software\Microsoft\Office\Word\Addins\MSOfficePLUS",
    "HKLM:\Software\Microsoft\Office\Excel\Addins\MSOfficePLUS",
    "HKLM:\Software\Microsoft\Office\PowerPoint\Addins\MSOfficePLUS",
    "HKLM:\Software\Microsoft\Office\Outlook\Addins\MSOfficePLUS",
    "HKLM:\Software\Wow6432Node\Microsoft\Office\Word\Addins\MSOfficePLUS",
    "HKLM:\Software\Wow6432Node\Microsoft\Office\Excel\Addins\MSOfficePLUS",
    "HKLM:\Software\Wow6432Node\Microsoft\Office\PowerPoint\Addins\MSOfficePLUS",
    "HKLM:\Software\Wow6432Node\Microsoft\Office\Outlook\Addins\MSOfficePLUS",
    "HKLM:\Software\Microsoft\Windows\CurrentVersion\Uninstall\MSOfficePLUS",
    "HKLM:\Software\Wow6432Node\Microsoft\Windows\CurrentVersion\Uninstall\MSOfficePLUS",
    "HKLM:\Software\Microsoft\OfficePLUS",
    "HKLM:\Software\Wow6432Node\Microsoft\OfficePLUS",
    "HKCU:\Software\Microsoft\Office\Word\Addins\MSOfficePLUS",
    "HKCU:\Software\Microsoft\Office\Excel\Addins\MSOfficePLUS",
    "HKCU:\Software\Microsoft\Office\PowerPoint\Addins\MSOfficePLUS",
    "HKCU:\Software\Microsoft\Office\Outlook\Addins\MSOfficePLUS",
    "HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\MSOfficePLUS",
    "HKCU:\Software\Microsoft\OfficePLUS"
)

$TargetDirectories = @(
    "C:\Program Files\Microsoft OfficePLUS",
    "C:\Program Files (x86)\Microsoft OfficePLUS",
    "C:\ProgramData\Microsoft OfficePLUS",
    "$env:LOCALAPPDATA\OfficePLUS",
    "$env:LOCALAPPDATA\Microsoft OfficePLUS",
    "$env:APPDATA\OfficePLUS",
    "$env:APPDATA\Microsoft OfficePLUS"
)

# ==========================================
# 2. 界面与辅助函数
# ==========================================
function Show-Banner {
    Clear-Host
    Write-Host "============================================================" -ForegroundColor Cyan
    Write-Host "         Remove-OfficePlus  |  Office 流氓插件彻底根除器     " -ForegroundColor Yellow
    Write-Host "       https://github.com/HenryYannis/Remove-OfficePlus     " -ForegroundColor DarkGray
    Write-Host "============================================================" -ForegroundColor Cyan
    Write-Host ""
}

function Write-Step {
    param([string]$Message)
    Write-Host "`n>>> $Message" -ForegroundColor Magenta
}

function Write-Success {
    param([string]$Message)
    Write-Host "  [+] $Message" -ForegroundColor Green
}

function Write-Info {
    param([string]$Message)
    Write-Host "  [*] $Message" -ForegroundColor Gray
}

function Write-Warn {
    param([string]$Message)
    Write-Host "  [!] $Message" -ForegroundColor Yellow
}

function Write-Danger {
    param([string]$Message)
    Write-Host "  [-] $Message" -ForegroundColor Red
}

# ==========================================
# 3. 扫描模块 (Scan / Audit)
# ==========================================
function Invoke-OfficePlusScan {
    Write-Step "正在进行系统环境全面排查扫描..."

    $foundItems = 0

    # 1. 检测运行进程
    Write-Host "`n[1] 进程检测：" -ForegroundColor Cyan
    $runningProcs = Get-Process -Name $TargetProcesses -ErrorAction SilentlyContinue
    if ($runningProcs) {
        foreach ($p in $runningProcs) {
            Write-Danger "发现运行中进程: $($p.Name) (PID: $($p.Id))"
            $foundItems++
        }
    } else {
        Write-Success "未发现 OfficePLUS 关联进程运行。"
    }

    # 2. 检测系统服务
    Write-Host "`n[2] Windows 系统服务检测：" -ForegroundColor Cyan
    foreach ($svcName in $TargetServices) {
        $svc = Get-Service -Name $svcName -ErrorAction SilentlyContinue
        if ($svc) {
            Write-Danger "发现后台常驻服务: $($svc.Name) (状态: $($svc.Status))"
            $foundItems++
        } else {
            Write-Success "系统服务 [$svcName] 未安装或已注销。"
        }
    }

    # 3. 检测注册表加载项与残留
    Write-Host "`n[3] Office 加载项与注册表残留检测：" -ForegroundColor Cyan
    $foundRegCount = 0
    foreach ($reg in $TargetRegistryKeys) {
        if (Test-Path $reg) {
            Write-Danger "发现注册表项: $reg"
            $foundRegCount++
            $foundItems++
        }
    }
    if ($foundRegCount -eq 0) {
        Write-Success "未发现任何 OfficePLUS 相关注册表项。"
    }

    # 4. 检测计划任务
    Write-Host "`n[4] 计划任务检测：" -ForegroundColor Cyan
    $tasks = Get-ScheduledTask -ErrorAction SilentlyContinue | Where-Object { $_.TaskName -like "*OfficePLUS*" -or $_.TaskPath -like "*OfficePLUS*" }
    if ($tasks) {
        foreach ($t in $tasks) {
            Write-Danger "发现守护计划任务: $($t.TaskName)"
            $foundItems++
        }
    } else {
        Write-Success "未发现 OfficePLUS 关联计划任务。"
    }

    # 5. 检测目录与缓存残留
    Write-Host "`n[5] 文件目录与缓存残留检测：" -ForegroundColor Cyan
    $foundDirCount = 0
    foreach ($dir in $TargetDirectories) {
        if (Test-Path $dir) {
            Write-Danger "发现残留目录: $dir"
            $foundDirCount++
            $foundItems++
        }
    }
    if ($foundDirCount -eq 0) {
        Write-Success "未发现任何 OfficePLUS 文件或缓存残留。"
    }

    Write-Host "`n------------------------------------------------------------" -ForegroundColor Cyan
    if ($foundItems -gt 0) {
        Write-Warn "排查完成：共检测到 $foundItems 处 OfficePLUS 关联项目/残留！"
        Write-Host "建议执行彻底根除清理以防止其后台常驻或死灰复燃。" -ForegroundColor Yellow
    } else {
        Write-Success "排查完成：你的系统干干净净，未发现任何 OfficePLUS 残留！"
    }
    Write-Host "------------------------------------------------------------`n" -ForegroundColor Cyan

    return $foundItems
}

# ==========================================
# 4. 彻底根除模块 (Nuke / Clean)
# ==========================================
function Invoke-OfficePlusNuke {
    Elevate-Privileges

    Write-Step "准备执行彻底根除清理..."

    # 注册表备份
    if (-not $NoBackup) {
        $backupDir = if ($PSScriptRoot) { "$PSScriptRoot\..\backup_regs" } else { "$env:TEMP\OfficePLUS_backup_regs" }
        if (-not (Test-Path $backupDir)) {
            New-Item -ItemType Directory -Path $backupDir -Force | Out-Null
        }
        $timestamp = (Get-Date).ToString("yyyyMMdd_HHmmss")
        $backupFile = "$backupDir\OfficePLUS_RegBackup_$timestamp.reg"
        Write-Info "正在自动检测并导出注册表备份至: $backupFile"
        
        $exportedCount = 0
        foreach ($reg in $TargetRegistryKeys) {
            if (Test-Path $reg) {
                $rawRegPath = $reg -replace 'HKLM:\\', 'HKLM\' -replace 'HKCU:\\', 'HKCU\'
                $tempExport = "$backupDir\part_$exportedCount.reg"
                & reg.exe export "$rawRegPath" "$tempExport" /y 2>$null
                if (Test-Path $tempExport) {
                    $exportedCount++
                }
            }
        }
        if ($exportedCount -gt 0) {
            Write-Success "已成功备份 $exportedCount 项注册表数据。"
        } else {
            Write-Info "未发现需备份的注册表项。"
        }
    }

    # 1. 终止所有占用进程
    Write-Step "第 1/5 步: 终止占用进程与 Office 软件..."
    foreach ($pName in $TargetProcesses) {
        $procs = Get-Process -Name $pName -ErrorAction SilentlyContinue
        if ($procs) {
            foreach ($p in $procs) {
                Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue
                Write-Danger "已强制终止进程: $pName (PID: $($p.Id))"
            }
        }
    }
    Write-Success "进程清理完毕。"

    # 2. 停止并注销 Windows 系统服务
    Write-Step "第 2/5 步: 停止并注销后台守护服务..."
    foreach ($svcName in $TargetServices) {
        $svc = Get-Service -Name $svcName -ErrorAction SilentlyContinue
        if ($svc) {
            Stop-Service -Name $svcName -Force -ErrorAction SilentlyContinue
            & sc.exe delete "$svcName" | Out-Null
            Write-Success "已彻底注销系统服务: $svcName"
        }
    }

    # 3. 清除 Office COM 加载项及注册表
    Write-Step "第 3/5 步: 彻底拔除全局与用户级注册表加载项..."
    foreach ($reg in $TargetRegistryKeys) {
        if (Test-Path $reg) {
            Remove-Item -Path $reg -Recurse -Force -ErrorAction SilentlyContinue
            Write-Success "已删除注册表项: $reg"
        }
    }

    # 4. 清理计划任务
    Write-Step "第 4/5 步: 清理关联计划任务..."
    $tasks = Get-ScheduledTask -ErrorAction SilentlyContinue | Where-Object { $_.TaskName -like "*OfficePLUS*" -or $_.TaskPath -like "*OfficePLUS*" }
    if ($tasks) {
        foreach ($t in $tasks) {
            $t | Unregister-ScheduledTask -Confirm:$false -ErrorAction SilentlyContinue
            Write-Success "已注销计划任务: $($t.TaskName)"
        }
    } else {
        Write-Info "无计划任务需要清理。"
    }

    # 5. 彻底删除程序与缓存文件
    Write-Step "第 5/5 步: 彻底删除安装目录与所有缓存..."
    foreach ($dir in $TargetDirectories) {
        if (Test-Path $dir) {
            # 解除只读/隐藏/系统文件属性锁定
            & cmd.exe /c "attrib -r -s -h `"$dir\*`" /s /d" 2>$null
            Remove-Item -Path $dir -Recurse -Force -ErrorAction SilentlyContinue
            Write-Success "已删除目录: $dir"
        }
    }

    Write-Host "`n============================================================" -ForegroundColor Green
    Write-Host " 🎉 微软OfficePLUS 及关联组件已全部彻底根除！" -ForegroundColor Green
    Write-Host "============================================================" -ForegroundColor Green

    # 执行清理后复检
    Write-Host "`n正在进行清理后状态复检..." -ForegroundColor Cyan
    $null = Invoke-OfficePlusScan
}

# ==========================================
# 5. 交互主流程
# ==========================================
Show-Banner

if ($Scan) {
    $null = Invoke-OfficePlusScan
    exit
}

if ($Nuke) {
    Invoke-OfficePlusNuke
    exit
}

# 默认交互菜单模式
$scanResult = Invoke-OfficePlusScan

if ($scanResult -eq 0) {
    Write-Host "系统目前处于干净状态，无需进一步清理。" -ForegroundColor Green
    Write-Host "按任意键退出..."
    $null = [Console]::ReadKey()
    exit
}

if (-not $Force) {
    Write-Host "是否立即执行彻底清理根除？(Y/N): " -NoNewline -ForegroundColor Yellow
    $choice = [Console]::ReadLine()
    if ($choice -notmatch "^[Yy]$") {
        Write-Host "操作已取消。" -ForegroundColor Gray
        exit
    }
}

Invoke-OfficePlusNuke

Write-Host "按任意键退出..."
$null = [Console]::ReadKey()
