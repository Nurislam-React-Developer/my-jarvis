"""Vision-скилл: анализ экрана через multimodal LLM.

Делает скриншот всего экрана (или активного окна) через нативный macOS
`screencapture`, кодирует в base64 и шлёт в vision-capable модель.
Использует OpenAI-совместимый API (работает с OpenAI, OpenRouter, NVIDIA NIM,
любым OpenAI-compatible vision-провайдером).

Config (config/skills.yaml):
    analyze_screen:
      enabled: true
      provider: openai            # openai | openrouter | nvidia | custom
      model: gpt-4o-mini          # любая vision-модель провайдера
      base_url: null              # для openrouter/nvidia/custom
      api_key_env: OPENAI_API_KEY # из какой env-переменной брать ключ
      max_tokens: 600
      capture: full               # full | window | selection

Если provider/model не заданы — берётся sane default (OpenAI gpt-4o-mini).
"""
from __future__ import annotations

import asyncio
import base64
import os
import tempfile
from pathlib import Path
from typing import Any, ClassVar

from loguru import logger

from .base import Skill, SkillResult


# Дефолтные пресеты на случай если ключ есть, а конфиг скилла не задан.
_PROVIDER_PRESETS: dict[str, dict[str, Any]] = {
    "openai": {
        "base_url": None,
        "model": "gpt-4o-mini",
        "api_key_env": "OPENAI_API_KEY",
    },
    "openrouter": {
        "base_url": "https://openrouter.ai/api/v1",
        "model": "google/gemini-2.0-flash-exp:free",
        "api_key_env": "OPENROUTER_API_KEY",
    },
    "nvidia": {
        "base_url": "https://integrate.api.nvidia.com/v1",
        "model": "meta/llama-3.2-90b-vision-instruct",
        "api_key_env": "NVIDIA_API_KEY",
    },
    # AIHubMix — OpenAI-совместимый агрегатор. Есть free vision-модели (gpt-5.5-free).
    "aihubmix": {
        "base_url": "https://aihubmix.com/v1",
        "model": "gpt-5.5-free",
        "api_key_env": "AIHUBMIX_API_KEY",
    },
}


