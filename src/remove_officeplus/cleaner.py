import os
import sys
import shutil
import winreg
import subprocess
import ctypes
from typing import List, Tuple
from .constants import TARGET_PROCESSES, TARGET_SERVICES, TARGET_REGISTRY_KEYS, get_target_directories
from .scanner import is_admin, list_scheduled_tasks, is_officeplus_task
from .backup import backup_registry
from .user_context import resolve_key

# 最近一次清理生成的注册表备份文件路径（没有可备份的项时为 None）
LAST_BACKUP_PATH = None

def _relaunch_command() -> Tuple[str, List[str]]:
    """以管理员身份重新启动自己时要执行的程序和参数。

    以前用 python + sys.argv[0] 重新执行，只有 `python main.py` 这一种启动方式可靠：
    - `python -m remove_officeplus` 时 argv[0] 是 __main__.py，单独执行会因相对导入失败；
    - pip 安装的 remove-officeplus 命令，argv[0] 是启动器，路径可能不带 .exe；
    - 打包成 exe 后 argv[0] 就是 exe 本身，会被当成参数再传一遍，导致参数解析报错。
    现在打包版直接重新运行 exe；其余情况都用 -c 直接导入本包的入口，和怎么启动的无关。
    """
    if getattr(sys, "frozen", False):
        return sys.executable, sys.argv[1:]
    package_parent = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    code = (f"import sys; sys.path.insert(0, {package_parent!r}); "
            "from remove_officeplus.cli import main; main()")
    return sys.executable, ["-c", code] + sys.argv[1:]

def elevate() -> bool:
    """没有管理员权限时弹出 UAC，以管理员身份重新启动自己并退出当前进程。

    已经是管理员返回 True；用户在 UAC 里点了「否」等启动失败的情况返回 False，
    由调用方决定怎么处理，而不是像以前那样直接退出、让窗口莫名消失。
    """
    if is_admin():
        return True
    program, args = _relaunch_command()
    result = ctypes.windll.shell32.ShellExecuteW(
        None, "runas", program, subprocess.list2cmdline(args), os.getcwd(), 1)
    if result > 32:  # ShellExecute 返回值大于 32 表示启动成功
        sys.exit(0)
    print("[!] 没有获得管理员权限（可能在 UAC 提示中选择了「否」）。", file=sys.stderr)
    return False

def kill_processes() -> List[str]:
    killed = []
    for proc in TARGET_PROCESSES:
        try:
            res = subprocess.run(
                ["taskkill", "/F", "/IM", proc],
                creationflags=subprocess.CREATE_NO_WINDOW,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            if res.returncode == 0:  # 没在运行或结束失败都不算
                killed.append(proc)
        except Exception:
            pass
    return killed

def delete_services() -> List[str]:
    removed = []
    for svc in TARGET_SERVICES:
        try:
            subprocess.run(
                ["net", "stop", svc],
                creationflags=subprocess.CREATE_NO_WINDOW,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            res = subprocess.run(
                ["sc.exe", "delete", svc],
                creationflags=subprocess.CREATE_NO_WINDOW,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            if res.returncode == 0:
                removed.append(svc)
        except Exception:
            pass
    return removed

def _delete_reg_key_tree(root, subkey):
    """递归删除注册表键。先把子键名字全部读出来再逐个删除，
    这样某个子键删不掉时也不会反复重试、卡死。"""
    try:
        with winreg.OpenKey(root, subkey, 0, winreg.KEY_READ) as key:
            children = []
            i = 0
            while True:
                try:
                    children.append(winreg.EnumKey(key, i))
                    i += 1
                except OSError:
                    break
    except OSError:
        return  # 不存在或打不开，交给调用方复查
    for child in children:
        _delete_reg_key_tree(root, f"{subkey}\\{child}")
    try:
        winreg.DeleteKey(root, subkey)
    except OSError:
        pass

def _reg_key_exists(root, subkey) -> bool:
    try:
        with winreg.OpenKey(root, subkey, 0, winreg.KEY_READ):
            return True
    except FileNotFoundError:
        return False
    except OSError:
        return True  # 没权限读也当作还在

def clean_registry(skip=()) -> List[str]:
    """删除目标注册表项。skip 中的项（备份失败的）不删，避免无法恢复。"""
    cleaned = []
    for key, root_name in TARGET_REGISTRY_KEYS:
        if (key, root_name) in skip:
            continue
        root, subkey, reg_path = resolve_key(key, root_name)
        if _reg_key_exists(root, subkey):
            _delete_reg_key_tree(root, subkey)
            if not _reg_key_exists(root, subkey):  # 删完复查，真的没了才算成功
                cleaned.append(reg_path)
    return cleaned

def clean_scheduled_tasks() -> List[str]:
    cleaned = []
    try:
        task_names = list_scheduled_tasks()
    except Exception:
        return cleaned
    for task_name in task_names:
        if not is_officeplus_task(task_name):
            continue
        res = subprocess.run(
            ["schtasks", "/Delete", "/TN", task_name, "/F"],
            creationflags=subprocess.CREATE_NO_WINDOW,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        if res.returncode == 0:
            cleaned.append(task_name)
    return cleaned

def _on_rm_error(func, path, exc_info):
    import stat
    try:
        os.chmod(path, stat.S_IWRITE)
        func(path)
    except Exception:
        pass

def delete_directories() -> List[str]:
    deleted = []
    for d in get_target_directories():
        if os.path.exists(d):
            try:
                shutil.rmtree(d, onerror=_on_rm_error)
                if not os.path.exists(d):
                    deleted.append(d)
            except Exception:
                pass
    return deleted

def run_nuke() -> Tuple[List[str], List[str], List[str], List[str], List[str]]:
    """Execute complete purge of OfficePLUS."""
    global LAST_BACKUP_PATH
    if not elevate():
        print("[!] 没有管理员权限，本次未做任何修改。")
        return [], [], [], [], []
    procs = kill_processes()
    svcs = delete_services()
    existing = [(k, r) for k, r in TARGET_REGISTRY_KEYS if _reg_key_exists(*resolve_key(k, r)[:2])]
    LAST_BACKUP_PATH, backup_failed = backup_registry(existing)
    regs = clean_registry(skip=backup_failed)
    tasks = clean_scheduled_tasks()
    dirs = delete_directories()
    return procs, svcs, regs, tasks, dirs
