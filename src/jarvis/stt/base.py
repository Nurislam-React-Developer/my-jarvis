"""Базовый интерфейс для Speech-to-Text движков."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

import numpy as np


@dataclass
class TranscriptionResult:
    text: str
    language: str
    duration_sec: float


class BaseSTT(ABC):
    @abstractmethod
    async def transcribe(self, audio: np.ndarray, sample_rate: int = 16000) -> TranscriptionResult: ...
