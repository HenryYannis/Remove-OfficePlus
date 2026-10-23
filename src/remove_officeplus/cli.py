import argparse
import sys
from . import __version__
from .scanner import run_scan
from . import cleaner, runlog
from .cleaner import run_nuke
from .user_context import get_target_user

BANNER = """
============================================================
         Remove-OfficePlus  |  OfficePLUS 加载项清理工具      
       https://github.com/HenryYannis/Remove-OfficePlus     
============================================================
"""

def confirm_office_saved(report) -> bool:
    """检测到 Office 正在运行时提醒用户先保存文件。返回 False 表示用户取消。"""
    running = sorted({p.split(" (PID")[0] for p in report.office_apps})
    if not running:
        return True
    print(f"[!] 检测到以下 Office 程序正在运行：{'、'.join(running)}")
    print("[!] 清理时会强制关闭它们，未保存的内容会丢失。请先保存好文件。")
    choice = input("保存好后按回车继续，输入 n 取消: ").strip().lower()
    if choice.startswith("n"):
        print("操作已取消。")
        return False
    return True

def print_banner():
    print(BANNER)

def display_scan(report):
    print(">>> 正在进行系统环境全面排查扫描...\n")
    print(f"[*] 管理员权限运行: {'是' if report.is_admin else '否'}")
    target = get_target_user()
    if target.sid:
        print(f"[*] 当前以其他管理员账号运行，将检查和清理登录用户「{target.name}」的个人设置与文件。")

    print("\n[1] 进程检测：")
    if report.processes:
        for p in report.processes:
            print(f"  [-] 发现运行中进程: {p}")
    else:
        print("  [+] 未发现 OfficePLUS 关联进程运行。")

    print("\n[2] Windows 系统服务检测：")
    if report.services:
        for s in report.services:
            print(f"  [-] 发现后台常驻服务: {s}")
    else:
        print("  [+] 系统服务未安装或已注销。")

    print("\n[3] Office 加载项与注册表残留检测：")
    if report.registry_keys:
        for r in report.registry_keys:
            print(f"  [-] 发现注册表项: {r}")
    else:
        print("  [+] 未发现任何 OfficePLUS 相关注册表项。")

    print("\n[4] 文件目录与缓存残留检测：")
    if report.directories:
        for d in report.directories:
            print(f"  [-] 发现残留目录: {d}")
    else:
        print("  [+] 未发现任何 OfficePLUS 文件或缓存残留。")

    print("\n[5] 计划任务检测：")
    if report.scheduled_tasks:
        for t in report.scheduled_tasks:
            print(f"  [-] 发现计划任务: {t}")
    else:
        print("  [+] 未发现 OfficePLUS 相关计划任务。")

    print("\n" + "-" * 60)
    if not report.is_clean:
        print(f"[!] 排查完成：共检测到 {report.total_threats} 处 OfficePLUS 关联项目/残留！")
        print("建议执行清理，避免它在后台常驻或重新加载。")
    else:
        print("[+] 排查完成：你的系统干干净净，未发现任何 OfficePLUS 残留！")
    print("-" * 60 + "\n")

def report_nuke_result() -> bool:
    """清理后复检，按实际结果汇报。返回 True 表示已清除干净。"""
    print("\n正在进行清理后状态复检...")
    report = run_scan()
    display_scan(report)
    if cleaner.LAST_BACKUP_PATH:
        print(f"\n[*] 已删除的注册表项备份在: {cleaner.LAST_BACKUP_PATH}")
        print("    如果误删了需要的设置，双击这个文件即可恢复。")
    if runlog.LAST_LOG_PATH:
        print(f"[*] 本次清理日志: {runlog.LAST_LOG_PATH}")
        if not report.is_clean:
            print("    提交 Issue 时附上这个文件，方便定位问题。")
    print("=" * 60)
    if report.is_clean:
        print(" [完成] 微软 OfficePLUS 及关联组件已全部清除。")
    else:
        print(f" [未完成] 还有 {report.total_threats} 处残留没能删除，见上方列表。")
        print(" 建议重启电脑后再运行一次；仍然删不掉的话，欢迎到 GitHub 提交 Issue。")
    print("=" * 60)
    return report.is_clean

def _safe_console_output():
    """输出被重定向到文件/管道且编码不支持中文时（例如英文 Windows 的 cp1252），
    用 ? 代替无法显示的字符，避免整个程序因 UnicodeEncodeError 崩溃。"""
    for stream in (sys.stdout, sys.stderr):
        if stream is not None and hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(errors="replace")
            except Exception:
                pass

def _has_console() -> bool:
    """打包成 exe 时用的是无控制台的 --windowed 模式，此时 sys.stdout/stdin 是 None，
    print 没有任何输出、input 会直接崩溃。"""
    return sys.stdout is not None and sys.stdin is not None

