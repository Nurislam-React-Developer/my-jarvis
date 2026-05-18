"""Главный оркестратор. Склеивает audio → STT → brain → skills → TTS."""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

from loguru import logger

from jarvis.audio.reactions import VoiceReactions
from jarvis.audio.recorder import Recorder
from jarvis.audio.wake_word import WakeWordListener
from jarvis.brain.base import BaseLLM, ToolCall
from jarvis.brain.openai_llm import OpenAIBrain
from jarvis.brain.prompts import get_system_prompt
from jarvis.config import PROJECT_ROOT, Config
from jarvis.core.state import ConversationState
from jarvis.skills.registry import SkillRegistry, build_default_registry
from jarvis.stt.base import BaseSTT
from jarvis.stt.whisper_stt import WhisperSTT
from jarvis.tts.base import BaseTTS
from jarvis.tts.say_tts import SayTTS


MAX_TOOL_ITERATIONS = 5  # защита от бесконечного цикла tool_use → result → tool_use → ...


# Паттерны "Джарвис" в начале фразы (включая типичные ошибки Whisper: Джаррис/Джарвес/Jarvis/etc)
_WAKE_PREFIXES = (
    "джарвис", "джарис", "джаррис", "джарвес", "джервис", "джервес", "джайвис",
    "jarvis", "jervis", "hey jarvis", "эй джарвис",
)


def _default_whisper_prompt() -> str:
    """Подсказка Whisper'у — фиксирует словарь команд и имён приложений.

    Whisper токенайзер на русском часто коверкает английские бренды и редкие
    слова. Если "подкрасить" модели типичный контекст диалога с Джарвисом,
    качество распознавания подскакивает на десятки процентов на наших командах.
    """
    return (
        "Привет, Джарвис. Открой Chrome, Telegram, Spotify, Safari, Visual Studio Code, "
        "Terminal, Finder, Notes, Mail, Calendar, WhatsApp, Slack. "
        "Закрой приложение, переключись на хром, открой ютуб, найди в гугле, "
        "включи музыку, поставь на паузу, следующий трек, какая сейчас песня. "
        "Какая погода в Бишкеке, который час, какая дата сегодня. "
        "Сделай громче, тише, заблокируй экран, скриншот, запиши заметку. "
        "Расскажи шутку, как тебя зовут, спасибо, до свидания."
    )


# Регекс для очистки выводов LLM от технических артефактов:
#  [tool_name]   — Mistral иногда вставляет имя инструмента в текст
#  <tool_call>   — раскрытый XML-тег tool вызова
#  ```...```     — кодовые блоки если их зацепило
_TOOL_LEAK_RE = re.compile(
    r"^\s*(?:\[[a-zA-Z_]+\]|<tool_call>|<tool_use>|```[a-zA-Z]*\n?.*?```)\s*",
    re.DOTALL,
)


def _sanitize_response(text: str) -> str:
    """Очистить ответ LLM от технических артефактов перед TTS.

    LLM иногда «протекает» имена инструментов в текст ответа
    (`[switch_app] Готово, сэр.`). RUAccent потом превращает это в
    «свиткх апп» и TTS озвучивает как мусор. Срезаем такие префиксы.
    Если после очистки осталось пусто — возвращаем дефолт.
    """
    if not text:
        return ""
    cleaned = text.strip()
    # Срезаем потенциально несколько подряд артефактов (например `[a] [b] текст`)
    for _ in range(3):
        new = _TOOL_LEAK_RE.sub("", cleaned, count=1).strip()
        if new == cleaned:
            break
        cleaned = new
    # Убираем одиночные `[слово]` в начале даже если регекс выше пропустил
    cleaned = re.sub(r"^\[[\w_]+\]\s*", "", cleaned).strip()
    return cleaned


def _strip_wake_word_prefix(text: str) -> str:
    """Убрать ведущее 'Джарвис[,]' из транскрипта если есть.

    Openwakeword может сработать чуть позже начала слова, из-за чего Whisper
    захватит "Джарвис, открой хром". Чистим чтобы это не попало в LLM.
    """
    lowered = text.lower().lstrip()
    for prefix in _WAKE_PREFIXES:
        if lowered.startswith(prefix):
            # Отрезаем префикс (+ возможные знаки препинания / пробелы после)
            rest = text.lstrip()[len(prefix):].lstrip(" ,.!?;:")
            return rest
    return text


