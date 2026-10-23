"""确定要清理“哪个用户”的注册表和 AppData。

普通用户双击 exe（或运行脚本）时，UAC 会让输入另一个管理员账号的密码，
程序随后以那个管理员身份运行。这时 HKCU、%APPDATA%、“文档”都指向管理员自己，
而不是正在用电脑、装了 OfficePLUS 的那个人。

这里找出当前桌面会话的登录用户；和当前进程用户不同时，改为清理他的数据。
找不到、或有任何不确定时，退回原来的做法（清理当前进程用户）。
"""
import ctypes
import os
import re
import winreg
from ctypes import wintypes
from functools import lru_cache
from typing import NamedTuple, Optional, Tuple

_WTS_USER_NAME = 5
_WTS_DOMAIN_NAME = 7
_NAME_SAM_COMPATIBLE = 2
_PROFILE_LIST = r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\ProfileList"
_SHELL_FOLDERS = r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders"


class TargetUser(NamedTuple):
    sid: Optional[str]  # None 表示就是当前进程用户（直接用 HKCU）
    name: str
    local_appdata: str
    roaming_appdata: str
    documents: str


def _my_documents() -> str:
    try:
        buf = ctypes.create_unicode_buffer(260)
        ctypes.windll.shell32.SHGetFolderPathW(None, 5, None, 0, buf)  # 5 = 我的文档
        if buf.value:
            return buf.value
    except Exception:
        pass
    return os.path.join(os.path.expanduser("~"), "Documents")


def _session_account() -> Optional[Tuple[str, str]]:
    """当前桌面会话的登录账号 (域, 用户名)；取不到返回 None。"""
    kernel32 = ctypes.WinDLL("kernel32")
    wtsapi = ctypes.WinDLL("wtsapi32")
    wtsapi.WTSQuerySessionInformationW.argtypes = [
        wintypes.HANDLE, wintypes.DWORD, ctypes.c_int,
        ctypes.POINTER(ctypes.c_void_p), ctypes.POINTER(wintypes.DWORD)]
    wtsapi.WTSFreeMemory.argtypes = [ctypes.c_void_p]

    session = wintypes.DWORD()
    if not kernel32.ProcessIdToSessionId(kernel32.GetCurrentProcessId(), ctypes.byref(session)):
        return None

    def query(info_class):
        buf, size = ctypes.c_void_p(), wintypes.DWORD()
        if not wtsapi.WTSQuerySessionInformationW(None, session, info_class, ctypes.byref(buf), ctypes.byref(size)):
            return ""
        try:
            return ctypes.wstring_at(buf.value) if buf.value else ""
        finally:
            wtsapi.WTSFreeMemory(buf)

    user = query(_WTS_USER_NAME)
    return (query(_WTS_DOMAIN_NAME), user) if user else None


def _current_account() -> Optional[Tuple[str, str]]:
    """当前进程的运行账号 (域, 用户名)。"""
    size = wintypes.DWORD(512)
    buf = ctypes.create_unicode_buffer(size.value)
    if not ctypes.WinDLL("secur32").GetUserNameExW(_NAME_SAM_COMPATIBLE, buf, ctypes.byref(size)):
        return None
    domain, _, user = buf.value.rpartition("\\")
    return domain, user


def _account_sid(domain: str, user: str) -> Optional[str]:
    advapi32 = ctypes.WinDLL("advapi32")
    sid = ctypes.create_string_buffer(256)
    sid_size = wintypes.DWORD(256)
    dom = ctypes.create_unicode_buffer(256)
    dom_size = wintypes.DWORD(256)
    use = wintypes.DWORD()
    name = f"{domain}\\{user}" if domain else user
    if not advapi32.LookupAccountNameW(None, name, sid, ctypes.byref(sid_size), dom,
                                       ctypes.byref(dom_size), ctypes.byref(use)):
        return None
    text = wintypes.LPWSTR()
    if not advapi32.ConvertSidToStringSidW(sid, ctypes.byref(text)):
        return None
    try:
        return text.value
    finally:
        ctypes.windll.kernel32.LocalFree(text)


def _shell_folder(sid: str, value: str, profile: str, default: str) -> str:
    try:
        with winreg.OpenKey(winreg.HKEY_USERS, f"{sid}\\{_SHELL_FOLDERS}") as key:
            path = winreg.QueryValueEx(key, value)[0]
        path = re.sub("%USERPROFILE%", lambda _: profile, path, flags=re.IGNORECASE)
        if "%" not in path:
            return os.path.normpath(path)
    except OSError:
        pass
    return os.path.join(profile, default)


def _current_user() -> TargetUser:
    return TargetUser(None, os.environ.get("USERNAME", ""), os.environ.get("LOCALAPPDATA", ""),
                      os.environ.get("APPDATA", ""), _my_documents())


@lru_cache(maxsize=None)
def get_target_user() -> TargetUser:
    current = _current_user()
    try:
        session, me = _session_account(), _current_account()
        if not session or not me:
            return current
        sid, my_sid = _account_sid(*session), _account_sid(*me)
        if not sid or not my_sid or sid == my_sid:
            return current
        # 登录用户的注册表必须已加载（他正登录着），并且能找到他的个人文件夹
        winreg.CloseKey(winreg.OpenKey(winreg.HKEY_USERS, sid))
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, f"{_PROFILE_LIST}\\{sid}") as key:
            profile = os.path.expandvars(winreg.QueryValueEx(key, "ProfileImagePath")[0])
        if not os.path.isdir(profile):
            return current
        return TargetUser(
            sid, session[1],
            _shell_folder(sid, "Local AppData", profile, r"AppData\Local"),
            _shell_folder(sid, "AppData", profile, r"AppData\Roaming"),
            _shell_folder(sid, "Personal", profile, "Documents"),
        )
    except Exception:
        return current


def resolve_key(subkey: str, root_name: str):
    """把 (子键, "HKLM"/"HKCU") 换成 (根键句柄, 子键, reg.exe 路径)。
    "HKCU" 会指向实际要清理的那个用户。"""
    if root_name == "HKLM":
        return winreg.HKEY_LOCAL_MACHINE, subkey, f"HKLM\\{subkey}"
    sid = get_target_user().sid
    if sid is None:
        return winreg.HKEY_CURRENT_USER, subkey, f"HKCU\\{subkey}"
    return winreg.HKEY_USERS, f"{sid}\\{subkey}", f"HKU\\{sid}\\{subkey}"
