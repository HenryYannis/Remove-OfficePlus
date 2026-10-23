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

# 必须在脚本顶层取路径：在函数里用 $MyInvocation 拿到的是函数本身，
# 会被误判成在线模式而去 GitHub 重新下载 main 分支的脚本。
$ScriptPath = $PSCommandPath

function Get-ElevationArguments {
    # 本地文件运行：用管理员身份重新执行当前这份脚本，并保留原参数
    if ($ScriptPath -and (Test-Path -LiteralPath $ScriptPath)) {
        $argList = "-NoProfile -ExecutionPolicy Bypass -File `"$ScriptPath`""
        if ($Scan) { $argList += " -Scan" }
        if ($Nuke) { $argList += " -Nuke" }
        if ($NoBackup) { $argList += " -NoBackup" }
        if ($Force) { $argList += " -Force" }
    } else {
        # irm | iex 在线运行时没有本地文件，只能重新拉取同一个地址
        $onlineCmd = "irm https://raw.githubusercontent.com/HenryYannis/Remove-OfficePlus/main/scripts/Remove-OfficePlus.ps1 | iex"
        $argList = "-NoProfile -ExecutionPolicy Bypass -Command `"$onlineCmd`""
    }
    return $argList
}

function Elevate-Privileges {
    if (-not (Test-IsAdmin)) {
        Write-Host "`n[!] 检测到当前非管理员权限，正在请求 UAC 管理员提权..." -ForegroundColor Yellow
        $argList = Get-ElevationArguments

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
# 0.5 确定要清理哪个用户
# ==========================================
# 普通用户运行时，UAC 会让输入另一个管理员账号的密码，脚本随后以那个管理员身份运行，
# HKCU 和 %APPDATA% 都会指向管理员自己。这里找出当前桌面会话的登录用户，
# 和当前运行账号不同时改为清理他的数据；有任何不确定就返回 $null，按原来的方式处理当前用户。
function Get-TargetUser {
    try {
        if (-not ("RemoveOfficePlus.Wts" -as [type])) {
            Add-Type -Namespace RemoveOfficePlus -Name Wts -MemberDefinition @"
[DllImport("wtsapi32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
public static extern bool WTSQuerySessionInformationW(IntPtr server, int sessionId, int infoClass, out IntPtr buffer, out int bytes);
[DllImport("wtsapi32.dll")]
public static extern void WTSFreeMemory(IntPtr memory);
public static string Query(int sessionId, int infoClass) {
    IntPtr buffer; int bytes;
    if (!WTSQuerySessionInformationW(IntPtr.Zero, sessionId, infoClass, out buffer, out bytes)) { return ""; }
    try { return Marshal.PtrToStringUni(buffer); } finally { WTSFreeMemory(buffer); }
}
"@
        }
        $sessionId = (Get-Process -Id $PID).SessionId
        $user = [RemoveOfficePlus.Wts]::Query($sessionId, 5)    # WTSUserName
        $domain = [RemoveOfficePlus.Wts]::Query($sessionId, 7)  # WTSDomainName
        if (-not $user) { return $null }
        $account = if ($domain) { "$domain\$user" } else { $user }
        $sid = (New-Object Security.Principal.NTAccount($account)).Translate([Security.Principal.SecurityIdentifier]).Value
        if (-not $sid -or $sid -eq [Security.Principal.WindowsIdentity]::GetCurrent().User.Value) { return $null }
        # 登录用户的注册表必须已加载（他正登录着），并且能找到他的个人文件夹
        if (-not (Test-Path -LiteralPath "Registry::HKEY_USERS\$sid")) { return $null }
        $userProfile = [Environment]::ExpandEnvironmentVariables((Get-ItemProperty -LiteralPath "HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\ProfileList\$sid").ProfileImagePath)
        if (-not $userProfile -or -not (Test-Path -LiteralPath $userProfile)) { return $null }
        $folders = Get-Item -LiteralPath "Registry::HKEY_USERS\$sid\Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders" -ErrorAction SilentlyContinue
        $folder = {
            param($name, $default)
            $value = if ($folders) { $folders.GetValue($name, $null, 'DoNotExpandEnvironmentNames') }
            if ($value) { $value = $value -replace '%USERPROFILE%', $userProfile.Replace('$', '$$') }
            if (-not $value -or $value -match '%') { $value = Join-Path $userProfile $default }
            $value
        }
        return [pscustomobject]@{
            Sid          = $sid
            Name         = $user
            LocalAppData = & $folder "Local AppData" "AppData\Local"
            AppData      = & $folder "AppData" "AppData\Roaming"
            Documents    = & $folder "Personal" "Documents"
        }
    } catch {
        return $null
    }
}

$TargetUser = Get-TargetUser
if ($TargetUser) {
    $UserRegRoot = "Registry::HKEY_USERS\$($TargetUser.Sid)"
    $UserLocalAppData = $TargetUser.LocalAppData
    $UserAppData = $TargetUser.AppData
    $UserDocuments = $TargetUser.Documents
} else {
    $UserRegRoot = "HKCU:"
    $UserLocalAppData = $env:LOCALAPPDATA
    $UserAppData = $env:APPDATA
    $UserDocuments = [Environment]::GetFolderPath("MyDocuments")
}

# ==========================================
# 1. 目标组件定义
# ==========================================
# ---- BEGIN RULES：由 scripts/sync_rules.py 根据 rules.json 生成，请勿手改 ----
# OfficePLUS 自身的进程：扫描时算作威胁
$OfficePlusProcesses = @(
    "MSOfficePLUSService",
    "OfficePLUS.AgentLauncher",
    "DeepLink",
    "OfficePLUS"
)

# 正常的 Office 程序：不是威胁，只是清理时要关闭它们，才能删掉被占用的加载项文件
$OfficeAppProcesses = @(
    "WINWORD",
    "EXCEL",
    "POWERPNT",
    "OUTLOOK"
)

# 清理时要结束的全部进程
$TargetProcesses = $OfficePlusProcesses + $OfficeAppProcesses

$TargetServices = @(
    "OfficePLUS Service"
)

# 计划任务名或路径里含有这个词就算 OfficePLUS 的
$TaskKeyword = "OfficePLUS"

$TargetRegistryKeys = @(
    "HKLM:\Software\Microsoft\Office\Word\Addins\MSOfficePLUS",
    "HKLM:\Software\Microsoft\Office\Excel\Addins\MSOfficePLUS",
    "HKLM:\Software\Microsoft\Office\PowerPoint\Addins\MSOfficePLUS",
    "HKLM:\Software\Microsoft\Office\Outlook\Addins\MSOfficePLUS",
    "HKLM:\Software\Microsoft\Windows\CurrentVersion\Uninstall\MSOfficePLUS",
    "HKLM:\Software\Microsoft\OfficePLUS",
    "HKLM:\Software\Wow6432Node\Microsoft\Office\Word\Addins\MSOfficePLUS",
    "HKLM:\Software\Wow6432Node\Microsoft\Office\Excel\Addins\MSOfficePLUS",
    "HKLM:\Software\Wow6432Node\Microsoft\Office\PowerPoint\Addins\MSOfficePLUS",
    "HKLM:\Software\Wow6432Node\Microsoft\Office\Outlook\Addins\MSOfficePLUS",
    "HKLM:\Software\Wow6432Node\Microsoft\Windows\CurrentVersion\Uninstall\MSOfficePLUS",
    "HKLM:\Software\Wow6432Node\Microsoft\OfficePLUS",
    "$UserRegRoot\Software\Microsoft\Office\Word\Addins\MSOfficePLUS",
    "$UserRegRoot\Software\Microsoft\Office\Excel\Addins\MSOfficePLUS",
    "$UserRegRoot\Software\Microsoft\Office\PowerPoint\Addins\MSOfficePLUS",
    "$UserRegRoot\Software\Microsoft\Office\Outlook\Addins\MSOfficePLUS",
    "$UserRegRoot\Software\Microsoft\Windows\CurrentVersion\Uninstall\MSOfficePLUS",
    "$UserRegRoot\Software\Microsoft\OfficePLUS"
)

# 系统目录取环境变量（系统不一定装在 C 盘）；哪个位置取不到就跳过，不能拼成盘符根目录
$TargetDirectories = @(
    if ($env:ProgramFiles) { Join-Path $env:ProgramFiles "Microsoft OfficePLUS" }
    if (${env:ProgramFiles(x86)}) { Join-Path ${env:ProgramFiles(x86)} "Microsoft OfficePLUS" }
    if ($env:ProgramData) { Join-Path $env:ProgramData "Microsoft OfficePLUS" }
    if ($UserLocalAppData) { Join-Path $UserLocalAppData "OfficePLUS" }
    if ($UserLocalAppData) { Join-Path $UserLocalAppData "Microsoft OfficePLUS" }
    if ($UserAppData) { Join-Path $UserAppData "OfficePLUS" }
    if ($UserAppData) { Join-Path $UserAppData "Microsoft OfficePLUS" }
)
# ---- END RULES ----

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
    if ($TargetUser) {
        Write-Info "当前以其他管理员账号运行，将检查和清理登录用户「$($TargetUser.Name)」的个人设置与文件。"
    }

    # 1. 检测运行进程
    Write-Host "`n[1] 进程检测：" -ForegroundColor Cyan
    $runningProcs = Get-Process -Name $OfficePlusProcesses -ErrorAction SilentlyContinue
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
    $tasks = Get-ScheduledTask -ErrorAction SilentlyContinue | Where-Object { $_.TaskName -like "*$TaskKeyword*" -or $_.TaskPath -like "*$TaskKeyword*" }
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
# 备份文件夹里的恢复说明（与 Python 版 backup.py 的 RESTORE_NOTE 内容一致）
$RestoreNote = "这个文件夹里是 Remove-OfficePlus 清理前自动备份的注册表。`r`n`r`n如果清理后某个 Office 功能或设置不正常，可以这样恢复：`r`n1. 找到那次清理对应的 .reg 文件，文件名里是清理的日期和时间，`r`n   例如 OfficePLUS_注册表备份_20261023_105700.reg；`r`n   同一秒内备份了多次时，后面的文件会加上 _2、_3。`r`n2. 双击它，在弹出的提示中点「是」（可能需要管理员权限）。`r`n3. 重新打开 Office 即可。`r`n`r`n注意：这些备份里只有被删除的 OfficePLUS 相关注册表项，恢复后 OfficePLUS 加载项也会回来。`r`n确认电脑一切正常后，可以直接删除这个文件夹。`r`n"

function Invoke-OfficePlusNuke {
    Elevate-Privileges

    Write-Step "准备执行彻底根除清理..."

    # 提醒用户先保存正在编辑的 Office 文档（-Force 时跳过）
    if (-not $Force) {
        $openOffice = Get-Process -Name $OfficeAppProcesses -ErrorAction SilentlyContinue
        if ($openOffice) {
            $names = ($openOffice | Select-Object -ExpandProperty Name -Unique) -join "、"
            Write-Warn "检测到以下 Office 程序正在运行：$names"
            Write-Warn "清理时会强制关闭它们，未保存的内容会丢失。请先保存好文件。"
            Write-Host "保存好后按回车继续，输入 N 取消: " -NoNewline -ForegroundColor Yellow
            $answer = [Console]::ReadLine()
            if ($answer -match "^[Nn]") {
                Write-Host "操作已取消。" -ForegroundColor Gray
                return
            }
        }
    }

    # 清理日志：把这次清理的全部输出（包括失败原因）记到备份文件夹里，方便排查和提交 Issue
    $script:LogFile = $null
    try {
        $logDir = Join-Path $UserDocuments "Remove-OfficePlus 备份"
        New-Item -ItemType Directory -Path $logDir -Force -ErrorAction Stop | Out-Null
        $stem = "清理日志_" + (Get-Date).ToString("yyyyMMdd_HHmmss")
        $logPath = Join-Path $logDir "$stem.txt"
        $n = 2
        while (Test-Path -LiteralPath $logPath) {
            $logPath = Join-Path $logDir "${stem}_$n.txt"
            $n++
        }
        Start-Transcript -LiteralPath $logPath -ErrorAction Stop | Out-Null
        $script:LogFile = $logPath
        Write-Host "Remove-OfficePlus 开始清理  系统: $([Environment]::OSVersion.VersionString)  PowerShell: $($PSVersionTable.PSVersion)"
    } catch {
        # 日志写不了不影响清理
        Write-Verbose "清理日志创建失败: $($_.Exception.Message)"
    }

    # 注册表备份：把要删的项合并导出成一个 .reg 文件，误删时双击即可恢复
    $script:BackupFile = $null
    $backupFailed = @()
    if (-not $NoBackup) {
        $existingRegs = @($TargetRegistryKeys | Where-Object { Test-Path $_ })
        if ($existingRegs.Count -gt 0) {
            $backupDir = Join-Path $UserDocuments "Remove-OfficePlus 备份"
            $tempDir = Join-Path $env:TEMP ("OfficePLUS_backup_" + [guid]::NewGuid())
            New-Item -ItemType Directory -Path $tempDir -Force | Out-Null
            $header = "Windows Registry Editor Version 5.00"
            $merged = New-Object System.Collections.Generic.List[string]
            $merged.Add($header)
            $i = 0
            foreach ($reg in $existingRegs) {
                $rawRegPath = $reg -replace '^HKLM:\\', 'HKLM\' -replace '^HKCU:\\', 'HKCU\' -replace '^Registry::HKEY_USERS\\', 'HKU\'
                $part = Join-Path $tempDir "$i.reg"
                $null = & reg.exe export "$rawRegPath" "$part" /y /reg:64 2>&1
                if ($LASTEXITCODE -eq 0 -and (Test-Path $part)) {
                    $merged.Add("")
                    $merged.AddRange([string[]](Get-Content -Path $part -Encoding Unicode | Where-Object { $_ -ne $header }))
                } else {
                    $backupFailed += $reg
                    Write-Warn "注册表项备份失败，为安全起见本次不删除它: $reg"
                }
                $i++
            }
            Remove-Item -Path $tempDir -Recurse -Force -ErrorAction SilentlyContinue
            if ($merged.Count -gt 1) {
                try {
                    New-Item -ItemType Directory -Path $backupDir -Force -ErrorAction Stop | Out-Null
                    # 同一秒内多次备份时加 _2、_3 后缀，绝不覆盖以前的备份
                    $stem = "OfficePLUS_注册表备份_" + (Get-Date).ToString("yyyyMMdd_HHmmss")
                    $backupPath = Join-Path $backupDir "$stem.reg"
                    $n = 2
                    while (Test-Path -LiteralPath $backupPath) {
                        $backupPath = Join-Path $backupDir "${stem}_$n.reg"
                        $n++
                    }
                    try {
                        Set-Content -LiteralPath $backupPath -Value $merged -Encoding Unicode -ErrorAction Stop
                    } catch {
                        # 写了一半的文件不能留下来冒充备份
                        Remove-Item -LiteralPath $backupPath -Force -ErrorAction SilentlyContinue
                        throw
                    }
                    $script:BackupFile = $backupPath
                    Write-Success "已备份 $($existingRegs.Count - $backupFailed.Count) 项注册表到: $($script:BackupFile)"
                    # 在备份文件夹里放一份恢复说明，只写一次；写不进去也不影响清理
                    $notePath = Join-Path $backupDir "如何恢复.txt"
                    if (-not (Test-Path -LiteralPath $notePath)) {
                        try {
                            [IO.File]::WriteAllText($notePath, $RestoreNote, (New-Object System.Text.UTF8Encoding $true))
                        } catch {
                            Write-Verbose "恢复说明写入失败: $($_.Exception.Message)"
                        }
                    }
                } catch {
                    # 备份文件写不进去（文件夹无权限、磁盘满等）：一项都不删，宁可这次不清注册表
                    Write-Warn "注册表备份文件写入失败（$($_.Exception.Message)），为安全起见本次不删除任何注册表项。"
                    $backupFailed = $existingRegs
                }
            }
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
                if (Get-Process -Id $p.Id -ErrorAction SilentlyContinue) {
                    Write-Danger "无法结束进程: $pName (PID: $($p.Id))"
                } else {
                    Write-Danger "已强制终止进程: $pName (PID: $($p.Id))"
                }
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
            if ($LASTEXITCODE -eq 0) {
                Write-Success "已彻底注销系统服务: $svcName"
            } else {
                Write-Danger "注销系统服务失败: $svcName"
            }
        }
    }

    # 3. 清除 Office COM 加载项及注册表
    Write-Step "第 3/5 步: 彻底拔除全局与用户级注册表加载项..."
    foreach ($reg in $TargetRegistryKeys) {
        if ($backupFailed -contains $reg) { continue }
        if (Test-Path $reg) {
            Remove-Item -Path $reg -Recurse -Force -ErrorAction SilentlyContinue -ErrorVariable regErr
            if (Test-Path $reg) {
                Write-Danger "删除注册表项失败: $reg"
                if ($regErr) { Write-Info "原因: $($regErr[0].Exception.Message)" }
            } else {
                Write-Success "已删除注册表项: $reg"
            }
        }
    }

    # 4. 清理计划任务
    Write-Step "第 4/5 步: 清理关联计划任务..."
    $tasks = Get-ScheduledTask -ErrorAction SilentlyContinue | Where-Object { $_.TaskName -like "*$TaskKeyword*" -or $_.TaskPath -like "*$TaskKeyword*" }
    if ($tasks) {
        foreach ($t in $tasks) {
            $t | Unregister-ScheduledTask -Confirm:$false -ErrorAction SilentlyContinue -ErrorVariable taskErr
            if (Get-ScheduledTask -TaskName $t.TaskName -TaskPath $t.TaskPath -ErrorAction SilentlyContinue) {
                Write-Danger "注销计划任务失败: $($t.TaskName)"
                if ($taskErr) { Write-Info "原因: $($taskErr[0].Exception.Message)" }
            } else {
                Write-Success "已注销计划任务: $($t.TaskName)"
            }
        }
    } else {
        Write-Info "无计划任务需要清理。"
    }

    # 5. 彻底删除程序与缓存文件
    Write-Step "第 5/5 步: 彻底删除安装目录与所有缓存..."
    foreach ($dir in $TargetDirectories) {
        if (Test-Path $dir) {
            # 解除只读/隐藏/系统文件属性锁定
            $null = & cmd.exe /c "attrib -r -s -h `"$dir\*`" /s /d" 2>$null
            Remove-Item -Path $dir -Recurse -Force -ErrorAction SilentlyContinue -ErrorVariable dirErr
            if (Test-Path $dir) {
                Write-Danger "目录未能完全删除（可能有文件正被占用）: $dir"
                foreach ($e in @($dirErr | Select-Object -First 3)) { Write-Info "原因: $($e.Exception.Message)" }
            } else {
                Write-Success "已删除目录: $dir"
            }
        }
    }

    # 执行清理后复检，按实际结果汇报
    Write-Host "`n正在进行清理后状态复检..." -ForegroundColor Cyan
    $script:NukeRemaining = [int](Invoke-OfficePlusScan | Select-Object -Last 1)

    if ($script:BackupFile) {
        Write-Info "已删除的注册表项备份在: $($script:BackupFile)"
        Write-Info "如果误删了需要的设置，双击这个文件即可恢复。"
    }
    if ($script:LogFile) {
        Write-Info "本次清理日志: $($script:LogFile)"
        if ($script:NukeRemaining -gt 0) { Write-Info "提交 Issue 时附上这个文件，方便定位问题。" }
    }

    if ($script:NukeRemaining -eq 0) {
        Write-Host "============================================================" -ForegroundColor Green
        Write-Host "  [+] 微软 OfficePLUS 及关联组件已全部清除。" -ForegroundColor Green
        Write-Host "============================================================" -ForegroundColor Green
    } else {
        Write-Host "============================================================" -ForegroundColor Red
        Write-Host "  [!] 还有 $($script:NukeRemaining) 处残留没能删除，见上方列表。" -ForegroundColor Red
        Write-Host "  建议重启电脑后再运行一次；仍然删不掉的话，欢迎到 GitHub 提交 Issue。" -ForegroundColor Red
        Write-Host "============================================================" -ForegroundColor Red
    }

    if ($script:LogFile) {
        try { Stop-Transcript | Out-Null } catch { }
    }
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
    if ($script:NukeRemaining -gt 0) { exit 1 }
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
