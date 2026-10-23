import csv
import os
import sys
import winreg
import subprocess
import ctypes
from dataclasses import dataclass, field
from typing import List
from .user_context import resolve_key
from .constants import OFFICEPLUS_PROCESSES, OFFICE_APP_PROCESSES, TARGET_SERVICES, TARGET_REGISTRY_KEYS, get_target_directories

@dataclass
class ScanReport:
    is_admin: bool
    processes: List[str] = field(default_factory=list)
    services: List[str] = field(default_factory=list)
    registry_keys: List[str] = field(default_factory=list)
    directories: List[str] = field(default_factory=list)
    scheduled_tasks: List[str] = field(default_factory=list)
    # 正在运行的正常 Office 程序，仅用于清理前提醒保存，不计入威胁
    office_apps: List[str] = field(default_factory=list)

    @property
    def total_threats(self) -> int:
        return len(self.processes) + len(self.services) + len(self.registry_keys) + len(self.directories) + len(self.scheduled_tasks)

    @property
    def is_clean(self) -> bool:
        return self.total_threats == 0

def is_admin() -> bool:
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False

def scan_processes(targets=OFFICEPLUS_PROCESSES) -> List[str]:
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
                for target in targets:
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
    for key, root_name in TARGET_REGISTRY_KEYS:
        root, subkey, reg_path = resolve_key(key, root_name)
        try:
            with winreg.OpenKey(root, subkey, 0, winreg.KEY_READ):
                found.append(reg_path)
        except FileNotFoundError:
            pass
        except PermissionError:
            found.append(f"{reg_path} [需管理员权限读取]")
        except Exception:
            pass
    return found

def is_officeplus_task(task_name: str) -> bool:
    return "officeplus" in task_name.lower()

def list_scheduled_tasks() -> List[str]:
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

def scan_scheduled_tasks() -> List[str]:
    """和 PowerShell 版一样，扫描时也报告 OfficePLUS 的计划任务；
    清理后复检时，没删掉的计划任务也会如实列出来。"""
    try:
        return [t for t in list_scheduled_tasks() if is_officeplus_task(t)]
    except Exception:
        return []

def scan_directories() -> List[str]:
    found = []
    for d in get_target_directories():
        if os.path.exists(d):
            found.append(d)
    return found

def _safe(fn, *args):
    """单独一项检测出错时只跳过这一项，不让整个扫描崩掉。

    GUI 在后台线程里调用 run_scan，一旦抛出异常线程就悄悄结束，
    按钮一直是灰的、界面停在“正在扫描”，用户只能关掉程序。
    """
    try:
        return fn(*args)
    except Exception as e:
        print(f"[!] {fn.__name__} 检测出错，已跳过：{e!r}", file=sys.stderr)
        return []

def run_scan() -> ScanReport:
    return ScanReport(
        is_admin=is_admin(),
        processes=_safe(scan_processes),
        services=_safe(scan_services),
        registry_keys=_safe(scan_registry),
        directories=_safe(scan_directories),
        scheduled_tasks=_safe(scan_scheduled_tasks),
        office_apps=_safe(scan_processes, OFFICE_APP_PROCESSES),
    )
