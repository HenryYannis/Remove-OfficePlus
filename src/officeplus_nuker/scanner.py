import os
import winreg
import subprocess
import ctypes
from dataclasses import dataclass, field
from typing import List
from .constants import TARGET_PROCESSES, TARGET_SERVICES, TARGET_REGISTRY_KEYS, get_target_directories

@dataclass
class ScanReport:
    is_admin: bool
    processes: List[str] = field(default_factory=list)
    services: List[str] = field(default_factory=list)
    registry_keys: List[str] = field(default_factory=list)
    directories: List[str] = field(default_factory=list)

    @property
    def total_threats(self) -> int:
        return len(self.processes) + len(self.services) + len(self.registry_keys) + len(self.directories)

    @property
    def is_clean(self) -> bool:
        return self.total_threats == 0

def is_admin() -> bool:
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False

def scan_processes() -> List[str]:
    found = []
    try:
        output = subprocess.check_output(
            ["tasklist", "/FO", "CSV", "/NH"],
            creationflags=subprocess.CREATE_NO_WINDOW,
            encoding="utf-8",
            errors="ignore"
        )
        for line in output.strip().splitlines():
            parts = [p.strip(' "') for p in line.split('","')]
            if parts:
                proc_name = parts[0]
                for target in TARGET_PROCESSES:
                    if proc_name.lower() == target.lower():
                        found.append(f"{proc_name} (PID: {parts[1]})")
    except Exception:
        pass
    return found

def scan_services() -> List[str]:
    found = []
    for svc in TARGET_SERVICES:
        try:
            output = subprocess.check_output(
                ["sc.exe", "query", svc],
                creationflags=subprocess.CREATE_NO_WINDOW,
                encoding="utf-8",
                errors="ignore"
            )
            if "RUNNING" in output or "STOPPED" in output or "PAUSED" in output:
                found.append(svc)
        except Exception:
            pass
    return found

def scan_registry() -> List[str]:
    found = []
    root_map = {
        "HKLM": winreg.HKEY_LOCAL_MACHINE,
        "HKCU": winreg.HKEY_CURRENT_USER,
    }
    for subkey, root_name in TARGET_REGISTRY_KEYS:
        root = root_map.get(root_name)
        if not root:
            continue
        try:
            with winreg.OpenKey(root, subkey, 0, winreg.KEY_READ):
                found.append(f"{root_name}\\{subkey}")
        except FileNotFoundError:
            pass
        except PermissionError:
            found.append(f"{root_name}\\{subkey} [需管理员权限读取]")
        except Exception:
            pass
    return found

def scan_directories() -> List[str]:
    found = []
    for d in get_target_directories():
        if os.path.exists(d):
            found.append(d)
    return found

def run_scan() -> ScanReport:
    return ScanReport(
        is_admin=is_admin(),
        processes=scan_processes(),
        services=scan_services(),
        registry_keys=scan_registry(),
        directories=scan_directories()
    )
