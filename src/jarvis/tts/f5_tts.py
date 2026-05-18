"""F5-TTS_RUSSIAN — voice cloning заточенный под русский язык.

Модель Misha24-10/F5-TTS_RUSSIAN — это F5-TTS базовая модель, дообученная
на русских корпусах с явной разметкой ударений.

Преимущества над XTTS-v2 на русском:
  - меньше дрожи и акцентного дрейфа
  - явный контроль ударений через символ "+" (молок+о → "молокó")
  - быстрее (диффузия 32 шага)
  - лучше сохраняет идентичность короткого референса (35 сек)

Поддержка ударений включена опционально через RUAccent (если установлен).

API использования:
    f5 = F5TtsTTS(
        ref_file="actor.wav",
        ref_text="...transcript...",
    )
    await f5.speak("Здравствуйте, сэр.")
"""
from __future__ import annotations

import asyncio
import hashlib
import os
from pathlib import Path
from typing import Any

import numpy as np
import soundfile as sf
from huggingface_hub import hf_hub_download
from loguru import logger

from jarvis.tts.base import BaseTTS
from jarvis.tts.say_tts import SayTTS

from jarvis.tts._text_utils import preprocess_text, split_into_sentences

_CACHE_DIR = Path.home() / ".cache" / "jarvis" / "tts_f5"

# HuggingFace репозиторий и доступные чекпоинты (по убыванию свежести)
_HF_REPO = "Misha24-10/F5-TTS_RUSSIAN"
_HF_CKPTS = {
    "v4_winter": "F5TTS_v1_Base_v4_winter/model_212000.safetensors",
    "v2": "F5TTS_v1_Base_v2/model_last_inference.safetensors",
    "accent_tune": "F5TTS_v1_Base_accent_tune/model_last_inference.safetensors",
    "v1": "F5TTS_v1_Base/model_240000_inference.safetensors",
}
_HF_VOCAB = "F5TTS_v1_Base/vocab.txt"


