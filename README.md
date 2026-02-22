# Claude Chat Manager

Claude Code 本地会话管理器，提供 CLI 和 GUI 两种界面，用于浏览、搜索、导出、删除和分析 Claude Code 的聊天记录。

直接读取 `~/.claude` 目录下的 JSONL 会话文件，无需额外数据库。

## 功能

- 按项目分组浏览所有会话
- 全文搜索消息内容
- 导出会话为 Markdown 文件
- 删除会话及关联文件
- 数据分析面板（Token 消耗、模型分布、活跃时段统计）
- 支持全局 / 项目级 / 会话级分析
- 右键菜单快捷操作

## 截图

```
┌──────────────────────────────────────────────────────────┐
│ 工具栏: [搜索框] [搜索] [导出] [删除] [分析] [刷新]       │
├────────────────┬─────────────────────────────────────────┤
│ 项目列表        │  会话信息: 标题 | 项目 | 模型 | 消息数   │
│ > 项目A (4)    │─────────────────────────────────────────│
│   项目B (23)   │                                         │
│────────────────│  --- You ---                            │
│ 会话列表        │  用户消息...                             │
│ abc123 标题..   │  --- Claude ---                         │
│ def456 标题..   │  助手回复...                             │
├────────────────┴─────────────────────────────────────────┤
│ 状态栏: 共 5 个项目, 33 个会话                             │
└──────────────────────────────────────────────────────────┘
```

## 安装

```bash
pip install -r requirements.txt
```

## 使用

### GUI

```bash
python gui_main.py
```

### CLI

```bash
# 列出所有项目
python main.py projects

# 列出某项目的会话
python main.py ls <project>

# 查看会话内容
python main.py show <session_id>

# 搜索消息
python main.py search <keyword>

# 导出会话为 Markdown
python main.py export <session_id>

# 删除会话
python main.py rm <session_id>
```

## 项目结构

```
claude_chat/
├── config.py       # 路径配置
├── db.py           # 数据层（解析 JSONL、搜索、统计）
├── export.py       # Markdown 导出
├── cli.py          # CLI 命令
├── gui.py          # GUI 主界面
└── analytics.py    # 数据分析弹窗与图表
main.py             # CLI 入口
gui_main.py         # GUI 入口
```

## 依赖

- Python 3.10+
- [click](https://click.palletsprojects.com/) — CLI 框架
- [customtkinter](https://github.com/TomSchimansky/CustomTkinter) — GUI 框架

## License

MIT
