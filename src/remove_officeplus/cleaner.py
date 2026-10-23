import os
import sys
import shutil
import winreg
import subprocess
import ctypes
from typing import List, Tuple
from .constants import TARGET_PROCESSES, TARGET_SERVICES, TARGET_REGISTRY_KEYS, get_target_directories
from .scanner import is_admin

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

def clean_registry() -> List[str]:
    cleaned = []
    root_map = {
        "HKLM": winreg.HKEY_LOCAL_MACHINE,
        "HKCU": winreg.HKEY_CURRENT_USER,
    }
    for subkey, root_name in TARGET_REGISTRY_KEYS:
        root = root_map.get(root_name)
        if not root:
            continue
        if _reg_key_exists(root, subkey):
            _delete_reg_key_tree(root, subkey)
            if not _reg_key_exists(root, subkey):  # 删完复查，真的没了才算成功
                cleaned.append(f"{root_name}\\{subkey}")
    return cleaned

def clean_scheduled_tasks() -> List[str]:
    cleaned = []
    try:
        output = subprocess.check_output(
            ["schtasks", "/Query", "/FO", "CSV", "/NH"],
            creationflags=subprocess.CREATE_NO_WINDOW,
            encoding="utf-8",
            errors="ignore"
        )
        for line in output.strip().splitlines():
            parts = [p.strip(' "') for p in line.split('","')]
            if parts:
                task_name = parts[0]
                if "officeplus" in task_name.lower():
                    res = subprocess.run(
                        ["schtasks", "/Delete", "/TN", task_name, "/F"],
                        creationflags=subprocess.CREATE_NO_WINDOW,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL
                    )
                    if res.returncode == 0:
                        cleaned.append(task_name)
    except Exception:
        pass
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
    elevate()
    procs = kill_processes()
    svcs = delete_services()
    regs = clean_registry()
    tasks = clean_scheduled_tasks()
    dirs = delete_directories()
    return procs, svcs, regs, tasks, dirs
