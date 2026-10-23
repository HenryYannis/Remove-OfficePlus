"""
端到端测试辅助脚本：在一台干净的 Windows（例如 GitHub Actions 的 windows-latest）上
“假装”装了 OfficePLUS，清理完再检查是否删干净、有没有误删别的东西。

用法（需要管理员权限）：
    python tests/e2e/fake_residue.py plant    # 种下假残留和“哨兵”（不应被删除的对照项）
    python tests/e2e/fake_residue.py verify   # 检查假残留是否全部清除、哨兵是否完好
    python tests/e2e/fake_residue.py cleanup  # 清掉哨兵等测试遗留

注意：假残留的位置取自 constants.py，只能验证“删除逻辑是否可靠”，
不能证明这些路径就是真实 OfficePLUS 的安装位置。
"""
import os
import stat
import subprocess
import sys
import tempfile
import time
import winreg

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "src"))
from remove_officeplus.constants import (  # noqa: E402
    TARGET_REGISTRY_KEYS,
    TARGET_SERVICES,
    get_target_directories,
)

HIVES = {"HKLM": winreg.HKEY_LOCAL_MACHINE, "HKCU": winreg.HKEY_CURRENT_USER}
VIEW = winreg.KEY_WOW64_64KEY  # 显式使用 64 位视图，路径里自带 Wow6432Node 的照写

FAKE_TASKS = [r"OfficePLUS Fake Updater", r"\OfficePLUS\FakeDaily"]
FAKE_PROCESS_NAME = "OfficePLUS.exe"

# 哨兵：名字相近但不属于 OfficePLUS，清理后必须还在
SENTINEL_KEY = ("HKCU", r"Software\Microsoft\Office\Word\Addins\SentinelKeepMe")
SENTINEL_DIR = os.path.join(os.environ["LOCALAPPDATA"], "SentinelKeepMe")
SENTINEL_TASK = "SentinelKeepMe"


def run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True, errors="replace")


def key_exists(hive, path):
    try:
        winreg.CloseKey(winreg.OpenKey(HIVES[hive], path, 0, winreg.KEY_READ | VIEW))
        return True
    except FileNotFoundError:
        return False


def create_key(hive, path, with_children=True):
    key = winreg.CreateKeyEx(HIVES[hive], path, 0, winreg.KEY_ALL_ACCESS | VIEW)
    winreg.SetValueEx(key, "FriendlyName", 0, winreg.REG_SZ, "Fake OfficePLUS")
    winreg.SetValueEx(key, "LoadBehavior", 0, winreg.REG_DWORD, 3)
    winreg.CloseKey(key)
    if with_children:
        # 多层子键，检验递归删除
        child = winreg.CreateKeyEx(HIVES[hive], path + r"\Sub\Deeper", 0, winreg.KEY_ALL_ACCESS | VIEW)
        winreg.SetValueEx(child, "x", 0, winreg.REG_SZ, "y")
        winreg.CloseKey(child)


def task_exists(name):
    return run(["schtasks", "/Query", "/TN", name]).returncode == 0


def service_exists(name):
    return run(["sc.exe", "query", name]).returncode != 1060  # 1060 = 服务不存在


def process_running(name):
    out = run(["tasklist", "/FI", f"IMAGENAME eq {name}", "/FO", "CSV", "/NH"]).stdout
    return name.lower() in out.lower()


