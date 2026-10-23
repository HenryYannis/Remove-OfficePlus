import os
import sys
import shutil
import winreg
import subprocess
import ctypes
from typing import List, Tuple
from .constants import OFFICEPLUS_PROCESSES, OFFICEPLUS_KEYWORD, TARGET_PROCESSES, get_target_directories
from .scanner import is_admin, list_scheduled_tasks, is_officeplus_task
from .backup import backup_registry, get_backup_dir
from . import runlog
from .user_context import resolve_key
from .discovery import get_registry_keys, get_services
from .winutil import (COMMAND_TIMEOUT, current_session_id, is_officeplus_image, list_processes,
                      process_path, system_exe)

# 32 位程序（如 32 位 exe）访问 HKLM\Software 会被重定向到 Wow6432Node，
# 一律指定 64 位视图；32 位那份由规则里的 Wow6432Node 路径单独覆盖
VIEW = winreg.KEY_WOW64_64KEY

# 最近一次清理生成的注册表备份文件路径（没有可备份的项时为 None）
LAST_BACKUP_PATH = None

def _relaunch_command() -> Tuple[str, List[str]]:
    """以管理员身份重新启动自己时要执行的程序和参数。

    以前用 python + sys.argv[0] 重新执行，只有 `python main.py` 这一种启动方式可靠：
    - `python -m remove_officeplus` 时 argv[0] 是 __main__.py，单独执行会因相对导入失败；
    - pip 安装的 remove-officeplus 命令，argv[0] 是启动器，路径可能不带 .exe；
    - 打包成 exe 后 argv[0] 就是 exe 本身，会被当成参数再传一遍，导致参数解析报错。
    现在打包版直接重新运行 exe；其余情况都用 -c 直接导入本包的入口，和怎么启动的无关。
    """
    if getattr(sys, "frozen", False):
        return sys.executable, sys.argv[1:]
    package_parent = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    code = (f"import sys; sys.path.insert(0, {package_parent!r}); "
            "from remove_officeplus.cli import main; main()")
    # 新开的管理员控制台窗口结束后会立刻关闭，加上这个参数让它停一下，用户才看得到结果
    extra = [] if "--pause-on-exit" in sys.argv else ["--pause-on-exit"]
    return sys.executable, ["-c", code] + sys.argv[1:] + extra

def elevate() -> bool:
    """没有管理员权限时弹出 UAC，以管理员身份重新启动自己并退出当前进程。

    已经是管理员返回 True；用户在 UAC 里点了「否」等启动失败的情况返回 False，
    由调用方决定怎么处理，而不是像以前那样直接退出、让窗口莫名消失。
    """
    if is_admin():
        return True
    program, args = _relaunch_command()
    result = ctypes.windll.shell32.ShellExecuteW(
        None, "runas", program, subprocess.list2cmdline(args), os.getcwd(), 1)
    if result > 32:  # ShellExecute 返回值大于 32 表示启动成功
        sys.exit(0)
    print("[!] 没有获得管理员权限（可能在 UAC 提示中选择了「否」）。", file=sys.stderr)
    return False

def _run(args):
    """运行系统命令：不读标准输入（不会等用户输入 Y/N），超时会抛 TimeoutExpired，由调用方记进日志。"""
    return subprocess.run(
        args,
        creationflags=subprocess.CREATE_NO_WINDOW,
        stdin=subprocess.DEVNULL,
        capture_output=True, text=True, errors="replace",
        timeout=COMMAND_TIMEOUT,
    )

def kill_processes() -> List[str]:
    """结束 OfficePLUS 进程和占用加载项文件的 Office 程序。

    - Word/Excel 等正常的 Office 程序只结束当前会话（当前登录用户）里的，
      不碰同一台电脑上其他用户的 Office，避免他们没保存的文档丢失；
    - OfficePLUS 自己的进程（服务进程在会话 0）不分会话，但要核对程序路径在 OfficePLUS 的文件夹里，
      路径读不到就不结束，避免误杀其他软件的同名进程。
    """
    killed = []
    try:
        procs = list_processes()
    except Exception as e:
        runlog.add(f"[失败] 读取进程列表: {e}")
        return killed
    my_session = current_session_id()
    officeplus = {p.lower() for p in OFFICEPLUS_PROCESSES}
    for target in TARGET_PROCESSES:
        for proc in procs:
            if proc.name.lower() != target.lower():
                continue
            label = f"{proc.name} (PID: {proc.pid})"
            if target.lower() in officeplus:
                path = process_path(proc.pid)
                if not is_officeplus_image(path, OFFICEPLUS_KEYWORD):
                    runlog.add(f"[跳过] 进程 {label} 的程序路径不属于 OfficePLUS，未结束: {path or '路径未知'}")
                    continue
            elif my_session is None or proc.session != my_session:
                runlog.add(f"[跳过] 进程 {label} 不在当前会话（其他用户的 Office），未结束")
                continue
            try:
                res = _run([system_exe("taskkill.exe"), "/F", "/PID", str(proc.pid)])
                if res.returncode == 0:
                    if target not in killed:
                        killed.append(target)
                    runlog.add(f"已结束进程: {label}")
                elif res.returncode != 128:  # 128 = 进程已经不在了
                    runlog.add(f"[失败] 结束进程 {label}: {runlog.output_text(res)}")
            except Exception as e:
                runlog.add(f"[失败] 结束进程 {label}: {e}")
    return killed

