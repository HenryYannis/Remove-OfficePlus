"""
打包脚本：使用 PyInstaller 将 Remove-OfficePlus 打包为单文件 Windows 可执行程序 (.exe)
并自动嵌入 requireAdministrator 管理员 UAC 清单。
"""

import os
import sys
import subprocess
import shutil

def build():
    print("=== 开始构建 Remove-OfficePlus 独立绿色版程序 (.exe) ===")
    
    # 检查 PyInstaller
    try:
        import PyInstaller
    except ImportError:
        print("[!] 正在安装 PyInstaller 打包工具...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])

    dist_dir = os.path.abspath("dist")
    build_dir = os.path.abspath("build")

    # 构建命令
    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--onedir", # 或 --onefile
        "--onefile",
        "--windowed", # 隐藏黑窗，纯 GUI 界面
        "--name", "Remove-OfficePlus-GUI",
        "--uac-admin", # 自动向 Windows 请求 UAC 管理员提权
        "--clean",
        os.path.abspath("main.py")
    ]

    print(f"执行打包命令: {' '.join(cmd)}")
    subprocess.check_call(cmd)

    exe_path = os.path.join(dist_dir, "Remove-OfficePlus-GUI.exe")
    if os.path.exists(exe_path):
        size_mb = os.path.getsize(exe_path) / (1024 * 1024)
        print(f"\n🎉 构建成功！输出可执行文件: {exe_path} ({size_mb:.2f} MB)")
    else:
        print("\n[!] 构建异常：未在 dist 目录找到可执行文件。")

if __name__ == "__main__":
    build()
