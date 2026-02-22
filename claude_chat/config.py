import os
from pathlib import Path

CLAUDE_DIR = Path.home() / ".claude"
PROJECTS_DIR = CLAUDE_DIR / "projects"
HISTORY_FILE = CLAUDE_DIR / "history.jsonl"

BASE_DIR = Path(__file__).resolve().parent.parent
EXPORTS_DIR = BASE_DIR / "exports"
EXPORTS_DIR.mkdir(exist_ok=True)