def delete_services() -> List[str]:
    removed = []
    for svc in get_services():
        try:
            # /y：有依赖服务时自动确认，不等用户输入
            _run([system_exe("net.exe"), "stop", svc, "/y"])
            res = _run([system_exe("sc.exe"), "delete", svc])
            if res.returncode == 0:
                removed.append(svc)
                runlog.add(f"已删除服务: {svc}")
            elif res.returncode != 1060:  # 1060 = 服务不存在
                runlog.add(f"[失败] 删除服务 {svc}: {runlog.output_text(res)}")
        except Exception as e:
            runlog.add(f"[失败] 删除服务 {svc}: {e}")
    return removed

def _delete_reg_key_tree(root, subkey):
    """递归删除注册表键。先把子键名字全部读出来再逐个删除，
    这样某个子键删不掉时也不会反复重试、卡死。"""
    try:
        with winreg.OpenKey(root, subkey, 0, winreg.KEY_READ | VIEW) as key:
            children = []
            i = 0
            while True:
                try:
                    children.append(winreg.EnumKey(key, i))
                    i += 1
                except OSError:
                    break
    except OSError:
        return  # 不存在或打不开，交给调用方复查
    for child in children:
        _delete_reg_key_tree(root, f"{subkey}\\{child}")
    try:
        winreg.DeleteKeyEx(root, subkey, VIEW, 0)
    except FileNotFoundError:
        pass
    except OSError as e:
        runlog.add(f"[失败] 删除注册表子项 {subkey}: {e}")

def _reg_key_exists(root, subkey) -> bool:
    try:
        with winreg.OpenKey(root, subkey, 0, winreg.KEY_READ | VIEW):
            return True
    except FileNotFoundError:
        return False
    except OSError:
        return True  # 没权限读也当作还在

def clean_registry(skip=(), keys=None) -> List[str]:
    """删除目标注册表项。skip 中的项（备份失败的）不删，避免无法恢复。
    keys 默认重新查找；run_nuke 传入备份时用的同一份列表，保证删的都备份过。"""
    if keys is None:
        keys = get_registry_keys()
    cleaned = []
    for key, root_name in keys:
        root, subkey, reg_path = resolve_key(key, root_name)
        if (key, root_name) in skip:
            if _reg_key_exists(root, subkey):
                runlog.add(f"[跳过] 备份失败，未删除注册表项: {reg_path}")
            continue
        if _reg_key_exists(root, subkey):
            _delete_reg_key_tree(root, subkey)
            if not _reg_key_exists(root, subkey):  # 删完复查，真的没了才算成功
                cleaned.append(reg_path)
                runlog.add(f"已删除注册表项: {reg_path}")
            else:
                runlog.add(f"[失败] 注册表项仍然存在: {reg_path}")
    return cleaned

def clean_scheduled_tasks() -> List[str]:
    cleaned = []
    try:
        task_names = list_scheduled_tasks()
    except Exception as e:
        runlog.add(f"[失败] 读取计划任务列表: {e}")
        return cleaned
    for task_name in task_names:
        if not is_officeplus_task(task_name):
            continue
        try:
            res = _run([system_exe("schtasks.exe"), "/Delete", "/TN", task_name, "/F"])
        except Exception as e:
            runlog.add(f"[失败] 删除计划任务 {task_name}: {e}")
            continue
        if res.returncode == 0:
            cleaned.append(task_name)
            runlog.add(f"已删除计划任务: {task_name}")
        else:
            runlog.add(f"[失败] 删除计划任务 {task_name}: {runlog.output_text(res)}")
    return cleaned

def _on_rm_error(func, path, exc_info):
    import stat
    try:
        os.chmod(path, stat.S_IWRITE)
        func(path)
    except Exception as e:
        runlog.add(f"[失败] 删除 {path}: {e}")

def delete_directories() -> List[str]:
    deleted = []
    for d in get_target_directories():
        if os.path.exists(d):
            try:
                shutil.rmtree(d, onerror=_on_rm_error)
                if not os.path.exists(d):
                    deleted.append(d)
                    runlog.add(f"已删除目录: {d}")
                else:
                    runlog.add(f"[失败] 目录未能完全删除: {d}")
            except Exception as e:
                runlog.add(f"[失败] 删除目录 {d}: {e}")
    return deleted

def run_nuke() -> Tuple[List[str], List[str], List[str], List[str], List[str]]:
    """Execute complete purge of OfficePLUS."""
    global LAST_BACKUP_PATH
    if not elevate():
        print("[!] 没有管理员权限，本次未做任何修改。")
        return [], [], [], [], []
    # 中途出现意外错误时不往外抛：GUI 在后台线程里调用这里，异常会让线程悄悄结束、
    # 界面一直卡在“正在清理”。改为停止后续步骤、记进日志，返回已经完成的部分，
    # 调用方随后的复检会如实列出没删掉的残留。
    procs, svcs, regs, tasks, dirs = [], [], [], [], []
    runlog.start()
    try:
        # 先备份注册表再动手（和 PowerShell 版顺序一致）
        existing = [(k, r) for k, r in get_registry_keys() if _reg_key_exists(*resolve_key(k, r)[:2])]
        LAST_BACKUP_PATH, backup_failed = backup_registry(existing)
        if LAST_BACKUP_PATH:
            runlog.add(f"注册表备份: {LAST_BACKUP_PATH}")
        procs = kill_processes()
        svcs = delete_services()
        regs = clean_registry(skip=backup_failed, keys=existing)
        tasks = clean_scheduled_tasks()
        dirs = delete_directories()
        runlog.add("清理结束")
    except Exception as e:
        import traceback
        runlog.add(f"[错误] 清理意外中断，后续步骤未执行: {e!r}\n{traceback.format_exc()}")
        print(f"[!] 清理意外中断：{e!r}，详情见清理日志。", file=sys.stderr)
    finally:
        runlog.save(get_backup_dir())
    return procs, svcs, regs, tasks, dirs
