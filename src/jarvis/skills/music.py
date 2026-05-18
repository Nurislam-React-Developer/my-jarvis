"""Скиллы управления музыкой (Spotify / Music.app)."""
from __future__ import annotations

from ._macos import run_applescript
from .base import Skill, SkillResult


def _app_for(player: str) -> str:
    p = (player or "spotify").strip().lower()
    if p in ("music", "apple music", "itunes", "applemusic"):
        return "Music"
    return "Spotify"


class PlayMusicSkill(Skill):
    name = "play_music"
    description = "Включить музыку (Spotify по умолчанию, либо Music.app)."
    parameters = {
        "type": "object",
        "properties": {
            "player": {
                "type": "string",
                "description": "Какой плеер: 'spotify' или 'music' (Apple Music). По умолчанию spotify.",
                "enum": ["spotify", "music"],
            }
        },
        "required": [],
    }

    async def execute(self, player: str = "spotify") -> SkillResult:  # type: ignore[override]
        app = _app_for(player)
        code, _, err = await run_applescript(f'tell application "{app}" to play')
        if code != 0:
            return SkillResult(False, f"Не смог включить {app}: {err}")
        return SkillResult(True, f"Включил {app}")


class PauseMusicSkill(Skill):
    name = "pause_music"
    description = "Поставить музыку на паузу."
    parameters = {
        "type": "object",
        "properties": {"player": {"type": "string", "enum": ["spotify", "music"]}},
        "required": [],
    }

    async def execute(self, player: str = "spotify") -> SkillResult:  # type: ignore[override]
        app = _app_for(player)
        code, _, err = await run_applescript(f'tell application "{app}" to pause')
        if code != 0:
            return SkillResult(False, f"Не смог поставить {app} на паузу: {err}")
        return SkillResult(True, "Пауза")


class NextTrackSkill(Skill):
    name = "next_track"
    description = "Следующий трек в музыкальном плеере."
    parameters = {
        "type": "object",
        "properties": {"player": {"type": "string", "enum": ["spotify", "music"]}},
        "required": [],
    }

    async def execute(self, player: str = "spotify") -> SkillResult:  # type: ignore[override]
        app = _app_for(player)
        code, _, err = await run_applescript(f'tell application "{app}" to next track')
        if code != 0:
            return SkillResult(False, f"Не смог переключить трек: {err}")
        return SkillResult(True, "Следующий трек")


class PrevTrackSkill(Skill):
    name = "prev_track"
    description = "Предыдущий трек в музыкальном плеере."
    parameters = {
        "type": "object",
        "properties": {"player": {"type": "string", "enum": ["spotify", "music"]}},
        "required": [],
    }

    async def execute(self, player: str = "spotify") -> SkillResult:  # type: ignore[override]
        app = _app_for(player)
        code, _, err = await run_applescript(f'tell application "{app}" to previous track')
        if code != 0:
            return SkillResult(False, f"Не смог переключить трек: {err}")
        return SkillResult(True, "Предыдущий трек")


class CurrentSongSkill(Skill):
    name = "current_song"
    description = "Узнать что сейчас играет."
    parameters = {
        "type": "object",
        "properties": {"player": {"type": "string", "enum": ["spotify", "music"]}},
        "required": [],
    }

    async def execute(self, player: str = "spotify") -> SkillResult:  # type: ignore[override]
        app = _app_for(player)
        script = (
            f'tell application "{app}"\n'
            f'  if it is running then\n'
            f'    set t to name of current track\n'
            f'    set a to artist of current track\n'
            f'    return a & " — " & t\n'
            f'  else\n'
            f'    return "not running"\n'
            f'  end if\n'
            f'end tell'
        )
        code, out, err = await run_applescript(script)
        if code != 0:
            return SkillResult(False, f"Не смог узнать трек: {err}")
        if out == "not running":
            return SkillResult(False, f"{app} не запущен")
        return SkillResult(True, f"Сейчас играет: {out}", {"track": out})