class Assistant:
    def __init__(self, config: Config) -> None:
        self.config = config
        self.state = ConversationState(max_messages=config.brain.max_history)

        self.recorder: Recorder = self._build_recorder()
        self.stt: BaseSTT = self._build_stt()
        self.brain: BaseLLM = self._build_brain()
        self.tts: BaseTTS = self._build_tts()
        self.skills: SkillRegistry = build_default_registry(
            PROJECT_ROOT / "config" / "skills.yaml"
        )
        self.wake_word: WakeWordListener | None = self._build_wake_word()
        self.reactions: VoiceReactions = self._build_reactions()

        self.system_prompt = get_system_prompt(self.config.language)

    # ---------- factory методы ---------- #

    def _build_recorder(self) -> Recorder:
        return Recorder(
            sample_rate=self.config.audio.sample_rate,
            channels=self.config.audio.channels,
            input_device=self.config.audio.input_device,
        )

    def _build_stt(self) -> BaseSTT:
        s = self.config.stt
        if s.engine != "whisper":
            raise ValueError(f"Неизвестный STT engine: {s.engine}")
        # Собираем initial_prompt — словарь команд + имена приложений.
        # Whisper использует его как «контекст» и существенно лучше распознаёт
        # эти слова. Берём из config.yaml → stt.initial_prompt либо генерим дефолт.
        prompt = s.initial_prompt or _default_whisper_prompt()
        return WhisperSTT(
            model=s.model,
            device=s.device,
            compute_type=s.compute_type,
            language=s.language,
            initial_prompt=prompt,
            beam_size=s.beam_size,
        )

    def _build_brain(self) -> BaseLLM:
        b = self.config.brain
        if b.engine == "aihubmix":
            cfg = b.aihubmix or {}
            # AIHubMix — OpenAI-совместимый агрегатор. Есть бесплатные модели
            # (gpt-5.5-free и др.). Ключ: AIHUBMIX_API_KEY.
            return OpenAIBrain(
                api_key=os.getenv("AIHUBMIX_API_KEY", ""),
                model=cfg.get("model", "gpt-5.5-free"),
                max_tokens=cfg.get("max_tokens", 1024),
                temperature=cfg.get("temperature", 0.7),
                base_url=cfg.get("base_url", "https://aihubmix.com/v1"),
            )
        if b.engine == "mistral":
            cfg = b.mistral or {}
            return OpenAIBrain(
                api_key=os.getenv("MISTRAL_API_KEY", ""),
                model=cfg.get("model", "mistral-small-latest"),
                max_tokens=cfg.get("max_tokens", 1024),
                temperature=cfg.get("temperature", 0.7),
                base_url=cfg.get("base_url", "https://api.mistral.ai/v1"),
            )
        if b.engine == "gemini":
            cfg = b.gemini or {}
            # Google AI Studio предоставляет OpenAI-совместимый эндпоинт.
            return OpenAIBrain(
                api_key=os.getenv("GOOGLE_API_KEY", ""),
                model=cfg.get("model", "gemini-2.5-flash"),
                max_tokens=cfg.get("max_tokens", 1024),
                temperature=cfg.get("temperature", 0.7),
                base_url=cfg.get(
                    "base_url",
                    "https://generativelanguage.googleapis.com/v1beta/openai/",
                ),
            )
        raise ValueError(
            f"Неизвестный brain engine: {b.engine}. "
            f"Доступны: aihubmix | mistral | gemini"
        )

    def _build_reactions(self) -> VoiceReactions:
        r = self.config.reactions
        return VoiceReactions(
            pack_dir=PROJECT_ROOT / r.pack_dir,
            fallback_dir=PROJECT_ROOT / r.fallback_dir,
            enabled=r.enabled,
        )

    def _build_wake_word(self) -> WakeWordListener | None:
        w = self.config.wake_word
        if not w.enabled:
            return None
        if w.engine != "openwakeword":
            raise ValueError(
                f"Неизвестный wake_word engine: {w.engine} (поддерживается только openwakeword)"
            )
        return WakeWordListener(
            wakeword_name=w.keyword,
            threshold=w.threshold,
            input_device=self.config.audio.input_device,
            silence_threshold=w.silence_threshold,
            silence_duration=w.silence_duration,
            initial_grace=w.initial_grace,
            max_command_duration=w.max_command_duration,
            cooldown_after_trigger=w.cooldown_after_trigger,
            debug_scores=w.debug_scores,
            min_consecutive_frames=w.min_consecutive_frames,
            pre_roll_ms=w.pre_roll_ms,
        )

    def _build_tts(self) -> BaseTTS:
        t = self.config.tts
        if t.engine == "say":
            return SayTTS(
                voice=t.say.get("voice", "Yuri"),
                rate=t.say.get("rate", 200),
            )
        if t.engine == "elevenlabs":
            from jarvis.tts.elevenlabs_tts import ElevenLabsTTS

            # voice_id из конфига или env (env имеет приоритет — удобно для экспериментов)
            voice_id = os.getenv("ELEVENLABS_VOICE_ID") or t.elevenlabs.get(
                "voice_id", "nPczCjzI2devNBz1zQrb"  # Brian (по умолчанию)
            )
            return ElevenLabsTTS(
                api_key=os.getenv("ELEVENLABS_API_KEY", ""),
                voice_id=voice_id,
                model=t.elevenlabs.get("model", "eleven_multilingual_v2"),
                stability=t.elevenlabs.get("stability", 0.5),
                similarity_boost=t.elevenlabs.get("similarity_boost", 0.75),
                cache_enabled=t.elevenlabs.get("cache_enabled", True),
            )
        if t.engine == "f5tts":
            from jarvis.tts.f5_tts import F5TtsTTS

            f = t.f5tts
            ref_file = PROJECT_ROOT / f.get(
                "ref_file", "assets/sounds/voices/jarvis-clean/actor_master.wav"
            )
            # ref_text: либо из конфига напрямую, либо из файла рядом с ref_file
            ref_text = f.get("ref_text")
            if not ref_text:
                txt_path = ref_file.with_suffix(".txt")
                if txt_path.exists():
                    ref_text = txt_path.read_text(encoding="utf-8").strip()
                else:
                    raise ValueError(
                        f"F5-TTS требует ref_text. Положи .txt рядом с {ref_file.name} "
                        f"или укажи в config.yaml → tts.f5tts.ref_text"
                    )

            return F5TtsTTS(
                ref_file=ref_file,
                ref_text=ref_text,
                checkpoint=f.get("checkpoint", "v2"),
                device=f.get("device", "cpu"),
                cache_enabled=f.get("cache_enabled", True),
                nfe_step=f.get("nfe_step", 32),
                cfg_strength=f.get("cfg_strength", 2.0),
                sway_sampling_coef=f.get("sway_sampling_coef", -1.0),
                speed=f.get("speed", 1.0),
                seed=f.get("seed", -1),
                use_ruaccent=f.get("use_ruaccent", True),
            )
        raise ValueError(
            f"Неизвестный TTS engine: {t.engine}. "
            f"Доступны: say | f5tts | elevenlabs"
        )

    # ---------- main loop ---------- #

    async def run(self) -> None:
        # Прогреваем TTS если поддерживает — съедает фиксированную стоимость
        # инициализации модели на старте, а не при первом ответе юзеру.
        prewarm = getattr(self.tts, "prewarm", None)
        if callable(prewarm):
            import asyncio as _a

            await _a.get_running_loop().run_in_executor(None, prewarm)

        logger.info("🤖 {} готов. Ctrl+C чтобы выйти.", self.config.assistant_name)
        # Приветствие — сначала пробуем играть клип Джарвиса (по времени дня),
        # если не получилось (нет файла или выключено) — TTS-фолбэк.
        played = False
        if self.config.reactions.play_on_greet:
            played = await self.reactions.play("greet")
        if not played:
            await self.tts.speak(f"{self.config.assistant_name} к вашим услугам.")

        try:
            while True:
                try:
                    await self.handle_one_turn()
                except KeyboardInterrupt:
                    raise
                except Exception:  # noqa: BLE001
                    logger.exception("Ошибка в turn — продолжаю")
        finally:
            # Прощание при выходе (Ctrl+C). Не блокирующее — если клипа нет, просто молчим.
            if self.config.reactions.play_on_goodbye:
                try:
                    await self.reactions.play("goodbye")
                except Exception:  # noqa: BLE001
                    pass

    async def handle_one_turn(self) -> None:
        """Один цикл: услышать → понять → выполнить инструменты → ответить голосом."""
        # 1. Получить аудио. Wake-word имеет приоритет над push-to-talk если включён.
        if self.wake_word is not None:
            # На срабатывание wake word проигрываем "Слушаю, сэр" реальным голосом.
            on_wake = (
                (lambda: self.reactions.play("wake"))
                if self.config.reactions.play_on_wake
                else None
            )
            audio = await self.wake_word.listen_and_capture(on_wake=on_wake)
        else:
            hotkey = self.config.push_to_talk.hotkey
            audio = await self.recorder.record_push_to_talk(hotkey=hotkey)

        if audio.size == 0:
            logger.warning("Пустая запись, пропускаю turn")
            return

        # 2. STT
        result = await self.stt.transcribe(audio, sample_rate=self.config.audio.sample_rate)
        user_text = _strip_wake_word_prefix(result.text.strip())
        if not user_text:
            logger.warning("STT не распознал речь (или только wake word), пропускаю turn")
            return
        print(f"🗣️  Ты:    {user_text}")

        # 3. Brain + tool calling loop
        self.state.add("user", user_text)
        answer = await self._chat_with_tools(user_text)
        self.state.add("assistant", answer)
        print(f"🤖 {self.config.assistant_name}: {answer}")

        # 4. TTS
        await self.tts.speak(answer)

    async def _chat_with_tools(self, user_text: str) -> str:
        """Чат с LLM с поддержкой tool calling. Многошаговый цикл.

        - Стартуем с истории + текущим user_text (он уже добавлен в state).
        - Если LLM вернул tool_calls — выполняем их, кладём результаты как role=tool, повторяем.
        - Если вернул просто текст — это финальный ответ.
        """
        # Базовые сообщения берём из state (включая только что добавленный user_text)
        messages: list[dict] = list(self.state.to_llm_messages())
        tools = self.skills.to_tools_schema() or None

        last_tool_results: list[str] = []  # запомним для фолбэка если LLM ответит пусто

        for iteration in range(MAX_TOOL_ITERATIONS):
            response = await self.brain.chat(
                messages=messages,
                system=self.system_prompt,
                tools=tools,
            )

            if not response.tool_calls:
                # Финальный текстовый ответ — чистим от технических артефактов
                cleaned = _sanitize_response(response.text or "")
                if cleaned:
                    return cleaned
                # LLM вернул пусто (или одни артефакты) — но если был tool-call,
                # озвучим его результат, чтобы юзер не оставался в тишине.
                if last_tool_results:
                    return "Готово, сэр. " + " ".join(last_tool_results[-2:])
                return "Простите, я не понял."

            # LLM хочет вызвать tool(s) — выполняем
            logger.info("🔧 Tool calls (iter {}): {}", iteration + 1,
                        [tc.name for tc in response.tool_calls])

            # 1) Добавить assistant-сообщение с tool_calls в формате OpenAI
            messages.append(self._build_assistant_tool_message(response.text, response.tool_calls))

            # 2) Выполнить каждый tool и добавить результат
            for tc in response.tool_calls:
                result = await self.skills.execute(tc.name, tc.arguments)
                tool_payload = {
                    "success": result.success,
                    "message": result.message,
                    "data": result.data,
                }
                logger.info("   → {} ({}): {}", tc.name,
                            "✓" if result.success else "✗", result.message)
                if result.success and result.message:
                    last_tool_results.append(result.message)
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": json.dumps(tool_payload, ensure_ascii=False),
                })

        logger.warning("Превышен лимит итераций tool calling ({})", MAX_TOOL_ITERATIONS)
        return "Слишком много шагов. Попробуй переформулировать."

    @staticmethod
    def _build_assistant_tool_message(text: str, tool_calls: list[ToolCall]) -> dict:
        """Сериализовать assistant-сообщение с tool_calls в формате OpenAI Chat Completions."""
        return {
            "role": "assistant",
            "content": text or None,
            "tool_calls": [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.name,
                        "arguments": json.dumps(tc.arguments, ensure_ascii=False),
                    },
                }
                for tc in tool_calls
            ],
        }
