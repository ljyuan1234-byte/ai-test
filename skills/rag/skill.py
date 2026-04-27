"""
RAGSkill —— 检索增强生成（Retrieval-Augmented Generation）。

工作流程：
  1. 从向量数据库中检索与 query 相关的文档片段（调用 VectorStoreSkill）
  2. 将检索结果拼接为上下文，发送给 LLM 生成最终回答
  3. 支持 OpenAI 兼容接口（本地 Ollama / OpenAI / Azure 均可）

context 读取：
    context["query"]          str   用户问题（必须）
    context["top_k"]          int   检索条数，默认 5
    context["llm_prompt"]     str   自定义系统提示词（可选）

context 写入：
    context["rag_answer"]     str   LLM 生成的回答
    context["rag_sources"]    list  引用的来源文档列表
"""
from __future__ import annotations

import logging
import os
from typing import Any, List, Dict, Optional

from skills.base import BaseSkill, SkillContext, SkillResult

logger = logging.getLogger(__name__)

_DEFAULT_SYSTEM_PROMPT = """\
你是一名专业的汽车资讯分析师。
请根据下方检索到的资讯内容，准确、简洁地回答用户问题。
如果资讯中没有相关内容，请直接说明无法回答，不要编造信息。

检索到的资讯：
{context_docs}
"""


class RAGSkill(BaseSkill):
    name = "rag"
    description = "基于向量检索的增强生成，从本地知识库中检索相关文档后由 LLM 生成回答"
    version = "1.0.0"

    def __init__(
        self,
        vector_store_skill_name: str = "vector_store",
        llm_base_url: str = "",
        llm_api_key: str = "",
        llm_model: str = "gpt-4o-mini",
    ) -> None:
        self.vector_store_skill_name = vector_store_skill_name
        self.llm_base_url = llm_base_url or os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")
        self.llm_api_key = llm_api_key or os.getenv("LLM_API_KEY", "")
        self.llm_model = llm_model or os.getenv("LLM_MODEL", "gpt-4o-mini")
        self._client = None

    async def setup(self) -> None:
        if not self.llm_api_key:
            logger.warning("LLM_API_KEY 未设置，RAG 问答功能将不可用")
            return
        try:
            from openai import AsyncOpenAI
            self._client = AsyncOpenAI(
                base_url=self.llm_base_url,
                api_key=self.llm_api_key,
            )
            logger.info("LLM 客户端初始化完成，模型: %s", self.llm_model)
        except ImportError:
            logger.warning("openai 包未安装，请运行: pip install openai")

    async def execute(self, context: SkillContext, **kwargs: Any) -> SkillResult:
        query: str = context.get("query", "")
        if not query:
            return SkillResult.fail("缺少 context['query']", self.name)

        # Step 1: 从向量库检索相关文档
        search_results: List[Dict] = context.get("search_results", [])
        if not search_results:
            # 如果上游没有检索结果，发起检索
            from skills.registry import SkillRegistry
            vs = SkillRegistry().get(self.vector_store_skill_name)
            if vs:
                context.set("vs_action", "search")
                await vs.execute(context)
                search_results = context.get("search_results", [])

        if not search_results:
            return SkillResult.fail("向量库中暂无相关文档，请先使用爬虫抓取并存储资讯", self.name)

        # Step 2: 构建上下文文本
        context_docs = "\n\n".join(
            f"[{i+1}] 来源: {r.get('metadata', {}).get('source', '未知')} | "
            f"标题: {r.get('metadata', {}).get('title', '')}\n{r.get('text', '')}"
            for i, r in enumerate(search_results)
        )
        sources = [r.get("metadata", {}) for r in search_results]
        context.set("rag_sources", sources)

        # Step 3: 调用 LLM
        if not self._client:
            # 无 LLM 时，直接返回检索文档作为答案
            answer = f"检索到以下相关资讯（未启用 LLM 总结）：\n\n{context_docs}"
            context.set("rag_answer", answer)
            return SkillResult.ok(data=answer, message="返回原始检索结果（LLM 未配置）", skill_name=self.name)

        system_prompt = context.get("llm_prompt") or _DEFAULT_SYSTEM_PROMPT.format(context_docs=context_docs)

        try:
            response = await self._client.chat.completions.create(
                model=self.llm_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": query},
                ],
                temperature=0.3,
                max_tokens=1500,
            )
            answer: str = response.choices[0].message.content or ""
            context.set("rag_answer", answer)
            return SkillResult.ok(data=answer, message="RAG 回答生成完成", skill_name=self.name)
        except Exception as exc:  # noqa: BLE001
            return SkillResult.fail(f"LLM 调用失败: {exc!s}", self.name)
