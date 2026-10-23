"""把 src/remove_officeplus/rules.json 同步进 PowerShell 脚本。

PowerShell 版可以通过 irm | iex 在线运行，那时手边只有这一个脚本文件，读不到 JSON，
所以规则以“生成代码”的形式内嵌在脚本里。规则只改 rules.json，然后运行：
    python scripts/sync_rules.py          # 写入 Remove-OfficePlus.ps1
    python scripts/sync_rules.py --check  # 只检查是否一致（CI 用），不一致时返回 1
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RULES = os.path.join(ROOT, "src", "remove_officeplus", "rules.json")
PS1 = os.path.join(ROOT, "scripts", "Remove-OfficePlus.ps1")
BEGIN = "# ---- BEGIN RULES：由 scripts/sync_rules.py 根据 rules.json 生成，请勿手改 ----"
END = "# ---- END RULES ----"

# 目录规则里的位置 → PowerShell 里的变量（用户目录指实际要清理的那个用户）
BASES = {
    "ProgramFiles": "$env:ProgramFiles",
    "ProgramFiles(x86)": "${env:ProgramFiles(x86)}",
    "ProgramData": "$env:ProgramData",
    "LocalAppData": "$UserLocalAppData",
    "AppData": "$UserAppData",
}
ROOTS = {"HKLM": "HKLM:", "HKCU": "$UserRegRoot"}


def q(text: str) -> str:
    """PowerShell 双引号字符串（注册表/目录名里没有 $ 和 `，这里只防止误用）。"""
    assert "`" not in text and '"' not in text, text
    return '"' + text + '"'


def ps_array(name: str, items) -> list:
    return [f"${name} = @("] + [f"    {item}{',' if i < len(items) - 1 else ''}" for i, item in enumerate(items)] + [")"]


def render(rules: dict) -> str:
    lines = [BEGIN]
    lines.append("# OfficePLUS 自身的进程：扫描时算作威胁")
    lines += ps_array("OfficePlusProcesses", [q(p) for p in rules["officeplus_processes"]])
    lines.append("")
    lines.append("# 正常的 Office 程序：不是威胁，只是清理时要关闭它们，才能删掉被占用的加载项文件")
    lines += ps_array("OfficeAppProcesses", [q(p) for p in rules["office_app_processes"]])
    lines.append("")
    lines.append("# 清理时要结束的全部进程")
    lines.append("$TargetProcesses = $OfficePlusProcesses + $OfficeAppProcesses")
    lines.append("")
    lines += ps_array("TargetServices", [q(s) for s in rules["services"]])
    lines.append("")
    lines.append("# 计划任务名或路径里含有这个词就算 OfficePLUS 的")
    lines.append(f"$TaskKeyword = {q(rules['task_keyword'])}")
    lines.append("")
    lines += ps_array("TargetRegistryKeys", [q(f"{ROOTS[r]}\\{p}") for r, p in rules["registry_keys"]])
    lines.append("")
    lines.append("# 系统目录取环境变量（系统不一定装在 C 盘）；哪个位置取不到就跳过，不能拼成盘符根目录")
    lines.append("$TargetDirectories = @(")
    for base, name in rules["directories"]:
        var = BASES[base]
        lines.append(f"    if ({var}) {{ Join-Path {var} {q(name)} }}")
    lines.append(")")
    lines.append("")
    lines.append("# 按特征识别（见 Find-OfficePlusAddins / Find-OfficePlusServices）")
    lines.append(f"$AddinKeyword = {q(rules['addin_keyword'])}")
    lines += ps_array("AddinApps", [q(a) for a in rules["addin_apps"]])
    lines += ps_array("AddinParents", [q(f"{ROOTS[r]}\\{p}") for r, p in rules["addin_parents"]])
    lines.append(f"$ServiceImage = {q(rules['service_image'])}")
    lines.append(END)
    return "\n".join(lines)


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")  # 英文 Windows 控制台不是 UTF-8，输出中文时不能崩
    with open(RULES, encoding="utf-8") as fh:
        block = render(json.load(fh))
    raw = open(PS1, "rb").read()
    bom = raw.startswith(b"\xef\xbb\xbf")
    crlf = b"\r\n" in raw
    text = raw.decode("utf-8-sig").replace("\r\n", "\n")
    start, end = text.find(BEGIN), text.find(END)
    if start < 0 or end < 0:
        print("找不到 PowerShell 脚本里的规则标记")
        return 1
    new = text[:start] + block + text[end + len(END):]
    if "--check" in sys.argv:
        if new != text:
            print("[FAIL] Remove-OfficePlus.ps1 里的规则和 rules.json 不一致，请运行 python scripts/sync_rules.py")
            return 1
        print("[OK] PowerShell 脚本里的规则和 rules.json 一致")
        return 0
    out = new.replace("\n", "\r\n") if crlf else new
    with open(PS1, "wb") as fh:
        fh.write((b"\xef\xbb\xbf" if bom else b"") + out.encode("utf-8"))
    print("已同步规则到 Remove-OfficePlus.ps1")
    return 0


if __name__ == "__main__":
    sys.exit(main())
