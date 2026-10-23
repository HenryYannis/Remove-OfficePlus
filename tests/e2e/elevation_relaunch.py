"""模拟非管理员运行时的提权重启，验证各种启动方式重启后都能正常清理。

CI 虚拟机本身就是管理员，真正的 UAC 弹窗没法点。这里把「当前是管理员」改成否，
把弹 UAC 的 ShellExecuteW 换成直接启动同样的命令行，其余全部走真实代码：
重新启动的子进程是真实的管理员进程，会真的清理假残留。

用法：python tests/e2e/elevation_relaunch.py module|main-py|cancel
"""
import ctypes
import os
import runpy
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
mode = sys.argv[1]
launched = []


def fake_shell_execute(hwnd, verb, program, params, directory, show):
    assert verb == "runas", verb
    if mode == "cancel":
        return 5  # 用户在 UAC 里点了「否」时 ShellExecute 返回 5（拒绝访问）
    cmdline = subprocess.list2cmdline([program]) + " " + params
    assert "--pause-on-exit" in params, f"提权重启时没有加 --pause-on-exit，新窗口会一闪而过: {params}"
    print(f"[test] 以管理员身份重新启动: {cmdline}")
    proc = subprocess.run(cmdline, cwd=directory)
    launched.append(proc.returncode)
    return 42


from remove_officeplus import cleaner  # noqa: E402

cleaner.is_admin = lambda: False
ctypes.windll.shell32.ShellExecuteW = fake_shell_execute

if mode in ("module", "cancel"):
    import remove_officeplus.__main__ as entry
    sys.argv = [entry.__file__, "--nuke", "-f"]  # python -m 时 argv[0] 就是这个文件
    target = lambda: runpy.run_module("remove_officeplus", run_name="__main__", alter_sys=True)
else:
    sys.argv = [os.path.join(ROOT, "main.py"), "--nuke", "-f"]
    target = lambda: runpy.run_path(sys.argv[0], run_name="__main__")

try:
    target()
    code = 0
except SystemExit as e:
    code = e.code or 0

if mode == "cancel":
    if launched:
        sys.exit("[FAIL] 取消提权后不应该再启动清理")
    if code != 1:
        sys.exit(f"[FAIL] 取消提权后应该报告残留未清除并返回 1，实际 {code}")
    print("[OK] 取消提权：没有做任何修改，并如实报告未完成")
else:
    if launched != [0]:
        sys.exit(f"[FAIL] 提权重启后的进程没有成功完成清理: {launched}")
    if code != 0:
        sys.exit(f"[FAIL] 原进程在成功提权后应正常退出，实际 {code}")
    print(f"[OK] {mode}: 提权重启后清理成功")
