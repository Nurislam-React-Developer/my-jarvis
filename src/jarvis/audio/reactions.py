"""Voice reactions — фиксированные клипы голоса Джарвиса (Priler/jarvis remaster pack).

Идея: для часто повторяющихся событий (услышал тебя, выполнил команду, прощаюсь)
проигрывать заранее записанные mp3/wav фразы голоса актёра. Это **во много раз**
аутентичнее любого TTS — звучит как настоящий Iron Man Jarvis.

Произвольные ответы LLM по-прежнему озвучивает основной TTS (ElevenLabs/say).

Категории и где они играют:
  wake      — услышал wake word          → reply1..6 ("Слушаю, сэр", "Да?", ...)
  ok        — команда выполнена          → ok1..4   ("Готово", "Конечно", ...)
  thanks    — пользователь поблагодарил  → thanks
  joke      — попросил пошутить          → joke1..8
  not_found — не понял команду           → stupid
  goodbye   — выход / "пока"             → off
  greet     — старт ассистента (по времени дня) → greet_morning/day/evening/night
"""
from __future__ import annotations

import asyncio
import random
from datetime import datetime
from pathlib import Path

from loguru import logger


# Соответствие категория → префикс файла. Один префикс = много вариантов (file1.mp3, file2.mp3, ...).
_CATEGORY_PREFIX: dict[str, str] = {
    "wake": "reply",
    "ok": "ok",
    "thanks": "thanks",
    "joke": "joke",
    "not_found": "stupid",
    "goodbye": "off",
}


def _greet_prefix() -> str:
    """Подобрать приветствие по времени суток."""
    h = datetime.now().hour
    if 5 <= h < 12:
        return "greet_morning"
    if 12 <= h < 17:
        return "greet_day"
    if 17 <= h < 22:
        return "greet_evening"
    return "greet_night"


class VoiceReactions:
    """Проигрывает рандомный mp3/wav клип из заданной категории через `afplay`."""

    def __init__(
        self,
        pack_dir: Path,
        fallback_dir: Path | None = None,
        enabled: bool = True,
    ) -> None:
        self.pack_dir = Path(pack_dir)
        self.fallback_dir = Path(fallback_dir) if fallback_dir else None
        self.enabled = enabled and self.pack_dir.exists()
        if self.enabled:
            count = len(list(self.pack_dir.glob("*.mp3"))) + len(list(self.pack_dir.glob("*.wav")))
            logger.info("🎙️  Voice reactions: {} клипов из {}", count, self.pack_dir.name)
        else:
            logger.warning("Voice reactions выключены (pack_dir={})", self.pack_dir)

    def _find_files(self, prefix: str) -> list[Path]:
        """Найти все варианты клипа: prefix*.mp3 / prefix*.wav. Сначала в основном паке, потом в fallback."""
        for d in (self.pack_dir, self.fallback_dir):
            if not d or not d.exists():
                continue
            files = sorted(d.glob(f"{prefix}*.mp3")) + sorted(d.glob(f"{prefix}*.wav"))
            if files:
                return files
        return []

    async def play(self, category: str) -> bool:
        """Проиграть случайный клип из категории. True если что-то сыграло."""
        if not self.enabled:
            return False

        if category == "greet":
            prefix = _greet_prefix()
        else:
            prefix = _CATEGORY_PREFIX.get(category, "")
            if not prefix:
                logger.debug("Неизвестная категория реакции: {}", category)
                return False

        files = self._find_files(prefix)
        if not files:
            # Часто prefix не найден (например greet_night отсутствует) — пробуем generic greet1
            if category == "greet":
                files = self._find_files("greet1") or self._find_files("greet")
            if not files:
                logger.debug("Нет клипов для категории {} (prefix {})", category, prefix)
                return False

        chosen = random.choice(files)
        logger.debug("🔊 reaction[{}]: {}", category, chosen.name)

        proc = await asyncio.create_subprocess_exec(
            "afplay",
            str(chosen),
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await proc.wait()
        return True
