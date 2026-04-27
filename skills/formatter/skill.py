"""
FormatterSkill —— 将原始抓取文章格式化为结构化 Markdown 输出。

context 读取：
    context["raw_articles"]     List[dict]  原始文章列表（来自 WebCrawlerSkill）

context 写入：
    context["formatted_articles"]  List[dict]  格式化后的文章列表
    context["documents"]            List[dict]  可直接传入 VectorStoreSkill 的文档格式

每篇文章格式化为：
    {
        "title": str,
        "source": str,
        "url": str,
        "publish_time": str,
        "formatted_text": str,   # Markdown 格式正文
        "text": str,             # 纯文本（供向量化）
        "metadata": dict,
    }
"""
from __future__ import annotations

import logging
import re
from typing import Any, Dict, List

from skills.base import BaseSkill, SkillContext, SkillResult

logger = logging.getLogger(__name__)

_SOURCE_LABEL = {
    "autohome": "汽车之家",
    "dongchedi": "懂车帝",
}


def _clean_text(text: str) -> str:
    """去除多余空行和空白"""
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _format_article(article: Dict) -> Dict:
    title = article.get("title", "（无标题）")
    source = article.get("source", "")
    source_label = _SOURCE_LABEL.get(source, source)
    url = article.get("url", "")
    publish_time = article.get("publish_time", "")
    content = article.get("content", "")
    summary = article.get("summary", "")
    body = _clean_text(content or summary)

    # Markdown 格式
    lines = [f"## {title}"]
    meta_parts = []
    if source_label:
        meta_parts.append(f"来源：{source_label}")
    if publish_time:
        meta_parts.append(f"时间：{publish_time}")
    if url:
        meta_parts.append(f"[原文链接]({url})")
    if meta_parts:
        lines.append("> " + " | ".join(meta_parts))
    lines.append("")
    if body:
        lines.append(body)
    else:
        lines.append("（暂无内容摘要）")

    formatted_text = "\n".join(lines)
    # 纯文本供向量化
    plain_text = f"{title}\n{body}" if body else title

    return {
        "title": title,
        "source": source_label,
        "url": url,
        "publish_time": publish_time,
        "formatted_text": formatted_text,
        "text": plain_text,
        "metadata": {
            "title": title,
            "source": source_label,
            "url": url,
            "publish_time": publish_time,
        },
    }


class FormatterSkill(BaseSkill):
    name = "formatter"
    description = "将原始抓取文章格式化为结构化 Markdown 并准备向量化文档"
    version = "1.0.0"

    async def execute(self, context: SkillContext, **kwargs: Any) -> SkillResult:
        raw: List[Dict] = context.get("raw_articles", [])
        if not raw:
            return SkillResult.fail("没有原始文章数据，请先运行 web_crawler", self.name)

        formatted = [_format_article(a) for a in raw]
        # 同时准备向量数据库所需格式
        docs_for_vs = [{"text": a["text"], "metadata": a["metadata"]} for a in formatted if a["text"]]

        context.set("formatted_articles", formatted)
        context.set("documents", docs_for_vs)  # VectorStoreSkill 直接读取

        logger.info("格式化完成：%d 篇文章", len(formatted))
        return SkillResult.ok(
            data=formatted,
            message=f"成功格式化 {len(formatted)} 篇文章",
            skill_name=self.name,
        )
