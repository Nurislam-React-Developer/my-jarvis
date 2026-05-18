"""Базовый интерфейс для Text-to-Speech движков."""
from __future__ import annotations

from abc import ABC, abstractmethod


class BaseTTS(ABC):
    @abstractmethod
    async def speak(self, text: str) -> None: ...
