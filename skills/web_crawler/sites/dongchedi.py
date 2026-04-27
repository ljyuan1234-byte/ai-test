"""
懂车帝 (dongchedi.com) 资讯爬虫
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import List

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Referer": "https://www.dongchedi.com/",
}


@dataclass
class Article:
    title: str
    url: str
    summary: str
    source: str
    publish_time: str = ""
    content: str = ""


async def fetch_news_list(keyword: str, max_items: int = 10) -> List[Article]:
    """
    在懂车帝搜索关键词，返回文章列表。
    优先使用懂车帝搜索 API，降级到 HTML 解析。
    """
    articles: List[Article] = []

    # 尝试懂车帝搜索接口（抖音系，返回 JSON）
    search_api = "https://www.dongchedi.com/auto/params-carlist/i/search"
    news_api = "https://www.dongchedi.com/search/v2/news"

    try:
        async with httpx.AsyncClient(headers=HEADERS, timeout=15.0, follow_redirects=True) as client:
            # 懂车帝搜索新闻
            resp = await client.get(
                "https://www.dongchedi.com/search",
                params={"keyword": keyword, "type": "news"},
            )
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")

            # 懂车帝卡片结构
            for item in soup.select(".article-card, .news-row, [class*='article']")[:max_items]:
                title_tag = item.select_one("a[title], h3 a, .title")
                if not title_tag:
                    continue
                title = title_tag.get("title") or title_tag.get_text(strip=True)
                url = title_tag.get("href", "")
                if url and not url.startswith("http"):
                    url = "https://www.dongchedi.com" + url
                desc_tag = item.select_one(".desc, .summary, p")
                summary = desc_tag.get_text(strip=True) if desc_tag else ""
                time_tag = item.select_one(".time, .date, [class*='time']")
                publish_time = time_tag.get_text(strip=True) if time_tag else ""

                if title and url:
                    articles.append(
                        Article(
                            title=title,
                            url=url,
                            summary=summary,
                            source="dongchedi",
                            publish_time=publish_time,
                        )
                    )
    except Exception as exc:  # noqa: BLE001
        logger.warning("dongchedi 抓取失败: %s", exc)

    return articles


async def fetch_article_content(url: str) -> str:
    """抓取单篇懂车帝文章正文"""
    try:
        async with httpx.AsyncClient(headers=HEADERS, timeout=15.0, follow_redirects=True) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")
            content_tag = soup.select_one(
                ".article-content, .post-content, [class*='article-body']"
            )
            if content_tag:
                for tag in content_tag.select("script, style"):
                    tag.decompose()
                return content_tag.get_text(separator="\n", strip=True)
    except Exception as exc:  # noqa: BLE001
        logger.warning("dongchedi 文章内容抓取失败 [%s]: %s", url, exc)
    return ""
