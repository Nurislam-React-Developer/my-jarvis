"""Запись с микрофона.

Phase 1: push-to-talk — нажми и держи `space`, говори, отпусти.
"""

from __future__ import annotations

import asyncio
import threading
from typing import Any

import numpy as np
import sounddevice as sd
from loguru import logger
from pynput import keyboard

_KEY_MAP: dict[str, Any] = {
    "space": keyboard.Key.space,
    "enter": keyboard.Key.enter,
    "shift": keyboard.Key.shift,
    "cmd": keyboard.Key.cmd,
    "alt": keyboard.Key.alt,
    "ctrl": keyboard.Key.ctrl,
}


class Recorder:
    """Запись аудио с микрофона.

    Push-to-talk через `sounddevice` + `pynput`: глобальный hotkey, юзер
    удерживает клавишу, пока говорит.
    """

    def __init__(
        self,
        sample_rate: int = 16000,
        channels: int = 1,
        input_device: int | None = None,
    ) -> None:
        self.sample_rate = sample_rate
        self.channels = channels
        self.input_device = input_device

    async def record_push_to_talk(
        self,
        hotkey: str = "space",
        max_duration: float = 60.0,
    ) -> np.ndarray:
        """Пишет пока удерживается hotkey. Возвращает float32 mono PCM в диапазоне [-1, 1].

        Использует pynput для глобального хоткея (работает даже если терминал не в фокусе,
        при условии что macOS дал Accessibility разрешения).
        """
        target_key = _KEY_MAP.get(hotkey.lower())
        if target_key is None:
            raise ValueError(f"Неизвестный hotkey: {hotkey}")

        loop = asyncio.get_running_loop()
        pressed = threading.Event()
        released = threading.Event()
        # Сигнал готовности чтобы вернуть управление в asyncio loop
        press_future: asyncio.Future[None] = loop.create_future()
        release_future: asyncio.Future[None] = loop.create_future()

        def on_press(key: Any) -> None:
            if key == target_key and not pressed.is_set():
                pressed.set()
                loop.call_soon_threadsafe(
                    lambda: press_future.done() or press_future.set_result(None)
                )

        def on_release(key: Any) -> None:
            if key == target_key and pressed.is_set() and not released.is_set():
                released.set()
                loop.call_soon_threadsafe(
                    lambda: release_future.done() or release_future.set_result(None)
                )

        listener = keyboard.Listener(on_press=on_press, on_release=on_release)
        listener.start()
        try:
            logger.info("🎙️  Удерживай [{}] чтобы говорить...", hotkey)
            await press_future
            logger.info("🔴 Запись началась — отпусти [{}] чтобы закончить", hotkey)

            frames: list[np.ndarray] = []

            def audio_callback(indata, _frames, _time, status):  # noqa: ANN001
                if status:
                    logger.debug("sounddevice status: {}", status)
                frames.append(indata.copy())

            with sd.InputStream(
                samplerate=self.sample_rate,
                channels=self.channels,
                dtype="float32",
                callback=audio_callback,
                device=self.input_device,
            ):
                try:
                    await asyncio.wait_for(release_future, timeout=max_duration)
                except TimeoutError:
                    logger.warning("Достигнут max_duration={}s, останавливаю запись", max_duration)
        finally:
            listener.stop()

        if not frames:
            return np.zeros(0, dtype=np.float32)

        audio = np.concatenate(frames, axis=0).flatten().astype(np.float32)
        logger.info("✅ Записано {:.1f}s аудио", len(audio) / self.sample_rate)
        return audio
