"""Скиллы управления приложениями macOS."""
from __future__ import annotations

from ._macos import run_applescript, run_shell
from .base import Skill, SkillResult


# Алиасы — чтобы LLM не парился над точным именем приложения.
_APP_ALIASES: dict[str, str] = {
    "хром": "Google Chrome",
    "chrome": "Google Chrome",
    "сафари": "Safari",
    "телеграм": "Telegram",
    "телега": "Telegram",
    "ватсап": "WhatsApp",
    "слак": "Slack",
    "vscode": "Visual Studio Code",
    "вс код": "Visual Studio Code",
    "код": "Visual Studio Code",
    "финдер": "Finder",
    "терминал": "Terminal",
    "айтерм": "iTerm",
    "айтуньс": "Music",
    "музыка": "Music",
    "спотифай": "Spotify",
    "спотик": "Spotify",
    "почта": "Mail",
    "календарь": "Calendar",
    "заметки": "Notes",
}


def _resolve_app(name: str) -> str:
    return _APP_ALIASES.get(name.strip().lower(), name)


class OpenAppSkill(Skill):
    name = "open_app"
    description = "Открыть приложение на macOS. Например: Spotify, Telegram, Chrome, Safari, VSCode."
    parameters = {
        "type": "object",
        "properties": {
            "app_name": {
                "type": "string",
                "description": "Имя приложения. Можно по-русски (Хром, Телеграм) или по-английски.",
            }
        },
        "required": ["app_name"],
    }

    async def execute(self, app_name: str) -> SkillResult:  # type: ignore[override]
        app = _resolve_app(app_name)
        code, _, err = await run_shell("open", "-a", app)
        if code != 0:
            return SkillResult(False, f"Не нашёл приложение «{app}»: {err}")
        return SkillResult(True, f"Открыл {app}")


class CloseAppSkill(Skill):
    name = "close_app"
    description = "Закрыть приложение на macOS."
    parameters = {
        "type": "object",
        "properties": {
            "app_name": {"type": "string", "description": "Имя приложения для закрытия"}
        },
        "required": ["app_name"],
    }

    async def execute(self, app_name: str) -> SkillResult:  # type: ignore[override]
        app = _resolve_app(app_name)
        code, _, err = await run_applescript(f'tell application "{app}" to quit')
        if code != 0:
            return SkillResult(False, f"Не смог закрыть {app}: {err}")
        return SkillResult(True, f"Закрыл {app}")


class SwitchAppSkill(Skill):
    name = "switch_app"
    description = "Переключиться на приложение (вынести его на передний план)."
    parameters = {
        "type": "object",
        "properties": {
            "app_name": {"type": "string", "description": "Имя приложения"}
        },
        "required": ["app_name"],
    }

    async def execute(self, app_name: str) -> SkillResult:  # type: ignore[override]
        app = _resolve_app(app_name)
        code, _, err = await run_applescript(f'tell application "{app}" to activate')
        if code != 0:
            return SkillResult(False, f"Не смог переключиться на {app}: {err}")
        return SkillResult(True, f"Активировал {app}")
