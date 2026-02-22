import click
from .db import (
    list_projects,
    list_sessions,
    get_session_detail,
    search_messages,
    delete_session,
)
from .export import export_session


@click.group()
def cli():
    """Claude 本地会话管理器 — 管理 ~/.claude 中的对话记录"""
    pass


@cli.command()
def projects():
    """列出所有项目"""
    items = list_projects()
    if not items:
        click.echo("未找到任何项目")
        return
    click.echo(f"{'项目':<40} {'会话数'}")
    click.echo("-" * 50)
    for p in items:
        click.echo(f"{p['display_name']:<40} {p['session_count']}")


@cli.command()
@click.argument("project", required=False)
def ls(project):
    """列出会话（可选指定项目目录名过滤）"""
    sessions = list_sessions(project)
    if not sessions:
        click.echo("未找到任何会话")
        return
    click.echo(f"{'ID':<10} {'项目':<25} {'标题':<35} {'大小':<8} {'修改时间'}")
    click.echo("-" * 100)
    for s in sessions:
        sid_short = s["session_id"][:8]
        proj_short = s["project"][-22:] if len(s["project"]) > 22 else s["project"]
        title = s["title"][:32] if len(s["title"]) > 32 else s["title"]
        click.echo(
            f"{sid_short:<10} {proj_short:<25} {title:<35} {s['size_kb']:>5}KB  {s['modified']}"
        )


@cli.command()
@click.argument("session_id")
def show(session_id):
    """查看会话内容"""
    data = get_session_detail(session_id)
    if not data:
        click.echo(f"会话 {session_id} 不存在")
        return

    click.echo(f"会话: {data.get('slug', session_id[:8])}")
    click.echo(f"项目: {data['project']}")
    click.echo(f"模型: {data.get('model', 'unknown')}")
    click.echo(f"消息数: {len(data['messages'])}")
    click.echo(f"路径: {data['path']}")
    click.echo("=" * 60)

    for msg in data["messages"]:
        role = "You" if msg["role"] == "user" else "Claude"
        click.echo(f"\n--- {role} ---")
        content = msg["content"]
        if len(content) > 500:
            click.echo(content[:500] + f"\n... (共 {len(content)} 字符)")
        else:
            click.echo(content)


@cli.command()
@click.argument("keyword")
@click.option("-n", "--limit", default=20, help="最大结果数")
def search(keyword, limit):
    """搜索历史消息"""
    results = search_messages(keyword)
    if not results:
        click.echo("未找到匹配结果")
        return
    click.echo(f"找到 {len(results)} 条结果（显示前 {min(limit, len(results))} 条）:\n")
    for r in results[:limit]:
        role = "User" if r["role"] == "user" else "Claude"
        click.echo(f"[{r['project']}] {r['session_id'][:8]} ({role}):")
        click.echo(f"  {r['match_preview']}")
        click.echo()


@cli.command()
@click.argument("session_id")
def export(session_id):
    """导出会话为 Markdown"""
    filepath = export_session(session_id)
    if filepath is None:
        click.echo(f"会话 {session_id} 不存在")
        return
    click.echo(f"已导出: {filepath}")


@cli.command()
@click.argument("session_id")
@click.option("--yes", "-y", is_flag=True, help="跳过确认")
def rm(session_id, yes):
    """删除会话"""
    if not yes:
        data = get_session_detail(session_id)
        if not data:
            click.echo(f"会话 {session_id} 不存在")
            return
        click.echo(f"即将删除: {session_id[:8]} ({data.get('slug', '')})")
        if not click.confirm("确认删除？"):
            click.echo("已取消")
            return
    ok = delete_session(session_id)
    if ok:
        click.echo(f"已删除会话: {session_id[:8]}")
    else:
        click.echo(f"会话 {session_id} 不存在")
