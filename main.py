"""
项目主入口

用法：
  python main.py --mode ui         # 启动 Streamlit 可视化界面
  python main.py --mode mcp        # 启动 MCP Server（stdio）
  python main.py --mode crawl --query "宝马X5 2025款"   # 命令行抓取
  python main.py --mode ask   --query "宝马X5和奔驰GLE哪个好"  # 命令行问答
  python main.py --mode list       # 列出所有 Skill
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import subprocess
import sys
from pathlib import Path

# ── 日志初始化 ─────────────────────────────────────────────────────────────────
import config as cfg

logging.basicConfig(
    level=getattr(logging, cfg.get("logging", "level", "INFO")),
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="汽车资讯 AI 助手")
    parser.add_argument(
        "--mode",
        choices=["ui", "mcp", "crawl", "ask", "list"],
        default="ui",
        help="运行模式",
    )
    parser.add_argument("--query", type=str, default="", help="搜索/问答关键词（crawl/ask 模式）")
    parser.add_argument("--sources", nargs="+", default=["autohome", "dongchedi"])
    parser.add_argument("--max-items", type=int, default=10)
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--fetch-full", action="store_true")
    return parser.parse_args()


async def mode_crawl(args: argparse.Namespace) -> None:
    from skills import get_registry
    from skills.pipeline import SkillPipeline

    if not args.query:
        logger.error("请通过 --query 指定搜索关键词")
        sys.exit(1)

    registry = get_registry()
    pipeline = SkillPipeline(
        skills=[
            registry.require("web_crawler"),
            registry.require("formatter"),
            registry.require("vector_store"),
        ],
        name="crawl_pipeline",
    )
    ctx = await pipeline.run(
        initial_data={
            "query": args.query,
            "sources": args.sources,
            "max_items": args.max_items,
            "fetch_full": args.fetch_full,
            "vs_action": "store",
        }
    )
    articles = ctx.get("formatted_articles", [])
    stored = ctx.get("stored_ids", [])
    print(f"\n✅ 共抓取 {len(articles)} 篇，存入向量库 {len(stored)} 条\n")
    for art in articles:
        print("-" * 60)
        print(art.get("formatted_text", ""))
    if ctx.has_errors:
        for e in ctx.errors:
            print(f"⚠  {e}")


async def mode_ask(args: argparse.Namespace) -> None:
    from skills import get_registry
    from skills.pipeline import SkillPipeline

    if not args.query:
        logger.error("请通过 --query 指定问题")
        sys.exit(1)

    registry = get_registry()
    pipeline = SkillPipeline(
        skills=[
            registry.require("vector_store"),
            registry.require("rag"),
        ],
        name="rag_pipeline",
    )
    ctx = await pipeline.run(
        initial_data={
            "query": args.query,
            "vs_action": "search",
            "top_k": args.top_k,
        }
    )
    answer = ctx.get("rag_answer", "")
    print(f"\n🤖 回答：\n{answer}\n")
    results = ctx.get("search_results", [])
    if results:
        print(f"📎 引用来源（top {len(results)}）：")
        for r in results:
            m = r.get("metadata", {})
            print(f"  · {m.get('title', '')}  [{m.get('source', '')}]")


def mode_list(_args: argparse.Namespace) -> None:
    from skills import get_registry
    registry = get_registry()
    print(f"\n已注册 Skill（共 {len(registry)} 个）：\n")
    for s in registry.list_skills():
        print(f"  [{s['name']}]  v{s['version']}")
        print(f"    {s['description']}\n")


def mode_ui(_args: argparse.Namespace) -> None:
    ui_path = str(Path(__file__).parent / "ui" / "app.py")
    logger.info("启动 Streamlit UI: %s", ui_path)
    subprocess.run(
        [sys.executable, "-m", "streamlit", "run", ui_path, "--server.runOnSave=true"],
        check=False,
    )


def mode_mcp(_args: argparse.Namespace) -> None:
    from mcp_server.server import run_mcp_server
    asyncio.run(run_mcp_server())


def main() -> None:
    args = parse_args()
    if args.mode == "ui":
        mode_ui(args)
    elif args.mode == "mcp":
        mode_mcp(args)
    elif args.mode == "crawl":
        asyncio.run(mode_crawl(args))
    elif args.mode == "ask":
        asyncio.run(mode_ask(args))
    elif args.mode == "list":
        mode_list(args)


if __name__ == "__main__":
    main()
