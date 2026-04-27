"""
汽车之家 (autohome.com.cn) 资讯爬虫
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import List, Optional

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
    "Referer": "https://www.autohome.com.cn/",
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
    在汽车之家搜索关键词，返回文章列表。
    使用搜索接口获取结果，避免频繁请求首页。
    """
    search_url = f"https://www.autohome.com.cn/ashx/search.ashx?type=news&keywords={keyword}&page=1"
    articles: List[Article] = []

    try:
        async with httpx.AsyncClient(headers=HEADERS, timeout=15.0, follow_redirects=True) as client:
            # 先尝试搜索接口
            resp = await client.get(
                "https://www.autohome.com.cn/search/",
                params={"keywords": keyword},
            )
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")

            # 解析搜索结果卡片
            for item in soup.select(".search-list-item, .article-list li")[:max_items]:
                title_tag = item.select_one("h3 a, .title a, a.title")
                if not title_tag:
                    continue
                title = title_tag.get_text(strip=True)
                url = title_tag.get("href", "")
                if url and not url.startswith("http"):
                    url = "https://www.autohome.com.cn" + url
                summary_tag = item.select_one(".summary, .desc, p")
                summary = summary_tag.get_text(strip=True) if summary_tag else ""
                time_tag = item.select_one(".time, .date, time")
                publish_time = time_tag.get_text(strip=True) if time_tag else ""

                if title and url:
                    articles.append(
                        Article(
                            title=title,
                            url=url,
                            summary=summary,
                            source="autohome",
                            publish_time=publish_time,
                        )
                    )
    except Exception as exc:  # noqa: BLE001
        logger.warning("autohome 抓取失败: %s", exc)

    return articles


async def fetch_article_content(url: str) -> str:
    """抓取单篇文章的正文内容"""
    try:
        async with httpx.AsyncClient(headers=HEADERS, timeout=15.0, follow_redirects=True) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")
            # 汽车之家文章正文常见选择器
            content_tag = soup.select_one(
                "#contenttxt, .article-content, .newsdetail-content, #article-content"
            )
            if content_tag:
                # 去掉广告和脚本
                for tag in content_tag.select("script, style, .ad, .advert"):
                    tag.decompose()
                return content_tag.get_text(separator="\n", strip=True)
    except Exception as exc:  # noqa: BLE001
        logger.warning("autohome 文章内容抓取失败 [%s]: %s", url, exc)
    return ""
