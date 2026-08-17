# 🧹 Remove-OfficePlus

<p align="center">
  <b>一键彻底根除“微软OfficePLUS”及同类顽固流氓 Office 加载项，彻底杜绝后台常驻与死灰复燃！</b><br>
  <i>Completely Eliminate Microsoft OfficePLUS & Rogue Office Add-ins with Zero Leftovers.</i>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Platform-Windows%2010%20%7C%2011-0078D6.svg?logo=windows" alt="Platform">
  <img src="https://img.shields.io/badge/Language-PowerShell%20%7C%20Python-blue.svg" alt="Language">
  <img src="https://img.shields.io/badge/License-MIT-green.svg" alt="License">
</p>

---

## ❓ 为什么需要这个项目？

很多用户在不知情或安装其他软件被捆绑时，电脑中被装上了 **“微软OfficePLUS”**（或称“微软PPT助手/Office助手”）。

当你试图卸载它时，会遭遇以下**典型流氓对抗机制**：
1. **无法关闭**：在 Word / Excel / PowerPoint 选项中取消勾选插件，重启 Office 后**依然被强制勾选加载**；
2. **无法删除**：文件管理器删除提示“文件已被占用”，无法删除；
3. **死灰复燃**：即使用某些工具删除了部分文件，开机后又被后台守护进程自动下载/修复“复活”！

### 🔍 底层技术原理揭秘
- **系统级服务守护**：常驻运行 `OfficePLUS Service` (`MSOfficePLUSService.exe`)，以 `LocalSystem` 最高权限开机自启。
- **系统全局注册表强载**：在 `HKEY_LOCAL_MACHINE`（而非当前用户 `HKCU`）强写 `LoadBehavior = 3`（强制开机载入）。每次打开 Office，Office 都会按系统级策略强制加载并覆盖用户设置。
- **多处缓存潜伏**：在 `ProgramData` 与 `AppData` 存有配置文件与更新种子。

---

## ✨ 核心特性

- 🛡️ **彻底根除**：进程 ➔ 服务 ➔ 注册表 (HKLM/HKCU/32位兼容层) ➔ 计划任务 ➔ 缓存目录全链路拔除。
- ⚡ **零依赖运行**：核心引擎基于原生 PowerShell 编写，任何 Windows 10/11 电脑无需安装任何环境即可直接运行。
- 🐍 **双模支持**：提供 **PowerShell 极速版** 与 **Python 模块化版**。
- 🔐 **自动提权**：自动检测管理员权限并触发 UAC 提权，无需复杂操作。
- 🔍 **诊断排查模式**：支持仅扫描诊断 (`-Scan` / `--scan`)，清晰列出系统中的威胁组件。

---

## 🚀 快速使用方法

### 方式 1：PowerShell 一键在线运行（最简单，小白推荐）

无需下载任何文件，直接在 Windows 桌面按快捷键 **`Win + X`** 打开 **终端 / PowerShell**，粘贴并运行以下单行命令：

```powershell
# 运行极速排查与彻底清理
irm https://raw.githubusercontent.com/HenryYannis/Remove-OfficePlus/main/scripts/Remove-OfficePlus.ps1 | iex
```

---

### 方式 2：本地双击运行（离线推荐）

1. 下载本仓库或 Release 压缩包；
2. 双击运行根目录下的 **`Quick-Remove.bat`**；
3. 在弹出的 UAC 管理员提权窗口点击 **【是】** 即可完成全自动清理与复检。

---

### 方式 3：Python 命令行运行

如果你已安装 Python 3.8+：

```bash
# 仅扫描诊断
python main.py --scan

# 执行彻底根除
python main.py --nuke
```

---

## 📋 清理覆盖范围

| 模块类别 | 目标路径 / 标识 | 处理方式 |
| :--- | :--- | :--- |
| **后台服务** | `OfficePLUS Service` (`MSOfficePLUSService.exe`) | 停止并 `sc delete` 彻底注销服务 |
| **占用进程** | `MSOfficePLUSService`, `OfficePLUS.AgentLauncher`, `DeepLink` 等 | 强制终止 |
| **系统注册表 (64位)** | `HKLM:\Software\Microsoft\Office\<App>\Addins\MSOfficePLUS` | 彻底移除加载项 |
| **系统注册表 (32位兼容)** | `HKLM:\Software\Wow6432Node\Microsoft\Office\<App>\Addins\MSOfficePLUS` | 彻底移除加载项 |
| **用户注册表** | `HKCU:\Software\Microsoft\Office\<App>\Addins\MSOfficePLUS` | 彻底移除加载项 |
| **卸载残留** | `...\Uninstall\MSOfficePLUS` | 清理控制面板残留键 |
| **安装目录** | `C:\Program Files\Microsoft OfficePLUS` | 彻底删除所有二进制与 DLL |
| **系统与应用缓存** | `C:\ProgramData\Microsoft OfficePLUS`<br>`%LOCALAPPDATA%\OfficePLUS` | 彻底清空数据与配置 |

---

## 📂 项目结构

```
Remove-OfficePlus/
├── scripts/
│   └── Remove-OfficePlus.ps1   # 原生 PowerShell 核心引擎 (零依赖)
├── src/
│   └── remove_officeplus/      # Python 模块化引擎 (支持扩展)
│       ├── __init__.py
│       ├── __main__.py
│       ├── cli.py              # CLI 命令行入口
│       ├── cleaner.py          # 核心清理实现
│       ├── constants.py        # 目标路径与特征定义
│       └── scanner.py          # 诊断与扫描模块
├── Quick-Remove.bat            # Windows 双击快速启动脚本
├── main.py                     # Python 快速启动入口
├── pyproject.toml              # Python 包构建配置
├── README.md                   # 项目说明
└── LICENSE                     # MIT 开源协议
```

---

## 🤝 参与贡献

欢迎提交 Issue 和 Pull Request！如果你发现了其他流氓 Office 加载项或新的变种特征，欢迎补充到规则库中。

## 📜 开源协议

本项目采用 [MIT License](LICENSE) 开源协议。