class AnalyzeScreenSkill(Skill):
    name = "analyze_screen"
    description = (
        "Сделать скриншот экрана пользователя и проанализировать его через vision-модель. "
        "Используй когда пользователь спрашивает 'что на экране', 'что тут написано', "
        "'объясни эту ошибку', 'переведи картинку', 'посмотри сюда', 'опиши экран'."
    )
    parameters: ClassVar[dict[str, Any]] = {
        "type": "object",
        "properties": {
            "question": {
                "type": "string",
                "description": (
                    "Что именно посмотреть/проанализировать на экране. "
                    "Например: 'опиши экран', 'объясни ошибку', 'переведи текст на русский', "
                    "'что это за приложение'."
                ),
            },
            "capture_mode": {
                "type": "string",
                "enum": ["full", "window", "selection"],
                "description": (
                    "full — весь экран (по умолчанию); "
                    "window — активное окно; "
                    "selection — юзер сам выделит область мышью."
                ),
            },
        },
        "required": ["question"],
    }

    # Эти поля можно переопределить через skills.yaml → merge в __init__ извне,
    # но реестр сейчас выставляет только requires_confirmation. Поэтому читаем env.
    _DEFAULT_PROVIDER = "openai"

    def __init__(
        self,
        provider: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
        api_key_env: str | None = None,
        max_tokens: int = 600,
        capture: str = "full",
    ) -> None:
        # Авто-определение провайдера если не задан: смотрим какой ключ есть в env.
        if not provider:
            for p in ("openai", "aihubmix", "openrouter", "nvidia"):
                env_name = _PROVIDER_PRESETS[p]["api_key_env"]
                if os.getenv(env_name):
                    provider = p
                    break
            provider = provider or self._DEFAULT_PROVIDER

        preset = _PROVIDER_PRESETS.get(provider, _PROVIDER_PRESETS[self._DEFAULT_PROVIDER])
        self.provider = provider
        self.model = model or preset["model"]
        self.base_url = base_url if base_url is not None else preset["base_url"]
        self.api_key_env = api_key_env or preset["api_key_env"]
        self.max_tokens = max_tokens
        self.default_capture = capture
        self._client: Any = None
        # Какой параметр лимита токенов принимает модель: max_tokens (legacy)
        # или max_completion_tokens (новые reasoning-модели: gpt-5, o1, o3).
        # None = ещё не выяснили; узнаём при первом запросе и кэшируем.
        self._token_param: str | None = None

    # ---------- screenshot ---------- #

    async def _screencapture(self, mode: str, out_path: Path) -> bool:
        """Запускает macOS `screencapture`. Возвращает True если файл создан."""
        args = ["screencapture", "-x"]  # -x = no shutter sound
        if mode == "window":
            args += ["-W"]  # юзер кликнет по окну
        elif mode == "selection":
            args += ["-i"]  # интерактивный выбор области
        # full = без флагов
        args.append(str(out_path))

        proc = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
        )
        _, err = await proc.communicate()
        if proc.returncode != 0:
            logger.error("screencapture failed: {}", err.decode(errors="ignore"))
            return False
        return out_path.exists() and out_path.stat().st_size > 0

    # ---------- LLM call ---------- #

    def _ensure_client(self):  # noqa: ANN202
        if self._client is None:
            from openai import AsyncOpenAI

            api_key = os.getenv(self.api_key_env, "")
            if not api_key:
                raise RuntimeError(
                    f"Vision-скилл: пустой ключ в env-переменной {self.api_key_env}. "
                    f"Положи ключ в .env."
                )
            kwargs: dict[str, Any] = {"api_key": api_key}
            if self.base_url:
                kwargs["base_url"] = self.base_url
            self._client = AsyncOpenAI(**kwargs)
        return self._client

    async def _ask_vision(self, question: str, image_b64: str) -> str:
        client = self._ensure_client()
        messages = [
            {
                "role": "system",
                "content": (
                    "Ты — Джарвис, голосовой помощник. Тебе показывают скриншот "
                    "экрана пользователя. Отвечай коротко, по делу, на русском "
                    "(если пользователь не попросил иначе). Без markdown."
                ),
            },
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": question},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{image_b64}",
                            "detail": "high",
                        },
                    },
                ],
            },
        ]

        async def _call(token_param: str):
            return await client.chat.completions.create(
                model=self.model,
                messages=messages,
                **{token_param: self.max_tokens},
            )

        # 1) Известен ли param лимита токенов — используем его.
        # 2) Иначе пробуем max_tokens, на 400 'max_tokens'/'unsupported_parameter'
        #    откатываемся на max_completion_tokens и кэшируем.
        from openai import BadRequestError

        if self._token_param:
            response = await _call(self._token_param)
        else:
            try:
                response = await _call("max_tokens")
                self._token_param = "max_tokens"
            except BadRequestError as e:
                msg = str(e).lower()
                if "max_tokens" in msg and "max_completion_tokens" in msg:
                    logger.debug("{} требует max_completion_tokens, переключаюсь", self.model)
                    response = await _call("max_completion_tokens")
                    self._token_param = "max_completion_tokens"
                else:
                    raise

        return (response.choices[0].message.content or "").strip()

    # ---------- execute ---------- #

    async def execute(  # type: ignore[override]
        self,
        question: str,
        capture_mode: str | None = None,
    ) -> SkillResult:
        mode = capture_mode or self.default_capture
        if mode not in {"full", "window", "selection"}:
            mode = "full"

        with tempfile.NamedTemporaryFile(prefix="jarvis_vision_", suffix=".png", delete=False) as f:
            shot_path = Path(f.name)

        try:
            ok = await self._screencapture(mode, shot_path)
            if not ok:
                return SkillResult(False, "Не удалось сделать скриншот.")

            image_b64 = base64.b64encode(shot_path.read_bytes()).decode("ascii")
            logger.info(
                "Vision: {} ({} KB) → {} ({})",
                mode, len(image_b64) // 1024, self.model, self.provider,
            )

            answer = await self._ask_vision(question, image_b64)
            if not answer:
                return SkillResult(False, "Vision-модель вернула пустой ответ.")

            return SkillResult(
                True,
                answer,
                {"provider": self.provider, "model": self.model, "capture_mode": mode},
            )
        except Exception as e:  # noqa: BLE001
            logger.exception("AnalyzeScreenSkill ошибка")
            return SkillResult(False, f"Ошибка анализа экрана: {e}")
        finally:
            try:
                shot_path.unlink(missing_ok=True)
            except Exception:  # noqa: BLE001
                pass
