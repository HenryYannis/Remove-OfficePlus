import csv
import os
import sys
import shutil
import winreg
import subprocess
import ctypes
from typing import List, Tuple
from .constants import TARGET_PROCESSES, TARGET_SERVICES, TARGET_REGISTRY_KEYS, get_target_directories
from .scanner import is_admin
from .backup import backup_registry
from .user_context import resolve_key

# 最近一次清理生成的注册表备份文件路径（没有可备份的项时为 None）
LAST_BACKUP_PATH = None

def elevate():
    """Request UAC elevation if not admin."""
    if not is_admin():
        script = os.path.abspath(sys.argv[0])
        params = " ".join([f'"{arg}"' for arg in sys.argv[1:]])
        ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, f'"{script}" {params}', None, 1)
        sys.exit(0)

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

def _list_scheduled_tasks() -> List[str]:
    """列出所有计划任务的完整路径（如 \\OfficePLUS\\每日更新）。

    直接读 Tasks 文件夹：文件名本身就是 Unicode，不受系统语言和代码页影响。
    以前解析 schtasks 的输出并按 UTF-8 解码，中文系统上实际是 GBK，
    带中文的任务名会变成乱码，拿去删除就会失败。
    """
    windir = os.environ.get("SystemRoot", r"C:\Windows")
    system32 = os.path.join(windir, "Sysnative")  # 32 位 Python 在 64 位系统上要绕过重定向
    if not os.path.isdir(system32):
        system32 = os.path.join(windir, "System32")
    root = os.path.join(system32, "Tasks")
    names = []
    for dirpath, _, files in os.walk(root):
        rel = os.path.relpath(dirpath, root)
        prefix = "\\" if rel == "." else "\\" + rel + "\\"
        names.extend(prefix + f for f in files)
    if names:
        return names

    # 读不到文件夹时退回 schtasks，按控制台实际使用的代码页解码（中文系统是 GBK）
    output = subprocess.check_output(
        ["schtasks", "/Query", "/FO", "CSV", "/NH"],
        creationflags=subprocess.CREATE_NO_WINDOW,
        encoding=f"cp{ctypes.windll.kernel32.GetOEMCP()}",
        errors="replace",
    )
    return [row[0] for row in csv.reader(output.splitlines()) if row]

def clean_scheduled_tasks() -> List[str]:
    cleaned = []
    try:
        task_names = _list_scheduled_tasks()
    except Exception:
        return cleaned
    for task_name in task_names:
        if "officeplus" not in task_name.lower():
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
    elevate()
    procs = kill_processes()
    svcs = delete_services()
    existing = [(k, r) for k, r in TARGET_REGISTRY_KEYS if _reg_key_exists(*resolve_key(k, r)[:2])]
    LAST_BACKUP_PATH, backup_failed = backup_registry(existing)
    regs = clean_registry(skip=backup_failed)
    tasks = clean_scheduled_tasks()
    dirs = delete_directories()
    return procs, svcs, regs, tasks, dirs
