"""Скиллы работы с Notes.app."""
from __future__ import annotations

from ._macos import run_applescript
from .base import Skill, SkillResult


def _escape(s: str) -> str:
    """Эскейп строки для AppleScript."""
    return s.replace("\\", "\\\\").replace('"', '\\"')


class CreateNoteSkill(Skill):
    name = "create_note"
    description = "Создать новую заметку в Notes.app."
    parameters = {
        "type": "object",
        "properties": {
            "title": {"type": "string", "description": "Заголовок заметки"},
            "body": {"type": "string", "description": "Текст заметки"},
        },
        "required": ["body"],
    }

    async def execute(self, body: str, title: str = "Заметка от Джарвиса") -> SkillResult:  # type: ignore[override]
        # В Notes.app body — это HTML. Первая строка becomes title в UI.
        full = f"<b>{_escape(title)}</b><br>{_escape(body).replace(chr(10), '<br>')}"
        script = f'tell application "Notes" to make new note with properties {{body:"{full}"}}'
        code, _, err = await run_applescript(script)
        if code != 0:
            return SkillResult(False, f"Не смог создать заметку: {err}")
        return SkillResult(True, "Создал заметку")
