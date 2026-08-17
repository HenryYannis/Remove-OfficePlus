import os
import sys
import ctypes
import threading
import webbrowser
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
from typing import Optional

from .scanner import run_scan, is_admin, ScanReport
from .cleaner import run_nuke, elevate

# 启用 Windows 高 DPI 缩放感知
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass


class ModernGUI(tk.Tk):
    def __init__(self):
        super().__init__()

        self.title("Remove-OfficePlus | Office 顽固插件彻底根除器")
        
        # 默认尺寸与最小尺寸
        default_w = 880
        default_h = 680
        self.geometry(f"{default_w}x{default_h}")
        self.minsize(720, 540)

        # 居中显示
        self._center_window(default_w, default_h)

        # 检查管理员权限
        self.is_admin_user = is_admin()

        self._setup_theme()
        self._create_widgets()

        # 启动后后台自动执行一次排查扫描
        self.after(200, self.start_scan)

    def _center_window(self, width: int, height: int):
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        x = (screen_width - width) // 2
        y = (screen_height - height) // 2
        self.geometry(f"{width}x{height}+{x}+{y}")

    def _setup_theme(self):
        self.configure(bg="#F3F4F6")

        self.style = ttk.Style(self)
        try:
            self.style.theme_use("clam")
        except Exception:
            pass

        # 统一字体配置
        self.default_font = ("Microsoft YaHei UI", 10)
        self.sub_font = ("Microsoft YaHei UI", 9)
        self.log_font = ("Consolas", 10)

        # 样式定义
        self.style.configure("TFrame", background="#F3F4F6")
        self.style.configure("Card.TFrame", background="#FFFFFF", relief="flat")
        self.style.configure("CardTitle.TLabel", background="#FFFFFF", font=("Microsoft YaHei UI", 9), foreground="#6B7280")
        self.style.configure("CardValue.TLabel", background="#FFFFFF", font=("Microsoft YaHei UI", 16, "bold"), foreground="#2563EB")
        self.style.configure("Status.TLabel", background="#F3F4F6", font=("Microsoft YaHei UI", 9), foreground="#4B5563")

    def _open_website(self, event=None):
        webbrowser.open_new_tab("https://xbkjz.cn")

    def _create_widgets(self):
        # ================= 1. 顶部简介与权限状态栏 =================
        top_frame = ttk.Frame(self, style="Card.TFrame", padding=(16, 10))
        top_frame.pack(fill="x", padx=16, pady=(12, 6))

        desc_label = tk.Label(
            top_frame,
            text="专注彻底根除「微软 OfficePLUS」流氓加载项、常驻后台服务与注册表残留。",
            bg="#FFFFFF",
            fg="#374151",
            font=("Microsoft YaHei UI", 9),
            anchor="w"
        )
        desc_label.pack(fill="x", anchor="w")

        # 权限提示横条
        if not self.is_admin_user:
            perm_bar = tk.Frame(top_frame, bg="#FEF3C7", padx=12, pady=5, highlightbackground="#FCD34D", highlightthickness=1)
            perm_bar.pack(fill="x", pady=(8, 0))

            elevate_btn = tk.Button(
                perm_bar,
                text="点击立即提权",
                bg="#D97706",
                activebackground="#B45309",
                fg="#FFFFFF",
                activeforeground="#FFFFFF",
                font=("Microsoft YaHei UI", 9, "bold"),
                relief="flat",
                padx=12,
                pady=2,
                cursor="hand2",
                command=self._do_elevate
            )
            elevate_btn.pack(side="right", padx=(8, 0))

            perm_label = tk.Label(
                perm_bar,
                text="[提示] 当前以普通权限运行，彻底清理服务与系统级注册表需要管理员权限。",
                bg="#FEF3C7",
                fg="#92400E",
                font=self.sub_font,
                anchor="w"
            )
            perm_label.pack(side="left", fill="x", expand=True)
        else:
            perm_bar = tk.Frame(top_frame, bg="#DEF7EC", padx=12, pady=5, highlightbackground="#A7F3D0", highlightthickness=1)
            perm_bar.pack(fill="x", pady=(8, 0))
            perm_label = tk.Label(
                perm_bar,
                text="[状态] 已获取管理员权限 (Administrator)，具备完整的深度根除清理能力。",
                bg="#DEF7EC",
                fg="#03543F",
                font=self.sub_font,
                anchor="w"
            )
            perm_label.pack(side="left", fill="x", expand=True)

        # ================= 2. 状态统计卡片区 (4个指标) =================
        stats_frame = ttk.Frame(self, style="TFrame")
        stats_frame.pack(fill="x", padx=16, pady=4)
        stats_frame.columnconfigure((0, 1, 2, 3), weight=1, uniform="col")

        self.card_proc_val = self._create_stat_card(stats_frame, 0, "运行进程", "0")
        self.card_svc_val = self._create_stat_card(stats_frame, 1, "常驻服务", "0")
        self.card_reg_val = self._create_stat_card(stats_frame, 2, "注册表项", "0")
        self.card_dir_val = self._create_stat_card(stats_frame, 3, "残留目录", "0")

        # ================= 3. 核心控制按钮与状态区 (整体居中对称布局) =================
        control_container = ttk.Frame(self, style="TFrame")
        control_container.pack(fill="x", padx=16, pady=8)

        # 居中按钮组
        buttons_box = ttk.Frame(control_container, style="TFrame")
        buttons_box.pack(anchor="center")

        self.scan_btn = tk.Button(
            buttons_box,
            text="重新排查扫描",
            bg="#2563EB",
            activebackground="#1D4ED8",
            fg="#FFFFFF",
            activeforeground="#FFFFFF",
            font=("Microsoft YaHei UI", 10, "bold"),
            relief="flat",
            padx=24,
            pady=8,
            cursor="hand2",
            command=self.start_scan
        )
        self.scan_btn.pack(side="left", padx=10)

        self.nuke_btn = tk.Button(
            buttons_box,
            text="一键彻底根除",
            bg="#DC2626",
            activebackground="#B91C1C",
            fg="#FFFFFF",
            activeforeground="#FFFFFF",
            font=("Microsoft YaHei UI", 10, "bold"),
            relief="flat",
            padx=28,
            pady=8,
            cursor="hand2",
            command=self.confirm_nuke
        )
        self.nuke_btn.pack(side="left", padx=10)

        # 居中状态显示条
        self.status_label = ttk.Label(control_container, text="准备就绪", style="Status.TLabel", anchor="center")
        self.status_label.pack(anchor="center", pady=(6, 0))

        # ================= 4. 底部状态栏 (固定在整个窗口最底部，左下角放置官网链接) =================
        bottom_bar = ttk.Frame(self, style="TFrame")
        bottom_bar.pack(side="bottom", fill="x", padx=16, pady=(4, 10))

        # 左下角：官方网站超链接
        site_link = tk.Label(
            bottom_bar,
            text="官方网站: xbkjz.cn",
            bg="#F3F4F6",
            fg="#2563EB",
            font=("Microsoft YaHei UI", 9, "underline"),
            cursor="hand2"
        )
        site_link.pack(side="left")
        site_link.bind("<Button-1>", self._open_website)

        # 右下角：轻量状态标识
        version_label = tk.Label(
            bottom_bar,
            text="Remove-OfficePlus 开源工具",
            bg="#F3F4F6",
            fg="#9CA3AF",
            font=("Microsoft YaHei UI", 9)
        )
        version_label.pack(side="right")

        # ================= 5. 日志控制台 (填充中间剩余全部空间) =================
        log_frame = ttk.Frame(self, style="Card.TFrame", padding=(14, 10))
        log_frame.pack(fill="both", expand=True, padx=16, pady=(4, 4))

        log_title = ttk.Label(log_frame, text="执行日志与排查详情：", style="CardTitle.TLabel")
        log_title.pack(anchor="w", pady=(0, 4))

        self.log_text = scrolledtext.ScrolledText(
            log_frame,
            wrap=tk.WORD,
            bg="#18181B",
            fg="#E4E4E7",
            insertbackground="#FFFFFF",
            font=self.log_font,
            relief="flat",
            padx=10,
            pady=8
        )
        self.log_text.pack(fill="both", expand=True)

        # 配置日志颜色标签
        self.log_text.tag_config("info", foreground="#60A5FA")
        self.log_text.tag_config("success", foreground="#34D399")
        self.log_text.tag_config("warn", foreground="#FBBF24")
        self.log_text.tag_config("danger", foreground="#F87171")
        self.log_text.tag_config("muted", foreground="#71717A")

    def _create_stat_card(self, parent, col: int, title: str, init_val: str):
        card = tk.Frame(parent, bg="#FFFFFF", padx=14, pady=8, relief="flat", highlightbackground="#E5E7EB", highlightthickness=1)
        card.grid(row=0, column=col, padx=4, sticky="nsew")

        lbl_title = tk.Label(card, text=title, bg="#FFFFFF", fg="#6B7280", font=self.sub_font)
        lbl_title.pack(anchor="w")

        lbl_val = tk.Label(card, text=init_val, bg="#FFFFFF", fg="#1F2937", font=("Microsoft YaHei UI", 16, "bold"))
        lbl_val.pack(anchor="w", pady=(1, 0))
        return lbl_val

    def log(self, message: str, tag: str = "info"):
        self.log_text.insert(tk.END, message + "\n", tag)
        self.log_text.see(tk.END)

    def _do_elevate(self):
        elevate()

    def set_buttons_state(self, enabled: bool):
        state = tk.NORMAL if enabled else tk.DISABLED
        self.scan_btn.config(state=state)
        self.nuke_btn.config(state=state)

    # ================= 异步任务 =================

    def start_scan(self):
        self.set_buttons_state(False)
        self.status_label.config(text="正在全面扫描排查中……")
        self.log("\n>>> 开始系统环境全面排查扫描……", "info")

        def _worker():
            report = run_scan()
            self.after(0, lambda: self._on_scan_finished(report))

        threading.Thread(target=_worker, daemon=True).start()

    def _on_scan_finished(self, report: ScanReport):
        self.set_buttons_state(True)
        self.status_label.config(text=f"扫描完成：发现 {report.total_threats} 项相关残留")

        # 更新卡片数值与颜色
        self.card_proc_val.config(
            text=str(len(report.processes)),
            fg="#EF4444" if report.processes else "#10B981"
        )
        self.card_svc_val.config(
            text=str(len(report.services)),
            fg="#EF4444" if report.services else "#10B981"
        )
        self.card_reg_val.config(
            text=str(len(report.registry_keys)),
            fg="#EF4444" if report.registry_keys else "#10B981"
        )
        self.card_dir_val.config(
            text=str(len(report.directories)),
            fg="#EF4444" if report.directories else "#10B981"
        )

        # 详细日志输出
        if report.processes:
            for p in report.processes:
                self.log(f"  [-] 发现运行中进程: {p}", "danger")
        else:
            self.log("  [+] 未发现 OfficePLUS 关联进程运行。", "success")

        if report.services:
            for s in report.services:
                self.log(f"  [-] 发现后台常驻服务: {s}", "danger")
        else:
            self.log("  [+] 系统服务未安装或已注销。", "success")

        if report.registry_keys:
            for r in report.registry_keys:
                self.log(f"  [-] 发现注册表项: {r}", "danger")
        else:
            self.log("  [+] 未发现任何 OfficePLUS 相关注册表项。", "success")

        if report.directories:
            for d in report.directories:
                self.log(f"  [-] 发现残留目录: {d}", "danger")
        else:
            self.log("  [+] 未发现任何 OfficePLUS 文件或缓存残留。", "success")

        if report.is_clean:
            self.log("[完成] 检查完毕：系统处于干净状态，未发现任何 OfficePLUS 残留。", "success")
        else:
            self.log(f"[提示] 检查完毕：共排查出 {report.total_threats} 处残留，点击「一键彻底根除」即可清理。", "warn")

    def confirm_nuke(self):
        if not self.is_admin_user:
            if messagebox.askyesno("权限提示", "彻底清理系统服务与全局注册表需要管理员权限。\n\n是否立即以管理员权限重新启动？"):
                self._do_elevate()
            return

        if messagebox.askyesno(
            "确认彻底根除",
            "即将彻底终止相关进程、注销系统服务、拔除注册表加载项并强删残留目录。\n\n请确保已保存当前正在编辑的 Office 文档。\n\n是否立即执行清理？"
        ):
            self.start_nuke()

    def start_nuke(self):
        self.set_buttons_state(False)
        self.status_label.config(text="正在执行彻底根除清理中……")
        self.log("\n==================================================", "muted")
        self.log(">>> 正在启动彻底根除清理程序……", "warn")

        def _worker():
            procs, svcs, regs, tasks, dirs = run_nuke()
            self.after(0, lambda: self._on_nuke_finished(procs, svcs, regs, tasks, dirs))

        threading.Thread(target=_worker, daemon=True).start()

    def _on_nuke_finished(self, procs, svcs, regs, tasks, dirs):
        self.log("  [+] 已终止相关进程", "success")
        self.log("  [+] 已注销并清理相关服务", "success")
        self.log(f"  [+] 已清理 {len(regs)} 项注册表加载项", "success")
        self.log(f"  [+] 已清理 {len(tasks)} 项计划任务", "success")
        self.log(f"  [+] 已强删 {len(dirs)} 处程序与缓存目录", "success")
        self.log("[完成] 微软 OfficePLUS 及关联组件已全部彻底根除。", "success")
        self.log("==================================================\n", "muted")

        messagebox.showinfo("清理完成", "微软 OfficePLUS 及关联组件已全部彻底清除！\n现在系统将自动进行一次复检。")
        self.start_scan()


def launch_gui():
    app = ModernGUI()
    app.mainloop()


if __name__ == "__main__":
    launch_gui()
