"""用真机样本核对识别规则。

docs/real-test/ 里是我 2026-10-23 在一台装了 OfficePLUS 3.10.0.28331 的 Win10 电脑上
实际清理时留下的注册表备份和清理日志。这里检查：样本里出现的每个注册表项、
进程、服务、目录，rules.json 都能认出来。以后改规则时，如果把真实存在的项漏掉了，CI 会报错。
只读文件，不碰注册表，任何系统都能跑。
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RULES = json.loads((ROOT / "src" / "remove_officeplus" / "rules.json").read_text(encoding="utf-8"))
SAMPLE = ROOT / "docs" / "real-test"
HIVES = {"HKEY_LOCAL_MACHINE": "HKLM", "HKEY_CURRENT_USER": "HKCU"}
# 目录规则里的环境变量，换成样本那台电脑上的实际路径
ENV = {
    "ProgramFiles": r"C:\Program Files",
    "ProgramFiles(x86)": r"C:\Program Files (x86)",
    "ProgramData": r"C:\ProgramData",
    "LocalAppData": r"C:\Users\HP\AppData\Local",
    "AppData": r"C:\Users\HP\AppData\Roaming",
}


def norm(s):
    return s.replace("/", "\\").rstrip("\\").lower()


def registry_known(hive, path, values):
    if (hive, norm(path)) in {(h, norm(p)) for h, p in RULES["registry_keys"]}:
        return True
    # 按特征识别：在 addin_parents 下，且名称或 FriendlyName/Description/Manifest 含关键字
    kw = RULES["addin_keyword"].lower()
    parent, _, name = path.rpartition("\\")
    for h, tmpl in RULES["addin_parents"]:
        for app in RULES["addin_apps"]:
            if h == hive and norm(tmpl.format(app=app)) == norm(parent):
                fields = [name] + [values.get(k, "") for k in ("FriendlyName", "Description", "Manifest")]
                if any(kw in f.lower() for f in fields):
                    return True
    return False


def parse_reg(text):
    keys, cur = [], None
    for line in text.splitlines():
        m = re.match(r"^\[(HKEY_[A-Z_]+)\\(.+)\]$", line.strip())
        if m:
            cur = (HIVES[m.group(1)], m.group(2), {})
            keys.append(cur)
            continue
        m = re.match(r'^"([^"]+)"="(.*)"$', line.strip())
        if m and cur:
            cur[2][m.group(1)] = m.group(2)
    return keys


def main():
    errors = []
    reg_files = list(SAMPLE.glob("*.reg.txt"))
    log_files = list(SAMPLE.glob("清理日志_*.txt"))
    if not reg_files or not log_files:
        errors.append("docs/real-test 里缺少注册表备份或清理日志样本")
    for f in reg_files:
        keys = parse_reg(f.read_text(encoding="utf-8"))
        if not keys:
            errors.append(f"{f.name} 里没有解析出注册表项")
        for hive, path, values in keys:
            if not registry_known(hive, path, values):
                errors.append(f"规则漏掉了注册表项 {hive}\\{path}")
    procs = {p.lower() for p in RULES["officeplus_processes"] + RULES["office_app_processes"]}
    services = {s.lower() for s in RULES["services"]}
    dirs = {norm(ENV[base] + "\\" + sub) for base, sub in RULES["directories"]}
    for f in log_files:
        for line in f.read_text(encoding="utf-8").splitlines():
            if "[失败]" in line or "[错误]" in line:
                errors.append(f"真机清理日志里有失败记录: {line}")
            m = re.search(r"已结束进程: (.+?)(\.exe)?$", line, re.I)
            if m and m.group(1).lower() not in procs:
                errors.append(f"规则漏掉了进程 {m.group(1)}")
            m = re.search(r"已删除服务: (.+)$", line)
            if m and m.group(1).strip().lower() not in services:
                errors.append(f"规则漏掉了服务 {m.group(1)}")
            m = re.search(r"已删除目录: (.+)$", line)
            if m and norm(m.group(1)) not in dirs:
                errors.append(f"规则漏掉了目录 {m.group(1)}")
    if errors:
        print("\n".join("[x] " + e for e in errors))
        return 1
    print(f"[ok] 真机样本里的注册表项、进程、服务、目录全部能被规则识别（{len(reg_files)} 份备份，{len(log_files)} 份日志）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
