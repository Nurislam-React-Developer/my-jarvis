"""faster-whisper STT — локальное распознавание речи."""
from __future__ import annotations

import asyncio
import time

import numpy as np
from loguru import logger

from .base import BaseSTT, TranscriptionResult


class WhisperSTT(BaseSTT):
    def __init__(
        self,
        model: str = "small",
        device: str = "auto",
        compute_type: str = "int8",
        language: str = "ru",
        initial_prompt: str | None = None,
        beam_size: int = 5,
    ) -> None:
        self.model_name = model
        self.device = device
        self.compute_type = compute_type
        self.language = language if language != "auto" else None
        # initial_prompt — ОЧЕНЬ важный параметр для Whisper.
        # Он "подсказывает" модели какой словарь ожидать. Без него Whisper часто
        # коверкает имена приложений (Chrome → Хром/Кром/Кран, Telegram → Телеграмм/Делегат).
        # Передаём список app-имён + типичные команды Джарвиса.
        self.initial_prompt = initial_prompt
        self.beam_size = beam_size
        self._model = None  # ленивая инициализация (модель тяжёлая)

    def _ensure_loaded(self) -> None:
        if self._model is not None:
            return
        # Импорт здесь чтобы не платить старт-ап стоимость пока STT не нужен
        from faster_whisper import WhisperModel

        # CTranslate2 на M-чипах эффективно работает на CPU с int8.
        # MPS пока не поддерживается faster-whisper, поэтому "auto" → cpu.
        device = "cpu" if self.device == "auto" else self.device
        logger.info(
            "Загружаю Whisper model={} device={} compute_type={}...",
            self.model_name,
            device,
            self.compute_type,
        )
        t0 = time.perf_counter()
        self._model = WhisperModel(
            self.model_name,
            device=device,
            compute_type=self.compute_type,
        )
        logger.info("✅ Whisper загружен за {:.1f}s", time.perf_counter() - t0)

    async def transcribe(
        self,
        audio: np.ndarray,
        sample_rate: int = 16000,
    ) -> TranscriptionResult:
        if audio.size == 0:
            return TranscriptionResult(text="", language=self.language or "", duration_sec=0.0)

        self._ensure_loaded()
        if sample_rate != 16000:
            raise ValueError("Whisper ожидает 16000 Hz; ресемпл не реализован")

        return await asyncio.to_thread(self._transcribe_sync, audio)

    def _transcribe_sync(self, audio: np.ndarray) -> TranscriptionResult:
        assert self._model is not None
        t0 = time.perf_counter()
        segments, info = self._model.transcribe(
            audio,
            language=self.language,
            beam_size=self.beam_size,
            vad_filter=True,
            vad_parameters={"min_silence_duration_ms": 500},
            initial_prompt=self.initial_prompt,
            # Низкая температура → детерминированнее распознавание команд
            temperature=0.0,
            # Более строгий no_speech-порог чтобы не выдумывать слова на тишине
            no_speech_threshold=0.6,
        )
        text = " ".join(seg.text.strip() for seg in segments).strip()
        elapsed = time.perf_counter() - t0
        logger.info("📝 STT: '{}' (lang={}, {:.1f}s)", text, info.language, elapsed)
        return TranscriptionResult(
            text=text,
            language=info.language,
            duration_sec=elapsed,
        )
