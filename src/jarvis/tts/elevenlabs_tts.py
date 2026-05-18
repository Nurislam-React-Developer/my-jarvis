"""ElevenLabs TTS — премиум голос для Джарвиса.

- Озвучивает в `eleven_multilingual_v2` (поддерживает русский, английский и др.).
- Кэширует mp3 на диск по хешу (text, voice, model) — повторные фразы
  ("Готово, сэр", "Конечно") не съедают free-tier лимит.
- При ошибке/исчерпании лимита автоматически фолбэчит на macOS `say`.
- Воспроизведение через `afplay` (системный плеер macOS — без доп. зависимостей).
"""
from __future__ import annotations

import asyncio
import hashlib
from pathlib import Path
from typing import Any

from elevenlabs.client import AsyncElevenLabs
from loguru import logger

from .base import BaseTTS
from .say_tts import SayTTS


# Кэш mp3 — переживает рестарты, экономит free-tier
_CACHE_DIR = Path.home() / ".cache" / "jarvis" / "tts_elevenlabs"


class ElevenLabsTTS(BaseTTS):
    def __init__(
        self,
        api_key: str,
        voice_id: str,
        model: str = "eleven_multilingual_v2",
        stability: float = 0.5,
        similarity_boost: float = 0.75,
        cache_enabled: bool = True,
        fallback: BaseTTS | None = None,
    ) -> None:
        if not api_key:
            raise ValueError("ELEVENLABS_API_KEY пустой — заполни .env")
        self.api_key = api_key
        self.voice_id = voice_id
        self.model = model
        self.stability = stability
        self.similarity_boost = similarity_boost
        self.cache_enabled = cache_enabled
        self.fallback = fallback or SayTTS()  # на случай если EL упадёт

        self._client = AsyncElevenLabs(api_key=api_key)
        if cache_enabled:
            _CACHE_DIR.mkdir(parents=True, exist_ok=True)

    def _cache_path(self, text: str) -> Path:
        h = hashlib.sha1(
            f"{self.voice_id}|{self.model}|{self.stability}|{self.similarity_boost}|{text}".encode()
        ).hexdigest()
        return _CACHE_DIR / f"{h}.mp3"

    async def speak(self, text: str) -> None:
        text = (text or "").strip()
        if not text:
            return

        # 1) Кэш-хит — мгновенно играем
        if self.cache_enabled:
            cached = self._cache_path(text)
            if cached.exists() and cached.stat().st_size > 0:
                logger.debug("🎯 EL cache hit: {}", text[:60])
                await self._play_mp3(cached)
                return

        # 2) Запрашиваем новый аудио
        try:
            mp3_bytes = await self._synthesize(text)
        except Exception as e:  # noqa: BLE001
            logger.warning("ElevenLabs упал ({}): {}. Фолбэк на say.", type(e).__name__, e)
            await self.fallback.speak(text)
            return

        # 3) Сохраняем в кэш + играем
        if self.cache_enabled:
            try:
                self._cache_path(text).write_bytes(mp3_bytes)
            except OSError as e:
                logger.debug("Не записал кэш: {}", e)

        # Записываем во временный файл и играем
        tmp = _CACHE_DIR / "_play_temp.mp3"
        tmp.write_bytes(mp3_bytes)
        await self._play_mp3(tmp)

    async def _synthesize(self, text: str) -> bytes:
        """Один HTTP запрос к ElevenLabs, возвращает mp3 байты."""
        logger.debug("🌐 EL synth voice={} text={!r}", self.voice_id, text[:60])
        # SDK возвращает async-итератор chunk'ов mp3 — собираем в bytes
        stream: Any = self._client.text_to_speech.convert(
            voice_id=self.voice_id,
            model_id=self.model,
            text=text,
            output_format="mp3_44100_128",
            voice_settings={
                "stability": self.stability,
                "similarity_boost": self.similarity_boost,
            },
        )
        chunks: list[bytes] = []
        async for chunk in stream:
            if chunk:
                chunks.append(chunk)
        return b"".join(chunks)

    @staticmethod
    async def _play_mp3(path: Path) -> None:
        """Воспроизвести mp3 через системный afplay (macOS)."""
        proc = await asyncio.create_subprocess_exec(
            "afplay",
            str(path),
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()
        if proc.returncode != 0:
            logger.error(
                "afplay failed (code={}): {}", proc.returncode, stderr.decode(errors="ignore")
            )
