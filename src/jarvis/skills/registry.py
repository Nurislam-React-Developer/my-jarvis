"""Регистр всех скиллов и фабрика по умолчанию."""
from __future__ import annotations

import inspect
from pathlib import Path
from typing import Any

import yaml
from loguru import logger

from .apps import CloseAppSkill, OpenAppSkill, SwitchAppSkill
from .base import Skill, SkillResult
from .browser import OpenURLSkill, WebSearchSkill, WikiSearchSkill, YouTubeSearchSkill
from .clipboard import CopyToClipboardSkill, ReadClipboardSkill
from .files import OpenPathSkill, SpotlightSearchSkill
from .info import GetDateSkill, GetTimeSkill, GetWeatherSkill
from .music import (
    CurrentSongSkill,
    NextTrackSkill,
    PauseMusicSkill,
    PlayMusicSkill,
    PrevTrackSkill,
)
from .notes import CreateNoteSkill
from .system import (
    GetVolumeSkill,
    LockScreenSkill,
    SetBrightnessSkill,
    SetVolumeSkill,
    TakeScreenshotSkill,
)
from .vision import AnalyzeScreenSkill


# Все доступные скиллы. Порядок не важен.
ALL_SKILL_CLASSES: list[type[Skill]] = [
    GetTimeSkill, GetDateSkill, GetWeatherSkill,
    OpenAppSkill, CloseAppSkill, SwitchAppSkill,
    WebSearchSkill, OpenURLSkill, YouTubeSearchSkill, WikiSearchSkill,
    SetVolumeSkill, GetVolumeSkill, SetBrightnessSkill,
    LockScreenSkill, TakeScreenshotSkill,
    PlayMusicSkill, PauseMusicSkill, NextTrackSkill, PrevTrackSkill, CurrentSongSkill,
    CopyToClipboardSkill, ReadClipboardSkill,
    OpenPathSkill, SpotlightSearchSkill,
    CreateNoteSkill,
    AnalyzeScreenSkill,
]


class SkillRegistry:
    def __init__(self) -> None:
        self._skills: dict[str, Skill] = {}

    def register(self, skill: Skill) -> None:
        if skill.name in self._skills:
            logger.warning("Skill {} уже зарегистрирован — перезаписываю", skill.name)
        self._skills[skill.name] = skill

    def get(self, name: str) -> Skill | None:
        return self._skills.get(name)

    def all(self) -> list[Skill]:
        return [s for s in self._skills.values() if s.enabled]

    def to_tools_schema(self) -> list[dict[str, Any]]:
        """Список tool-схем для LLM."""
        return [type(s).to_tool_schema() for s in self.all()]

    async def execute(self, name: str, arguments: dict[str, Any]) -> SkillResult:
        skill = self.get(name)
        if skill is None:
            return SkillResult(False, f"Неизвестный skill: {name}")
        if not skill.enabled:
            return SkillResult(False, f"Skill {name} отключён")
        try:
            return await skill.execute(**arguments)
        except TypeError as e:
            return SkillResult(False, f"Неверные аргументы для {name}: {e}")
        except Exception as e:  # noqa: BLE001
            logger.exception("Ошибка в skill {}", name)
            return SkillResult(False, f"Ошибка выполнения {name}: {e}")


def _load_skills_yaml(path: Path) -> dict[str, dict[str, Any]]:
    """Загрузить config/skills.yaml. Безопасно если файла нет — вернёт {}."""
    if not path.exists():
        return {}
    with path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data.get("skills", {}) or {}


def build_default_registry(skills_yaml_path: Path | None = None) -> SkillRegistry:
    """Собрать реестр со всеми скиллами, отфильтровав по `config/skills.yaml`."""
    overrides = _load_skills_yaml(skills_yaml_path) if skills_yaml_path else {}

    # Ключи в skills.yaml которые НЕ передаём в конструктор скилла
    META_KEYS = {"enabled", "requires_confirmation"}

    registry = SkillRegistry()
    for cls in ALL_SKILL_CLASSES:
        cfg = overrides.get(cls.name, {}) or {}
        if cfg.get("enabled", True) is False:
            logger.debug("Skill {} отключён в skills.yaml", cls.name)
            continue

        # Передаём в __init__ только те ключи, которые он принимает.
        try:
            sig = inspect.signature(cls.__init__)
            accepted = {p for p in sig.parameters if p != "self"}
        except (TypeError, ValueError):
            accepted = set()
        init_kwargs = {
            k: v for k, v in cfg.items()
            if k not in META_KEYS and k in accepted
        }

        try:
            skill = cls(**init_kwargs) if init_kwargs else cls()
        except Exception as e:  # noqa: BLE001
            logger.error("Не удалось инициализировать skill {}: {}", cls.name, e)
            continue

        if "requires_confirmation" in cfg:
            skill.requires_confirmation = bool(cfg["requires_confirmation"])
        registry.register(skill)

    logger.info("Зарегистрировано {} скиллов", len(registry.all()))
    return registry
