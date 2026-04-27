"""
VectorStoreSkill —— 使用 ChromaDB 实现本地持久化向量数据库。

支持的操作（通过 context["vs_action"] 控制）：
  - "store"   : 将 context["documents"] 存入数据库（默认）
  - "search"  : 检索与 context["query"] 最相近的文档
  - "delete"  : 删除 context["doc_ids"] 中的文档

context 读取（store 模式）：
    context["documents"]          List[dict]  每条包含 text, metadata 字段
    context["collection_name"]    str         集合名称，默认 "car_news"

context 读取（search 模式）：
    context["query"]              str         查询文本
    context["top_k"]              int         返回条数，默认 5

context 写入：
    context["stored_ids"]         List[str]   (store) 写入的文档 ID 列表
    context["search_results"]     List[dict]  (search) 检索结果
"""
from __future__ import annotations

import hashlib
import logging
from typing import Any, Dict, List, Optional

from skills.base import BaseSkill, SkillContext, SkillResult

logger = logging.getLogger(__name__)

# ChromaDB 会在 execute 中懒加载，避免启动时必须安装
_chroma_client = None
_embedding_fn = None


def _get_client(persist_dir: str):
    import chromadb
    from chromadb.config import Settings

    client = chromadb.PersistentClient(
        path=persist_dir,
        settings=Settings(anonymized_telemetry=False),
    )
    return client


def _get_embedding_fn(model_name: str):
    """使用 sentence-transformers 生成向量"""
    from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
    return SentenceTransformerEmbeddingFunction(model_name=model_name)


class VectorStoreSkill(BaseSkill):
    name = "vector_store"
    description = "基于 ChromaDB 的本地持久化向量数据库，支持存储和语义检索"
    version = "1.0.0"

    def __init__(
        self,
        persist_dir: str = "./data/vector_db",
        embedding_model: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
        default_collection: str = "car_news",
    ) -> None:
        self.persist_dir = persist_dir
        self.embedding_model = embedding_model
        self.default_collection = default_collection
        self._client = None
        self._ef = None

    async def setup(self) -> None:
        """懒初始化 Chroma"""
        if self._client is None:
            logger.info("初始化 ChromaDB，持久化路径: %s", self.persist_dir)
            self._client = _get_client(self.persist_dir)
            self._ef = _get_embedding_fn(self.embedding_model)

    def _get_collection(self, name: str):
        return self._client.get_or_create_collection(
            name=name,
            embedding_function=self._ef,
            metadata={"hnsw:space": "cosine"},
        )

    async def execute(self, context: SkillContext, **kwargs: Any) -> SkillResult:
        action: str = context.get("vs_action", "store")
        collection_name: str = context.get("collection_name", self.default_collection)
        collection = self._get_collection(collection_name)

        if action == "store":
            return await self._store(context, collection)
        elif action == "search":
            return await self._search(context, collection)
        elif action == "delete":
            return await self._delete(context, collection)
        else:
            return SkillResult.fail(f"未知操作: {action!r}，合法值: store/search/delete", self.name)

    async def _store(self, context: SkillContext, collection) -> SkillResult:
        documents: List[Dict] = context.get("documents", [])

        # 若没有 documents，尝试从格式化结果或原始文章转换
        if not documents:
            formatted = context.get("formatter_result")
            raw = context.get("raw_articles", [])
            source = formatted if formatted else raw
            documents = [
                {
                    "text": item.get("formatted_text") or item.get("content") or item.get("summary", ""),
                    "metadata": {
                        "title": item.get("title", ""),
                        "url": item.get("url", ""),
                        "source": item.get("source", ""),
                        "publish_time": item.get("publish_time", ""),
                    },
                }
                for item in (source if isinstance(source, list) else [])
                if item.get("formatted_text") or item.get("content") or item.get("summary")
            ]

        if not documents:
            return SkillResult.fail("没有可存储的文档，请先运行 web_crawler 或设置 context['documents']", self.name)

        ids, texts, metadatas = [], [], []
        for doc in documents:
            text = doc.get("text", "")
            if not text:
                continue
            doc_id = hashlib.md5(text.encode()).hexdigest()
            ids.append(doc_id)
            texts.append(text)
            metadatas.append(doc.get("metadata", {}))

        if not ids:
            return SkillResult.fail("所有文档均为空文本，跳过存储", self.name)

        collection.upsert(ids=ids, documents=texts, metadatas=metadatas)
        context.set("stored_ids", ids)
        logger.info("已存入 %d 条文档到集合 %r", len(ids), collection.name)
        return SkillResult.ok(data=ids, message=f"成功存入 {len(ids)} 条文档", skill_name=self.name)

    async def _search(self, context: SkillContext, collection) -> SkillResult:
        query: str = context.get("query", "")
        if not query:
            return SkillResult.fail("搜索需要 context['query']", self.name)

        top_k: int = int(context.get("top_k", 5))
        results = collection.query(
            query_texts=[query],
            n_results=min(top_k, collection.count() or 1),
            include=["documents", "metadatas", "distances"],
        )

        hits = []
        docs = results.get("documents", [[]])[0]
        metas = results.get("metadatas", [[]])[0]
        dists = results.get("distances", [[]])[0]

        for doc, meta, dist in zip(docs, metas, dists):
            hits.append({"text": doc, "metadata": meta, "distance": dist})

        context.set("search_results", hits)
        return SkillResult.ok(data=hits, message=f"检索到 {len(hits)} 条相关文档", skill_name=self.name)

    async def _delete(self, context: SkillContext, collection) -> SkillResult:
        doc_ids: List[str] = context.get("doc_ids", [])
        if not doc_ids:
            return SkillResult.fail("需要 context['doc_ids'] 来删除文档", self.name)
        collection.delete(ids=doc_ids)
        return SkillResult.ok(data=doc_ids, message=f"已删除 {len(doc_ids)} 条文档", skill_name=self.name)
