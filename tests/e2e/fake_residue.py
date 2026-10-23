"""
端到端测试辅助脚本：在一台干净的 Windows（例如 GitHub Actions 的 windows-latest）上
“假装”装了 OfficePLUS，清理完再检查是否删干净、有没有误删别的东西。

用法（需要管理员权限）：
    python tests/e2e/fake_residue.py plant    # 种下假残留和“哨兵”（不应被删除的对照项）
    python tests/e2e/fake_residue.py verify   # 检查假残留是否全部清除、哨兵是否完好
    python tests/e2e/fake_residue.py cleanup  # 清掉哨兵等测试遗留
    python tests/e2e/fake_residue.py office-scan   # 正常运行的 Word 不应被扫描当成威胁（Python 版）
    python tests/e2e/fake_residue.py office-start  # 启动一个假的 WINWORD.EXE（给 PowerShell 版测试用）
    python tests/e2e/fake_residue.py office-stop
    python tests/e2e/fake_residue.py lock-start    # 占住残留目录里的一个文件，让清理必然失败
    python tests/e2e/fake_residue.py lock-stop
    python tests/e2e/fake_residue.py backup-check  # 清理后用备份文件恢复，检查注册表是否完整回来

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

# 带中文的任务名：中文系统上命令行输出是 GBK，曾因按 UTF-8 解码而删不掉
FAKE_TASKS = [r"OfficePLUS Fake Updater", r"\OfficePLUS\FakeDaily", r"\OfficePLUS\每日更新"]
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


def start_fake(name, minutes=60):
    """把 ping.exe 复制成指定名字并后台运行，模拟一个进程。"""
    fake_exe = os.path.join(tempfile.mkdtemp(), name)
    with open(r"C:\Windows\System32\PING.EXE", "rb") as src, open(fake_exe, "wb") as dst:
        dst.write(src.read())
    subprocess.Popen([fake_exe, "-n", str(minutes * 60), "127.0.0.1"],
                     stdout=subprocess.DEVNULL, creationflags=0x08000000 | 0x00000008)
    time.sleep(1)
    if not process_running(name):
        sys.exit(f"假进程 {name} 启动失败")


def office_start():
    start_fake("WINWORD.EXE")


def office_stop():
    run(["taskkill", "/F", "/IM", "WINWORD.EXE"])


def office_scan():
    from remove_officeplus.scanner import run_scan
    office_start()
    try:
        report = run_scan()
    finally:
        office_stop()
    errors = []
    if any("WINWORD" in p.upper() for p in report.processes):
        errors.append(f"把正常运行的 Word 当成了威胁：{report.processes}")
    if not any("WINWORD" in p.upper() for p in report.office_apps):
        errors.append("没检测到正在运行的 Word，清理前就不会提醒用户保存文件")
    if not report.is_clean:
        errors.append(f"干净的系统只开着 Word，却报告有 {report.total_threats} 处威胁")
    if errors:
        print("❌", *errors, sep="\n  ")
        sys.exit(1)
    print("✅ 正常运行的 Word 没被当成威胁，且能被识别出来用于保存提醒。")


LOCK_PID_FILE = os.path.join(tempfile.gettempdir(), "officeplus_e2e_lock.pid")


def lock_start():
    """另起一个进程打开残留目录里的文件不放（不允许删除），模拟“文件被占用删不掉”。"""
    target = os.path.join(get_target_directories()[-1], "locked.dat")
    code = f"import time; f = open(r'{target}', 'w'); time.sleep(900)"
    proc = subprocess.Popen([sys.executable, "-c", code], creationflags=0x08000000 | 0x00000008)
    with open(LOCK_PID_FILE, "w") as fh:
        fh.write(str(proc.pid))
    time.sleep(2)
    try:
        os.remove(target)
        sys.exit("文件没有被占住，测试无效")
    except PermissionError:
        print(f"已占住 {target}")


def lock_stop():
    if os.path.exists(LOCK_PID_FILE):
        with open(LOCK_PID_FILE) as fh:
            run(["taskkill", "/F", "/PID", fh.read().strip()])
        os.remove(LOCK_PID_FILE)
        time.sleep(1)


def backup_check():
    import glob
    from remove_officeplus.backup import get_backup_dir
    files = sorted(glob.glob(os.path.join(get_backup_dir(), "*.reg")), key=os.path.getmtime)
    if not files:
        sys.exit(f"❌ 清理后没有生成注册表备份（{get_backup_dir()}）")
    backup = files[-1]
    print(f"备份文件: {backup}")
    r = run(["reg.exe", "import", backup, "/reg:64"])
    if r.returncode != 0:
        sys.exit(f"❌ 备份文件无法导入: {r.stderr}")
    missing = [f"{h}\\{p}" for p, h in TARGET_REGISTRY_KEYS if not key_exists(h, p + r"\Sub\Deeper")]
    # 恢复完再删掉，让后续步骤从干净状态开始
    for p, h in TARGET_REGISTRY_KEYS:
        run(["reg.exe", "delete", f"{h}\\{p}", "/f", "/reg:64"])
    for f in files:
        os.remove(f)
    if missing:
        print("❌ 用备份恢复后，这些注册表项没有回来：", *missing, sep="\n  ")
        sys.exit(1)
    print(f"✅ 备份可用：{len(TARGET_REGISTRY_KEYS)} 项注册表（含子键和值）全部恢复。")


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
    start_fake(FAKE_PROCESS_NAME)
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
    {
        "plant": plant, "verify": verify, "cleanup": cleanup,
        "office-scan": office_scan, "office-start": office_start, "office-stop": office_stop,
        "lock-start": lock_start, "lock-stop": lock_stop, "backup-check": backup_check,
    }.get(action, lambda: sys.exit(__doc__))()
