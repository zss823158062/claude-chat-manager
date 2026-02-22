import threading
import subprocess
import sys
import tkinter as tk
import customtkinter as ctk
from claude_chat import db
from claude_chat.export import export_session


class App(ctk.CTk):
    def __init__(self):
        super().__init__()

        # Windows DPI 感知
        if sys.platform == "win32":
            try:
                from ctypes import windll
                windll.shcore.SetProcessDpiAwareness(1)
            except Exception:
                pass

        self.title("Claude Code 会话管理器")
        self.geometry("1200x700")
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self._current_project = None
        self._current_session_id = None
        self._project_buttons = []
        self._session_buttons = []

        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=0)
        self.grid_columnconfigure(1, weight=1)

        self._build_toolbar()
        self._build_sidebar()
        self._build_content()
        self._build_statusbar()

        self.bind("<Control-f>", lambda e: self._search_entry.focus_set())

        self._status_label.configure(text="加载中...")
        threading.Thread(target=self._initial_load, daemon=True).start()

    def _initial_load(self):
        projects = db.list_projects()
        self.after(0, lambda: self._render_projects(projects))

    # ── UI 构建 ──────────────────────────────────────────

    def _build_toolbar(self):
        toolbar = ctk.CTkFrame(self, height=40)
        toolbar.grid(row=0, column=0, columnspan=2, sticky="ew", padx=5, pady=(5, 0))
        toolbar.grid_columnconfigure(0, weight=1)

        self._search_entry = ctk.CTkEntry(toolbar, placeholder_text="搜索消息内容...")
        self._search_entry.grid(row=0, column=0, sticky="ew", padx=(5, 2), pady=5)
        self._search_entry.bind("<Return>", lambda e: self._on_search())

        for i, (text, cmd) in enumerate([
            ("搜索", self._on_search),
            ("导出", self._on_export),
            ("删除", self._on_delete),
            ("分析", self._on_analytics),
            ("刷新", self._on_refresh),
        ], start=1):
            ctk.CTkButton(toolbar, text=text, width=60, command=cmd).grid(
                row=0, column=i, padx=2, pady=5
            )

    def _build_sidebar(self):
        sidebar = ctk.CTkFrame(self, width=260)
        sidebar.grid(row=1, column=0, sticky="nsew", padx=(5, 0), pady=5)
        sidebar.grid_rowconfigure(0, weight=1)
        sidebar.grid_rowconfigure(1, weight=1)
        sidebar.grid_columnconfigure(0, weight=1)
        sidebar.grid_propagate(False)

        # 项目列表
        proj_label = ctk.CTkLabel(sidebar, text="项目", anchor="w", font=ctk.CTkFont(size=13, weight="bold"))
        proj_label.grid(row=0, column=0, sticky="nw", padx=8, pady=(6, 0))

        self._project_frame = ctk.CTkScrollableFrame(sidebar, width=240)
        self._project_frame.grid(row=0, column=0, sticky="nsew", padx=4, pady=(28, 2))

        # 会话列表
        sess_label = ctk.CTkLabel(sidebar, text="会话", anchor="w", font=ctk.CTkFont(size=13, weight="bold"))
        sess_label.grid(row=1, column=0, sticky="nw", padx=8, pady=(6, 0))

        self._session_frame = ctk.CTkScrollableFrame(sidebar, width=240)
        self._session_frame.grid(row=1, column=0, sticky="nsew", padx=4, pady=(28, 4))

    def _build_content(self):
        content = ctk.CTkFrame(self)
        content.grid(row=1, column=1, sticky="nsew", padx=5, pady=5)
        content.grid_rowconfigure(1, weight=1)
        content.grid_columnconfigure(0, weight=1)

        # 信息栏
        self._info_label = ctk.CTkLabel(
            content, text="选择一个会话查看详情", anchor="w",
            font=ctk.CTkFont(size=12)
        )
        self._info_label.grid(row=0, column=0, sticky="ew", padx=8, pady=(6, 2))

        # 消息内容
        self._textbox = ctk.CTkTextbox(content, wrap="word", state="disabled",
                                        font=ctk.CTkFont(size=13))
        self._textbox.grid(row=1, column=0, sticky="nsew", padx=4, pady=(0, 4))

        # 配置角色颜色 tag
        tw = self._textbox._textbox
        tw.tag_configure("role_user", foreground="#5dade2", font=("Consolas", 13, "bold"))
        tw.tag_configure("role_assistant", foreground="#58d68d", font=("Consolas", 13, "bold"))
        tw.tag_configure("separator", foreground="#555555")

    def _build_statusbar(self):
        self._status_label = ctk.CTkLabel(self, text="就绪", anchor="w",
                                           font=ctk.CTkFont(size=11))
        self._status_label.grid(row=2, column=0, columnspan=2, sticky="ew", padx=10, pady=(0, 4))

    # ── 数据加载 ──────────────────────────────────────────

    def _load_projects(self):
        projects = db.list_projects()
        self._render_projects(projects)

    def _render_projects(self, projects):

        for btn in self._project_buttons:
            btn.destroy()
        self._project_buttons.clear()

        for p in projects:
            label = f"{p['display_name']}  ({p['session_count']})"
            btn = ctk.CTkButton(
                self._project_frame, text=label, anchor="w",
                fg_color="transparent", hover_color=("gray75", "gray30"),
                font=ctk.CTkFont(size=12),
                command=lambda d=p["dirname"]: self._on_project_select(d),
            )
            btn.pack(fill="x", padx=2, pady=1)
            btn._dirname = p["dirname"]
            btn.bind("<Button-3>", lambda e, d=p["dirname"]: self._show_project_menu(e, d))
            self._project_buttons.append(btn)

        total_sessions = sum(p["session_count"] for p in projects)
        self._status_label.configure(text=f"共 {len(projects)} 个项目, {total_sessions} 个会话")

    def _load_sessions(self, dirname):
        sessions = db.list_sessions(dirname)

        for btn in self._session_buttons:
            btn.destroy()
        self._session_buttons.clear()

        for s in sessions:
            label = f"{s['session_id'][:8]}  {s['title']}"
            btn = ctk.CTkButton(
                self._session_frame, text=label, anchor="w",
                fg_color="transparent", hover_color=("gray75", "gray30"),
                font=ctk.CTkFont(size=11),
                command=lambda sid=s["session_id"]: self._on_session_select(sid),
            )
            btn.pack(fill="x", padx=2, pady=1)
            btn._session_id = s["session_id"]
            btn.bind("<Button-3>", lambda e, sid=s["session_id"]: self._show_session_menu(e, sid))
            self._session_buttons.append(btn)

    def _load_detail(self, session_id):
        data = db.get_session_detail(session_id)
        if not data:
            self._info_label.configure(text="无法加载会话")
            return

        title = data.get("slug") or session_id[:8]
        project = data.get("project") or "未知"
        model = data.get("model") or "未知"
        msg_count = len(data["messages"])
        self._info_label.configure(
            text=f"{title}  |  项目: {project}  |  模型: {model}  |  消息: {msg_count}"
        )

        self._textbox.configure(state="normal")
        self._textbox.delete("1.0", "end")
        tw = self._textbox._textbox

        for msg in data["messages"]:
            role_label = "You" if msg["role"] == "user" else "Claude"
            tag = "role_user" if msg["role"] == "user" else "role_assistant"

            tw.insert("end", f"--- {role_label} ---\n", tag)
            tw.insert("end", msg["content"] + "\n\n")

        self._textbox.configure(state="disabled")

    # ── 交互事件 ──────────────────────────────────────────

    def _on_project_select(self, dirname):
        self._current_project = dirname
        self._current_session_id = None

        # 高亮选中项目
        for btn in self._project_buttons:
            if btn._dirname == dirname:
                btn.configure(fg_color=("gray70", "gray35"))
            else:
                btn.configure(fg_color="transparent")

        self._load_sessions(dirname)

    def _on_session_select(self, session_id):
        self._current_session_id = session_id

        # 高亮选中会话
        for btn in self._session_buttons:
            if btn._session_id == session_id:
                btn.configure(fg_color=("gray70", "gray35"))
            else:
                btn.configure(fg_color="transparent")

        self._load_detail(session_id)

    def _on_search(self):
        keyword = self._search_entry.get().strip()
        if not keyword:
            return

        self._status_label.configure(text=f"搜索 \"{keyword}\" 中...")

        def _do_search():
            results = db.search_messages(keyword)
            self.after(0, lambda: self._show_search_results(results, keyword))

        threading.Thread(target=_do_search, daemon=True).start()

    def _show_search_results(self, results, keyword):
        self._status_label.configure(text=f"搜索 \"{keyword}\": 找到 {len(results)} 条结果")

        # 清空会话列表，显示搜索结果
        for btn in self._session_buttons:
            btn.destroy()
        self._session_buttons.clear()

        # 去重：同一会话只显示一次
        seen = set()
        for r in results:
            sid = r["session_id"]
            if sid in seen:
                continue
            seen.add(sid)

            label = f"{sid[:8]}  {r['match_preview'][:40]}"
            btn = ctk.CTkButton(
                self._session_frame, text=label, anchor="w",
                fg_color="transparent", hover_color=("gray75", "gray30"),
                font=ctk.CTkFont(size=11),
                command=lambda s=sid: self._on_session_select(s),
            )
            btn.pack(fill="x", padx=2, pady=1)
            btn._session_id = sid
            btn.bind("<Button-3>", lambda e, s=sid: self._show_session_menu(e, s))
            self._session_buttons.append(btn)

        # 取消项目高亮
        for btn in self._project_buttons:
            btn.configure(fg_color="transparent")
        self._current_project = None

    def _on_export(self):
        if not self._current_session_id:
            self._status_label.configure(text="请先选择一个会话")
            return
        self._export_session(self._current_session_id)

    def _on_delete(self):
        if not self._current_session_id:
            self._status_label.configure(text="请先选择一个会话")
            return
        self._delete_session(self._current_session_id)

    def _on_analytics(self):
        from claude_chat.analytics import AnalyticsWindow
        AnalyticsWindow(self)

    def _on_refresh(self):
        db._session_project_cache = None
        db._first_message_cache = None
        db._token_stats_cache = None
        db._activity_cache = None
        self._current_project = None
        self._current_session_id = None

        for btn in self._session_buttons:
            btn.destroy()
        self._session_buttons.clear()

        self._info_label.configure(text="选择一个会话查看详情")
        self._textbox.configure(state="normal")
        self._textbox.delete("1.0", "end")
        self._textbox.configure(state="disabled")

        self._load_projects()
        self._status_label.configure(text="已刷新")

    # ── 右键菜单 ──────────────────────────────────────────

    def _show_session_menu(self, event, session_id):
        menu = tk.Menu(self, tearoff=0)
        menu.configure(bg="#2b2b2b", fg="white", activebackground="#3a7ebf",
                       activeforeground="white", relief="flat")
        menu.add_command(label="导出", command=lambda: self._export_session(session_id))
        menu.add_command(label="删除", command=lambda: self._delete_session(session_id))
        menu.add_separator()
        menu.add_command(label="分析", command=lambda: self._analyze_session(session_id))
        menu.tk_popup(event.x_root, event.y_root)

    def _show_project_menu(self, event, dirname):
        menu = tk.Menu(self, tearoff=0)
        menu.configure(bg="#2b2b2b", fg="white", activebackground="#3a7ebf",
                       activeforeground="white", relief="flat")
        menu.add_command(label="导出所有会话", command=lambda: self._export_project(dirname))
        menu.add_command(label="删除所有会话", command=lambda: self._delete_project(dirname))
        menu.add_separator()
        menu.add_command(label="分析", command=lambda: self._analyze_project(dirname))
        menu.tk_popup(event.x_root, event.y_root)

    def _analyze_session(self, session_id):
        from claude_chat.analytics import AnalyticsWindow
        AnalyticsWindow(self, session_id=session_id)

    def _analyze_project(self, dirname):
        from claude_chat.analytics import AnalyticsWindow
        AnalyticsWindow(self, project_dirname=dirname)

    def _export_session(self, session_id):
        filepath = export_session(session_id)
        if filepath:
            self._status_label.configure(text=f"已导出: {filepath.name}")
            if sys.platform == "win32":
                subprocess.Popen(["explorer", "/select,", str(filepath)])
        else:
            self._status_label.configure(text="导出失败")

    def _delete_session(self, session_id):
        self._show_confirm_dialog(
            f"确定删除会话 {session_id[:8]}... ?",
            lambda: self._do_delete_session(session_id),
        )

    def _do_delete_session(self, session_id):
        ok = db.delete_session(session_id)
        if ok:
            self._status_label.configure(text="已删除")
            if self._current_session_id == session_id:
                self._current_session_id = None
                self._info_label.configure(text="选择一个会话查看详情")
                self._textbox.configure(state="normal")
                self._textbox.delete("1.0", "end")
                self._textbox.configure(state="disabled")
            if self._current_project:
                self._load_sessions(self._current_project)
            self._load_projects()
        else:
            self._status_label.configure(text="删除失败")

    def _export_project(self, dirname):
        sessions = db.list_sessions(dirname)
        if not sessions:
            self._status_label.configure(text="该项目没有会话")
            return
        exported = 0
        last_path = None
        for s in sessions:
            fp = export_session(s["session_id"])
            if fp:
                exported += 1
                last_path = fp
        self._status_label.configure(text=f"已导出 {exported} 个会话")
        if last_path and sys.platform == "win32":
            subprocess.Popen(["explorer", "/select,", str(last_path)])

    def _delete_project(self, dirname):
        sessions = db.list_sessions(dirname)
        count = len(sessions)
        if not count:
            self._status_label.configure(text="该项目没有会话")
            return
        self._show_confirm_dialog(
            f"确定删除该项目下全部 {count} 个会话?",
            lambda: self._do_delete_project(dirname, sessions),
        )

    def _do_delete_project(self, dirname, sessions):
        deleted = 0
        for s in sessions:
            if db.delete_session(s["session_id"]):
                deleted += 1
        self._status_label.configure(text=f"已删除 {deleted} 个会话")
        self._current_session_id = None
        self._info_label.configure(text="选择一个会话查看详情")
        self._textbox.configure(state="normal")
        self._textbox.delete("1.0", "end")
        self._textbox.configure(state="disabled")
        if self._current_project == dirname:
            for btn in self._session_buttons:
                btn.destroy()
            self._session_buttons.clear()
            self._current_project = None
        self._load_projects()

    # ── 确认对话框 ────────────────────────────────────────

    def _show_confirm_dialog(self, message, on_confirm):
        dialog = ctk.CTkToplevel(self)
        dialog.title("确认")
        dialog.geometry("360x150")
        dialog.resizable(False, False)
        dialog.transient(self)
        dialog.grab_set()

        # 居中
        dialog.update_idletasks()
        x = self.winfo_x() + (self.winfo_width() - 360) // 2
        y = self.winfo_y() + (self.winfo_height() - 150) // 2
        dialog.geometry(f"+{x}+{y}")

        ctk.CTkLabel(dialog, text=message, wraplength=300).pack(pady=(20, 15))

        btn_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_frame.pack()

        def confirm():
            dialog.destroy()
            on_confirm()

        ctk.CTkButton(btn_frame, text="确定", width=80, fg_color="#c0392b",
                       hover_color="#e74c3c", command=confirm).pack(side="left", padx=10)
        ctk.CTkButton(btn_frame, text="取消", width=80,
                       command=dialog.destroy).pack(side="left", padx=10)
