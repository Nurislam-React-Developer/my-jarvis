"""OpenAI-совместимый клиент.

Используется как универсальный transport для всех brain-движков Джарвиса:
- AIHubMix (gpt-5.5-free и др.)
- Mistral La Plateforme
- Google Gemini (через OpenAI-совместимый эндпоинт)
- любой другой OpenAI-совместимый провайдер.
"""
from __future__ import annotations

from loguru import logger

from .base import BaseLLM, LLMResponse, ToolCall


class OpenAIBrain(BaseLLM):
    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4o-mini",
        max_tokens: int = 1024,
        temperature: float = 0.7,
        base_url: str | None = None,
        extra_headers: dict[str, str] | None = None,
    ) -> None:
        if not api_key:
            raise ValueError(
                "API key пустой. Заполни .env: AIHUBMIX_API_KEY (по умолчанию) "
                "или MISTRAL_API_KEY / GOOGLE_API_KEY в зависимости от brain.engine."
            )
        self.api_key = api_key
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.base_url = base_url
        self.extra_headers = extra_headers or {}
        self._client = None
        # Какой параметр лимита токенов принимает модель: max_tokens (legacy)
        # или max_completion_tokens (новые reasoning-модели: gpt-5, o1, o3).
        # None = ещё не выяснили; узнаём при первом запросе и кэшируем.
        self._token_param: str | None = None

    def _ensure_client(self):  # noqa: ANN202
        if self._client is None:
            from openai import AsyncOpenAI

            kwargs: dict = {"api_key": self.api_key}
            if self.base_url:
                kwargs["base_url"] = self.base_url
            if self.extra_headers:
                kwargs["default_headers"] = self.extra_headers
            self._client = AsyncOpenAI(**kwargs)
        return self._client

    async def chat(
        self,
        messages: list[dict[str, str]],
        system: str | None = None,
        tools: list[dict] | None = None,
    ) -> LLMResponse:
        client = self._ensure_client()

        # OpenAI принимает system как первое сообщение role=system
        full_messages: list[dict] = []
        if system:
            full_messages.append({"role": "system", "content": system})
        full_messages.extend(messages)

        kwargs: dict = {
            "model": self.model,
            "messages": full_messages,
            "temperature": self.temperature,
        }
        if tools:
            # OpenAI tools формат: {type:"function", function:{name, description, parameters}}
            kwargs["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": t["name"],
                        "description": t.get("description", ""),
                        "parameters": t.get("input_schema") or t.get("parameters", {}),
                    },
                }
                for t in tools
            ]

        logger.debug("→ {} ({} msgs)", self.model, len(full_messages))

        # Лимит токенов: новые reasoning-модели (gpt-5, o1, o3) требуют
        # max_completion_tokens, остальные — max_tokens. Узнаём при первом
        # запросе и кэшируем выбор на инстансе.
        from openai import BadRequestError

        async def _create(token_param: str):
            return await client.chat.completions.create(
                **kwargs, **{token_param: self.max_tokens}
            )

        if self._token_param:
            response = await _create(self._token_param)
        else:
            try:
                response = await _create("max_tokens")
                self._token_param = "max_tokens"
            except BadRequestError as e:
                err = str(e).lower()
                if "max_tokens" in err and "max_completion_tokens" in err:
                    logger.debug("{} требует max_completion_tokens, переключаюсь", self.model)
                    response = await _create("max_completion_tokens")
                    self._token_param = "max_completion_tokens"
                else:
                    raise

        msg = response.choices[0].message
        text = (msg.content or "").strip()

        tool_calls: list[ToolCall] = []
        for tc in (msg.tool_calls or []):
            import json

            try:
                args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}
            tool_calls.append(ToolCall(id=tc.id, name=tc.function.name, arguments=args))

        logger.debug("← {}: {} chars, {} tool_calls", self.model, len(text), len(tool_calls))
        return LLMResponse(text=text, tool_calls=tool_calls, raw=response)
