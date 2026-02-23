import json
from pathlib import Path
from datetime import datetime
from .config import PROJECTS_DIR, HISTORY_FILE, CODEX_SESSIONS_DIR


_session_project_cache = None
_first_message_cache = None
_token_stats_cache = None
_activity_cache = None


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

    # 一次遍历建立 dirname → session_ids
    dir_sessions = {}
    for d in sorted(PROJECTS_DIR.iterdir()):
        if d.is_dir():
            files = list(d.glob("*.jsonl"))
            dir_sessions[d.name] = [f.stem for f in files]

    # 从 session → project 映射反查 dirname → display_name
    mapping = _build_session_project_map()
    dir_to_real = {}
    for dirname, sids in dir_sessions.items():
        for sid in sids:
            if sid in mapping:
                dir_to_real[dirname] = mapping[sid]
                break

    projects = []
    for dirname, sids in dir_sessions.items():
        projects.append({
            "dirname": dirname,
            "display_name": dir_to_real.get(dirname, dirname),
            "session_count": len(sids),
            "path": PROJECTS_DIR / dirname,
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


def _build_first_message_map():
    """一次性从 history.jsonl 建立 sessionId → 第一条用户消息的映射"""
    global _first_message_cache
    if _first_message_cache is not None:
        return _first_message_cache
    _first_message_cache = {}
    if not HISTORY_FILE.exists():
        return _first_message_cache
    with open(HISTORY_FILE, encoding="utf-8") as f:
        for line in f:
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            sid = obj.get("sessionId", "")
            display = obj.get("display", "")
            if sid and display and not display.startswith("/") and sid not in _first_message_cache:
                _first_message_cache[sid] = display
    return _first_message_cache


def _get_first_message(session_id):
    """从缓存获取某会话的第一条用户消息"""
    return _build_first_message_map().get(session_id, "")


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


# ── 数据分析采集 ──────────────────────────────────────────


def collect_token_stats():
    """遍历所有 JSONL，提取每条 assistant 消息的 token 用量"""
    global _token_stats_cache
    if _token_stats_cache is not None:
        return _token_stats_cache

    if not PROJECTS_DIR.exists():
        return []

    records = []
    for proj_dir in PROJECTS_DIR.iterdir():
        if not proj_dir.is_dir():
            continue
        for f in proj_dir.glob("*.jsonl"):
            session_id = f.stem
            project = _get_project_display(proj_dir.name, session_id)
            with open(f, encoding="utf-8") as fh:
                for line in fh:
                    try:
                        obj = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if obj.get("type") != "assistant":
                        continue
                    msg = obj.get("message", {})
                    usage = msg.get("usage")
                    if not usage:
                        continue
                    records.append({
                        "session_id": session_id,
                        "project": project,
                        "project_dirname": proj_dir.name,
                        "model": msg.get("model", "unknown"),
                        "timestamp": obj.get("timestamp", ""),
                        "input_tokens": usage.get("input_tokens", 0),
                        "output_tokens": usage.get("output_tokens", 0),
                        "cache_creation_input_tokens": usage.get("cache_creation_input_tokens", 0),
                        "cache_read_input_tokens": usage.get("cache_read_input_tokens", 0),
                    })
    _token_stats_cache = records
    return records


def collect_session_activity():
    """从 history.jsonl 提取活动时间线"""
    global _activity_cache
    if _activity_cache is not None:
        return _activity_cache

    if not HISTORY_FILE.exists():
        return []

    records = []
    for line in open(HISTORY_FILE, encoding="utf-8"):
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        ts = obj.get("timestamp")
        if not ts:
            continue
        dt = datetime.fromtimestamp(ts / 1000)
        records.append({
            "session_id": obj.get("sessionId", ""),
            "project": obj.get("project", ""),
            "timestamp_ms": ts,
            "hour": dt.hour,
            "date": dt.strftime("%Y-%m-%d"),
        })
    _activity_cache = records
    return records


# ── Codex 会话管理 ──────────────────────────────────────────


def list_codex_sessions():
    """列出所有 Codex 会话文件"""
    if not CODEX_SESSIONS_DIR.exists():
        return []

    results = []
    for f in sorted(CODEX_SESSIONS_DIR.rglob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True):
        session_id = f.stem
        stat = f.stat()
        meta = _parse_codex_meta(f)
        results.append({
            "session_id": session_id,
            "path": f,
            "cwd": meta.get("cwd", ""),
            "model": meta.get("model", ""),
            "title": meta.get("first_user_msg", session_id[:30]),
            "modified": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M"),
            "size_kb": round(stat.st_size / 1024, 1),
        })
    return results


def _parse_codex_meta(filepath):
    """快速解析 Codex session 文件的元信息"""
    meta = {}
    with open(filepath, encoding="utf-8") as f:
        for line in f:
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if obj.get("type") == "session_meta":
                payload = obj.get("payload", {})
                meta["cwd"] = payload.get("cwd", "")
                meta["id"] = payload.get("id", "")
            if obj.get("type") == "turn_context":
                payload = obj.get("payload", {})
                meta["model"] = payload.get("model", "")
            if obj.get("type") == "event_msg":
                payload = obj.get("payload", {})
                if payload.get("type") == "user_message" and "first_user_msg" not in meta:
                    msg = payload.get("message", "")
                    if msg and not msg.startswith("/"):
                        meta["first_user_msg"] = msg[:80]
            if "cwd" in meta and "model" in meta and "first_user_msg" in meta:
                break
    return meta


def get_codex_session_detail(filepath):
    """解析 Codex session 文件，返回消息列表和元信息"""
    messages = []
    model = None
    cwd = None

    with open(filepath, encoding="utf-8") as f:
        for line in f:
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue

            if obj.get("type") == "session_meta":
                cwd = obj.get("payload", {}).get("cwd", "")

            if obj.get("type") == "turn_context" and not model:
                model = obj.get("payload", {}).get("model", "")

            if obj.get("type") == "event_msg":
                payload = obj.get("payload", {})
                if payload.get("type") == "user_message":
                    text = payload.get("message", "")
                    if text.strip():
                        messages.append({"role": "user", "content": text})
                elif payload.get("type") == "agent_message":
                    text = payload.get("message", "")
                    if text.strip():
                        messages.append({"role": "assistant", "content": text})

    return {
        "messages": messages,
        "model": model,
        "cwd": cwd,
        "path": filepath,
    }


def delete_codex_session(filepath):
    """删除 Codex 会话文件"""
    p = Path(filepath)
    if p.exists():
        p.unlink()
        return True
    return False


def collect_codex_token_stats():
    """遍历所有 Codex JSONL，提取每次请求的 token 用量"""
    if not CODEX_SESSIONS_DIR.exists():
        return []

    records = []
    for f in CODEX_SESSIONS_DIR.rglob("*.jsonl"):
        session_id = f.stem
        model = None
        cwd = None
        with open(f, encoding="utf-8") as fh:
            for line in fh:
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if obj.get("type") == "session_meta":
                    cwd = obj.get("payload", {}).get("cwd", "")
                if obj.get("type") == "turn_context" and not model:
                    model = obj.get("payload", {}).get("model", "")
                if obj.get("type") == "event_msg":
                    payload = obj.get("payload", {})
                    if payload.get("type") == "token_count":
                        info = payload.get("info")
                        if not info:
                            continue
                        usage = info.get("last_token_usage", {})
                        if not usage or usage.get("input_tokens", 0) == 0:
                            continue
                        ts = obj.get("timestamp", "")
                        records.append({
                            "session_id": session_id,
                            "project": cwd or "",
                            "model": model or "unknown",
                            "timestamp": ts,
                            "input_tokens": usage.get("input_tokens", 0),
                            "output_tokens": usage.get("output_tokens", 0),
                            "cached_input_tokens": usage.get("cached_input_tokens", 0),
                            "reasoning_output_tokens": usage.get("reasoning_output_tokens", 0),
                        })
    return records


def collect_codex_activity():
    """从 Codex session 文件提取活动时间线"""
    if not CODEX_SESSIONS_DIR.exists():
        return []

    records = []
    for f in CODEX_SESSIONS_DIR.rglob("*.jsonl"):
        session_id = f.stem
        with open(f, encoding="utf-8") as fh:
            for line in fh:
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if obj.get("type") == "event_msg":
                    payload = obj.get("payload", {})
                    if payload.get("type") == "user_message":
                        ts = obj.get("timestamp", "")
                        if ts:
                            # ISO 格式: 2026-02-23T08:14:26.822Z
                            try:
                                dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                                records.append({
                                    "session_id": session_id,
                                    "timestamp": ts,
                                    "hour": dt.hour,
                                    "date": dt.strftime("%Y-%m-%d"),
                                })
                            except (ValueError, AttributeError):
                                continue
    return records