class F5TtsTTS(BaseTTS):
    """Voice cloning TTS на базе F5-TTS_RUSSIAN."""

    def __init__(
        self,
        ref_file: Path | str,
        ref_text: str,
        checkpoint: str = "v2",
        device: str = "cpu",
        cache_enabled: bool = True,
        fallback: BaseTTS | None = None,
        # Параметры синтеза
        nfe_step: int = 32,            # шаги diffusion (16-64). 32 — оптимум скорость/качество
        cfg_strength: float = 2.0,     # classifier-free guidance (1.5-3.0)
        sway_sampling_coef: float = -1.0,  # -1 = новый sampler (рекомендован), 0 = старый
        speed: float = 1.0,            # темп речи
        seed: int = -1,                # -1 = случайный
        use_ruaccent: bool = True,     # автоматическая расстановка ударений
    ) -> None:
        ref_path = Path(ref_file)
        if not ref_path.exists():
            raise FileNotFoundError(f"ref_file не найден: {ref_path}")
        if not ref_text or not ref_text.strip():
            raise ValueError("ref_text не может быть пустым (F5-TTS требует транскрипт референса)")

        self.ref_file = str(ref_path.resolve())
        self.ref_text = ref_text.strip()
        self.checkpoint = checkpoint
        self.device = self._resolve_device(device)
        self.cache_enabled = cache_enabled
        self.fallback = fallback or SayTTS()

        self.synth_params = {
            "nfe_step": nfe_step,
            "cfg_strength": cfg_strength,
            "sway_sampling_coef": sway_sampling_coef,
            "speed": speed,
            "seed": seed,
        }

        self._model: Any = None             # F5TTS instance (ленивая)
        self._ruaccent: Any = None          # авто-ударения (опционально)
        self._use_ruaccent = use_ruaccent

        if cache_enabled:
            _CACHE_DIR.mkdir(parents=True, exist_ok=True)

        logger.info("🎙️  F5-TTS_RUSSIAN готов (device={}, ckpt={})", self.device, checkpoint)

    # ---------- internal helpers ---------- #

    @staticmethod
    def _resolve_device(device: str) -> str:
        if device != "auto":
            return device
        # На Apple Silicon включаем MPS — даёт ~3-5x ускорение vs CPU.
        # Если по какой-то причине MPS недоступен, фолбэк на CPU.
        try:
            import torch

            if torch.backends.mps.is_available():
                return "mps"
        except Exception:  # noqa: BLE001
            pass
        return "cpu"

    def prewarm(self) -> None:
        """Загрузить модель + сделать одну "пустую" генерацию.

        Это съедает фиксированную стоимость инициализации (~30-40 сек первый
        раз) ВО ВРЕМЯ запуска ассистента, а не когда юзер ждёт ответ.
        Безопасно вызывать многократно — последующие вызовы no-op.
        """
        if self._model is not None:
            return
        try:
            self._ensure_loaded()
            # Одна короткая генерация чтобы прогреть граф/кэши
            tmp = _CACHE_DIR / "_prewarm.wav"
            self._synthesize_to_file("Тест.", str(tmp))
            try:
                tmp.unlink()
            except OSError:
                pass
            logger.info("🔥 F5-TTS прогрет — следующая фраза синтезируется быстро")
        except Exception as e:  # noqa: BLE001
            logger.warning("F5-TTS prewarm не удался ({}), продолжим лениво", e)

    def _ensure_loaded(self) -> Any:
        if self._model is not None:
            return self._model

        from f5_tts.api import F5TTS

        ckpt_rel = _HF_CKPTS.get(self.checkpoint)
        if ckpt_rel is None:
            raise ValueError(f"Неизвестный чекпоинт: {self.checkpoint}. Доступные: {list(_HF_CKPTS)}")

        logger.info("⏳ Загружаю F5-TTS чекпоинт {} (~1.3 GB при первом разе)...", self.checkpoint)
        ckpt_path = hf_hub_download(_HF_REPO, ckpt_rel)
        vocab_path = hf_hub_download(_HF_REPO, _HF_VOCAB)

        # F5TTS API: model = модель архитектуры, ckpt_file = веса, vocab_file = словарь
        self._model = F5TTS(
            model="F5TTS_v1_Base",
            ckpt_file=ckpt_path,
            vocab_file=vocab_path,
            device=self.device,
        )
        logger.info("✅ F5-TTS_RUSSIAN загружен (device={})", self.device)

        # Опционально: auto-ударения через RUAccent
        if self._use_ruaccent:
            try:
                from ruaccent import RUAccent

                self._ruaccent = RUAccent()
                self._ruaccent.load(omograph_model_size="turbo", use_dictionary=True)
                logger.info("✅ RUAccent загружен (авто-ударения активны)")
            except Exception as e:  # noqa: BLE001
                logger.debug("RUAccent недоступен ({}), работаем без авто-ударений", e)
                self._ruaccent = None

        return self._model

    def _cache_path(self, text: str) -> Path:
        params_str = ",".join(f"{k}={v}" for k, v in sorted(self.synth_params.items()))
        seed = f"{self.ref_file}|{self.ref_text}|{self.checkpoint}|{params_str}|{text}"
        h = hashlib.sha1(seed.encode()).hexdigest()
        return _CACHE_DIR / f"{h}.wav"

    def _add_accents(self, text: str) -> str:
        """Прогоняет текст через RUAccent чтобы расставить ударения через "+"."""
        if self._ruaccent is None:
            return text
        try:
            return self._ruaccent.process_all(text)
        except Exception as e:  # noqa: BLE001
            logger.debug("RUAccent упал на {!r}: {}", text[:60], e)
            return text

    # ---------- публичный API ---------- #

    async def speak(self, text: str) -> None:
        text = (text or "").strip()
        if not text:
            return

        original = text
        text = preprocess_text(text)
        if text != original:
            logger.debug("📝 preprocessed: {!r} → {!r}", original[:80], text[:80])

        sentences = split_into_sentences(text, max_chars=200)
        logger.debug("🪓 sentences: {}", len(sentences))

        for sent in sentences:
            await self._speak_sentence(sent)

    async def _speak_sentence(self, sentence: str) -> None:
        # Авто-ударения только для генерации (не для кэш-ключа — словарь может меняться)
        gen_text = self._add_accents(sentence)
        if gen_text != sentence:
            logger.debug("🔤 accents: {!r} → {!r}", sentence[:60], gen_text[:60])

        if self.cache_enabled:
            cached = self._cache_path(gen_text)
            if cached.exists() and cached.stat().st_size > 0:
                logger.debug("🎯 cache hit: {}", sentence[:60])
                await self._play_wav(cached)
                return

        out_path = (
            self._cache_path(gen_text) if self.cache_enabled else (_CACHE_DIR / "_temp.wav")
        )

        try:
            await asyncio.get_running_loop().run_in_executor(
                None, self._synthesize_to_file, gen_text, str(out_path)
            )
        except Exception as e:  # noqa: BLE001
            logger.warning("F5-TTS упал ({}): {}. Фолбэк на say.", type(e).__name__, e)
            await self.fallback.speak(sentence)
            return

        await self._play_wav(out_path)

    def _synthesize_to_file(self, text: str, file_path: str) -> None:
        model = self._ensure_loaded()
        logger.debug("🎙️  F5-TTS synth: {!r}", text[:60])

        wav, sr, _ = model.infer(
            ref_file=self.ref_file,
            ref_text=self.ref_text,
            gen_text=text,
            **self.synth_params,
            remove_silence=False,
            file_wave=None,    # вернуть в память, сохраним сами
            file_spec=None,
        )

        # F5TTS возвращает np.ndarray float32 — сохраняем как WAV
        if isinstance(wav, np.ndarray):
            sf.write(file_path, wav, sr)
        else:
            # На всякий случай — конвертируем torch tensor
            arr = wav.detach().cpu().numpy() if hasattr(wav, "detach") else np.asarray(wav)
            sf.write(file_path, arr, sr)

    @staticmethod
    async def _play_wav(path: Path) -> None:
        proc = await asyncio.create_subprocess_exec(
            "afplay",
            str(path),
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
        )
        await proc.wait()
