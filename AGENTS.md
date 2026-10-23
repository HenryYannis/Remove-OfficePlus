# AGENTS.md — Remove-OfficePlus

本项目用于检测并清除顽固的「微软 OfficePLUS」Office 加载项及其后台服务，防止它自动复活。

## 架构

- **PowerShell 版**（`scripts/Remove-OfficePlus.ps1`）：零依赖，支持 `irm | iex` 在线运行、本地运行和 `Quick-Remove.bat` 双击运行。
- **Python 版**（`src/remove_officeplus/`）：命令行和图形界面，打包后的 exe 也用这套代码。
- **识别规则**（`src/remove_officeplus/rules.json`）：两个版本共用的唯一规则来源。Python 直接读取；PowerShell 由 `scripts/sync_rules.py` 生成到脚本里 BEGIN/END RULES 标记之间（在线运行时手边只有脚本文件）。
- **按特征识别**（`discovery.py` / PS 里的 `Find-OfficePlusAddins`、`Find-OfficePlusServices`）：在写死的名称之外，找名称或描述含 OfficePLUS 的加载项、程序路径指向 `MSOfficePLUSService.exe` 的服务。

## 开发命令

```bash
pip install -e .                      # 安装（开发模式）
python -m remove_officeplus --scan    # 只扫描
python -m remove_officeplus --dry-run # 预演
python scripts/sync_rules.py          # 改完 rules.json 后同步到 PowerShell 脚本
python scripts/sync_rules.py --check  # 检查两边规则是否一致（CI 会跑）
python build_exe.py                   # 打包 exe 和 SHA256SUMS.txt（需要 pip install pyinstaller）
```

端到端测试在 GitHub Actions 的 Windows 虚拟机里运行（`.github/workflows/e2e.yml`）：种下假残留和哨兵，分别用 Python、PowerShell 5.1、PowerShell 7 清理，检查残留删干净、哨兵完好、备份能恢复。

## 硬性规则

1. **先备份再删除**：删注册表前必须先导出备份，备份失败的项不许删；删除后必须复检并如实报告没删掉的项。
2. **不误删**：只按明确的 OfficePLUS 特征匹配。新增规则或匹配方式时，E2E 里要有对应的哨兵（正常的加载项、服务、目录、计划任务）证明不会误删。
3. **不随便关 Office**：正常运行的 Word/Excel/PowerPoint/Outlook 不算威胁；清理时要关闭它们，必须先提醒用户保存。
4. **不吞错误**：扫描或清理出错要记进日志、如实报告，不能让程序卡住或谎报成功。不要写空的 `except: pass`。
5. **规则只改 `rules.json`**，然后运行 `sync_rules.py`；最好附上真实安装的注册表导出作为依据。
6. **编码**：`Remove-OfficePlus.ps1` 保持 UTF-8 带 BOM（PowerShell 5.1 才能正确读中文）；`Quick-Remove.bat` 保持纯 ASCII + CRLF。
7. **兼容性**：Windows 10/11；PowerShell 5.1 和 7+；Python 3.8+。
8. **不改 `gui.py`**：图形界面需要的改进放在它调用的核心代码里。

## 提交流程

- 每个问题一个分支和一个 PR，CI 和 E2E 全绿后再合并，合并后删除分支，仓库只保留 `main`。
- 提交信息和 PR 描述用第一人称写清楚：遇到的问题、我的改动、怎么测试的。

## 发布流程

1. 修改 `src/remove_officeplus/__init__.py` 里的 `__version__`。
2. 推送标签 `v<版本号>`（必须和 `__version__` 一致，否则发布流程会失败）。
3. `release.yml` 自动打包 exe，连同 `SHA256SUMS.txt` 上传到 Release。
4. 在 Release 页面补充更新说明。
