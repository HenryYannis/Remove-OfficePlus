"""调用系统命令、查进程、检查目录时共用的 Windows 小工具。

- system_exe：系统命令（reg、taskkill、sc、net、schtasks、tasklist）一律用 System32 下的绝对路径。
  只写文件名时，Windows 会先在程序自己所在的目录（比如「下载」）里找同名 exe，
  有人在那里放一个假的 taskkill.exe，就会被以管理员身份执行。
- list_processes：列出进程的名字、PID、会话号和程序路径，用来只关当前会话的 Office、
  只结束程序路径确实属于 OfficePLUS 的进程。
- is_reparse_point：备份和日志写进用户自己的「文档」，写之前确认文件夹不是联接/符号链接，
  避免被引到系统目录里去。
"""
import csv
import ctypes
import os
import stat
import subprocess
from typing import List, NamedTuple, Optional

# 单个系统命令最长等多久（秒）。超时按失败处理并记进日志，不让命令行或 GUI 卡死
COMMAND_TIMEOUT = 60

_PROCESS_QUERY_LIMITED_INFORMATION = 0x1000


def system_dir() -> str:
    """真正的系统目录（通常是 C:\\Windows\\System32）。优先问系统，不信环境变量。"""
    try:
        buf = ctypes.create_unicode_buffer(260)
        if ctypes.windll.kernel32.GetSystemDirectoryW(buf, 260) and buf.value:
            return buf.value
    except Exception:
        pass
    return os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32")


def system_exe(name: str) -> str:
    """System32 下系统命令的绝对路径，例如 system_exe("taskkill.exe")。"""
    return os.path.join(system_dir(), name)


def current_session_id() -> Optional[int]:
    """当前进程所在的会话号；取不到返回 None。"""
    try:
        kernel32 = ctypes.windll.kernel32
        session = ctypes.c_ulong()
        if kernel32.ProcessIdToSessionId(kernel32.GetCurrentProcessId(), ctypes.byref(session)):
            return session.value
    except Exception:
        pass
    return None


def process_path(pid: int) -> Optional[str]:
    """进程的程序完整路径；没权限或进程已退出时返回 None。"""
    try:
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.OpenProcess(_PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not handle:
            return None
        try:
            size = ctypes.c_ulong(32768)
            buf = ctypes.create_unicode_buffer(size.value)
            if kernel32.QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(size)):
                return buf.value
        finally:
            kernel32.CloseHandle(handle)
    except Exception:
        pass
    return None


class ProcessInfo(NamedTuple):
    name: str
    pid: int
    session: Optional[int]


def parse_tasklist_csv(output: str) -> List[ProcessInfo]:
    """解析 `tasklist /FO CSV /NH` 的输出：映像名称, PID, 会话名, 会话#, 内存。
    某一行格式不对只跳过这一行，不影响后面的进程。"""
    procs = []
    for row in csv.reader(output.splitlines()):
        try:
            if len(row) < 2:
                continue
            session = int(row[3]) if len(row) > 3 and row[3].strip().isdigit() else None
            procs.append(ProcessInfo(row[0].strip(), int(row[1]), session))
        except (ValueError, IndexError):
            continue
    return procs


def list_processes() -> List[ProcessInfo]:
    output = subprocess.check_output(
        [system_exe("tasklist.exe"), "/FO", "CSV", "/NH"],
        creationflags=subprocess.CREATE_NO_WINDOW,
        stdin=subprocess.DEVNULL,
        encoding="utf-8",
        errors="ignore",
        timeout=COMMAND_TIMEOUT,
    )
    return parse_tasklist_csv(output)


def is_officeplus_image(path: Optional[str], keyword: str) -> bool:
    """程序所在的文件夹路径里含 keyword（不区分大小写），才算 OfficePLUS 自己的进程。
    DeepLink.exe、OfficePLUS.exe 这类名字很常见，只看进程名会误杀别的软件。"""
    return bool(path) and keyword.lower() in os.path.dirname(path).lower()


def is_reparse_point(path: str) -> bool:
    """path 本身是联接、符号链接等重解析点时返回 True；不存在返回 False。"""
    try:
        st = os.lstat(path)
    except OSError:
        return False
    if stat.S_ISLNK(st.st_mode):
        return True
    attrs = getattr(st, "st_file_attributes", 0)
    return bool(attrs & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))