def plant():
    for path, hive in TARGET_REGISTRY_KEYS:
        create_key(hive, path)
    for d in get_target_directories():
        os.makedirs(os.path.join(d, "bin"), exist_ok=True)
        f = os.path.join(d, "bin", "readonly.dll")
        with open(f, "w") as fh:
            fh.write("fake")
        os.chmod(f, stat.S_IREAD)  # 只读文件，检验强删
        with open(os.path.join(d, "中文文件名.log"), "w", encoding="utf-8") as fh:
            fh.write("fake")
    for svc in TARGET_SERVICES:
        r = run(["sc.exe", "create", svc, "binPath=", r"C:\Windows\System32\cmd.exe /c exit", "start=", "demand"])
        print(f"create service {svc}: {r.returncode}")
    for t in FAKE_TASKS + [SENTINEL_TASK]:
        r = run(["schtasks", "/Create", "/TN", t, "/TR", "cmd /c exit", "/SC", "ONCE", "/ST", "23:59", "/F"])
        print(f"create task {t}: {r.returncode}")
    # 假进程：把 ping.exe 复制成 OfficePLUS.exe 跑一小时
    fake_exe = os.path.join(tempfile.gettempdir(), FAKE_PROCESS_NAME)
    with open(r"C:\Windows\System32\PING.EXE", "rb") as src, open(fake_exe, "wb") as dst:
        dst.write(src.read())
    subprocess.Popen([fake_exe, "-n", "3600", "127.0.0.1"], stdout=subprocess.DEVNULL, creationflags=0x08000000)
    time.sleep(1)
    # 哨兵
    create_key(SENTINEL_KEY[0], SENTINEL_KEY[1], with_children=False)
    os.makedirs(SENTINEL_DIR, exist_ok=True)

    missing = [p for p, h in TARGET_REGISTRY_KEYS if not key_exists(h, p)]
    missing += [d for d in get_target_directories() if not os.path.isdir(d)]
    missing += [s for s in TARGET_SERVICES if not service_exists(s)]
    missing += [t for t in FAKE_TASKS if not task_exists(t)]
    if not process_running(FAKE_PROCESS_NAME):
        missing.append(FAKE_PROCESS_NAME)
    if missing:
        print("种植失败：", *missing, sep="\n  ")
        sys.exit(2)
    print(f"已种下假残留：注册表 {len(TARGET_REGISTRY_KEYS)} 项、目录 {len(get_target_directories())} 个、"
          f"服务 {len(TARGET_SERVICES)} 个、计划任务 {len(FAKE_TASKS)} 个、进程 1 个")


def verify():
    left = [f"注册表 {h}\\{p}" for p, h in TARGET_REGISTRY_KEYS if key_exists(h, p)]
    left += [f"目录 {d}" for d in get_target_directories() if os.path.exists(d)]
    left += [f"服务 {s}" for s in TARGET_SERVICES if service_exists(s)]
    left += [f"计划任务 {t}" for t in FAKE_TASKS if task_exists(t)]
    if process_running(FAKE_PROCESS_NAME):
        left.append(f"进程 {FAKE_PROCESS_NAME}")

    hurt = []
    if not key_exists(*SENTINEL_KEY):
        hurt.append(f"注册表 {SENTINEL_KEY[0]}\\{SENTINEL_KEY[1]}")
    if not os.path.isdir(SENTINEL_DIR):
        hurt.append(f"目录 {SENTINEL_DIR}")
    if not task_exists(SENTINEL_TASK):
        hurt.append(f"计划任务 {SENTINEL_TASK}")

    if left:
        print("❌ 没删干净：", *left, sep="\n  ")
    if hurt:
        print("❌ 误删了不该删的东西：", *hurt, sep="\n  ")
    if left or hurt:
        sys.exit(1)
    print("✅ 假残留已全部清除，哨兵完好。")


def cleanup():
    try:
        winreg.DeleteKeyEx(HIVES[SENTINEL_KEY[0]], SENTINEL_KEY[1], VIEW, 0)
    except OSError:
        pass
    run(["schtasks", "/Delete", "/TN", SENTINEL_TASK, "/F"])
    if os.path.isdir(SENTINEL_DIR):
        os.rmdir(SENTINEL_DIR)


if __name__ == "__main__":
    action = sys.argv[1] if len(sys.argv) > 1 else ""
    {"plant": plant, "verify": verify, "cleanup": cleanup}.get(action, lambda: sys.exit(__doc__))()
