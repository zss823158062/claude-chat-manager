import json
from pathlib import Path
from datetime import datetime
from .config import PROJECTS_DIR, HISTORY_FILE


_session_project_cache = None


def _build_session_project_map():
    """从 history.jsonl 建立 sessionId → 真实项目路径的映射"""
    global _session_project_cache
    if _session_project_cache is not None:
        return _session_project_cache

    _session_project_cache = {}
    if not HISTORY_FILE.exists():
        return _session_project_cache

    with open(HISTORY_FILE, encoding="utf-8") as f:
        for line in f:
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            sid = obj.get("sessionId", "")
            proj = obj.get("project", "")
            if sid and proj and sid not in _session_project_cache:
                _session_project_cache[sid] = proj
    return _session_project_cache


def _get_project_display(dirname, session_id=None):
    """获取项目显示名。优先从 history 映射获取，否则从 session 文件的 cwd 获取"""
    if session_id:
        mapping = _build_session_project_map()
        proj = mapping.get(session_id)
        if proj:
            return proj
    # fallback: 从目录名近似还原
    return dirname


def _parse_session_file(filepath):
    """解析单个 session JSONL 文件，返回消息列表和元信息"""
    messages = []
    model = None
    slug = None
    cwd = None

    with open(filepath, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            msg_type = obj.get("type")

            if msg_type not in ("user", "assistant"):
                continue

            if not slug:
                slug = obj.get("slug")
            if not cwd:
                cwd = obj.get("cwd")

            msg = obj.get("message", {})
            role = msg.get("role", msg_type)
            content = msg.get("content", "")

            # assistant 消息的 content 可能是 list
            if isinstance(content, list):
                text_parts = []
                for block in content:
                    if block.get("type") == "text":
                        text_parts.append(block["text"])
                text = "\n".join(text_parts)
            else:
                text = content

            if not text.strip():
                continue

            if msg_type == "assistant" and not model:
                model = msg.get("model")

            messages.append({
                "role": role,
                "content": text,
                "uuid": obj.get("uuid"),
            })

    return {
        "messages": messages,
        "model": model,
        "slug": slug,
        "cwd": cwd,
    }


def list_projects():
    """列出所有项目"""
    if not PROJECTS_DIR.exists():
        return []

    # 从 history 建立目录名 → 真实路径的映射
    dir_to_real = {}
    mapping = _build_session_project_map()
    for sid, proj_path in mapping.items():
        # 找到这个 session 属于哪个目录
        for d in PROJECTS_DIR.iterdir():
            if d.is_dir() and (d / f"{sid}.jsonl").exists():
                dir_to_real[d.name] = proj_path
                break

    projects = []
    for d in sorted(PROJECTS_DIR.iterdir()):
        if d.is_dir():
            session_files = list(d.glob("*.jsonl"))
            display = dir_to_real.get(d.name, d.name)
            projects.append({
                "dirname": d.name,
                "display_name": display,
                "session_count": len(session_files),
                "path": d,
            })
    return projects


def list_sessions(project_dirname=None):
    """列出会话。可选按项目过滤"""
    if not PROJECTS_DIR.exists():
        return []

    results = []
    dirs = [PROJECTS_DIR / project_dirname] if project_dirname else sorted(PROJECTS_DIR.iterdir())

    for proj_dir in dirs:
        if not proj_dir.is_dir():
            continue
        for f in sorted(proj_dir.glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True):
            session_id = f.stem
            stat = f.stat()
            first_msg = _get_first_message(session_id)
            results.append({
                "session_id": session_id,
                "project": _get_project_display(proj_dir.name, session_id),
                "project_dirname": proj_dir.name,
                "title": first_msg[:50] if first_msg else session_id[:8],
                "modified": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M"),
                "size_kb": round(stat.st_size / 1024, 1),
                "path": f,
            })
    return results


def _get_first_message(session_id):
    """从 history.jsonl 获取某会话的第一条用户消息"""
    if not HISTORY_FILE.exists():
        return ""
    with open(HISTORY_FILE, encoding="utf-8") as f:
        for line in f:
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if obj.get("sessionId") == session_id:
                display = obj.get("display", "")
                if display and not display.startswith("/"):
                    return display
    return ""


def get_session_detail(session_id):
    """获取会话详情（解析 JSONL）"""
    filepath = _find_session_file(session_id)
    if not filepath:
        return None
    data = _parse_session_file(filepath)
    full_id = filepath.stem  # 用文件名的完整 UUID 查映射
    data["session_id"] = full_id
    data["path"] = filepath
    data["project"] = _get_project_display(filepath.parent.name, full_id)
    return data


def _find_session_file(session_id):
    """根据 session_id 查找 JSONL 文件（支持前缀匹配）"""
    if not PROJECTS_DIR.exists():
        return None
    for proj_dir in PROJECTS_DIR.iterdir():
        if not proj_dir.is_dir():
            continue
        exact = proj_dir / f"{session_id}.jsonl"
        if exact.exists():
            return exact
        # 前缀匹配
        for f in proj_dir.glob("*.jsonl"):
            if f.stem.startswith(session_id):
                return f
    return None


def search_messages(keyword):
    """在所有会话中搜索关键词"""
    keyword_lower = keyword.lower()
    results = []

    if not PROJECTS_DIR.exists():
        return results

    for proj_dir in PROJECTS_DIR.iterdir():
        if not proj_dir.is_dir():
            continue
        for f in proj_dir.glob("*.jsonl"):
            session_id = f.stem
            with open(f, encoding="utf-8") as fh:
                for line in fh:
                    try:
                        obj = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if obj.get("type") not in ("user", "assistant"):
                        continue
                    msg = obj.get("message", {})
                    content = msg.get("content", "")
                    if isinstance(content, list):
                        text = " ".join(b.get("text", "") for b in content if b.get("type") == "text")
                    else:
                        text = content

                    if keyword_lower in text.lower():
                        results.append({
                            "session_id": session_id,
                            "project": _get_project_display(proj_dir.name, session_id),
                            "role": obj.get("type"),
                            "content": text,
                            "match_preview": _extract_match_context(text, keyword_lower),
                        })
    return results


def _extract_match_context(text, keyword_lower, context_chars=80):
    """提取关键词周围的上下文片段"""
    idx = text.lower().find(keyword_lower)
    if idx == -1:
        return text[:150]
    start = max(0, idx - context_chars)
    end = min(len(text), idx + len(keyword_lower) + context_chars)
    snippet = text[start:end]
    if start > 0:
        snippet = "..." + snippet
    if end < len(text):
        snippet = snippet + "..."
    return snippet


def delete_session(session_id):
    """删除会话文件"""
    filepath = _find_session_file(session_id)
    if not filepath:
        return False
    companion_dir = filepath.with_suffix("")
    filepath.unlink()
    if companion_dir.exists() and companion_dir.is_dir():
        import shutil
        shutil.rmtree(companion_dir)
    return True
