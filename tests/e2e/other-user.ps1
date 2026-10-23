# 端到端测试（PowerShell 版）：模拟“普通用户 e2eother 在用电脑，脚本以另一个管理员账号运行”。
# 先用 tests/e2e/other_user.py plant 准备好 e2eother，再运行本文件，最后用 other_user.py verify 检查。
# 做法：在同一个 PowerShell 进程里预先放一个假的 RemoveOfficePlus.Wts 类型，
# 让脚本读到的“当前桌面会话登录用户”是 e2eother，其余逻辑全部照常运行。
$ErrorActionPreference = 'Stop'
Add-Type -Namespace RemoveOfficePlus -Name Wts -MemberDefinition @"
public static string Query(int sessionId, int infoClass) { return infoClass == 5 ? "e2eother" : ""; }
"@
$script = (Resolve-Path (Join-Path $PSScriptRoot '..\..\scripts\Remove-OfficePlus.ps1')).Path
$ErrorActionPreference = 'Continue'
& $script -Nuke -Force
exit $LASTEXITCODE
