"""检查图形界面的清理结果提示是否如实（不弹窗、不碰系统，任何系统都能跑）。

- 清理完成弹窗按复检结果区分：全部清除 / 部分完成 / 失败，并显示备份和日志路径；
- 统计卡片包含计划任务，各项加起来等于总数；
- 点「提权」被 UAC 拒绝时有提示，而不是什么都不发生。
没有 tkinter 或 winreg 的环境（如 Linux）会用假模块代替，只测逻辑。
"""
import importlib
import importlib.util
import os
import sys
import types

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

if importlib.util.find_spec("winreg") is None:
    fake = types.ModuleType("winreg")
    for name in ("HKEY_LOCAL_MACHINE", "HKEY_CURRENT_USER", "HKEY_USERS", "KEY_READ",
                 "KEY_WOW64_64KEY", "KEY_ALL_ACCESS", "KEY_WRITE"):
        setattr(fake, name, 0)
    sys.modules["winreg"] = fake
try:
    # tkinter 本身能找到，但缺 Tk 库时导入 _tkinter 才会报错
    importlib.import_module("_tkinter")
    tk_ok = True
except ImportError:
    tk_ok = False
if not tk_ok:
    tk = types.ModuleType("tkinter")
    tk.Tk = object
    tk.NORMAL, tk.DISABLED, tk.END, tk.WORD = "normal", "disabled", "end", "word"
    for sub in ("ttk", "messagebox", "scrolledtext"):
        m = types.ModuleType("tkinter." + sub)
        setattr(tk, sub, m)
        sys.modules["tkinter." + sub] = m
    sys.modules["tkinter"] = tk

from remove_officeplus import gui  # noqa: E402
from remove_officeplus.scanner import ScanReport  # noqa: E402

FAILS = []


def check(cond, msg):
    print(("[OK] " if cond else "[FAIL] ") + msg)
    if not cond:
        FAILS.append(msg)


class FakeMessagebox:
    def __init__(self):
        self.calls = []

    def __getattr__(self, kind):
        if not kind.startswith("show"):
            raise AttributeError(kind)
        return lambda title, message: self.calls.append((kind, title, message))


class FakeLabel:
    def __init__(self):
        self.text = None

    def config(self, **kw):
        self.text = kw.get("text", self.text)


class FakeApp:
    """只带 _on_nuke_finished 用到的属性，不创建窗口。"""

    def __init__(self):
        self.lines = []
        self.rescanned = None
        self.status_label = FakeLabel()
        self.buttons = None

    def log(self, message, tag="info"):
        self.lines.append((tag, message))

    def _on_scan_finished(self, report):
        self.rescanned = report

    def set_buttons_state(self, enabled):
        self.buttons = enabled


def run_finish(nuke_result, report, backup="C:\\backup\\b.reg", log="C:\\backup\\log.txt"):
    box = FakeMessagebox()
    gui.messagebox = box
    gui.cleaner.LAST_BACKUP_PATH = backup
    gui.runlog.LAST_LOG_PATH = log
    app = FakeApp()
    gui.ModernGUI._on_nuke_finished(app, *nuke_result, report)
    return app, box.calls


def main():
    clean = ScanReport(is_admin=True)
    left = ScanReport(is_admin=True, registry_keys=["HKLM\\x"], scheduled_tasks=["\\OfficePLUS"])

    app, calls = run_finish((["a.exe"], ["svc"], ["HKLM\\k"], ["\\t"], ["C:\\d"]), clean)
    check(calls and calls[0][0] == "showinfo" and calls[0][1] == "清理完成", "复检干净时弹出「清理完成」")
    check(calls and "b.reg" in calls[0][2] and "log.txt" in calls[0][2], "成功弹窗里有备份和日志路径")
    check(app.rescanned is clean, "复检结果显示在卡片和日志里")

    app, calls = run_finish(([], [], ["HKLM\\k"], [], []), left)
    check(calls and calls[0][0] == "showwarning" and calls[0][1] == "部分完成", "删掉一部分、仍有残留时提示「部分完成」")
    check(calls and "2 处残留" in calls[0][2], "部分完成时写明剩余残留数")

    app, calls = run_finish(([], [], [], [], []), left)
    check(calls and calls[0][0] == "showerror" and calls[0][1] == "清理失败", "什么都没删掉时提示「清理失败」")
    check(calls and "log.txt" in calls[0][2], "失败弹窗里有日志路径")
    check(not any("已清理完成" in m for _, m in app.lines), "失败时日志里没有谎报“已清理完成”")

    app, calls = run_finish((["a.exe"], [], [], [], []), None, backup=None, log=None)
    check(calls and calls[0][0] == "showerror", "复检出错时不当作成功")
    check(app.buttons is True, "复检出错时按钮恢复可用，界面不卡住")

    # 统计卡片：总数等于各项之和（含计划任务）
    r = ScanReport(is_admin=True, processes=["p"], services=["s"], registry_keys=["r"],
                   directories=["d"], scheduled_tasks=["t1", "t2"])
    src = open(gui.__file__, encoding="utf-8").read()
    check("card_task_val" in src and "report.scheduled_tasks" in src, "界面有计划任务卡片")
    parts = len(r.processes) + len(r.services) + len(r.registry_keys) + len(r.scheduled_tasks) + len(r.directories)
    check(parts == r.total_threats, "五张卡片加起来等于总数")

    # 提权被拒绝时要有提示
    box = FakeMessagebox()
    gui.messagebox = box
    gui.elevate = lambda: False
    gui.ModernGUI._do_elevate(object())
    check(box.calls and box.calls[0][0] == "showwarning" and "UAC" in box.calls[0][2], "UAC 被拒绝时弹出提示")

    def broken():
        raise OSError("ShellExecute 失败")
    box = FakeMessagebox()
    gui.messagebox = box
    gui.elevate = broken
    gui.ModernGUI._do_elevate(object())
    check(box.calls and box.calls[0][0] == "showerror", "提权出错时弹出错误提示")

    if FAILS:
        print(f"\n{len(FAILS)} 项检查失败")
        return 1
    print("\n全部通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
