"""用 pytest 跑一遍不碰系统的检查脚本，Linux 和 Windows 上都能跑。

这些脚本本身就能单独运行（CI 里也会单独跑），这里只是把它们收进 pytest，
方便本地一条命令 `pytest tests` 全部检查。E2E 脚本会改动系统，不在这里跑。
"""
import os
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

CHECKS = [
    ["scripts/sync_rules.py", "--check"],
    ["tests/real_sample_check.py"],
    ["tests/gui_result_check.py"],
]


@pytest.mark.parametrize("args", CHECKS, ids=lambda a: " ".join(a))
def test_check_script(args):
    env = dict(os.environ, PYTHONUTF8="1")
    res = subprocess.run(
        [sys.executable] + [os.path.join(ROOT, args[0])] + args[1:],
        cwd=ROOT, env=env, capture_output=True, text=True, encoding="utf-8",
        errors="replace", check=False,
    )
    assert res.returncode == 0, f"{' '.join(args)} 失败：\n{res.stdout}\n{res.stderr}"
