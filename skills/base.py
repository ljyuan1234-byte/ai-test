"""
Skills 架构基础模块
每个 Skill 继承 BaseSkill，实现 execute() 方法即可接入系统。
新增功能 = 新建 Skill 文件 + 注册 → 不改动任何已有代码。
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class SkillContext:
    """
    Skill 之间共享的上下文，在 Pipeline 中逐步传递。
    每个 Skill 可以向 context.data 写入中间结果，供后续 Skill 读取。
    """
    data: Dict[str, Any] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def set(self, key: str, value: Any) -> None:
        self.data[key] = value

    def get(self, key: str, default: Any = None) -> Any:
        return self.data.get(key, default)

    def add_error(self, msg: str) -> None:
        logger.error(msg)
        self.errors.append(msg)

    @property
    def has_errors(self) -> bool:
        return len(self.errors) > 0


@dataclass
class SkillResult:
    """统一的 Skill 执行结果"""
    success: bool
    data: Any = None
    message: str = ""
    skill_name: str = ""

    @classmethod
    def ok(cls, data: Any = None, message: str = "", skill_name: str = "") -> "SkillResult":
        return cls(success=True, data=data, message=message, skill_name=skill_name)

    @classmethod
    def fail(cls, message: str, skill_name: str = "") -> "SkillResult":
        return cls(success=False, data=None, message=message, skill_name=skill_name)


class BaseSkill(ABC):
    """
    所有 Skill 的抽象基类。

    实现一个新 Skill 只需：
    1. 继承 BaseSkill
    2. 设置 name / description / version
    3. 实现 execute() 方法
    4. 在 skills/__init__.py 中注册
    """

    # 子类必须覆盖这三个属性
    name: str = "base_skill"
    description: str = "Base skill, do not use directly."
    version: str = "1.0.0"

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        # 确保子类定义了 name
        if not hasattr(cls, "name") or cls.name == "base_skill":
            pass  # 允许中间层抽象类不设置 name

    @abstractmethod
    async def execute(self, context: SkillContext, **kwargs: Any) -> SkillResult:
        """
        核心执行方法。

        Args:
            context: 共享上下文，可读取上游 Skill 的输出
            **kwargs: 额外参数

        Returns:
            SkillResult
        """

    async def setup(self) -> None:
        """可选：Skill 初始化，在首次执行前调用"""

    async def teardown(self) -> None:
        """可选：Skill 清理，在 Pipeline 结束后调用"""

    def get_info(self) -> Dict[str, str]:
        return {
            "name": self.name,
            "description": self.description,
            "version": self.version,
        }

    def __repr__(self) -> str:
        return f"<Skill name={self.name!r} version={self.version!r}>"
