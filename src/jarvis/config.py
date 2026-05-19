"""Загрузка конфига из config/config.yaml + .env."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, Field

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = PROJECT_ROOT / "config" / "config.yaml"
ENV_PATH = PROJECT_ROOT / ".env"


# ---------- Pydantic-схемы для валидации ---------- #


class WakeWordConfig(BaseModel):
    enabled: bool = False
    engine: str = "openwakeword"  # openwakeword (только)
    # str — одна модель (старый формат), list[str] — несколько моделей,
    # любая срабатывание засчитывается.
    keyword: str | list[str] = "hey_jarvis"
    threshold: float = 0.5  # порог срабатывания (0..1)
    silence_threshold: float = 0.005  # RMS-уровень = тишина
    silence_duration: float = 1.2  # сколько тишины подряд = конец фразы
    initial_grace: float = 2.5  # сколько ждать пока юзер начнёт после wake
    max_command_duration: float = 12.0
    cooldown_after_trigger: float = 1.5
    debug_scores: bool = False  # печатать каждый score >= 0.1 для калибровки
    min_consecutive_frames: int = 2  # сколько кадров подряд должно быть выше порога
    pre_roll_ms: int = 600  # сохранить ~N мс аудио ДО wake (защита от срезанного начала)
    # max-of-N окно: триггер если max за последние N фреймов >= threshold.
    # 6 фреймов ≈ 480 мс, что покрывает длительность одного «джарвис».
    window_frames: int = 6


class PushToTalkConfig(BaseModel):
    enabled: bool = True
    hotkey: str = "space"
    # Глобальная hotkey-комбинация (формат pynput.GlobalHotKeys), например
    # "<cmd>+<shift>+j". В отличие от `hotkey` (push-and-hold), это тап:
    # нажал — Джарвис активируется и пишет команду до тишины.
    # Работает параллельно с wake-word.
    hotkey_combo: str = "<cmd>+<shift>+j"


class STTConfig(BaseModel):
    engine: str = "whisper"
    model: str = "medium"  # tiny|base|small|medium|large-v3
    device: str = "auto"
    compute_type: str = "int8"
    language: str = "ru"
    # Whisper initial_prompt — подсказывает модели словарь команд и имён приложений.
    # Пусто = используем дефолт из jarvis.core.assistant._default_whisper_prompt.
    initial_prompt: str = ""
    beam_size: int = 5  # 1=greedy (быстро) | 5=точно (медленнее)


class TTSConfig(BaseModel):
    engine: str = "say"  # say (macOS native) | xtts (voice cloning)
    say: dict[str, Any] = Field(default_factory=dict)
    xtts: dict[str, Any] = Field(default_factory=dict)  # XTTS-v2 voice cloning


class BrainConfig(BaseModel):
    engine: str = "aihubmix"  # aihubmix | mistral | gemini
    aihubmix: dict[str, Any] = Field(default_factory=dict)
    mistral: dict[str, Any] = Field(default_factory=dict)
    gemini: dict[str, Any] = Field(default_factory=dict)
    max_history: int = 20
    system_prompt_path: str | None = None


class VADConfig(BaseModel):
    enabled: bool = True
    threshold: float = 0.5
    silence_duration: float = 1.5
    min_speech_duration: float = 0.3


class AudioConfig(BaseModel):
    sample_rate: int = 16000
    channels: int = 1
    input_device: int | None = None
    output_device: int | None = None
    vad: VADConfig = Field(default_factory=VADConfig)


class LoggingConfig(BaseModel):
    level: str = "INFO"
    file: str = "logs/jarvis.log"
    rotation: str = "10 MB"
    retention: str = "7 days"


class ReactionsConfig(BaseModel):
    """Готовые клипы голоса Джарвиса для частых событий (Priler/jarvis remaster).

    Если enabled=true и pack_dir содержит файлы — Джарвис будет проигрывать
    реальный голос актёра вместо TTS на эти события.
    """

    enabled: bool = True
    pack_dir: str = "assets/sounds/voices/jarvis-remaster"
    fallback_dir: str = "assets/sounds/voices/jarvis-og"
    play_on_wake: bool = True  # реакция "Слушаю, сэр" на wake word
    play_on_ok: bool = True  # "Готово, сэр" после успешной команды
    play_on_greet: bool = True  # приветствие при старте (по времени дня)
    play_on_goodbye: bool = True  # "До свидания" при выходе


class Config(BaseModel):
    language: str = "ru"
    assistant_name: str = "Джарвис"
    wake_word: WakeWordConfig = Field(default_factory=WakeWordConfig)
    push_to_talk: PushToTalkConfig = Field(default_factory=PushToTalkConfig)
    stt: STTConfig = Field(default_factory=STTConfig)
    tts: TTSConfig = Field(default_factory=TTSConfig)
    brain: BrainConfig = Field(default_factory=BrainConfig)
    audio: AudioConfig = Field(default_factory=AudioConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    reactions: ReactionsConfig = Field(default_factory=ReactionsConfig)

    project_root: Path = PROJECT_ROOT


def load_config(path: Path | None = None) -> Config:
    """Прочитать YAML + загрузить .env переменные. Безопасно если файлы отсутствуют — вернёт дефолты."""
    load_dotenv(ENV_PATH, override=False)

    cfg_path = path or CONFIG_PATH
    raw: dict[str, Any] = {}
    if cfg_path.exists():
        with cfg_path.open(encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}

    return Config(**raw)
