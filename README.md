# Remove-OfficePlus

**简体中文** | [繁體中文](README.zh-Hant.md) | [English](README.en.md)

一键清理「微软 OfficePLUS」Office 加载项、后台服务和残留文件，删除前自动备份注册表。

[![CI](https://github.com/HenryYannis/Remove-OfficePlus/actions/workflows/ci.yml/badge.svg)](https://github.com/HenryYannis/Remove-OfficePlus/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/HenryYannis/remove-officeplus)](https://github.com/HenryYannis/Remove-OfficePlus/releases)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
![Platform](https://img.shields.io/badge/Platform-Windows%2010%20%7C%2011-0078D6.svg?logo=windows)

---

## 能清理什么

不少人发现电脑里多了「微软 OfficePLUS」（也叫「微软 PPT 助手 / Office 助手」），却不记得自己装过。手动卸载时常遇到：

1. **关不掉**：在 Word / Excel / PowerPoint 选项里取消勾选，重启 Office 后又被勾上。
2. **删不掉**：文件管理器提示「文件已被占用」。
3. **会回来**：删掉部分文件后，开机又被后台服务下载或修复回来。

本工具按下面的顺序全链路清理：进程 ➔ 服务 ➔ 注册表（HKLM / HKCU / 32 位 / 即点即用版 Office）➔ 计划任务 ➔ 缓存目录。

| 类别 | 目标路径 / 标识 | 处理方式 |
| :--- | :--- | :--- |
| **后台服务** | `OfficePLUS Service`，以及程序路径指向 `MSOfficePLUSService.exe` 的任何服务 | 停止并用 `sc delete` 注销 |
| **占用进程** | `MSOfficePLUSService`、`OfficePLUS.AgentLauncher`、`DeepLink`、`OfficePLUS`（只结束程序路径在 OfficePLUS 文件夹里的） | 强制结束 |
| **系统注册表（64 位）** | `HKLM:\Software\Microsoft\Office\<App>\Addins\MSOfficePLUS` | 删除加载项 |
| **系统注册表（32 位兼容）** | `HKLM:\Software\Wow6432Node\Microsoft\Office\<App>\Addins\MSOfficePLUS` | 删除加载项 |
| **用户注册表** | `HKCU:\Software\Microsoft\Office\<App>\Addins\MSOfficePLUS` | 删除加载项 |
| **按特征识别的加载项** | 以上各位置及即点即用版 Office 的虚拟注册表中，名称、FriendlyName、Description 或 Manifest 含「OfficePLUS」的加载项 | 删除加载项 |
| **程序配置** | `Software\Microsoft\OfficePLUS`（HKLM、HKLM 32 位、HKCU） | 删除 |
| **卸载残留** | `...\CurrentVersion\Uninstall\MSOfficePLUS`（HKLM、HKLM 32 位、HKCU） | 清理控制面板残留键 |
| **计划任务** | 名称或路径含「OfficePLUS」的计划任务 | 删除 |
| **安装目录** | `%ProgramFiles%\Microsoft OfficePLUS`、`%ProgramFiles(x86)%\Microsoft OfficePLUS` | 删除 |
| **缓存与配置** | `%ProgramData%\Microsoft OfficePLUS`<br>`%LOCALAPPDATA%` 和 `%APPDATA%` 下的 `OfficePLUS`、`Microsoft OfficePLUS` | 删除 |

`<App>` 指 Word、Excel、PowerPoint、Outlook。全部规则写在 [`src/remove_officeplus/rules.json`](src/remove_officeplus/rules.json)，Python 版和 PowerShell 版共用。

其他特点：

- **按特征识别**：除了已知名称，还会找出名称、描述里带「OfficePLUS」的加载项，以及程序指向 `MSOfficePLUSService.exe` 的服务，改了名也能找到；其他加载项和服务一概不碰。
- **图形界面**：原生窗口，扫描状态和清理结果一目了然。
- **零依赖**：PowerShell 脚本和独立 exe，Windows 10 / 11 不用装任何环境。
- **自动提权**：需要管理员权限时弹出 UAC；用其他管理员账号授权时，清理的仍是当前登录用户的数据。
- **只看不删**：支持只扫描（`-Scan` / `--scan`）和预演（`--dry-run`）。

目前专门针对 OfficePLUS。遇到它的新变种或类似的加载项，欢迎提交 Issue。

---

## 下载与快速使用

### 方式 1：下载 exe（推荐）

1. 到 [Releases 页面](https://github.com/HenryYannis/Remove-OfficePlus/releases) 下载最新的 `Remove-OfficePlus-GUI-v版本号.exe`（例如 `Remove-OfficePlus-GUI-v1.3.0.exe`）。打不开 GitHub 的话，可以从[国内下载页](https://files.xbkjz.cn/apps/officeplus/)下载。程序窗口右下角显示当前版本号，点「下载最新版」会打开国内下载页。
2. 双击运行，在 UAC 提示中点「是」。
3. 点「一键清理」，程序会自动清理并复检。

### 方式 2：PowerShell 在线运行（免下载）

按 `Win + X` 打开「终端」或「PowerShell」，粘贴运行：

```powershell
irm https://raw.githubusercontent.com/HenryYannis/remove-officeplus/main/scripts/Remove-OfficePlus.ps1 | iex
```

脚本会先扫描并列出发现的残留，确认后才清理。这条命令始终运行仓库里的最新版本；想先看脚本内容，可以在浏览器里打开上面的链接。

### 方式 3：双击 bat（离线）

1. 下载本仓库源码压缩包并解压。
2. 双击根目录下的 `Quick-Remove.bat`。
3. 在 UAC 提示中点「是」，脚本会先扫描，确认后清理。

### 方式 4：Python

需要 Python 3.8 及以上：

```bash
python main.py            # 启动图形界面（默认）
python main.py --scan     # 只扫描
python main.py --dry-run  # 预演：列出清理时会删除的项目，不做任何修改
python main.py --nuke     # 清理（先列出要删的项目并询问确认，加 -f 跳过确认）
python main.py --version  # 查看版本号
```

### 命令行参数

| PowerShell 脚本 | Python 版 | 作用 |
| :--- | :--- | :--- |
| （不带参数） | `--cli` | 扫描后询问是否清理 |
| `-Scan` | `--scan` | 只扫描，不做任何修改 |
| — | `--dry-run` | 预演：列出清理时会删除的每一项，不做任何修改 |
| `-Nuke` | `--nuke` | 执行清理。Python 版会先列出要删的项目并询问确认；Office 在运行时两者都会先提醒保存 |
| `-Force` | `-f` / `--force` / `--yes` | 跳过确认，直接清理 |
| — | `--gui` | 启动图形界面 |
| — | `--version` | 显示版本号 |

Python 版不带参数时启动图形界面。

---

## 安全：备份与恢复

- **先备份再删除**：要删除的注册表项会先导出成 `.reg` 备份，备份失败的项不删。删完自动复检，没删掉的项会如实列出。
- **备份和日志的位置**：`文档\Remove-OfficePlus 备份`。里面有注册表备份（`.reg`）、《如何恢复.txt》和每次的 `清理日志_日期_时间.txt`（记录这次删了什么、哪里失败及原因）。
- **如何恢复**：双击备份的 `.reg` 文件导入即可恢复注册表。删除的程序文件不会恢复，需要的话重新安装即可。
- **会关闭 Office**：清理时要结束 Word、Excel、PowerPoint、Outlook 才能删掉被占用的文件。检测到它们在运行时会先提醒你保存，请先保存好正在编辑的文档。
- **需要管理员权限**：系统服务和全局注册表只有管理员才能删除，运行时会弹出 UAC 提示。
- **只想先看看**：用扫描或预演模式，不会做任何修改。

### 实测效果

2026-10-23 我在一台 Windows 10 电脑上实测了 v1.1.0：无论是 Office 自动装上的 OfficePLUS，还是从官网下载安装包装的，都能扫描出来并清理干净，复扫为 0。

| 清理前扫描 | 清理后复扫 |
| :---: | :---: |
| ![清理前扫描到 14 处残留](docs/images/scan-before.png) | ![清理后复扫为 0](docs/images/scan-after.png) |

清理前会自动备份注册表，和清理日志一起放在「文档\Remove-OfficePlus 备份」：

![备份文件夹](docs/images/backup-folder.png)

原始日志和注册表备份见 [docs/real-test](docs/real-test/)。

---

## 从源码构建

```bash
pip install -e .                      # 安装（开发模式）
python -m remove_officeplus --scan    # 只扫描
python -m remove_officeplus --dry-run # 预演
python scripts/sync_rules.py          # 改完 rules.json 后同步到 PowerShell 脚本
python scripts/sync_rules.py --check  # 检查两边规则是否一致
pip install pyinstaller
python build_exe.py                   # 打包 exe，并生成 SHA256SUMS.txt，输出在 dist/
pip install pytest
python -m pytest tests                # 不碰系统的检查（规则一致性、真机样本、图形界面提示）
```

端到端测试在 GitHub Actions 的 Windows 虚拟机里运行（[`.github/workflows/e2e.yml`](.github/workflows/e2e.yml)）：种下假残留和哨兵，分别用 Python、PowerShell 5.1、PowerShell 7 清理，检查残留删干净、哨兵完好、备份能恢复。推送 `v*` 标签时，[`release.yml`](.github/workflows/release.yml) 会自动打包 exe 并连同 `SHA256SUMS.txt` 上传到 Release。

### 项目结构

```
remove-officeplus/
├── .github/
│   ├── ISSUE_TEMPLATE/          # Issue 模板
│   └── workflows/
│       ├── ci.yml               # Ruff、pytest、PowerShell 检查、规则一致性和真机样本检查、打包 exe
│       ├── e2e.yml              # 在 Windows 上种下假残留，真实清理并校验
│       └── release.yml          # 推送 v* 标签时自动打包 exe 并发布
├── docs/
│   ├── images/                  # README 用的实测截图
│   └── real-test/               # 真机清理日志和注册表备份样本
├── scripts/
│   ├── Remove-OfficePlus.ps1    # PowerShell 版（零依赖）
│   └── sync_rules.py            # 把 rules.json 同步进 PowerShell 脚本
├── src/
│   └── remove_officeplus/       # Python 版（图形界面和 exe 也用这套代码）
│       ├── rules.json           # 识别规则（唯一来源）
│       ├── constants.py         # 读取规则
│       ├── discovery.py         # 按特征识别改名的加载项和服务
│       ├── scanner.py           # 扫描
│       ├── cleaner.py           # 清理
│       ├── backup.py            # 注册表备份与恢复说明
│       ├── runlog.py            # 清理日志
│       ├── user_context.py      # 确定要清理哪个用户
│       ├── winutil.py           # Windows 系统调用的小工具
│       ├── cli.py               # 命令行入口
│       └── gui.py               # 图形界面
├── tests/
│   ├── e2e/                     # 端到端测试脚本
│   ├── gui_result_check.py      # 图形界面如实提示清理结果
│   ├── real_sample_check.py     # 用真机样本核对识别规则
│   └── test_checks.py           # 用 pytest 跑上面这些检查
├── build_exe.py                 # 打包 exe（含版本信息和 SHA256）
├── Quick-Remove.bat             # 双击运行
├── main.py                      # Python 启动入口
├── pyproject.toml               # Python 包配置
├── AGENTS.md                    # 开发规范
├── SECURITY.md                  # 安全策略
└── LICENSE                      # MIT 开源协议
```

### 参与贡献

欢迎提交 Issue 和 Pull Request。清理没删干净时，提交 Issue 请附上那次的清理日志。发现了新的变种特征，欢迎补充到 `rules.json`，最好附上真实安装后的注册表导出作为依据；开发规范见 [AGENTS.md](AGENTS.md)。

---

## 常见问题

**为什么在 Office 里取消勾选没用？**

- OfficePLUS 有一个常驻的系统服务 `OfficePLUS Service`（`MSOfficePLUSService.exe`），以 `LocalSystem` 权限开机自启。
- 它在 `HKEY_LOCAL_MACHINE`（而不是当前用户的 `HKCU`）写入 `LoadBehavior = 3`（随 Office 启动自动加载）。系统级的加载项设置优先于你在 Office 选项里的勾选，所以取消勾选后重启又会被加载。
- 它还在 `ProgramData` 和 `AppData` 存有配置文件和更新文件。

**Windows 提示「已保护你的电脑」？**

exe 没有购买代码签名证书，第一次运行时 SmartScreen 可能拦截。点「更多信息」→「仍要运行」即可。

**怎么确认下载的 exe 没被改过？**

Release 里附有 `SHA256SUMS.txt`。在 PowerShell 里运行 `Get-FileHash .\Remove-OfficePlus-GUI-v*.exe`，结果和文件里的值一致，说明文件没有被改动。

**会影响 Office 本身吗？**

不会。本工具只在你主动操作时，删除你自己电脑上的 OfficePLUS 相关组件，删除前会备份注册表。如果你需要 OfficePLUS，可以随时从官方渠道重新安装。

**清理后还有残留怎么办？**

再运行一次扫描看看还剩什么。如果仍然删不掉，请提交 Issue 并附上 `文档\Remove-OfficePlus 备份` 里的清理日志。

---

## 开源协议

[MIT](LICENSE) © 2026 程小宝

官网：[xbkjz.cn](https://xbkjz.cn)

**免责声明**：本项目是个人开发的免费开源工具，与微软公司及 OfficePLUS 产品无任何关联，也未获其授权或认可。Microsoft、Office、OfficePLUS 是其各自权利人的商标，本项目提到它们只为说明清理对象。使用风险由使用者自行承担。
