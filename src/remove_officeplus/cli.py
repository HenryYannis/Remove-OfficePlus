import argparse
import sys
from .scanner import run_scan
from .cleaner import run_nuke

BANNER = """
============================================================
         Remove-OfficePlus  |  Office 流氓插件彻底根除器      
       https://github.com/HenryYannis/Remove-OfficePlus     
============================================================
"""

def print_banner():
    print(BANNER)

def display_scan(report):
    print(">>> 正在进行系统环境全面排查扫描...\n")
    print(f"[*] 管理员权限运行: {'是' if report.is_admin else '否'}")

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

    print("\n" + "-" * 60)
    if not report.is_clean:
        print(f"[!] 排查完成：共检测到 {report.total_threats} 处 OfficePLUS 关联项目/残留！")
        print("建议执行彻底根除清理以防止其后台常驻或死灰复燃。")
    else:
        print("[+] 排查完成：你的系统干干净净，未发现任何 OfficePLUS 残留！")
    print("-" * 60 + "\n")

def main():
    parser = argparse.ArgumentParser(description="Remove-OfficePlus: 一键彻底根除微软OfficePLUS及同类流氓加载项")
    parser.add_argument("--scan", action="store_true", help="仅扫描诊断系统残留，不进行任何修改")
    parser.add_argument("--nuke", action="store_true", help="执行彻底根除清理")
    parser.add_argument("-f", "--force", action="store_true", help="跳过交互确认直接执行清理")

    args = parser.parse_args()
    print_banner()

    if args.scan:
        report = run_scan()
        display_scan(report)
        return

    if args.nuke:
        print(">>> 正在执行彻底根除清理...")
        procs, svcs, regs, tasks, dirs = run_nuke()
        print("\n" + "=" * 60)
        print(" 🎉 微软OfficePLUS 及关联组件已全部彻底根除！")
        print("=" * 60)
        print("\n正在进行清理后状态复检...")
        report = run_scan()
        display_scan(report)
        return

    # Interactive mode
    report = run_scan()
    display_scan(report)

    if report.is_clean:
        print("系统目前处于干净状态，无需进一步清理。")
        input("\n按回车键退出...")
        return

    if not args.force:
        choice = input("是否立即执行彻底清理根除？(y/N): ").strip()
        if choice.lower() != 'y':
            print("操作已取消。")
            return

    print("\n>>> 正在执行彻底根除清理...")
    run_nuke()
    print("\n" + "=" * 60)
    print(" 🎉 微软OfficePLUS 及关联组件已全部彻底根除！")
    print("=" * 60)
    print("\n正在进行清理后状态复检...")
    report = run_scan()
    display_scan(report)
    input("\n按回车键退出...")

if __name__ == "__main__":
    main()
