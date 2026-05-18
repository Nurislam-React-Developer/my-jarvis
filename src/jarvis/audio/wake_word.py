"""Wake word через openWakeWord (open-source, бесплатно навсегда).

Использует pretrained ONNX модель `hey_jarvis_v0.1`. Слушает микрофон
непрерывно тонким детектором (~2% CPU), при срабатывании запускает запись
команды до момента тишины.
"""
from __future__ import annotations

import asyncio
import queue
import threading
from collections import deque
from typing import Any, Awaitable, Callable

import numpy as np
import sounddevice as sd
from loguru import logger
from openwakeword.model import Model


# openwakeword работает на 16kHz, mono, int16, фрейм 1280 сэмплов = 80мс
SAMPLE_RATE = 16_000
FRAME_SIZE = 1280
FRAME_DURATION = FRAME_SIZE / SAMPLE_RATE  # 0.08 сек


class WakeWordListener:
    """Слушает микрофон и ждёт wake word, затем пишет команду до тишины."""

    def __init__(
        self,
        wakeword_name: str = "hey_jarvis",
        threshold: float = 0.5,
        input_device: int | None = None,
        # VAD параметры (energy-based, без доп. библиотек)
        silence_threshold: float = 0.005,    # RMS ниже этого = тишина
        silence_duration: float = 1.2,        # сколько подряд тишины = конец фразы
        initial_grace: float = 2.5,           # сколько ждать пока юзер начнёт говорить
        max_command_duration: float = 12.0,   # потолок длины команды
        cooldown_after_trigger: float = 1.5,  # сколько игнорить wake word после срабатывания
        debug_scores: bool = False,           # логировать каждый score >= 0.1
        min_consecutive_frames: int = 2,      # сколько кадров подряд должно быть выше порога
        pre_roll_ms: int = 600,               # сохранять последние N мс аудио ПЕРЕД триггером
    ) -> None:
        self.wakeword_name = wakeword_name
        self.threshold = threshold
        self.input_device = input_device
        self.silence_threshold = silence_threshold
        self.silence_duration = silence_duration
        self.initial_grace = initial_grace
        self.max_command_duration = max_command_duration
        self.cooldown_after_trigger = cooldown_after_trigger
        self.debug_scores = debug_scores
        self.min_consecutive_frames = max(1, min_consecutive_frames)
        # Кольцевой буфер для pre-roll — сохраняем ~N мс аудио до wake.
        # Это защита от ситуации "юзер начал команду до конца слова Джарвис".
        self._pre_roll_frames = max(0, int(pre_roll_ms / 1000.0 / FRAME_DURATION))
        self._pre_roll: deque[np.ndarray] = deque(maxlen=self._pre_roll_frames)

        logger.info("Загружаю openWakeWord модель: {}", wakeword_name)
        self._model = Model(wakeword_models=[wakeword_name], inference_framework="onnx")
        if wakeword_name not in self._model.models:
            available = list(self._model.models.keys())
            raise ValueError(
                f"Модель {wakeword_name} не загрузилась. Доступные: {available}"
            )
        logger.info("✅ openWakeWord готов")

    async def listen_and_capture(
        self,
        on_wake: Callable[[], Awaitable[None]] | None = None,
    ) -> np.ndarray:
        """Главный метод: блокирует пока не услышит wake word, потом записывает команду.

        Args:
            on_wake: опциональный async callback который вызывается СРАЗУ после
                распознавания wake word — до того как мы начнём захватывать команду.
                Удобно чтобы проиграть «Слушаю, сэр» голосом Джарвиса. После
                выполнения callback мы дренируем очередь, чтобы записанный
                из микрофона звук этого клипа не попал в команду.

        Возвращает float32 mono PCM аудио команды (без слова "Джарвис").
        Если ничего внятного не услышал — пустой массив.
        """
        loop = asyncio.get_running_loop()
        # Очередь сырых int16 фреймов от sd-callback в наш asyncio-таск.
        frame_q: queue.Queue[np.ndarray] = queue.Queue(maxsize=200)
        stop_flag = threading.Event()

        def audio_cb(indata: np.ndarray, _frames: int, _time: Any, status: Any) -> None:
            if status:
                logger.debug("sounddevice status: {}", status)
            # indata: (FRAME_SIZE, 1) float32 в [-1, 1]. Конвертим в int16 для модели.
            mono = indata[:, 0]
            int16 = (np.clip(mono, -1.0, 1.0) * 32767).astype(np.int16)
            try:
                frame_q.put_nowait(int16)
            except queue.Full:
                # Пропускаем если очередь забилась — лучше потерять кадр чем заблокировать поток.
                pass

        stream = sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=1,
            dtype="float32",
            blocksize=FRAME_SIZE,
            callback=audio_cb,
            device=self.input_device,
        )
        stream.start()
        try:
            logger.info('🟢 Слушаю фоном. Скажи "Джарвис" чтобы активировать...')

            # 1) Ждём wake word
            triggered = await loop.run_in_executor(
                None, self._wait_for_wakeword, frame_q, stop_flag
            )
            if not triggered:
                return np.zeros(0, dtype=np.float32)

            logger.info("✨ Wake word услышан — слушаю команду...")

            # 2) Если есть on_wake callback — играем реакцию ("Слушаю, сэр") и
            # после её окончания дренируем очередь, чтобы клип не попал в запись.
            # В этом случае pre-roll НЕ используем — юзер всё равно ждёт окончания клипа.
            prepend_frames: list[np.ndarray] = []
            if on_wake is not None:
                try:
                    await on_wake()
                except Exception:  # noqa: BLE001
                    logger.exception("on_wake callback упал")
                self._drain_queue(frame_q, frames_to_drop=frame_q.qsize())
            else:
                # Без on_wake — добавим pre-roll (~600 мс ДО wake) в начало записи.
                # ВАЖНО: НЕ дренируем очередь после триггера. Иначе мы дропнем
                # начало команды (например "от" из "открой") если юзер говорит
                # без паузы после "Джарвис". Pre-roll + полная пост-wake запись
                # вместе дают непрерывное аудио без дыр. Защита от двойного
                # срабатывания обеспечивается через self._model.reset() выше.
                prepend_frames = list(self._pre_roll)

            # 3) Записываем команду до тишины
            command_audio = await loop.run_in_executor(
                None,
                self._capture_until_silence,
                frame_q,
                stop_flag,
                prepend_frames,
            )
            return command_audio
        finally:
            stop_flag.set()
            stream.stop()
            stream.close()

    # ---- блокирующие методы, выполняются в executor ---- #

    def _wait_for_wakeword(
        self,
        frame_q: queue.Queue[np.ndarray],
        stop_flag: threading.Event,
    ) -> bool:
        """Гоняет openwakeword на каждом фрейме пока не сработает wake word.

        Срабатывает только если score >= threshold в течение
        `min_consecutive_frames` подряд — это режет ложняки от случайных
        звуков. Дополнительно ведёт pre-roll буфер из последних ~600 мс
        аудио, чтобы при срабатывании можно было «подмотать» начало команды.
        """
        peak = 0.0  # пиковый score в текущем "окошке" — для диагностики
        peak_frames_left = 0  # сколько фреймов ещё считаем пик до сброса
        consecutive = 0  # сколько подряд кадров было выше порога

        # Сбрасываем pre-roll перед началом нового цикла
        self._pre_roll.clear()

        while not stop_flag.is_set():
            try:
                frame = frame_q.get(timeout=0.5)
            except queue.Empty:
                continue

            # Накапливаем pre-roll (кольцевой буфер, лишнее само вытесняется)
            self._pre_roll.append(frame)

            scores = self._model.predict(frame)
            score = float(scores.get(self.wakeword_name, 0.0))

            # Диагностический режим — печатаем все заметные значения
            if self.debug_scores and score >= 0.1:
                logger.info("🔬 wake score: {:.3f} (run={})", score, consecutive)

            # Отслеживаем пик за последние ~2 секунды и логируем когда он спадёт
            if score > peak:
                peak = score
                peak_frames_left = int(2.0 / FRAME_DURATION)
            elif peak_frames_left > 0:
                peak_frames_left -= 1
                if peak_frames_left == 0 and peak >= 0.2:
                    logger.info("📊 пик score за окно: {:.3f} (порог {:.2f})", peak, self.threshold)
                    peak = 0.0

            # Стабильность: триггер только когда N подряд кадров выше порога
            if score >= self.threshold:
                consecutive += 1
                if consecutive >= self.min_consecutive_frames:
                    logger.info(
                        "✨ Wake word triggered! score={:.3f} (consec={})",
                        score, consecutive,
                    )
                    # Сбросить состояние модели чтобы тот же звук не сработал ещё раз
                    self._model.reset()
                    # NB: НЕ дропаем буфер тут — _capture_until_silence сам решит
                    # стартовать запись с pre-roll (чтобы не потерять начало команды)
                    return True
            else:
                consecutive = 0

        return False

    def _capture_until_silence(
        self,
        frame_q: queue.Queue[np.ndarray],
        stop_flag: threading.Event,
        prepend_frames: list[np.ndarray] | None = None,
    ) -> np.ndarray:
        """Пишет аудио из очереди пока не услышит достаточно длинную паузу.

        Если переданы `prepend_frames` (например pre-roll из последних 600 мс),
        они добавляются в самое начало команды и сразу считаются «речью»,
        чтобы grace-окно не съело их за тишину.
        """
        collected: list[np.ndarray] = list(prepend_frames or [])
        elapsed = 0.0
        silence_elapsed = 0.0
        # Если есть pre-roll — в нём гарантированно была речь рядом со словом
        # «Джарвис», поэтому считаем что команда уже началась.
        speech_started = bool(collected)
        grace_left = self.initial_grace

        while not stop_flag.is_set():
            if elapsed >= self.max_command_duration:
                logger.warning("Достигнут потолок {}s", self.max_command_duration)
                break

            try:
                frame = frame_q.get(timeout=0.5)
            except queue.Empty:
                continue

            collected.append(frame)
            elapsed += FRAME_DURATION

            # Energy-based VAD: RMS текущего фрейма, нормализованный к [-1, 1]
            rms = float(np.sqrt(np.mean((frame.astype(np.float32) / 32768.0) ** 2)))
            is_silent = rms < self.silence_threshold

            if not speech_started:
                # Ждём пока юзер начнёт говорить
                if not is_silent:
                    speech_started = True
                else:
                    grace_left -= FRAME_DURATION
                    if grace_left <= 0:
                        logger.info("Юзер ничего не сказал после wake word — отмена")
                        return np.zeros(0, dtype=np.float32)
            else:
                # Уже говорит — отслеживаем паузу
                if is_silent:
                    silence_elapsed += FRAME_DURATION
                    if silence_elapsed >= self.silence_duration:
                        break
                else:
                    silence_elapsed = 0.0

        if not collected:
            return np.zeros(0, dtype=np.float32)

        # int16 → float32 в диапазоне [-1, 1]
        full_int16 = np.concatenate(collected)
        audio = full_int16.astype(np.float32) / 32768.0
        logger.info("✅ Записал команду {:.1f}s", len(audio) / SAMPLE_RATE)
        return audio

    @staticmethod
    def _drain_queue(q: queue.Queue[np.ndarray], frames_to_drop: int = 0) -> None:
        """Сбросить очередь (опционально пропустить N фреймов как "cooldown")."""
        dropped = 0
        while dropped < frames_to_drop:
            try:
                q.get_nowait()
                dropped += 1
            except queue.Empty:
                return
