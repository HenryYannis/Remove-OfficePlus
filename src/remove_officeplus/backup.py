"""清理前把要删除的注册表项导出成一个 .reg 文件，误删时双击它就能恢复。"""
import os
import subprocess
import tempfile
from datetime import datetime
from typing import Iterable, Optional, Set, Tuple

from .user_context import get_target_user, resolve_key

BACKUP_FOLDER_NAME = "Remove-OfficePlus 备份"
REG_HEADER = "Windows Registry Editor Version 5.00"


def get_backup_dir() -> str:
    """备份放在“文档”文件夹里，用户容易找到。
    用其他管理员账号提权时，放进正在用电脑的那个用户的文档。"""
    return os.path.join(get_target_user().documents, BACKUP_FOLDER_NAME)


def backup_registry(keys: Iterable[Tuple[str, str]]) -> Tuple[Optional[str], Set[Tuple[str, str]]]:
    """导出所有存在的注册表项，合并成一个 .reg 文件。

    keys: [(子键路径, "HKLM"/"HKCU"), ...]，只传当前确实存在的项。
    返回 (备份文件路径或 None, 备份失败的项)。备份失败的项不应删除。
    """
    keys = list(keys)
    if not keys:
        return None, set()

    parts, failed = [], set()
    with tempfile.TemporaryDirectory() as tmp:
        for i, (subkey, root_name) in enumerate(keys):
            part = os.path.join(tmp, f"{i}.reg")
            res = subprocess.run(
                ["reg.exe", "export", resolve_key(subkey, root_name)[2], part, "/y", "/reg:64"],
                creationflags=subprocess.CREATE_NO_WINDOW,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            if res.returncode == 0 and os.path.exists(part):
                with open(part, encoding="utf-16") as fh:
                    text = fh.read()
                # 去掉每个分段自带的文件头，合并后只保留一个
                parts.append(text.replace(REG_HEADER, "", 1).strip("\r\n"))
            else:
                failed.add((subkey, root_name))

    if not parts:
        return None, failed

    backup_dir = get_backup_dir()
    os.makedirs(backup_dir, exist_ok=True)
    path = os.path.join(backup_dir, f"OfficePLUS_注册表备份_{datetime.now():%Y%m%d_%H%M%S}.reg")
    with open(path, "w", encoding="utf-16", newline="\r\n") as fh:
        fh.write(REG_HEADER + "\n\n" + "\n\n".join(parts) + "\n")
    return path, failed
