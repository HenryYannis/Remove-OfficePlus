"""
端到端测试：普通用户在用电脑，UAC 时输入了另一个管理员账号的密码，
清理程序于是以管理员身份运行。此时必须清理“正在用电脑的那个用户”的数据，
而不是管理员自己的。

做法：新建一个本地账号 e2eother，手工给它建个人文件夹并加载它的注册表（不需要真的登录），
在它名下种下 OfficePLUS 残留；同时在当前账号（扮演管理员）的 HKCU 里也种一份当对照。
清理时把“当前桌面会话的登录用户”换成 e2eother（Python 版替换函数，PowerShell 版见 other-user.ps1），
检查 e2eother 的残留被清除、备份在他的文档里，而管理员自己的那份完全没动。

用法（需要管理员权限）：
    python tests/e2e/other_user.py plant
    python tests/e2e/other_user.py run-python   # 用 Python 版清理
    python tests/e2e/other_user.py verify
    python tests/e2e/other_user.py cleanup
"""
import glob
import os
import secrets
import shutil
import subprocess
import sys
import winreg

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "src"))
from remove_officeplus import user_context  # noqa: E402
from remove_officeplus.constants import TARGET_REGISTRY_KEYS  # noqa: E402

USER = "e2eother"
PROFILE = os.path.join(os.environ.get("SystemDrive", "C:") + "\\", "Users", USER)
PROFILE_LIST = r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\ProfileList"
USER_KEYS = [k for k, root in TARGET_REGISTRY_KEYS if root == "HKCU"]
USER_DIRS = [os.path.join(PROFILE, "AppData", sub, name)
             for sub in ("Local", "Roaming") for name in ("OfficePLUS", "Microsoft OfficePLUS")]
BACKUP_DIR = os.path.join(PROFILE, "Documents", "Remove-OfficePlus 备份")


def run(cmd, check=False):
    r = subprocess.run(cmd, capture_output=True, text=True, errors="replace")
    if check and r.returncode != 0:
        sys.exit(f"命令失败: {cmd}\n{r.stdout}{r.stderr}")
    return r


def sid():
    return user_context._account_sid("", USER)


def exists(root, path):
    try:
        winreg.CloseKey(winreg.OpenKey(root, path))
        return True
    except FileNotFoundError:
        return False


def plant():
    run(["net", "user", USER, "Aa1!" + secrets.token_hex(4), "/add"], check=True)
    s = sid()
    os.makedirs(PROFILE, exist_ok=True)
    shutil.copy(os.path.join(os.path.dirname(PROFILE), "Default", "NTUSER.DAT"), os.path.join(PROFILE, "NTUSER.DAT"))
    with winreg.CreateKey(winreg.HKEY_LOCAL_MACHINE, f"{PROFILE_LIST}\\{s}") as k:
        winreg.SetValueEx(k, "ProfileImagePath", 0, winreg.REG_EXPAND_SZ, PROFILE)
    run(["reg.exe", "load", f"HKU\\{s}", os.path.join(PROFILE, "NTUSER.DAT")], check=True)
    for key in USER_KEYS:
        for root in (winreg.HKEY_USERS, winreg.HKEY_CURRENT_USER):
            path = f"{s}\\{key}" if root == winreg.HKEY_USERS else key
            with winreg.CreateKey(root, path + r"\Sub") as k:
                winreg.SetValueEx(k, "v", 0, winreg.REG_SZ, "fake")
    for d in USER_DIRS:
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "fake.dll"), "w") as fh:
            fh.write("fake")
    print(f"已为 {USER}（{s}）种下 {len(USER_KEYS)} 项注册表、{len(USER_DIRS)} 个目录，当前账号 HKCU 也种了一份对照。")


def run_python():
    user_context._session_account = lambda: ("", USER)
    target = user_context.get_target_user()
    if target.sid != sid():
        sys.exit(f"❌ 没有识别出登录用户 {USER}: {target}")
    from remove_officeplus import cleaner
    cleaner.run_nuke()
    print(f"Python 版清理完成，备份: {cleaner.LAST_BACKUP_PATH}")


def verify():
    s = sid()
    left = [f"HKU\\{s}\\{k}" for k in USER_KEYS if exists(winreg.HKEY_USERS, f"{s}\\{k}")]
    left += [d for d in USER_DIRS if os.path.exists(d)]
    hurt = [f"HKCU\\{k}" for k in USER_KEYS if not exists(winreg.HKEY_CURRENT_USER, k + r"\Sub")]
    backups = glob.glob(os.path.join(BACKUP_DIR, "*.reg"))
    if left:
        print(f"❌ {USER} 的残留没清掉：", *left, sep="\n  ")
    if hurt:
        print("❌ 动了管理员自己的注册表（应该只清理登录用户的）：", *hurt, sep="\n  ")
    if not backups:
        print(f"❌ 备份没有放在 {USER} 的文档里：{BACKUP_DIR}")
    if left or hurt or not backups:
        sys.exit(1)
    for f in backups:
        os.remove(f)
    print(f"✅ 只清理了登录用户 {USER} 的残留，备份在他的文档里，管理员自己的数据没动。")


def cleanup():
    s = sid()
    for key in USER_KEYS:
        run(["reg.exe", "delete", f"HKCU\\{key}", "/f"])
    if s:
        run(["reg.exe", "unload", f"HKU\\{s}"])
        run(["reg.exe", "delete", f"HKLM\\{PROFILE_LIST}\\{s}", "/f"])
    shutil.rmtree(PROFILE, ignore_errors=True)
    run(["net", "user", USER, "/delete"])


if __name__ == "__main__":
    {"plant": plant, "run-python": run_python, "verify": verify, "cleanup": cleanup}[sys.argv[1]]()
