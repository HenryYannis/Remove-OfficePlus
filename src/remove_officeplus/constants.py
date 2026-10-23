"""OfficePLUS 的识别规则。

规则只维护在同目录的 rules.json 一处，PowerShell 版也由它生成（scripts/sync_rules.py），
避免两套实现越走越远。
"""
import json
import os
from .user_context import get_target_user

with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "rules.json"), encoding="utf-8") as _fh:
    RULES = json.load(_fh)

# OfficePLUS 自身的进程：扫描时算作威胁
OFFICEPLUS_PROCESSES = [f"{name}.exe" for name in RULES["officeplus_processes"]]

# 正常的 Office 程序：不是威胁，只是清理时要关闭它们，才能删掉被占用的加载项文件
OFFICE_APP_PROCESSES = [f"{name}.EXE" for name in RULES["office_app_processes"]]

# 清理时要结束的全部进程
TARGET_PROCESSES = OFFICEPLUS_PROCESSES + OFFICE_APP_PROCESSES

TARGET_SERVICES = list(RULES["services"])

# 计划任务名或路径里含有这个词（不区分大小写）就算 OfficePLUS 的
TASK_KEYWORD = RULES["task_keyword"]

# [(子键路径, "HKLM"/"HKCU"), ...]；HKCU 会换成实际要清理的那个用户
TARGET_REGISTRY_KEYS = [(path, root) for root, path in RULES["registry_keys"]]


def get_target_directories():
    # 用户目录取“实际要清理的用户”的，避免用其他管理员账号提权时清错人；
    # 系统目录取环境变量，系统不装在 C 盘也能找到。哪个位置取不到就跳过，
    # 绝不能拼成盘符根目录下的路径。
    user = get_target_user()
    bases = {
        "ProgramFiles": os.environ.get("ProgramFiles"),
        "ProgramFiles(x86)": os.environ.get("ProgramFiles(x86)"),
        "ProgramData": os.environ.get("ProgramData"),
        "LocalAppData": user.local_appdata,
        "AppData": user.roaming_appdata,
    }
    dirs = []
    for base, name in RULES["directories"]:
        if bases.get(base):
            dirs.append(os.path.normpath(os.path.join(bases[base], name)))
    return dirs
