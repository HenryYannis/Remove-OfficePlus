"""GUI 在后台线程里调用 run_scan / run_nuke，它们一旦抛出异常，线程悄悄结束，
界面会一直卡在“正在扫描/清理”。这里人为让其中一步出错，检查：
- 扫描：出错的那一项跳过，其他项照常报告；
- 清理：不抛异常，返回已完成的部分，日志里写明中断原因；
- 两者都在线程里跑完并回调（模拟 GUI 的用法）。
需要先 plant 假残留，且以管理员身份运行。
"""
import glob
import os
import sys
import threading

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "src"))
from remove_officeplus import cleaner, scanner  # noqa: E402
from remove_officeplus.backup import get_backup_dir  # noqa: E402


def boom(*_args, **_kwargs):
    raise RuntimeError("E2E 故意制造的错误")


def in_thread(fn):
    """像 GUI 一样在后台线程里调用，返回结果；线程里抛了异常就返回 None。"""
    box = {}

    def worker():
        box["result"] = fn()

    t = threading.Thread(target=worker, daemon=True)
    t.start()
    t.join(300)
    return box.get("result")


def main():
    ok = True

    original = scanner.scan_registry
    scanner.scan_registry = boom
    report = in_thread(scanner.run_scan)
    scanner.scan_registry = original
    if report is None:
        print("[FAIL] 扫描中一项出错，整个扫描线程崩了")
        ok = False
    elif not report.directories:
        print("[FAIL] 一项出错后，其他项（残留目录）没有照常报告")
        ok = False
    else:
        print(f"[OK] 注册表检测出错时，扫描仍完成，报告了 {len(report.directories)} 个残留目录")

    original = cleaner.clean_registry
    cleaner.clean_registry = boom
    result = in_thread(cleaner.run_nuke)
    cleaner.clean_registry = original
    if result is None:
        print("[FAIL] 清理中一步出错，整个清理线程崩了")
        ok = False
    else:
        logs = sorted(glob.glob(os.path.join(get_backup_dir(), "清理日志_*.txt")), key=os.path.getmtime)
        text = open(logs[-1], encoding="utf-8-sig").read() if logs else ""
        if "清理意外中断" not in text:
            print("[FAIL] 清理中断了，日志里却没有记录原因")
            ok = False
        else:
            print(f"[OK] 清理中途出错时不抛异常，返回了已完成的部分，日志写明了原因：{logs[-1]}")

    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
