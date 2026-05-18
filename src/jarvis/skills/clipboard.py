"""Скиллы работы с буфером обмена."""
from __future__ import annotations

import asyncio

from ._macos import run_shell
from .base import Skill, SkillResult


class CopyToClipboardSkill(Skill):
    name = "copy_to_clipboard"
    description = "Скопировать текст в буфер обмена macOS."
    parameters = {
        "type": "object",
        "properties": {
            "text": {"type": "string", "description": "Текст который нужно скопировать"}
        },
        "required": ["text"],
    }

    async def execute(self, text: str) -> SkillResult:  # type: ignore[override]
        proc = await asyncio.create_subprocess_exec(
            "pbcopy",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.DEVNULL,
        )
        await proc.communicate(text.encode("utf-8"))
        if proc.returncode != 0:
            return SkillResult(False, "Не смог скопировать")
        return SkillResult(True, "Скопировал в буфер")


class ReadClipboardSkill(Skill):
    name = "read_clipboard"
    description = "Прочитать текст из буфера обмена macOS."
    parameters = {"type": "object", "properties": {}, "required": []}

    async def execute(self) -> SkillResult:  # type: ignore[override]
        code, out, err = await run_shell("pbpaste")
        if code != 0:
            return SkillResult(False, f"Не смог прочитать буфер: {err}")
        return SkillResult(True, out or "Буфер пустой", {"text": out})
