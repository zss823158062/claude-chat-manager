import sys
import io

# Windows 终端 UTF-8 输出
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

from claude_chat.cli import cli

if __name__ == "__main__":
    cli()
