"""
打包脚本：使用 PyInstaller 将 Remove-OfficePlus 打包为单文件 Windows 可执行程序 (.exe)，
自动嵌入 requireAdministrator 管理员 UAC 清单和文件版本信息，并生成 SHA256 校验文件。

所有路径都相对于本脚本所在目录，在任何电脑上都能直接运行：python build_exe.py
"""

import hashlib
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ROOT, "src"))
from remove_officeplus import __version__  # noqa: E402

EXE_NAME = "Remove-OfficePlus-GUI"
AUTHOR = "程小宝 (Cheng Xiaobao - xbkjz.cn)"

VERSION_INFO = """VSVersionInfo(
  ffi=FixedFileInfo(filevers={tup}, prodvers={tup}, mask=0x3f, flags=0x0, OS=0x40004,
                    fileType=0x1, subtype=0x0, date=(0, 0)),
  kids=[
    StringFileInfo([StringTable('080404B0', [
      StringStruct('CompanyName', {author!r}),
      StringStruct('FileDescription', 'Remove-OfficePlus - OfficePLUS 清理工具'),
      StringStruct('FileVersion', {ver!r}),
      StringStruct('InternalName', {name!r}),
      StringStruct('LegalCopyright', {copyright!r}),
      StringStruct('OriginalFilename', {exe!r}),
      StringStruct('ProductName', 'Remove-OfficePlus'),
      StringStruct('ProductVersion', {ver!r})])]),
    VarFileInfo([VarStruct('Translation', [2052, 1200])])
  ]
)
"""


def write_version_file(path: str) -> None:
    """生成 PyInstaller 的版本信息文件，版本号取自 __init__.py，避免两处不一致。"""
    nums = [int(x) for x in __version__.split(".")[:4]]
    nums += [0] * (4 - len(nums))
    text = VERSION_INFO.format(
        tup=tuple(nums), ver=__version__, name=EXE_NAME, exe=f"{EXE_NAME}.exe",
        author=AUTHOR, copyright=f"© 2026 {AUTHOR}，MIT 协议",
    )
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)


def sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def build() -> int:
    print(f"=== 开始构建 Remove-OfficePlus {__version__} 独立绿色版程序 (.exe) ===")
    dist_dir = os.path.join(ROOT, "dist")
    version_file = os.path.join(ROOT, "build", "version_info.txt")
    os.makedirs(os.path.dirname(version_file), exist_ok=True)
    write_version_file(version_file)

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm",
        "--onefile",
        "--windowed",  # 隐藏黑窗，纯 GUI 界面
        "--noupx",  # UPX 压缩容易被杀毒软件误报
        "--name", EXE_NAME,
        "--paths", os.path.join(ROOT, "src"),
        "--collect-all", "remove_officeplus",
        "--uac-admin",  # 自动向 Windows 请求 UAC 管理员提权
        "--version-file", version_file,
        "--specpath", os.path.join(ROOT, "build"),  # 生成的 spec 放进 build，不污染仓库
        "--distpath", dist_dir,
        "--workpath", os.path.join(ROOT, "build"),
        "--clean",
        os.path.join(ROOT, "main.py"),
    ]
    print(f"执行打包命令: {' '.join(cmd)}")
    subprocess.check_call(cmd)

    built_path = os.path.join(dist_dir, f"{EXE_NAME}.exe")
    if not os.path.exists(built_path):
        print("\n[!] 构建失败：未在 dist 目录找到可执行文件。")
        return 1

    # 发布用的文件名带上版本号，方便用户分辨下载的是哪一版
    release_name = f"{EXE_NAME}-v{__version__}.exe"
    exe_path = os.path.join(dist_dir, release_name)
    os.replace(built_path, exe_path)

    digest = sha256(exe_path)
    with open(os.path.join(dist_dir, "SHA256SUMS.txt"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(f"{digest}  {release_name}\n")
    size_mb = os.path.getsize(exe_path) / (1024 * 1024)
    print(f"\n[+] 构建成功！输出可执行文件: {exe_path} ({size_mb:.2f} MB)")
    print(f"[+] SHA256: {digest}")
    return 0


if __name__ == "__main__":
    sys.exit(build())
