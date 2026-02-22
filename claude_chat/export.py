from .config import EXPORTS_DIR
from .db import get_session_detail


def export_session(session_id):
    """导出会话为 Markdown 文件"""
    data = get_session_detail(session_id)
    if not data:
        return None

    messages = data["messages"]
    title = data.get("slug") or session_id[:8]
    model = data.get("model") or "unknown"
    project = data.get("project") or "unknown"

    lines = [
        f"# {title}",
        "",
        f"> Project: {project}",
        f"> Model: {model}",
        f"> Messages: {len(messages)}",
        "",
        "---",
    ]

    for msg in messages:
        role_label = "User" if msg["role"] == "user" else "Assistant"
        lines.append("")
        lines.append(f"## {role_label}")
        lines.append("")
        lines.append(msg["content"])
        lines.append("")
        lines.append("---")

    content = "\n".join(lines) + "\n"
    filename = f"{session_id[:8]}_{title}.md"
    for ch in r'<>:"/\|?*':
        filename = filename.replace(ch, "_")
    filepath = EXPORTS_DIR / filename
    filepath.write_text(content, encoding="utf-8")
    return filepath
