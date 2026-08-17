# AGENTS.md — OfficePLUS-Nuker

本项目用于全面检测、彻底清除顽固的“微软OfficePLUS”及同类流氓 Office 加载项，杜绝其后台服务常驻及自动复活。

## 项目定位与架构

- **定位**：轻量、开源、安全、零依赖的 Windows Office 顽固插件彻底根除工具。
- **双模设计**：
  1. **PowerShell Core (`scripts/OfficePLUS-Nuker.ps1`)**：零依赖的原生 PowerShell 核心引擎，支持无 Python 环境下的开箱即用与单行网页直接运行。
  2. **Python CLI/GUI (`src/officeplus_nuker/`)**：面向对象封装，提供交互式命令行与后续轻量桌面 GUI 扩展能力。
- **启动器 (`Quick-Nuke.bat`)**：提供双击直接触发 UAC 管理员提权运行的便携方式。

## 核心规范

1. **安全性第一**：任何破坏性操作（如删除注册表键、注销服务、删除目录）必须支持前置检测、`-Backup` 备份机制及友好提示。
2. **零残留标准**：
   - 进程：关闭所有可能锁死文件的 Office 主程序及守护进程；
   - 服务：彻底停止并 `sc delete` 注销 `OfficePLUS Service`；
   - 注册表：完整覆盖 `HKLM`、`HKCU`、`Wow6432Node` 下的 Word/Excel/PowerPoint/Outlook 加载项与卸载残留；
   - 目录：扫除 `Program Files`、`Program Files (x86)`、`ProgramData`、`AppData\Local` 目录。
3. **环境约束**：
   - 运行环境为 Windows 10/11 x64。
   - PowerShell 脚本需完全兼容 PowerShell 5.1 及 PowerShell 7+。
