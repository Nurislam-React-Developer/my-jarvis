"""Транскрибирует actor_master.wav через Whisper — нужен для F5-TTS как ref_text."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import asyncio
import librosa

from jarvis.stt.whisper_stt import WhisperSTT


async def main() -> None:
    audio_path = Path(__file__).resolve().parents[1] / "assets/sounds/voices/jarvis-clean/actor_master.wav"
    out_path = audio_path.with_suffix(".txt")

    audio, sr = librosa.load(audio_path, sr=16000, mono=True)
    print(f"Loaded {audio_path.name}: {len(audio) / sr:.2f}s @ {sr}Hz")

    stt = WhisperSTT(model="medium", device="auto", compute_type="int8", language="ru")
    result = await stt.transcribe(audio, sample_rate=sr)
    text = result.text.strip()

    print(f"\n📝 Transcript ({len(text)} chars):")
    print(text)

    out_path.write_text(text, encoding="utf-8")
    print(f"\n✅ Сохранил: {out_path}")


asyncio.run(main())
