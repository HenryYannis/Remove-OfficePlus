# Remove-OfficePlus

[简体中文](README.md) | [繁體中文](README.zh-Hant.md) | **English**

One-click removal of the Microsoft OfficePLUS Office add-in, its background service and leftover files, with an automatic registry backup before anything is deleted.

[![CI](https://github.com/HenryYannis/remove-officeplus/actions/workflows/ci.yml/badge.svg)](https://github.com/HenryYannis/remove-officeplus/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/HenryYannis/remove-officeplus)](https://github.com/HenryYannis/remove-officeplus/releases)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
![Platform](https://img.shields.io/badge/Platform-Windows%2010%20%7C%2011-0078D6.svg?logo=windows)

---

## What it removes

Many people find "Microsoft OfficePLUS" (also shown as "微软 PPT 助手 / Office 助手") on their PC without remembering installing it. Removing it by hand usually runs into:

1. **It can't be turned off**: you untick it in Word / Excel / PowerPoint options, and after restarting Office it is ticked again.
2. **It can't be deleted**: File Explorer says the file is in use.
3. **It comes back**: after deleting some files, the background service downloads or repairs them on the next boot.

This tool cleans the whole chain, in this order: processes ➔ services ➔ registry (HKLM / HKCU / 32-bit / Click-to-Run Office) ➔ scheduled tasks ➔ cache folders.

| Category | Target path / identifier | Action |
| :--- | :--- | :--- |
| **Background service** | `OfficePLUS Service`, plus any service whose program path points to `MSOfficePLUSService.exe` | Stopped and removed with `sc delete` |
| **Processes holding files** | `MSOfficePLUSService`, `OfficePLUS.AgentLauncher`, `DeepLink`, `OfficePLUS` (only when the program lives in an OfficePLUS folder) | Force-terminated |
| **System registry (64-bit)** | `HKLM:\Software\Microsoft\Office\<App>\Addins\MSOfficePLUS` | Add-in removed |
| **System registry (32-bit)** | `HKLM:\Software\Wow6432Node\Microsoft\Office\<App>\Addins\MSOfficePLUS` | Add-in removed |
| **User registry** | `HKCU:\Software\Microsoft\Office\<App>\Addins\MSOfficePLUS` | Add-in removed |
| **Add-ins matched by pattern** | In all the locations above and in Click-to-Run Office's virtual registry: add-ins whose name, FriendlyName, Description or Manifest contains "OfficePLUS" | Add-in removed |
| **Program settings** | `Software\Microsoft\OfficePLUS` (HKLM, HKLM 32-bit, HKCU) | Removed |
| **Uninstall leftovers** | `...\CurrentVersion\Uninstall\MSOfficePLUS` (HKLM, HKLM 32-bit, HKCU) | Control Panel leftover key removed |
| **Scheduled tasks** | Tasks whose name or path contains "OfficePLUS" | Removed |
| **Install folders** | `%ProgramFiles%\Microsoft OfficePLUS`, `%ProgramFiles(x86)%\Microsoft OfficePLUS` | Removed |
| **Cache and settings** | `%ProgramData%\Microsoft OfficePLUS`<br>`OfficePLUS` and `Microsoft OfficePLUS` under `%LOCALAPPDATA%` and `%APPDATA%` | Removed |

`<App>` means Word, Excel, PowerPoint and Outlook. All rules live in [`src/remove_officeplus/rules.json`](src/remove_officeplus/rules.json), shared by the Python and PowerShell versions.

Other features:

- **Pattern matching**: besides the known names, it finds add-ins whose name or description contains "OfficePLUS" and services whose program points to `MSOfficePLUSService.exe`, so renamed copies are caught too. Other add-ins and services are never touched.
- **Desktop GUI**: a native window that shows scan status and results at a glance.
- **No dependencies**: a PowerShell script and a standalone exe; nothing to install on Windows 10 / 11.
- **Automatic elevation**: a UAC prompt appears when admin rights are needed. If you approve with a different admin account, it still cleans the signed-in user's data.
- **Look before you delete**: scan only (`-Scan` / `--scan`) and dry run (`--dry-run`).

It targets OfficePLUS specifically. If you meet a new variant or a similar add-in, please open an Issue.

---

## Download and quick start

### Option 1: download the exe (recommended)

1. Download the latest `Remove-OfficePlus-GUI-v<version>.exe` (for example `Remove-OfficePlus-GUI-v1.3.0.exe`) from the [Releases page](https://github.com/HenryYannis/remove-officeplus/releases). If GitHub is unreachable, use the [mirror download page](https://files.xbkjz.cn/apps/officeplus/). The app shows its version in the bottom-right corner; the "下载最新版" (download latest) link opens that mirror page.
2. Double-click it and choose "Yes" in the UAC prompt.
3. Click "一键清理" (one-click clean). It cleans and then re-scans automatically.

### Option 2: run online in PowerShell (no download)

Press `Win + X`, open "Terminal" or "PowerShell", then paste and run:

```powershell
irm https://raw.githubusercontent.com/HenryYannis/remove-officeplus/main/scripts/Remove-OfficePlus.ps1 | iex
```

The script scans and lists what it found first, and only cleans after you confirm. This command always runs the latest version in the repository; to read the script first, open the link above in a browser.

### Option 3: double-click the bat file (offline)

1. Download the source zip of this repository and extract it.
2. Double-click `Quick-Remove.bat` in the root folder.
3. Choose "Yes" in the UAC prompt. The script scans first and cleans after you confirm.

### Option 4: Python

Requires Python 3.8 or later:

```bash
python main.py            # start the GUI (default)
python main.py --scan     # scan only
python main.py --dry-run  # dry run: list what cleaning would delete, change nothing
python main.py --nuke     # clean (lists the items and asks to confirm; add -f to skip)
python main.py --version  # show the version
```

### Command-line options

| PowerShell script | Python | What it does |
| :--- | :--- | :--- |
| (no arguments) | `--cli` | Scan, then ask whether to clean |
| `-Scan` | `--scan` | Scan only, change nothing |
| — | `--dry-run` | Dry run: list every item cleaning would delete, change nothing |
| `-Nuke` | `--nuke` | Clean. The Python version lists the items and asks to confirm first; both remind you to save if Office is running |
| `-Force` | `-f` / `--force` / `--yes` | Skip the confirmation and clean |
| — | `--gui` | Start the GUI |
| — | `--version` | Show the version |

With no arguments, the Python version starts the GUI.

> The app's interface and output are currently in Simplified Chinese only.

---

## Safety: backup and restore

- **Back up before deleting**: registry keys are exported to a `.reg` backup before they are deleted; a key whose backup fails is not deleted. After cleaning it re-scans and reports anything that could not be removed.
- **Where backups and logs go**: `Documents\Remove-OfficePlus 备份`. It holds the registry backup (`.reg`), a restore guide (`如何恢复.txt`) and one log per run (`清理日志_<date>_<time>.txt`) recording what was deleted and what failed, with reasons.
- **How to restore**: double-click the backup `.reg` file to import it. Deleted program files are not restored; reinstall the program if you need it.
- **Office will be closed**: Word, Excel, PowerPoint and Outlook must be closed to delete files they hold. If they are running you are reminded to save first, so save your open documents.
- **Admin rights required**: only an administrator can remove system services and machine-wide registry keys, so a UAC prompt appears.
- **Just want to look**: scan or dry-run mode changes nothing.

### Real-world test

On 2026-10-23 I tested v1.1.0 on a Windows 10 PC: OfficePLUS installed automatically by Office and OfficePLUS installed from the official installer were both detected and fully removed; the re-scan found 0 items.

| Scan before cleaning | Re-scan after cleaning |
| :---: | :---: |
| ![14 leftovers found before cleaning](docs/images/scan-before.png) | ![0 found after cleaning](docs/images/scan-after.png) |

The registry is backed up automatically before cleaning and saved with the log in `Documents\Remove-OfficePlus 备份`:

![Backup folder](docs/images/backup-folder.png)

The raw log and registry backup are in [docs/real-test](docs/real-test/).

---

## Build from source

```bash
pip install -e .                      # install (editable)
python -m remove_officeplus --scan    # scan only
python -m remove_officeplus --dry-run # dry run
python scripts/sync_rules.py          # after editing rules.json, sync it into the PowerShell script
python scripts/sync_rules.py --check  # check that both versions use the same rules
pip install pyinstaller
python build_exe.py                   # build the exe and SHA256SUMS.txt into dist/
pip install pytest
python -m pytest tests                # checks that don't touch the system (rule sync, real sample, GUI messages)
```

End-to-end tests run on Windows VMs in GitHub Actions ([`.github/workflows/e2e.yml`](.github/workflows/e2e.yml)): they plant fake leftovers and sentinels, clean with Python, PowerShell 5.1 and PowerShell 7, and check that the leftovers are gone, the sentinels are intact and the backup restores. Pushing a `v*` tag makes [`release.yml`](.github/workflows/release.yml) build the exe and upload it to the Release together with `SHA256SUMS.txt`.

### Project layout

```
remove-officeplus/
├── .github/
│   ├── ISSUE_TEMPLATE/          # Issue templates
│   └── workflows/
│       ├── ci.yml               # Ruff, pytest, PowerShell lint, rule sync and real-sample checks, exe build
│       ├── e2e.yml              # plant fake leftovers on Windows, clean for real, verify
│       └── release.yml          # build and publish the exe when a v* tag is pushed
├── docs/
│   ├── images/                  # screenshots used in the README
│   └── real-test/               # real cleaning log and registry backup sample
├── scripts/
│   ├── Remove-OfficePlus.ps1    # PowerShell version (no dependencies)
│   └── sync_rules.py            # sync rules.json into the PowerShell script
├── src/
│   └── remove_officeplus/       # Python version (also used by the GUI and exe)
│       ├── rules.json           # detection rules (single source)
│       ├── constants.py         # loads the rules
│       ├── discovery.py         # finds renamed add-ins and services by pattern
│       ├── scanner.py           # scanning
│       ├── cleaner.py           # cleaning
│       ├── backup.py            # registry backup and restore guide
│       ├── runlog.py            # cleaning log
│       ├── user_context.py      # decides which user to clean
│       ├── winutil.py           # small Windows system helpers
│       ├── cli.py               # command-line entry
│       └── gui.py               # GUI
├── tests/
│   ├── e2e/                     # end-to-end test scripts
│   ├── gui_result_check.py      # GUI reports cleaning results truthfully
│   ├── real_sample_check.py     # checks rules against the real sample
│   └── test_checks.py           # runs the checks above under pytest
├── build_exe.py                 # builds the exe (with version info and SHA256)
├── Quick-Remove.bat             # double-click to run
├── main.py                      # Python entry point
├── pyproject.toml               # Python package config
├── AGENTS.md                    # development rules
├── SECURITY.md                  # security policy
└── LICENSE                      # MIT License
```

### Contributing

Issues and pull requests are welcome. If cleaning left something behind, please attach that run's log to the Issue. If you find a new variant, add it to `rules.json`, ideally with a registry export from a real installation as evidence. Development rules are in [AGENTS.md](AGENTS.md).

---

## FAQ

**Why doesn't unticking it in Office work?**

- OfficePLUS runs a resident system service, `OfficePLUS Service` (`MSOfficePLUSService.exe`), which starts at boot as `LocalSystem`.
- It writes `LoadBehavior = 3` (load when Office starts) under `HKEY_LOCAL_MACHINE` rather than the current user's `HKCU`. Machine-wide add-in settings take priority over your choice in Office options, so it loads again after a restart.
- It also keeps settings and update files in `ProgramData` and `AppData`.

**Windows says "Windows protected your PC"?**

The exe is not signed with a code-signing certificate, so SmartScreen may block it the first time. Click "More info" → "Run anyway".

**How do I check the exe hasn't been tampered with?**

Each Release includes `SHA256SUMS.txt`. Run `Get-FileHash .\Remove-OfficePlus-GUI-v*.exe` in PowerShell; if the hash matches the file, the download is unchanged.

**Does it affect Office itself?**

No. It only removes OfficePLUS components from your own PC when you run it, and backs up the registry first. If you want OfficePLUS back, reinstall it from the official source at any time.

**Something is still left after cleaning?**

Run a scan again to see what remains. If it still can't be removed, open an Issue and attach the log from `Documents\Remove-OfficePlus 备份`.

---

## License

[MIT](LICENSE) © Henry Yannis

Website: [xbkjz.cn](https://xbkjz.cn)

**Disclaimer**: this is a free, open-source tool developed by an individual. It is not affiliated with, authorized or endorsed by Microsoft or the OfficePLUS product. Microsoft, Office and OfficePLUS are trademarks of their respective owners and are mentioned only to describe what this tool removes. Use at your own risk.
