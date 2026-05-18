"""Trim silence + normalize + concat → один master reference для XTTS-v2.

Берёт все 8 demucs-очищенных vocals.wav, обрезает тишину по краям,
склеивает с короткими паузами и сохраняет как
`assets/sounds/voices/jarvis-clean/actor_master.wav`.

XTTS-v2 даёт стабильнее клон когда подаёшь один длинный непрерывный wav
вместо множества коротких фрагментов.
"""
from __future__ import annotations

from pathlib import Path

import librosa
import numpy as np
import soundfile as sf

SRC_DIR = Path("/tmp/demucs_out/htdemucs")
OUT_DIR = Path(__file__).resolve().parents[1] / "assets/sounds/voices/jarvis-clean"
OUT_DIR.mkdir(parents=True, exist_ok=True)

TARGET_SR = 22050
PAD = np.zeros(int(0.25 * TARGET_SR), dtype=np.float32)


def main() -> None:
    segments: list[np.ndarray] = []
    for i in range(1, 9):
        path = SRC_DIR / f"joke{i}" / "vocals.wav"
        if not path.exists():
            print(f"[skip] {path}")
            continue
        y, _ = librosa.load(path, sr=TARGET_SR, mono=True)
        # top_db=30 — щадящий порог: не режет тихие выдохи актёра
        y_trim, _ = librosa.effects.trim(y, top_db=30)
        print(f"  joke{i}: {len(y) / TARGET_SR:.2f}s -> trim -> {len(y_trim) / TARGET_SR:.2f}s")
        segments.append(y_trim)

    if not segments:
        raise SystemExit("Нет ни одного vocals.wav в /tmp/demucs_out/htdemucs/")

    # Между сегментами — короткая пауза 250 мс
    parts: list[np.ndarray] = []
    for idx, seg in enumerate(segments):
        parts.append(seg)
        if idx < len(segments) - 1:
            parts.append(PAD)
    master = np.concatenate(parts)

    # Peak-нормализация до -1 dBFS (без агрессивного компрессора)
    peak = float(np.abs(master).max())
    if peak > 0:
        master = master * (10 ** (-1 / 20) / peak)

    out = OUT_DIR / "actor_master.wav"
    sf.write(out, master, TARGET_SR)
    print(f"\n[ok] {out}")
    print(f"     length: {len(master) / TARGET_SR:.2f}s @ {TARGET_SR}Hz mono")
    print(f"     peak:   {float(np.abs(master).max()):.3f}")


if __name__ == "__main__":
    main()
