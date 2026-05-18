"""Скиллы работы с файлами и Spotlight."""
from __future__ import annotations

import os

from ._macos import run_shell
from .base import Skill, SkillResult


class OpenPathSkill(Skill):
    name = "open_path"
    description = "Открыть файл или папку в Finder/дефолтном приложении."
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Путь. Поддерживается ~ для домашней папки."}
        },
        "required": ["path"],
    }

    async def execute(self, path: str) -> SkillResult:  # type: ignore[override]
        expanded = os.path.expanduser(path)
        if not os.path.exists(expanded):
            return SkillResult(False, f"Путь не существует: {expanded}")
        code, _, err = await run_shell("open", expanded)
        if code != 0:
            return SkillResult(False, f"Не смог открыть: {err}")
        return SkillResult(True, f"Открыл {expanded}")


class SpotlightSearchSkill(Skill):
    name = "spotlight_search"
    description = "Найти файлы через Spotlight (mdfind). Возвращает первые 10 результатов."
    parameters = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Что искать"}
        },
        "required": ["query"],
    }

    async def execute(self, query: str) -> SkillResult:  # type: ignore[override]
        code, out, err = await run_shell("mdfind", query)
        if code != 0:
            return SkillResult(False, f"Spotlight ошибка: {err}")
        results = [line for line in out.splitlines() if line][:10]
        if not results:
            return SkillResult(True, f"Ничего не нашёл по запросу '{query}'")
        return SkillResult(
            True,
            f"Нашёл {len(results)} результатов",
            {"results": results, "query": query},
        )
