"""按特征识别 OfficePLUS，补充 rules.json 里写死的注册表项和服务名。

写死的名字（如 Addins\\MSOfficePLUS、服务名 OfficePLUS Service）没有用真实安装验证过，
OfficePLUS 换个 ProgID 或服务名就会漏掉。这里额外：
- 在各 Office 程序的 Addins 下（含 32 位视图和即点即用版 Office 的虚拟注册表），
  找键名、FriendlyName、Description 或 Manifest 含关键词的加载项；
- 在系统服务里找程序路径（ImagePath）指向 MSOfficePLUSService.exe 的服务。
只认这两个明确的特征，其他加载项和服务一概不碰。每次调用都重新查找，清理后复检能如实反映结果。
"""
import winreg
from typing import List, Tuple

from .constants import RULES, TARGET_REGISTRY_KEYS, TARGET_SERVICES
from .user_context import resolve_key

VIEW = winreg.KEY_WOW64_64KEY  # 32 位程序也看 64 位视图，32 位那份由 Wow6432Node 路径单独覆盖
ADDIN_VALUES = ("FriendlyName", "Description", "Manifest")
SERVICES_KEY = r"SYSTEM\CurrentControlSet\Services"


def _subkeys(root, path) -> List[str]:
    names = []
    try:
        with winreg.OpenKey(root, path, 0, winreg.KEY_READ | VIEW) as key:
            i = 0
            while True:
                try:
                    names.append(winreg.EnumKey(key, i))
                except OSError:
                    break
                i += 1
    except OSError:
        pass
    return names


def _value(root, path, name) -> str:
    try:
        with winreg.OpenKey(root, path, 0, winreg.KEY_READ | VIEW) as key:
            value, _ = winreg.QueryValueEx(key, name)
            return value if isinstance(value, str) else ""
    except OSError:
        return ""


def _matches_addin(root, path, name) -> bool:
    keyword = RULES["addin_keyword"].lower()
    if keyword in name.lower():
        return True
    return any(keyword in _value(root, f"{path}\\{name}", v).lower() for v in ADDIN_VALUES)


def find_addin_keys() -> List[Tuple[str, str]]:
    found = []
    for root_name, template in RULES["addin_parents"]:
        for app in RULES["addin_apps"]:
            parent = template.format(app=app)
            root, real_parent, _ = resolve_key(parent, root_name)
            for name in _subkeys(root, real_parent):
                if _matches_addin(root, real_parent, name):
                    found.append((f"{parent}\\{name}", root_name))
    return found


def find_services() -> List[str]:
    image = RULES["service_image"].lower()
    return [name for name in _subkeys(winreg.HKEY_LOCAL_MACHINE, SERVICES_KEY)
            if image in _value(winreg.HKEY_LOCAL_MACHINE, f"{SERVICES_KEY}\\{name}", "ImagePath").lower()]


def _unique(items, key=lambda x: x):
    seen, out = set(), []
    for item in items:
        k = key(item)
        if k not in seen:
            seen.add(k)
            out.append(item)
    return out


def get_registry_keys() -> List[Tuple[str, str]]:
    """写死的注册表项 + 按特征找到的加载项，去重（不区分大小写）。"""
    try:
        extra = find_addin_keys()
    except Exception:
        extra = []
    return _unique(TARGET_REGISTRY_KEYS + extra, key=lambda k: (k[0].lower(), k[1]))


def get_services() -> List[str]:
    """写死的服务名 + 程序路径指向 OfficePLUS 的服务，去重（不区分大小写）。"""
    try:
        extra = find_services()
    except Exception:
        extra = []
    return _unique(TARGET_SERVICES + extra, key=str.lower)
