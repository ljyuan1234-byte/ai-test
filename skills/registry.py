"""
Skill 注册中心（单例）
用于统一管理所有 Skill 的注册、查询和生命周期。
"""
from __future__ import annotations

import logging
from typing import Dict, List, Optional, Type

from .base import BaseSkill

logger = logging.getLogger(__name__)


class SkillRegistry:
    """
    全局单例注册中心。

    使用方式：
        registry = SkillRegistry()
        registry.register(MySkill())
        skill = registry.get("my_skill")
    """

    _instance: Optional["SkillRegistry"] = None
    _skills: Dict[str, BaseSkill] = {}

    def __new__(cls) -> "SkillRegistry":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._skills = {}
        return cls._instance

    def register(self, skill: BaseSkill) -> None:
        """注册一个 Skill 实例"""
        if skill.name in self._skills:
            logger.warning("Skill %r 已存在，将被覆盖", skill.name)
        self._skills[skill.name] = skill
        logger.info("已注册 Skill: %r", skill.name)

    def register_many(self, skills: List[BaseSkill]) -> None:
        """批量注册"""
        for skill in skills:
            self.register(skill)

    def get(self, name: str) -> Optional[BaseSkill]:
        """按名称获取 Skill"""
        skill = self._skills.get(name)
        if skill is None:
            logger.warning("Skill %r 未找到", name)
        return skill

    def require(self, name: str) -> BaseSkill:
        """获取 Skill，不存在则抛出异常"""
        skill = self._skills.get(name)
        if skill is None:
            raise KeyError(f"Skill {name!r} 未注册，请先在 skills/__init__.py 中注册。")
        return skill

    def list_skills(self) -> List[Dict[str, str]]:
        """返回所有已注册 Skill 的信息"""
        return [s.get_info() for s in self._skills.values()]

    def names(self) -> List[str]:
        return list(self._skills.keys())

    def __contains__(self, name: str) -> bool:
        return name in self._skills

    def __len__(self) -> int:
        return len(self._skills)
