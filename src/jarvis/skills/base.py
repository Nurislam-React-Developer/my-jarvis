"""Базовый класс Skill и SkillResult."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, ClassVar


@dataclass
class SkillResult:
    success: bool
    message: str
    data: dict[str, Any] = field(default_factory=dict)


class Skill(ABC):
    """Базовый класс для всех скиллов.

    Подклассы обязаны определить class-атрибуты `name`, `description`, `parameters`.
    """

    name: ClassVar[str]
    description: ClassVar[str]
    parameters: ClassVar[dict[str, Any]]
    enabled: ClassVar[bool] = True
    requires_confirmation: ClassVar[bool] = False

    @abstractmethod
    async def execute(self, **kwargs: Any) -> SkillResult: ...

    @classmethod
    def to_tool_schema(cls) -> dict[str, Any]:
        """Формат для Anthropic tool / OpenAI function."""
        return {
            "name": cls.name,
            "description": cls.description,
            "input_schema": cls.parameters,
        }
