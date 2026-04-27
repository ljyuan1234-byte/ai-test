"""
Skill Pipeline —— 将多个 Skill 串联成工作流。

使用示例：
    pipeline = SkillPipeline([
        registry.require("web_crawler"),
        registry.require("formatter"),
        registry.require("vector_store"),
    ])
    context = await pipeline.run(query="最新宝马新车")
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Dict, List, Optional

from .base import BaseSkill, SkillContext, SkillResult
from .registry import SkillRegistry

logger = logging.getLogger(__name__)


class SkillPipeline:
    """
    顺序执行一组 Skill，共享同一 SkillContext。
    任何一个 Skill 失败时，默认停止流水线（可设 stop_on_error=False 继续执行）。
    """

    def __init__(
        self,
        skills: List[BaseSkill],
        stop_on_error: bool = True,
        name: str = "default_pipeline",
    ) -> None:
        self.skills = skills
        self.stop_on_error = stop_on_error
        self.name = name

    async def run(
        self,
        initial_data: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> SkillContext:
        """
        执行流水线。

        Args:
            initial_data: 注入到 context.data 的初始数据，例如 {"query": "宝马X5"}
            **kwargs: 透传给每个 Skill.execute() 的额外参数

        Returns:
            执行完毕的 SkillContext（包含所有中间结果和最终结果）
        """
        context = SkillContext(data=initial_data or {})
        logger.info("Pipeline [%s] 开始，共 %d 个 Skill", self.name, len(self.skills))

        # 初始化所有 Skill
        for skill in self.skills:
            await skill.setup()

        start_time = time.perf_counter()
        try:
            for i, skill in enumerate(self.skills, 1):
                step_start = time.perf_counter()
                logger.info("[%d/%d] 执行 Skill: %s", i, len(self.skills), skill.name)
                try:
                    result: SkillResult = await skill.execute(context, **kwargs)
                    elapsed = time.perf_counter() - step_start
                    if result.success:
                        logger.info("  ✓ %s 完成 (%.2fs)", skill.name, elapsed)
                        # Skill 的输出自动写入 context
                        if result.data is not None:
                            context.set(f"{skill.name}_result", result.data)
                    else:
                        logger.error("  ✗ %s 失败: %s", skill.name, result.message)
                        context.add_error(f"[{skill.name}] {result.message}")
                        if self.stop_on_error:
                            break
                except Exception as exc:  # noqa: BLE001
                    context.add_error(f"[{skill.name}] 异常: {exc!s}")
                    logger.exception("Skill %s 抛出异常", skill.name)
                    if self.stop_on_error:
                        break
        finally:
            for skill in self.skills:
                await skill.teardown()

        total = time.perf_counter() - start_time
        logger.info("Pipeline [%s] 结束，耗时 %.2fs，错误数: %d", self.name, total, len(context.errors))
        context.metadata["pipeline_elapsed"] = total
        return context


def build_pipeline_from_registry(
    skill_names: List[str],
    registry: Optional[SkillRegistry] = None,
    **kwargs: Any,
) -> SkillPipeline:
    """
    通过 Skill 名称列表，从注册中心构建 Pipeline（便捷函数）。

    Example:
        pipeline = build_pipeline_from_registry(
            ["web_crawler", "formatter", "vector_store"]
        )
    """
    reg = registry or SkillRegistry()
    skills = [reg.require(name) for name in skill_names]
    return SkillPipeline(skills, **kwargs)
