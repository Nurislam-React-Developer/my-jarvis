"""Voice Activity Detection через silero-vad. Реализация в Phase 2."""
from __future__ import annotations

import numpy as np


class VAD:
    def __init__(self, threshold: float = 0.5, sample_rate: int = 16000) -> None:
        self.threshold = threshold
        self.sample_rate = sample_rate

    def is_speech(self, frame: np.ndarray) -> bool:
        raise NotImplementedError("Phase 2")
