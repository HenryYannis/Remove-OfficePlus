import os

# OfficePLUS 自身的进程：扫描时算作威胁
OFFICEPLUS_PROCESSES = [
    "MSOfficePLUSService.exe",
    "OfficePLUS.AgentLauncher.exe",
    "DeepLink.exe",
    "OfficePLUS.exe",
]

# 正常的 Office 程序：不是威胁，只是清理时要关闭它们，才能删掉被占用的加载项文件
OFFICE_APP_PROCESSES = [
    "WINWORD.EXE",
    "EXCEL.EXE",
    "POWERPNT.EXE",
    "OUTLOOK.EXE",
]

# 清理时要结束的全部进程
TARGET_PROCESSES = OFFICEPLUS_PROCESSES + OFFICE_APP_PROCESSES

TARGET_SERVICES = [
    "OfficePLUS Service",
]

TARGET_REGISTRY_KEYS = [
    # HKLM 64-bit & Default
    (r"Software\Microsoft\Office\Word\Addins\MSOfficePLUS", "HKLM"),
    (r"Software\Microsoft\Office\Excel\Addins\MSOfficePLUS", "HKLM"),
    (r"Software\Microsoft\Office\PowerPoint\Addins\MSOfficePLUS", "HKLM"),
    (r"Software\Microsoft\Office\Outlook\Addins\MSOfficePLUS", "HKLM"),
    (r"Software\Microsoft\Windows\CurrentVersion\Uninstall\MSOfficePLUS", "HKLM"),
    (r"Software\Microsoft\OfficePLUS", "HKLM"),
    # HKLM 32-bit (Wow6432Node)
    (r"Software\Wow6432Node\Microsoft\Office\Word\Addins\MSOfficePLUS", "HKLM"),
    (r"Software\Wow6432Node\Microsoft\Office\Excel\Addins\MSOfficePLUS", "HKLM"),
    (r"Software\Wow6432Node\Microsoft\Office\PowerPoint\Addins\MSOfficePLUS", "HKLM"),
    (r"Software\Wow6432Node\Microsoft\Office\Outlook\Addins\MSOfficePLUS", "HKLM"),
    (r"Software\Wow6432Node\Microsoft\Windows\CurrentVersion\Uninstall\MSOfficePLUS", "HKLM"),
    (r"Software\Wow6432Node\Microsoft\OfficePLUS", "HKLM"),
    # HKCU User Level
    (r"Software\Microsoft\Office\Word\Addins\MSOfficePLUS", "HKCU"),
    (r"Software\Microsoft\Office\Excel\Addins\MSOfficePLUS", "HKCU"),
    (r"Software\Microsoft\Office\PowerPoint\Addins\MSOfficePLUS", "HKCU"),
    (r"Software\Microsoft\Office\Outlook\Addins\MSOfficePLUS", "HKCU"),
    (r"Software\Microsoft\Windows\CurrentVersion\Uninstall\MSOfficePLUS", "HKCU"),
    (r"Software\Microsoft\OfficePLUS", "HKCU"),
]

def get_target_directories():
    local_app_data = os.environ.get("LOCALAPPDATA", "")
    app_data = os.environ.get("APPDATA", "")
    program_data = os.environ.get("ProgramData", r"C:\ProgramData")
    program_files = os.environ.get("ProgramFiles", r"C:\Program Files")
    program_files_x86 = os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")

    dirs = [
        os.path.join(program_files, "Microsoft OfficePLUS"),
        os.path.join(program_files_x86, "Microsoft OfficePLUS"),
        os.path.join(program_data, "Microsoft OfficePLUS"),
    ]
    if local_app_data:
        dirs.append(os.path.join(local_app_data, "OfficePLUS"))
        dirs.append(os.path.join(local_app_data, "Microsoft OfficePLUS"))
    if app_data:
        dirs.append(os.path.join(app_data, "OfficePLUS"))
        dirs.append(os.path.join(app_data, "Microsoft OfficePLUS"))

    return [os.path.normpath(d) for d in dirs]
