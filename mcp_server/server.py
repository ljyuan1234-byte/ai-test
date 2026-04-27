"""
MCP Server —— 将 Skills 暴露为 MCP (Model Context Protocol) 工具。

启动方式：
    python -m mcp_server.server

或通过 main.py：
    python main.py --mode mcp

MCP 工具列表：
  - search_car_news   : 搜索最新车辆资讯并存入向量库
  - query_knowledge   : 从向量库检索已存储资讯并生成 RAG 回答
  - list_skills       : 查看所有已注册 Skill
"""
from __future__ import annotations

import asyncio
import json
import logging
import sys

# 将项目根目录加入 sys.path
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from skills import get_registry
from skills.pipeline import SkillPipeline

logger = logging.getLogger(__name__)


async def _run_crawl_pipeline(query: str, sources: list[str], max_items: int, fetch_full: bool) -> dict:
    """爬取 → 格式化 → 存储 完整流水线"""
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
            "query": query,
            "sources": sources,
            "max_items": max_items,
            "fetch_full": fetch_full,
            "vs_action": "store",
        }
    )
    return {
        "stored_count": len(ctx.get("stored_ids", [])),
        "article_count": len(ctx.get("raw_articles", [])),
        "errors": ctx.errors,
        "formatted_preview": [
            {
                "title": a.get("title"),
                "source": a.get("source"),
                "publish_time": a.get("publish_time"),
                "url": a.get("url"),
            }
            for a in ctx.get("formatted_articles", [])[:5]
        ],
    }


async def _run_rag_pipeline(query: str, top_k: int) -> dict:
    """检索 → RAG 回答 流水线"""
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
            "query": query,
            "vs_action": "search",
            "top_k": top_k,
        }
    )
    return {
        "answer": ctx.get("rag_answer", ""),
        "sources": ctx.get("rag_sources", []),
        "errors": ctx.errors,
    }


def create_mcp_app():
    """
    创建 MCP 服务器。
    需要安装：pip install mcp
    """
    try:
        from mcp.server import Server
        from mcp.server.stdio import stdio_server
        from mcp import types
    except ImportError:
        logger.error("mcp 包未安装，请运行: pip install mcp")
        raise

    server = Server("car-info-assistant")

    @server.list_tools()
    async def list_tools() -> list[types.Tool]:
        return [
            types.Tool(
                name="search_car_news",
                description=(
                    "从汽车之家、懂车帝搜索最新车辆资讯，"
                    "格式化后存入向量数据库，返回抓取摘要。"
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "搜索关键词，例如：宝马X5 2025款"},
                        "sources": {
                            "type": "array",
                            "items": {"type": "string", "enum": ["autohome", "dongchedi"]},
                            "default": ["autohome", "dongchedi"],
                            "description": "数据源列表",
                        },
                        "max_items": {"type": "integer", "default": 10, "description": "每个数据源最多抓取条数"},
                        "fetch_full": {"type": "boolean", "default": False, "description": "是否抓取全文"},
                    },
                    "required": ["query"],
                },
            ),
            types.Tool(
                name="query_knowledge",
                description="从本地向量知识库检索车辆资讯并生成智能回答（RAG）",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "用户问题，例如：宝马X5和奔驰GLE哪个更值"},
                        "top_k": {"type": "integer", "default": 5, "description": "检索返回条数"},
                    },
                    "required": ["query"],
                },
            ),
            types.Tool(
                name="list_skills",
                description="列出系统中所有已注册的 Skill 及其描述",
                inputSchema={"type": "object", "properties": {}, "required": []},
            ),
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
        try:
            if name == "search_car_news":
                result = await _run_crawl_pipeline(
                    query=arguments["query"],
                    sources=arguments.get("sources", ["autohome", "dongchedi"]),
                    max_items=arguments.get("max_items", 10),
                    fetch_full=arguments.get("fetch_full", False),
                )
            elif name == "query_knowledge":
                result = await _run_rag_pipeline(
                    query=arguments["query"],
                    top_k=arguments.get("top_k", 5),
                )
            elif name == "list_skills":
                registry = get_registry()
                result = {"skills": registry.list_skills()}
            else:
                result = {"error": f"未知工具: {name}"}
        except Exception as exc:  # noqa: BLE001
            result = {"error": str(exc)}

        return [types.TextContent(type="text", text=json.dumps(result, ensure_ascii=False, indent=2))]

    return server


async def run_mcp_server():
    from mcp.server.stdio import stdio_server

    server = create_mcp_app()
    logger.info("MCP Server 启动（stdio 模式）")
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_mcp_server())