def _no_console_exit(detail: str = ""):
    """没有控制台却要走命令行模式时，弹窗说明原因后退出，而不是悄无声息地崩溃。"""
    msg = ("这个 exe 是图形界面版，不支持命令行参数。\n"
           "命令行请使用 PowerShell 脚本或 Python 版（见 GitHub 项目说明）。")
    if detail:
        msg = f"{detail}\n\n{msg}"
    try:
        import ctypes
        ctypes.windll.user32.MessageBoxW(None, msg, "Remove-OfficePlus", 0x30)
    except Exception:
        pass
    sys.exit(2)

def _pause_on_exit(enabled: bool):
    """提权后会在新的控制台窗口里运行，结束后窗口立即关闭，看不到结果。
    这种情况下停一下；输入被重定向（脚本、测试）时不停。"""
    if enabled and sys.stdin is not None and sys.stdin.isatty():
        try:
            input("\n按回车键退出...")
        except (EOFError, KeyboardInterrupt):
            pass

def display_plan(report):
    """预演：列出清理时会执行的操作，不做任何修改。"""
    from .backup import get_backup_dir
    print(">>> 预演模式：以下是执行清理时会做的操作，本次不做任何修改。\n")
    if report.is_clean:
        print("[+] 没有需要清理的项目。")
        return
    steps = [
        ("结束进程", report.processes),
        ("停止并删除服务", report.services),
        ("删除注册表项（删除前先备份）", report.registry_keys),
        ("删除计划任务", report.scheduled_tasks),
        ("删除目录", report.directories),
    ]
    for title, items in steps:
        for item in items:
            print(f"  [{title}] {item}")
    office = sorted({p.split(" (PID")[0] for p in report.office_apps})
    if office:
        print(f"\n[!] 清理时会强制关闭正在运行的 Office：{'、'.join(office)}，请先保存文件。")
    print(f"\n[*] 注册表备份和清理日志会保存到：{get_backup_dir()}")
    print("[*] 确认无误后，用 --nuke 执行清理。")

def main():
    _safe_console_output()
    parser = argparse.ArgumentParser(description="Remove-OfficePlus: 清理微软 OfficePLUS 加载项及残留")
    parser.add_argument("--version", action="version", version=f"Remove-OfficePlus {__version__}")
    parser.add_argument("--gui", action="store_true", help="启动图形界面桌面窗口 (默认)")
    parser.add_argument("--cli", action="store_true", help="使用命令行交互模式")
    parser.add_argument("--scan", action="store_true", help="仅扫描诊断系统残留，不进行任何修改")
    parser.add_argument("--dry-run", action="store_true", help="预演：列出清理时会删除的项目，不进行任何修改")
    parser.add_argument("--nuke", action="store_true", help="执行清理（会先询问确认，加 -f 跳过）")
    parser.add_argument("-f", "--force", "--yes", action="store_true", help="跳过交互确认直接执行清理")
    parser.add_argument("--pause-on-exit", action="store_true", help=argparse.SUPPRESS)  # 提权重启时自动加上

    cli_args = [a for a in sys.argv[1:] if a not in ("--gui", "--pause-on-exit")]
    if not _has_console() and cli_args:
        _no_console_exit()
    args = parser.parse_args()

    # 如果指定了 --gui 或者没有指定任何命令行操作参数，默认启动 GUI 窗口
    if args.gui or (not args.cli and not args.scan and not args.dry_run and not args.nuke and not args.force):
        try:
            from .gui import launch_gui
            launch_gui()
            return
        except Exception as e:
            if not _has_console():
                _no_console_exit(f"启动图形界面失败：{e}")
            print(f"启动图形界面失败 ({e})，将回退至命令行模式。\n")

    try:
        code = _run_cli(args)
    finally:
        _pause_on_exit(args.pause_on_exit)
    if code:
        sys.exit(code)

def _run_cli(args) -> int:
    print_banner()

    if args.scan:
        report = run_scan()
        display_scan(report)
        return 0

    if args.dry_run:
        report = run_scan()
        display_scan(report)
        display_plan(report)
        return 0

    if args.nuke:
        report = run_scan()
        if not args.force:
            if report.is_clean:
                display_scan(report)
                print("系统目前处于干净状态，无需清理。")
                return 0
            display_plan(report)
            choice = input("\n确认执行以上清理？(y/N): ").strip()
            if choice.lower() != "y":
                print("操作已取消。")
                return 0
            if not confirm_office_saved(report):
                return 0
        print(">>> 正在清理...")
        run_nuke()
        return 0 if report_nuke_result() else 1

    # Interactive mode
    report = run_scan()
    display_scan(report)

    if report.is_clean:
        print("系统目前处于干净状态，无需进一步清理。")
        input("\n按回车键退出...")
        return 0

    if not args.force:
        choice = input("是否立即执行清理？(y/N): ").strip()
        if choice.lower() != 'y':
            print("操作已取消。")
            return 0
        if not confirm_office_saved(report):
            return 0

    print("\n>>> 正在清理...")
    run_nuke()
    clean = report_nuke_result()
    input("\n按回车键退出...")
    return 0 if clean else 1

if __name__ == "__main__":
    main()
