"""Скиллы управления системой macOS."""
from __future__ import annotations

import datetime
from pathlib import Path

from ._macos import run_applescript, run_shell
from .base import Skill, SkillResult


class SetVolumeSkill(Skill):
    name = "set_volume"
    description = "Установить громкость системы macOS."
    parameters = {
        "type": "object",
        "properties": {
            "level": {
                "type": "integer",
                "description": "Уровень громкости от 0 до 100",
                "minimum": 0,
                "maximum": 100,
            }
        },
        "required": ["level"],
    }

    async def execute(self, level: int) -> SkillResult:  # type: ignore[override]
        level = max(0, min(100, int(level)))
        # AppleScript использует шкалу 0-7 для output volume, но `set volume output volume X` принимает 0-100.
        code, _, err = await run_applescript(f"set volume output volume {level}")
        if code != 0:
            return SkillResult(False, f"Не смог изменить громкость: {err}")
        return SkillResult(True, f"Громкость: {level}%")


class GetVolumeSkill(Skill):
    name = "get_volume"
    description = "Узнать текущую громкость системы."
    parameters = {"type": "object", "properties": {}, "required": []}

    async def execute(self) -> SkillResult:  # type: ignore[override]
        code, out, err = await run_applescript("output volume of (get volume settings)")
        if code != 0:
            return SkillResult(False, f"Не смог узнать громкость: {err}")
        return SkillResult(True, f"Громкость {out}%", {"level": int(out)})


class SetBrightnessSkill(Skill):
    """Требует утилиту `brightness` (brew install brightness) или CLI инструмент."""

    name = "set_brightness"
    description = "Установить яркость экрана. Требует утилиту `brightness` (brew install brightness)."
    parameters = {
        "type": "object",
        "properties": {
            "level": {"type": "integer", "minimum": 0, "maximum": 100, "description": "0-100"}
        },
        "required": ["level"],
    }

    async def execute(self, level: int) -> SkillResult:  # type: ignore[override]
        level = max(0, min(100, int(level)))
        # brightness принимает 0.0-1.0
        code, _, err = await run_shell("brightness", f"{level/100:.2f}")
        if code == 0:
            return SkillResult(True, f"Яркость: {level}%")
        if "not found" in err.lower() or code == 127:
            return SkillResult(False, "Утилита brightness не установлена. brew install brightness")
        return SkillResult(False, f"Не смог изменить яркость: {err}")


class LockScreenSkill(Skill):
    name = "lock_screen"
    description = "Заблокировать экран macOS."
    requires_confirmation = True
    parameters = {"type": "object", "properties": {}, "required": []}

    async def execute(self) -> SkillResult:  # type: ignore[override]
        # Cmd+Ctrl+Q через AppleScript
        await run_applescript(
            'tell application "System Events" to keystroke "q" using {command down, control down}'
        )
        return SkillResult(True, "Блокирую экран")


class TakeScreenshotSkill(Skill):
    name = "take_screenshot"
    description = "Сделать скриншот всего экрана и сохранить на рабочий стол."
    parameters = {"type": "object", "properties": {}, "required": []}

    async def execute(self) -> SkillResult:  # type: ignore[override]
        ts = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        path = Path.home() / "Desktop" / f"jarvis-screenshot-{ts}.png"
        code, _, err = await run_shell("screencapture", "-x", str(path))
        if code != 0:
            return SkillResult(False, f"Не смог сделать скриншот: {err}")
        return SkillResult(True, f"Сохранил скриншот на рабочий стол", {"path": str(path)})
