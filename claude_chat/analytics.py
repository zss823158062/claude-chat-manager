import threading
import math
import tkinter as tk
from collections import defaultdict, Counter
import customtkinter as ctk
from claude_chat import db

CHART_COLORS = [
    "#3498db", "#2ecc71", "#e74c3c", "#f39c12",
    "#9b59b6", "#1abc9c", "#e67e22", "#34495e",
]


def _format_tokens(n):
    if n >= 1_000_000:
        return f"{n / 1_000_000:.2f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return str(n)


# ── 图表绘制 ──────────────────────────────────────────────


def draw_bar_chart(canvas, data, title="", bar_color="#3498db", show_values=True):
    """绘制柱状图。data: [(label, value), ...]"""
    canvas.delete("all")
    w = canvas.winfo_width()
    h = canvas.winfo_height()
    if w < 50 or h < 50 or not data:
        return

    left, right, top, bottom = 60, 20, 40, 50
    chart_w = w - left - right
    chart_h = h - top - bottom

    if title:
        canvas.create_text(w // 2, 16, text=title, fill="#cccccc",
                           font=("", 12, "bold"))

    max_val = max(v for _, v in data) or 1
    bar_w = max(4, chart_w // len(data) - 6)

    # Y 轴刻度
    for i in range(5):
        y = top + chart_h * i // 4
        val = max_val * (4 - i) / 4
        canvas.create_line(left, y, w - right, y, fill="#3a3a3a")
        canvas.create_text(left - 5, y, text=_format_tokens(int(val)),
                           fill="#888888", anchor="e", font=("", 9))

    # 基线
    canvas.create_line(left, top + chart_h, w - right, top + chart_h, fill="#555555")

    for i, (label, val) in enumerate(data):
        x = left + (i + 0.5) * chart_w / len(data)
        bar_h = (val / max_val) * chart_h if max_val else 0
        x1 = x - bar_w // 2
        x2 = x + bar_w // 2
        y1 = top + chart_h - bar_h
        y2 = top + chart_h

        canvas.create_rectangle(x1, y1, x2, y2, fill=bar_color, outline="")

        if show_values and val > 0:
            canvas.create_text(x, y1 - 8, text=_format_tokens(int(val)),
                               fill="#cccccc", font=("", 8))

        # X 轴标签（截断过长的）
        display_label = label if len(label) <= 8 else label[:7] + ".."
        canvas.create_text(x, top + chart_h + 12, text=display_label,
                           fill="#aaaaaa", font=("", 8), angle=30 if len(data) > 10 else 0)


def draw_stacked_bar_chart(canvas, data, legend, colors=None, title=""):
    """绘制堆叠柱状图。data: [(label, [val1, val2, ...]), ...]"""
    canvas.delete("all")
    w = canvas.winfo_width()
    h = canvas.winfo_height()
    if w < 50 or h < 50 or not data:
        return

    colors = colors or CHART_COLORS
    left, right, top, bottom = 60, 20, 40, 60

    chart_w = w - left - right
    chart_h = h - top - bottom

    if title:
        canvas.create_text(w // 2, 16, text=title, fill="#cccccc",
                           font=("", 12, "bold"))

    max_val = max(sum(vals) for _, vals in data) or 1
    bar_w = max(4, chart_w // len(data) - 6)

    # Y 轴
    for i in range(5):
        y = top + chart_h * i // 4
        val = max_val * (4 - i) / 4
        canvas.create_line(left, y, w - right, y, fill="#3a3a3a")
        canvas.create_text(left - 5, y, text=_format_tokens(int(val)),
                           fill="#888888", anchor="e", font=("", 9))

    canvas.create_line(left, top + chart_h, w - right, top + chart_h, fill="#555555")

    for i, (label, vals) in enumerate(data):
        x = left + (i + 0.5) * chart_w / len(data)
        x1 = x - bar_w // 2
        x2 = x + bar_w // 2
        y_bottom = top + chart_h

        for j, v in enumerate(vals):
            seg_h = (v / max_val) * chart_h if max_val else 0
            y_top = y_bottom - seg_h
            canvas.create_rectangle(x1, y_top, x2, y_bottom,
                                    fill=colors[j % len(colors)], outline="")
            y_bottom = y_top

        display_label = label if len(label) <= 8 else label[:7] + ".."
        canvas.create_text(x, top + chart_h + 12, text=display_label,
                           fill="#aaaaaa", font=("", 8), angle=30 if len(data) > 10 else 0)

    # 图例
    lx = left
    for j, name in enumerate(legend):
        canvas.create_rectangle(lx, h - 18, lx + 12, h - 6,
                                fill=colors[j % len(colors)], outline="")
        canvas.create_text(lx + 16, h - 12, text=name, fill="#cccccc",
                           anchor="w", font=("", 9))
        lx += len(name) * 8 + 40


def draw_pie_chart(canvas, data, colors=None, title=""):
    """绘制饼图。data: [(label, value), ...]"""
    canvas.delete("all")
    w = canvas.winfo_width()
    h = canvas.winfo_height()
    if w < 50 or h < 50 or not data:
        return

    colors = colors or CHART_COLORS
    total = sum(v for _, v in data) or 1

    if title:
        canvas.create_text(w // 3, 16, text=title, fill="#cccccc",
                           font=("", 12, "bold"))

    # 饼图区域（左侧 2/3）
    pie_cx = w // 3
    pie_cy = h // 2 + 10
    radius = min(w // 3, h // 2) - 30
    if radius < 20:
        return

    start = 90  # 从 12 点方向开始
    for i, (label, val) in enumerate(data):
        extent = (val / total) * 360
        canvas.create_arc(
            pie_cx - radius, pie_cy - radius,
            pie_cx + radius, pie_cy + radius,
            start=start, extent=-extent,
            fill=colors[i % len(colors)], outline="#2b2b2b", width=2,
        )
        start -= extent

    # 右侧图例
    legend_x = w * 2 // 3
    legend_y = 40
    for i, (label, val) in enumerate(data):
        pct = val / total * 100
        canvas.create_rectangle(legend_x, legend_y, legend_x + 14, legend_y + 14,
                                fill=colors[i % len(colors)], outline="")
        display = label if len(label) <= 20 else label[:18] + ".."
        canvas.create_text(legend_x + 20, legend_y + 7,
                           text=f"{display}  {pct:.1f}%",
                           fill="#cccccc", anchor="w", font=("", 10))
        legend_y += 24


# ── 分析弹窗 ──────────────────────────────────────────────


class AnalyticsWindow(ctk.CTkToplevel):
    def __init__(self, master, project_dirname=None, session_id=None):
        super().__init__(master)
        self.geometry("900x650")
        self.transient(master)

        self._project_dirname = project_dirname
        self._session_id = session_id
        self._token_records = []
        self._activity_records = []

        # 窗口标题
        if session_id:
            self.title(f"数据分析 - 会话 {session_id[:8]}")
        elif project_dirname:
            self.title(f"数据分析 - 项目")
        else:
            self.title("数据分析 - 全局")

        # 加载提示
        self._loading_label = ctk.CTkLabel(self, text="正在分析...",
                                            font=ctk.CTkFont(size=16))
        self._loading_label.pack(expand=True)

        threading.Thread(target=self._load_data, daemon=True).start()

    def _load_data(self):
        token_records = db.collect_token_stats()
        activity_records = db.collect_session_activity()

        # 按范围过滤
        if self._session_id:
            token_records = [r for r in token_records
                            if r["session_id"] == self._session_id]
            activity_records = [r for r in activity_records
                               if r["session_id"] == self._session_id]
        elif self._project_dirname:
            token_records = [r for r in token_records
                            if r["project_dirname"] == self._project_dirname]
            # activity_records 没有 project_dirname，用 project 名匹配
            project_names = {r["project"] for r in token_records}
            session_ids = {r["session_id"] for r in token_records}
            activity_records = [r for r in activity_records
                               if r["session_id"] in session_ids
                               or r["project"] in project_names]

        self._token_records = token_records
        self._activity_records = activity_records

        # 更新窗口标题（用实际项目名）
        if self._project_dirname and token_records:
            proj_name = token_records[0]["project"]
            self.after(0, lambda: self.title(f"数据分析 - {proj_name}"))

        self.after(0, self._build_ui)

    def _build_ui(self):
        self._loading_label.destroy()

        tabview = ctk.CTkTabview(self)
        tabview.pack(fill="both", expand=True, padx=10, pady=10)

        self._tab_overview = tabview.add("总览")
        self._tab_tokens = tabview.add("Token 消耗")
        self._tab_models = tabview.add("模型分布")
        self._tab_activity = tabview.add("活跃时段")

        self._build_overview()
        self._build_tokens()
        self._build_models()
        self._build_activity()

    # ── 总览 ──

    def _build_overview(self):
        tab = self._tab_overview
        tab.grid_columnconfigure((0, 1, 2, 3), weight=1)
        tab.grid_rowconfigure(1, weight=1)

        # 统计数据
        sessions = set()
        total_msgs = len(self._token_records)
        total_tokens = 0
        dates = set()

        for r in self._token_records:
            sessions.add(r["session_id"])
            total_tokens += r["input_tokens"] + r["output_tokens"]
            ts = r["timestamp"]
            if ts:
                dates.add(ts[:10])

        cards = [
            ("会话数", str(len(sessions))),
            ("消息数", str(total_msgs)),
            ("总 Token", _format_tokens(total_tokens)),
            ("活跃天数", str(len(dates))),
        ]
        for i, (title, value) in enumerate(cards):
            self._build_stat_card(tab, title, value, 0, i)

        # 按日期会话数柱状图
        date_sessions = defaultdict(set)
        for r in self._token_records:
            ts = r["timestamp"]
            if ts:
                date_sessions[ts[:10]].add(r["session_id"])

        chart_data = sorted(
            [(d, len(sids)) for d, sids in date_sessions.items()]
        )
        # 只显示最近 30 天
        chart_data = chart_data[-30:]
        # 日期标签简化为 MM-DD
        chart_data = [(d[5:], v) for d, v in chart_data]

        canvas = tk.Canvas(tab, bg="#2b2b2b", highlightthickness=0)
        canvas.grid(row=1, column=0, columnspan=4, sticky="nsew", padx=4, pady=4)
        self._overview_canvas = canvas
        self._overview_data = chart_data
        canvas.bind("<Configure>", lambda e: draw_bar_chart(
            canvas, self._overview_data, title="每日会话数（近 30 天）"))

    def _build_stat_card(self, parent, title, value, row, col):
        card = ctk.CTkFrame(parent, corner_radius=8)
        card.grid(row=row, column=col, padx=6, pady=6, sticky="nsew")
        ctk.CTkLabel(card, text=title, font=ctk.CTkFont(size=11),
                     text_color="gray60").pack(pady=(10, 2))
        ctk.CTkLabel(card, text=value,
                     font=ctk.CTkFont(size=22, weight="bold")).pack(pady=(0, 10))

    # ── Token 消耗 ──

    def _build_tokens(self):
        tab = self._tab_tokens
        tab.grid_rowconfigure(1, weight=1)
        tab.grid_rowconfigure(2, weight=0)
        tab.grid_columnconfigure(0, weight=1)

        self._token_dim_var = ctk.StringVar(value="按项目")
        seg = ctk.CTkSegmentedButton(
            tab, values=["按项目", "按模型", "按日期"],
            variable=self._token_dim_var,
            command=self._on_token_dim_change,
        )
        seg.grid(row=0, column=0, padx=10, pady=(8, 4), sticky="ew")

        self._token_canvas = tk.Canvas(tab, bg="#2b2b2b", highlightthickness=0)
        self._token_canvas.grid(row=1, column=0, sticky="nsew", padx=4, pady=4)

        self._token_table_frame = ctk.CTkScrollableFrame(tab, height=140)
        self._token_table_frame.grid(row=2, column=0, sticky="ew", padx=4, pady=(0, 4))

        self._on_token_dim_change("按项目")

    def _on_token_dim_change(self, dim):
        if dim == "按项目":
            agg = self._agg_tokens_by("project")
        elif dim == "按模型":
            agg = self._agg_tokens_by("model")
        else:
            agg = self._agg_tokens_by_date()

        # 限制显示前 15 项
        agg = agg[:15]

        chart_data = [(label, [inp, out]) for label, inp, out in agg]
        self._token_chart_data = chart_data

        self._token_canvas.bind("<Configure>", lambda e: draw_stacked_bar_chart(
            self._token_canvas, self._token_chart_data,
            legend=["Input", "Output"],
            colors=["#3498db", "#2ecc71"],
        ))
        # 立即绘制一次
        self._token_canvas.after(50, lambda: draw_stacked_bar_chart(
            self._token_canvas, self._token_chart_data,
            legend=["Input", "Output"],
            colors=["#3498db", "#2ecc71"],
        ))

        # 更新表格
        for w in self._token_table_frame.winfo_children():
            w.destroy()

        headers = ["名称", "Input", "Output", "合计"]
        for j, h in enumerate(headers):
            ctk.CTkLabel(self._token_table_frame, text=h,
                         font=ctk.CTkFont(size=11, weight="bold")).grid(
                row=0, column=j, padx=8, pady=2, sticky="w")

        for i, (label, inp, out) in enumerate(agg, start=1):
            vals = [label, _format_tokens(inp), _format_tokens(out),
                    _format_tokens(inp + out)]
            for j, v in enumerate(vals):
                ctk.CTkLabel(self._token_table_frame, text=v,
                             font=ctk.CTkFont(size=11)).grid(
                    row=i, column=j, padx=8, pady=1, sticky="w")

    def _agg_tokens_by(self, key):
        agg = defaultdict(lambda: [0, 0])
        for r in self._token_records:
            k = r[key]
            agg[k][0] += r["input_tokens"]
            agg[k][1] += r["output_tokens"]
        result = [(k, v[0], v[1]) for k, v in agg.items()]
        result.sort(key=lambda x: x[1] + x[2], reverse=True)
        return result

    def _agg_tokens_by_date(self):
        agg = defaultdict(lambda: [0, 0])
        for r in self._token_records:
            ts = r["timestamp"]
            if ts:
                d = ts[:10]
                agg[d][0] += r["input_tokens"]
                agg[d][1] += r["output_tokens"]
        result = [(k, v[0], v[1]) for k, v in agg.items()]
        result.sort()
        return result[-30:]  # 最近 30 天

    # ── 模型分布 ──

    def _build_models(self):
        tab = self._tab_models

        counter = Counter()
        for r in self._token_records:
            counter[r["model"]] += 1

        chart_data = counter.most_common(8)
        self._model_data = chart_data

        canvas = tk.Canvas(tab, bg="#2b2b2b", highlightthickness=0)
        canvas.pack(fill="both", expand=True, padx=4, pady=4)
        canvas.bind("<Configure>", lambda e: draw_pie_chart(
            canvas, self._model_data, title="模型使用分布"))

    # ── 活跃时段 ──

    def _build_activity(self):
        tab = self._tab_activity

        counter = Counter()
        for r in self._activity_records:
            counter[r["hour"]] += 1

        chart_data = [(f"{h}时", counter.get(h, 0)) for h in range(24)]
        self._activity_data = chart_data

        canvas = tk.Canvas(tab, bg="#2b2b2b", highlightthickness=0)
        canvas.pack(fill="both", expand=True, padx=4, pady=4)
        canvas.bind("<Configure>", lambda e: draw_bar_chart(
            canvas, self._activity_data, title="每日活跃时段分布",
            bar_color="#f39c12"))
