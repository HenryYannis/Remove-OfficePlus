import sys
import os

# 确保无论在源码运行还是 PyInstaller 单文件打包运行 (_MEIPASS) 下均能正确定位 src 模块
base_dir = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
src_dir = os.path.join(base_dir, "src")
if os.path.exists(src_dir):
    sys.path.insert(0, src_dir)
sys.path.insert(0, base_dir)

from remove_officeplus.cli import main

if __name__ == "__main__":
    main()
