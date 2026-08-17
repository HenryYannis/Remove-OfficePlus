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
            subprocess.run(
                ["taskkill", "/F", "/IM", proc],
                creationflags=subprocess.CREATE_NO_WINDOW,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
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
    try:
        key = winreg.OpenKey(root, subkey, 0, winreg.KEY_ALL_ACCESS)
    except FileNotFoundError:
        return
    except Exception:
        return

    while True:
        try:
            child_name = winreg.EnumKey(key, 0)
            _delete_reg_key_tree(root, f"{subkey}\\{child_name}")
        except OSError:
            break
    winreg.CloseKey(key)
    try:
        winreg.DeleteKey(root, subkey)
    except Exception:
        pass

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
        try:
            # Check existence first
            with winreg.OpenKey(root, subkey, 0, winreg.KEY_READ):
                exists = True
        except FileNotFoundError:
            exists = False
        except Exception:
            exists = True

        if exists:
            _delete_reg_key_tree(root, subkey)
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
                    subprocess.run(
                        ["schtasks", "/Delete", "/TN", task_name, "/F"],
                        creationflags=subprocess.CREATE_NO_WINDOW,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL
                    )
                    cleaned.append(task_name)
    except Exception:
        pass
    return cleaned

def delete_directories() -> List[str]:
    deleted = []
    for d in get_target_directories():
        if os.path.exists(d):
            try:
                shutil.rmtree(d, ignore_errors=True)
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
