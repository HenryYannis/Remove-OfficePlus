# 检查非管理员提权时，会重新执行本地这份脚本（带上原参数），而不是去 GitHub 重新下载。
# 只从脚本里取出函数来测，不会真的运行清理。
$ErrorActionPreference = 'Stop'
$script = (Resolve-Path (Join-Path $PSScriptRoot '..\..\scripts\Remove-OfficePlus.ps1')).Path
$ast = [System.Management.Automation.Language.Parser]::ParseFile($script, [ref]$null, [ref]$null)
$fn = $ast.FindAll({ param($n) $n -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $n.Name -eq 'Get-ElevationArguments' }, $true) | Select-Object -First 1
if (-not $fn) { throw '找不到 Get-ElevationArguments' }
. ([scriptblock]::Create($fn.Extent.Text))

$ScriptPath = $script; $Scan = $false; $Nuke = $true; $Force = $true
$a = Get-ElevationArguments
Write-Host "本地模式参数: $a"
if ($a -notlike "*-File `"$script`"*") { throw '没有执行本地脚本' }
if ($a -notmatch ' -Nuke' -or $a -notmatch ' -Force') { throw '原参数丢失' }
if ($a -match 'raw.githubusercontent') { throw '本地运行却去下载了远程脚本' }

$ScriptPath = $null
$b = Get-ElevationArguments
if ($b -notmatch 'raw.githubusercontent') { throw '在线模式参数不对' }
Write-Host '提权参数检查通过'
