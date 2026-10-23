"""清理日志：每次清理把做了什么、哪里失败、失败原因写进一个文本文件。

以前进程、服务、注册表、计划任务、目录这几步出错时，错误全被吞掉，
用户只看到“还有 N 处残留”，不知道为什么，也没法附在 Issue 里。
日志和注册表备份放在同一个文件夹（文档\\Remove-OfficePlus 备份），好找。
写日志本身出任何问题都不影响清理。
"""
import os
import platform
import sys
from datetime import datetime
from typing import List, Optional

from . import __version__

_lines: List[str] = []
# 最近一次清理的日志文件路径（没写成功时为 None）
LAST_LOG_PATH: Optional[str] = None


def start() -> None:
    global LAST_LOG_PATH
    LAST_LOG_PATH = None
    _lines.clear()
    add(f"Remove-OfficePlus {__version__} 开始清理")
    add(f"系统: {platform.platform()}  Python: {platform.python_version()}"
        f"{'  (打包版)' if getattr(sys, 'frozen', False) else ''}")


def add(message: str) -> None:
    _lines.append(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {message}")


def output_text(res) -> str:
    """把命令行工具的输出整理成一行，用来说明失败原因。"""
    text = " ".join(filter(None, [getattr(res, "stdout", None), getattr(res, "stderr", None)]))
    return " ".join(text.split())


def save(folder: str) -> Optional[str]:
    """写入 folder\\清理日志_时间.txt，同一秒多次运行时加 _2、_3，不覆盖旧日志。"""
    global LAST_LOG_PATH
    try:
        os.makedirs(folder, exist_ok=True)
        stem = f"清理日志_{datetime.now():%Y%m%d_%H%M%S}"
        n = 1
        while True:
            path = os.path.join(folder, f"{stem}.txt" if n == 1 else f"{stem}_{n}.txt")
            try:
                with open(path, "x", encoding="utf-8-sig", newline="\r\n") as fh:
                    fh.write("\n".join(_lines) + "\n")
                break
            except FileExistsError:
                n += 1
        LAST_LOG_PATH = path
    except Exception:
        LAST_LOG_PATH = None
    return LAST_LOG_PATH
