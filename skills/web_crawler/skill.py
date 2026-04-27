"""
WebCrawlerSkill —— 从汽车之家、懂车帝等网站抓取最新车辆资讯。

context 读取：
    context["query"]       str  搜索关键词（必须）
    context["sources"]     list 数据源列表，默认 ["autohome","dongchedi"]
    context["max_items"]   int  每个数据源最多抓取条数，默认 10
    context["fetch_full"]  bool 是否抓取全文，默认 False

context 写入：
    context["raw_articles"]  List[dict]  抓取到的原始文章列表
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import asdict
from typing import Any, Dict, List

from skills.base import BaseSkill, SkillContext, SkillResult
from .sites import autohome_fetch, autohome_content, dongchedi_fetch, dongchedi_content

logger = logging.getLogger(__name__)

# 数据源 → (list_fetcher, content_fetcher)
_SOURCE_MAP = {
    "autohome": (autohome_fetch, autohome_content),
    "dongchedi": (dongchedi_fetch, dongchedi_content),
}


class WebCrawlerSkill(BaseSkill):
    name = "web_crawler"
    description = "从汽车之家、懂车帝等网站抓取最新车辆资讯"
    version = "1.0.0"

    async def execute(self, context: SkillContext, **kwargs: Any) -> SkillResult:
        query: str = context.get("query", kwargs.get("query", ""))
        if not query:
            return SkillResult.fail("缺少搜索关键词 context['query']", self.name)

        sources: List[str] = context.get("sources", ["autohome", "dongchedi"])
        max_items: int = int(context.get("max_items", 10))
        fetch_full: bool = bool(context.get("fetch_full", False))

        all_articles: List[Dict] = []

        for source in sources:
            if source not in _SOURCE_MAP:
                logger.warning("未知数据源: %s，跳过", source)
                continue

            list_fn, content_fn = _SOURCE_MAP[source]
            logger.info("正在从 %s 搜索: %r", source, query)

            articles = await list_fn(query, max_items)
            logger.info("%s 抓取到 %d 条资讯", source, len(articles))

            if fetch_full and articles:
                # 并发抓取全文（限制并发数）
                sem = asyncio.Semaphore(5)
                async def _get_content(art):
                    async with sem:
                        art.content = await content_fn(art.url)

                await asyncio.gather(*[_get_content(a) for a in articles])

            all_articles.extend([asdict(a) for a in articles])

        if not all_articles:
            return SkillResult.fail(f"未能从任何数据源获取到资讯，关键词: {query!r}", self.name)

        context.set("raw_articles", all_articles)
        return SkillResult.ok(
            data=all_articles,
            message=f"共抓取 {len(all_articles)} 条资讯",
            skill_name=self.name,
        )
