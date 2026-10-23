"""清理前把要删除的注册表项导出成一个 .reg 文件，误删时双击它就能恢复。"""
import os
import subprocess
import tempfile
from datetime import datetime
from typing import Iterable, Optional, Set, Tuple

from .user_context import get_target_user, resolve_key

BACKUP_FOLDER_NAME = "Remove-OfficePlus 备份"
REG_HEADER = "Windows Registry Editor Version 5.00"
RESTORE_NOTE_NAME = "如何恢复.txt"
RESTORE_NOTE = """这个文件夹里是 Remove-OfficePlus 清理前自动备份的注册表。

如果清理后某个 Office 功能或设置不正常，可以这样恢复：
1. 找到那次清理对应的 .reg 文件，文件名里是清理的日期和时间，
   例如 OfficePLUS_注册表备份_20261023_105700.reg；
   同一秒内备份了多次时，后面的文件会加上 _2、_3。
2. 双击它，在弹出的提示中点「是」（可能需要管理员权限）。
3. 重新打开 Office 即可。

注意：这些备份里只有被删除的 OfficePLUS 相关注册表项，恢复后 OfficePLUS 加载项也会回来。
确认电脑一切正常后，可以直接删除这个文件夹。
"""


def get_backup_dir() -> str:
    """备份放在“文档”文件夹里，用户容易找到。
    用其他管理员账号提权时，放进正在用电脑的那个用户的文档。"""
    return os.path.join(get_target_user().documents, BACKUP_FOLDER_NAME)


def _write_backup_file(backup_dir: str, text: str) -> str:
    """写入备份文件。同一秒内多次备份时加 _2、_3 后缀，绝不覆盖以前的备份。"""
    stem = f"OfficePLUS_注册表备份_{datetime.now():%Y%m%d_%H%M%S}"
    n = 1
    while True:
        path = os.path.join(backup_dir, f"{stem}.reg" if n == 1 else f"{stem}_{n}.reg")
        try:
            fh = open(path, "x", encoding="utf-16", newline="\r\n")  # "x"：文件已存在就换个名字
        except FileExistsError:
            n += 1
            continue
        try:
            with fh:
                fh.write(text)
        except Exception:
            try:
                os.remove(path)  # 写了一半的文件不能留下来冒充备份
            except OSError:
                pass
            raise
        return path


def _write_restore_note(backup_dir: str) -> None:
    """在备份文件夹里放一份恢复说明，只写一次；写不进去也不影响清理。"""
    path = os.path.join(backup_dir, RESTORE_NOTE_NAME)
    if os.path.exists(path):
        return
    try:
        with open(path, "w", encoding="utf-8-sig", newline="\r\n") as fh:
            fh.write(RESTORE_NOTE)
    except OSError:
        pass


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
    try:
        os.makedirs(backup_dir, exist_ok=True)
        path = _write_backup_file(backup_dir, REG_HEADER + "\n\n" + "\n\n".join(parts) + "\n")
    except Exception as e:
        # 备份文件写不进去（文件夹无权限、磁盘满等）：一项都不删，宁可这次不清注册表
        print(f"[!] 注册表备份文件写入失败（{e}），为安全起见本次不删除任何注册表项。")
        return None, set(keys)
    _write_restore_note(backup_dir)
    return path, failed
