# Remove-OfficePlus

[简体中文](README.md) | **繁體中文** | [English](README.en.md)

一鍵清理「微軟 OfficePLUS」Office 增益集、背景服務和殘留檔案，刪除前自動備份登錄檔。

[![CI](https://github.com/HenryYannis/Remove-OfficePlus/actions/workflows/ci.yml/badge.svg)](https://github.com/HenryYannis/Remove-OfficePlus/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/HenryYannis/remove-officeplus)](https://github.com/HenryYannis/Remove-OfficePlus/releases)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
![Platform](https://img.shields.io/badge/Platform-Windows%2010%20%7C%2011-0078D6.svg?logo=windows)

---

## 能清理什麼

不少人發現電腦裡多了「微軟 OfficePLUS」（也叫「微軟 PPT 助手 / Office 助手」），卻不記得自己裝過。手動移除時常遇到：

1. **關不掉**：在 Word / Excel / PowerPoint 選項裡取消勾選，重新啟動 Office 後又被勾上。
2. **刪不掉**：檔案總管提示「檔案正在使用中」。
3. **會回來**：刪掉部分檔案後，開機又被背景服務下載或修復回來。

本工具依下面的順序完整清理：處理程序 ➔ 服務 ➔ 登錄檔（HKLM / HKCU / 32 位元 / 隨選即用版 Office）➔ 排程工作 ➔ 快取資料夾。

| 類別 | 目標路徑 / 識別 | 處理方式 |
| :--- | :--- | :--- |
| **背景服務** | `OfficePLUS Service`，以及程式路徑指向 `MSOfficePLUSService.exe` 的任何服務 | 停止並用 `sc delete` 註銷 |
| **占用的處理程序** | `MSOfficePLUSService`、`OfficePLUS.AgentLauncher`、`DeepLink`、`OfficePLUS`（只結束程式路徑在 OfficePLUS 資料夾裡的） | 強制結束 |
| **系統登錄檔（64 位元）** | `HKLM:\Software\Microsoft\Office\<App>\Addins\MSOfficePLUS` | 刪除增益集 |
| **系統登錄檔（32 位元相容）** | `HKLM:\Software\Wow6432Node\Microsoft\Office\<App>\Addins\MSOfficePLUS` | 刪除增益集 |
| **使用者登錄檔** | `HKCU:\Software\Microsoft\Office\<App>\Addins\MSOfficePLUS` | 刪除增益集 |
| **依特徵識別的增益集** | 以上各位置及隨選即用版 Office 的虛擬登錄檔中，名稱、FriendlyName、Description 或 Manifest 含「OfficePLUS」的增益集 | 刪除增益集 |
| **程式設定** | `Software\Microsoft\OfficePLUS`（HKLM、HKLM 32 位元、HKCU） | 刪除 |
| **解除安裝殘留** | `...\CurrentVersion\Uninstall\MSOfficePLUS`（HKLM、HKLM 32 位元、HKCU） | 清理控制台殘留機碼 |
| **排程工作** | 名稱或路徑含「OfficePLUS」的排程工作 | 刪除 |
| **安裝資料夾** | `%ProgramFiles%\Microsoft OfficePLUS`、`%ProgramFiles(x86)%\Microsoft OfficePLUS` | 刪除 |
| **快取與設定** | `%ProgramData%\Microsoft OfficePLUS`<br>`%LOCALAPPDATA%` 和 `%APPDATA%` 下的 `OfficePLUS`、`Microsoft OfficePLUS` | 刪除 |

`<App>` 指 Word、Excel、PowerPoint、Outlook。所有規則寫在 [`src/remove_officeplus/rules.json`](src/remove_officeplus/rules.json)，Python 版和 PowerShell 版共用。

其他特點：

- **依特徵識別**：除了已知名稱，還會找出名稱、描述裡帶「OfficePLUS」的增益集，以及程式指向 `MSOfficePLUSService.exe` 的服務，改了名也找得到；其他增益集和服務一概不碰。
- **圖形介面**：原生視窗，掃描狀態和清理結果一目了然。
- **免安裝環境**：PowerShell 指令碼和獨立 exe，Windows 10 / 11 不用安裝任何環境。
- **自動提升權限**：需要系統管理員權限時跳出 UAC；用其他系統管理員帳號授權時，清理的仍是目前登入使用者的資料。
- **只看不刪**：支援只掃描（`-Scan` / `--scan`）和預演（`--dry-run`）。

目前專門針對 OfficePLUS。遇到它的新變種或類似的增益集，歡迎提交 Issue。

---

## 下載與快速使用

### 方式 1：下載 exe（推薦）

1. 到 [Releases 頁面](https://github.com/HenryYannis/Remove-OfficePlus/releases) 下載最新的 `Remove-OfficePlus-GUI-v版本號.exe`（例如 `Remove-OfficePlus-GUI-v1.3.0.exe`）。打不開 GitHub 的話，可以從[中國大陸下載頁](https://files.xbkjz.cn/apps/officeplus/)下載。程式視窗右下角顯示目前版本號，點「下载最新版」會開啟這個下載頁。
2. 按兩下執行，在 UAC 提示中點「是」。
3. 點「一键清理」，程式會自動清理並複檢。

### 方式 2：PowerShell 線上執行（免下載）

按 `Win + X` 開啟「終端機」或「PowerShell」，貼上執行：

```powershell
irm https://raw.githubusercontent.com/HenryYannis/remove-officeplus/main/scripts/Remove-OfficePlus.ps1 | iex
```

指令碼會先掃描並列出發現的殘留，確認後才清理。這條指令一律執行儲存庫裡的最新版本；想先看指令碼內容，可以在瀏覽器裡開啟上面的連結。

### 方式 3：按兩下 bat（離線）

1. 下載本儲存庫原始碼壓縮檔並解壓縮。
2. 按兩下根目錄下的 `Quick-Remove.bat`。
3. 在 UAC 提示中點「是」，指令碼會先掃描，確認後清理。

### 方式 4：Python

需要 Python 3.8 以上：

```bash
python main.py            # 啟動圖形介面（預設）
python main.py --scan     # 只掃描
python main.py --dry-run  # 預演：列出清理時會刪除的項目，不做任何修改
python main.py --nuke     # 清理（先列出要刪的項目並詢問確認，加 -f 略過確認）
python main.py --version  # 查看版本號
```

### 命令列參數

| PowerShell 指令碼 | Python 版 | 作用 |
| :--- | :--- | :--- |
| （不帶參數） | `--cli` | 掃描後詢問是否清理 |
| `-Scan` | `--scan` | 只掃描，不做任何修改 |
| — | `--dry-run` | 預演：列出清理時會刪除的每一項，不做任何修改 |
| `-Nuke` | `--nuke` | 執行清理。Python 版會先列出要刪的項目並詢問確認；Office 在執行時兩者都會先提醒存檔 |
| `-Force` | `-f` / `--force` / `--yes` | 略過確認，直接清理 |
| — | `--gui` | 啟動圖形介面 |
| — | `--version` | 顯示版本號 |

Python 版不帶參數時啟動圖形介面。

> 程式介面和輸出目前只有簡體中文。

---

## 安全：備份與還原

- **先備份再刪除**：要刪除的登錄機碼會先匯出成 `.reg` 備份，備份失敗的項目不刪。刪完自動複檢，沒刪掉的項目會如實列出。
- **備份和記錄檔的位置**：`文件\Remove-OfficePlus 备份`（資料夾名稱為簡體中文）。裡面有登錄檔備份（`.reg`）、《如何恢复.txt》和每次的 `清理日志_日期_時間.txt`（記錄這次刪了什麼、哪裡失敗及原因）。
- **如何還原**：按兩下備份的 `.reg` 檔匯入即可還原登錄檔。刪除的程式檔案不會還原，需要的話重新安裝即可。
- **會關閉 Office**：清理時要結束 Word、Excel、PowerPoint、Outlook 才能刪掉被占用的檔案。偵測到它們在執行時會先提醒你存檔，請先儲存正在編輯的文件。
- **需要系統管理員權限**：系統服務和全域登錄檔只有系統管理員才能刪除，執行時會跳出 UAC 提示。
- **只想先看看**：用掃描或預演模式，不會做任何修改。

### 實測結果

2026-10-23 我在一台 Windows 10 電腦上實測了 v1.1.0：無論是 Office 自動裝上的 OfficePLUS，還是從官網下載安裝檔裝的，都能掃描出來並清理乾淨，重新掃描為 0。

| 清理前掃描 | 清理後重新掃描 |
| :---: | :---: |
| ![清理前掃描到 14 處殘留](docs/images/scan-before.png) | ![清理後重新掃描為 0](docs/images/scan-after.png) |

清理前會自動備份登錄檔，和清理記錄檔一起放在「文件\Remove-OfficePlus 备份」：

![備份資料夾](docs/images/backup-folder.png)

原始記錄檔和登錄檔備份見 [docs/real-test](docs/real-test/)。

---

## 從原始碼建置

```bash
pip install -e .                      # 安裝（開發模式）
python -m remove_officeplus --scan    # 只掃描
python -m remove_officeplus --dry-run # 預演
python scripts/sync_rules.py          # 改完 rules.json 後同步到 PowerShell 指令碼
python scripts/sync_rules.py --check  # 檢查兩邊規則是否一致
pip install pyinstaller
python build_exe.py                   # 打包 exe，並產生 SHA256SUMS.txt，輸出在 dist/
pip install pytest
python -m pytest tests                # 不碰系統的檢查（規則一致性、實機樣本、圖形介面提示）
```

端對端測試在 GitHub Actions 的 Windows 虛擬機裡執行（[`.github/workflows/e2e.yml`](.github/workflows/e2e.yml)）：植入假殘留和哨兵，分別用 Python、PowerShell 5.1、PowerShell 7 清理，檢查殘留刪乾淨、哨兵完好、備份能還原。推送 `v*` 標籤時，[`release.yml`](.github/workflows/release.yml) 會自動打包 exe 並連同 `SHA256SUMS.txt` 上傳到 Release。

### 專案結構

```
remove-officeplus/
├── .github/
│   ├── ISSUE_TEMPLATE/          # Issue 範本
│   └── workflows/
│       ├── ci.yml               # Ruff、pytest、PowerShell 檢查、規則一致性和實機樣本檢查、打包 exe
│       ├── e2e.yml              # 在 Windows 上植入假殘留，實際清理並驗證
│       └── release.yml          # 推送 v* 標籤時自動打包 exe 並發布
├── docs/
│   ├── images/                  # README 用的實測截圖
│   └── real-test/               # 實機清理記錄檔和登錄檔備份樣本
├── scripts/
│   ├── Remove-OfficePlus.ps1    # PowerShell 版（免安裝環境）
│   └── sync_rules.py            # 把 rules.json 同步進 PowerShell 指令碼
├── src/
│   └── remove_officeplus/       # Python 版（圖形介面和 exe 也用這套程式碼）
│       ├── rules.json           # 識別規則（唯一來源）
│       ├── constants.py         # 讀取規則
│       ├── discovery.py         # 依特徵識別改名的增益集和服務
│       ├── scanner.py           # 掃描
│       ├── cleaner.py           # 清理
│       ├── backup.py            # 登錄檔備份與還原說明
│       ├── runlog.py            # 清理記錄檔
│       ├── user_context.py      # 決定要清理哪個使用者
│       ├── winutil.py           # Windows 系統呼叫的小工具
│       ├── cli.py               # 命令列入口
│       └── gui.py               # 圖形介面
├── tests/
│   ├── e2e/                     # 端對端測試指令碼
│   ├── gui_result_check.py      # 圖形介面如實提示清理結果
│   ├── real_sample_check.py     # 用實機樣本核對識別規則
│   └── test_checks.py           # 用 pytest 執行上面這些檢查
├── build_exe.py                 # 打包 exe（含版本資訊和 SHA256）
├── Quick-Remove.bat             # 按兩下執行
├── main.py                      # Python 啟動入口
├── pyproject.toml               # Python 套件設定
├── AGENTS.md                    # 開發規範
├── SECURITY.md                  # 安全性政策
└── LICENSE                      # MIT 開源授權
```

### 參與貢獻

歡迎提交 Issue 和 Pull Request。清理沒刪乾淨時，提交 Issue 請附上那次的清理記錄檔。發現了新的變種特徵，歡迎補充到 `rules.json`，最好附上實際安裝後的登錄檔匯出作為依據；開發規範見 [AGENTS.md](AGENTS.md)。

---

## 常見問題

**為什麼在 Office 裡取消勾選沒用？**

- OfficePLUS 有一個常駐的系統服務 `OfficePLUS Service`（`MSOfficePLUSService.exe`），以 `LocalSystem` 權限開機自動啟動。
- 它在 `HKEY_LOCAL_MACHINE`（而不是目前使用者的 `HKCU`）寫入 `LoadBehavior = 3`（隨 Office 啟動自動載入）。系統層級的增益集設定優先於你在 Office 選項裡的勾選，所以取消勾選後重新啟動又會被載入。
- 它還在 `ProgramData` 和 `AppData` 存有設定檔和更新檔。

**Windows 提示「Windows 已保護您的電腦」？**

exe 沒有購買程式碼簽章憑證，第一次執行時 SmartScreen 可能攔截。點「其他資訊」→「仍要執行」即可。

**怎麼確認下載的 exe 沒被改過？**

Release 裡附有 `SHA256SUMS.txt`。在 PowerShell 裡執行 `Get-FileHash .\Remove-OfficePlus-GUI-v*.exe`，結果和檔案裡的值一致，表示檔案沒有被改動。

**會影響 Office 本身嗎？**

不會。本工具只在你主動操作時，刪除你自己電腦上的 OfficePLUS 相關元件，刪除前會備份登錄檔。如果你需要 OfficePLUS，可以隨時從官方管道重新安裝。

**清理後還有殘留怎麼辦？**

再執行一次掃描看看還剩什麼。如果仍然刪不掉，請提交 Issue 並附上 `文件\Remove-OfficePlus 备份` 裡的清理記錄檔。

---

## 開源授權

[MIT](LICENSE) © 2026 程小宝

官網：[xbkjz.cn](https://xbkjz.cn)

**免責聲明**：本專案是個人開發的免費開源工具，與微軟公司及 OfficePLUS 產品無任何關聯，也未獲其授權或認可。Microsoft、Office、OfficePLUS 是其各自權利人的商標，本專案提到它們只為說明清理對象。使用風險由使用者自行承擔。
