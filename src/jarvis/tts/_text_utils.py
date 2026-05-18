"""Препроцессинг текста для voice-cloning TTS (F5-TTS на русском).

Любая cloning-модель на русском дрожит на:
- латинских символах в середине предложения
- редких/нестандартных словах (бренды, аббревиатуры)
- знаках типа кавычек, звёздочек, бэктиков
- слишком длинных предложениях

Этот модуль:
1) применяет словарь фонетических замен (бренды, аббревиатуры);
2) транслитерирует оставшуюся латиницу в кириллицу;
3) чистит знаки препинания;
4) режет длинный текст на предложения для посентенсного синтеза.
"""
from __future__ import annotations

import re


# Фонетические замены конкретных слов (ловят раньше, чем общая транслитерация).
# Ключи в lower(), значения — "как актёр прочитал бы".
PHONETIC_FIXES: dict[str, str] = {
    # --- География (СНГ + частые) ---
    "бишкек": "Бищкэк",          # фикс "биш-э"
    "ош": "Ошш",
    "иссык-куль": "Иссыккуль",
    "алматы": "Алмааты",
    "ташкент": "Ташкэнт",
    "москва": "Масква",
    "нью-йорк": "Нью-Йорк",
    # --- Tech-сервисы ---
    "github": "гитхаб",
    "telegram": "телеграм",
    "spotify": "спотифай",
    "youtube": "ютуб",
    "google": "гугл",
    "openai": "опэн эй ай",
    "anthropic": "энтропик",
    "claude": "клод",
    "gemini": "джемини",
    "mistral": "мистраль",
    "whatsapp": "ватсап",
    "instagram": "инстаграм",
    # --- Аббревиатуры ---
    "api": "апи",
    "url": "ю-эр-эл",
    "json": "джейсон",
    "html": "эйч-ти-эм-эль",
    "css": "си-эс-эс",
    "ip": "ай-пи",
    "wifi": "вайфай",
    "wi-fi": "вайфай",
    "vpn": "ви-пи-эн",
    "usb": "ю-эс-би",
    "ssd": "эс-эс-ди",
    "cpu": "си-пи-ю",
    "gpu": "джи-пи-ю",
    "ai": "эй-ай",
    "ml": "эм-эл",
    "ok": "окей",
    "пк": "писи",
    "мак": "мак",
    "macos": "макос",
    "ios": "айос",
    "iphone": "айфон",
    "ipad": "айпад",
    "macbook": "макбук",
    # --- Единицы ---
    "°c": " градусов цельсия",
    "°": " градусов",
    "%": " процентов",
    "₽": " рублей",
    "$": " долларов",
    "€": " евро",
}

# Грубая транслитерация одиночных латинских символов в кириллицу.
# Применяется ПОСЛЕ словаря — для слов которых нет в PHONETIC_FIXES.
LATIN_TO_CYRILLIC: dict[str, str] = {
    "a": "а", "b": "б", "c": "к", "d": "д", "e": "е", "f": "ф",
    "g": "г", "h": "х", "i": "и", "j": "дж", "k": "к", "l": "л",
    "m": "м", "n": "н", "o": "о", "p": "п", "q": "ку", "r": "р",
    "s": "с", "t": "т", "u": "у", "v": "в", "w": "в", "x": "кс",
    "y": "й", "z": "з",
}


def _apply_phonetic_fixes(text: str) -> str:
    """Шаг 1: словарные замены проблемных слов (регистронезависимо)."""
    out = text
    for src, dst in PHONETIC_FIXES.items():
        lower = out.lower()
        idx = lower.find(src)
        while idx >= 0:
            out = out[:idx] + dst + out[idx + len(src):]
            lower = out.lower()
            idx = lower.find(src, idx + len(dst))
    return out


def _transliterate_latin(text: str) -> str:
    """Шаг 2: транслит оставшейся латиницы в кириллицу."""
    return "".join(
        LATIN_TO_CYRILLIC.get(ch.lower(), ch) if ch.isascii() and ch.isalpha() else ch
        for ch in text
    )


# Знаки препинания которые cloning-модели токенизируют криво
_BAD_CHARS = re.compile(r'[«»"\'`*_~\[\]{}<>|\\^]')
_MULTI_SPACE = re.compile(r"\s+")


def _normalize_punctuation(text: str) -> str:
    """Шаг 3: чистим знаки препинания, нормализуем пробелы."""
    text = _BAD_CHARS.sub(" ", text)
    text = text.replace(";", ".").replace(":", ".")
    text = _MULTI_SPACE.sub(" ", text).strip()
    return text


def preprocess_text(text: str) -> str:
    """Полный препроцессинг — убирает всё что может сломать TTS на русском."""
    text = _apply_phonetic_fixes(text)
    text = _transliterate_latin(text)
    text = _normalize_punctuation(text)
    return text


# Разбиение длинного текста на предложения для посентенсного синтеза.
# Cloning-модели дрожат и теряют голос на фразах >150 символов — лучше резать.
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[А-ЯA-Z])")


def split_into_sentences(text: str, max_chars: int = 200) -> list[str]:
    """Режет текст на предложения. Длинные предложения дополнительно режем по запятым."""
    sentences: list[str] = []
    for s in _SENTENCE_SPLIT.split(text):
        s = s.strip()
        if not s:
            continue
        if len(s) <= max_chars:
            sentences.append(s)
            continue
        chunks: list[str] = []
        buf = ""
        for piece in s.split(", "):
            if len(buf) + len(piece) + 2 > max_chars and buf:
                chunks.append(buf.rstrip(", ") + ".")
                buf = piece
            else:
                buf = (buf + ", " + piece) if buf else piece
        if buf:
            chunks.append(buf)
        sentences.extend(chunks)
    return sentences or [text]
