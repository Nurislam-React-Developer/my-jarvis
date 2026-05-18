"""Состояние диалога: история сообщений + метаданные сессии."""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal

Role = Literal["user", "assistant", "tool"]


@dataclass
class Message:
    role: Role
    content: str
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ConversationState:
    """Кольцевая история последних N сообщений."""
    max_messages: int = 20
    history: deque[Message] = field(default_factory=deque)
    session_started_at: datetime = field(default_factory=datetime.now)

    def add(self, role: Role, content: str, **meta: Any) -> None:
        self.history.append(Message(role=role, content=content, metadata=dict(meta)))
        while len(self.history) > self.max_messages:
            self.history.popleft()

    def to_llm_messages(self) -> list[dict[str, str]]:
        """Формат, понятный Anthropic / OpenAI chat API."""
        return [{"role": m.role, "content": m.content} for m in self.history]

    def clear(self) -> None:
        self.history.clear()
