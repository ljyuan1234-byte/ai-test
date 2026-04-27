"""
skills/__init__.py —— Skill 注册入口

★ 新增 Skill 只需在此处三步操作：
   1. import 你的 Skill 类
   2. 在 _register_all() 中调用 registry.register(YourSkill(...))
   3. 完成！不需要修改任何其他文件。
"""
from __future__ import annotations

import logging

import config as cfg
from .base import BaseSkill, SkillContext, SkillResult
from .registry import SkillRegistry
from .pipeline import SkillPipeline, build_pipeline_from_registry

# ── 导入所有 Skill ────────────────────────────────────────────────────────────
from .web_crawler import WebCrawlerSkill
from .formatter import FormatterSkill
from .vector_store import VectorStoreSkill
from .rag import RAGSkill

logger = logging.getLogger(__name__)

_registry_initialized = False


def _register_all(registry: SkillRegistry) -> None:
    """在这里注册所有 Skill 实例"""

    # 1. 网页爬虫
    registry.register(WebCrawlerSkill())

    # 2. 格式化输出
    registry.register(FormatterSkill())

    # 3. 向量数据库
    registry.register(
        VectorStoreSkill(
            persist_dir=cfg.get("vector_store", "persist_dir", "./data/vector_db"),
            embedding_model=cfg.get(
                "vector_store",
                "embedding_model",
                "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
            ),
            default_collection=cfg.get("vector_store", "default_collection", "car_news"),
        )
    )

    # 4. RAG 问答
    registry.register(
        RAGSkill(
            llm_base_url=cfg.get("llm", "base_url", ""),
            llm_api_key=cfg.get("llm", "api_key", ""),
            llm_model=cfg.get("llm", "model", "gpt-4o-mini"),
        )
    )

    # ── 在此添加新 Skill ──────────────────────────────────────────────────────
    # from .your_new_skill import YourNewSkill
    # registry.register(YourNewSkill())
    # ─────────────────────────────────────────────────────────────────────────


def get_registry() -> SkillRegistry:
    """获取已初始化的全局注册中心（单例，首次调用自动注册所有 Skill）"""
    global _registry_initialized
    registry = SkillRegistry()
    if not _registry_initialized:
        _register_all(registry)
        _registry_initialized = True
        logger.info("Skills 注册完成，共 %d 个：%s", len(registry), registry.names())
    return registry


__all__ = [
    "BaseSkill",
    "SkillContext",
    "SkillResult",
    "SkillRegistry",
    "SkillPipeline",
    "build_pipeline_from_registry",
    "get_registry",
]
