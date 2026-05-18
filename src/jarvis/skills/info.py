"""Информационные скиллы: время, дата, погода."""
from __future__ import annotations

from datetime import datetime

import httpx

from .base import Skill, SkillResult


class GetTimeSkill(Skill):
    name = "get_time"
    description = "Получить текущее время. Используй когда пользователь спрашивает 'который час', 'сколько времени'."
    parameters = {"type": "object", "properties": {}, "required": []}

    async def execute(self) -> SkillResult:  # type: ignore[override]
        now = datetime.now()
        text = now.strftime("%H:%M")
        return SkillResult(True, f"Сейчас {text}", {"time": text, "iso": now.isoformat()})


class GetDateSkill(Skill):
    name = "get_date"
    description = "Получить сегодняшнюю дату и день недели."
    parameters = {"type": "object", "properties": {}, "required": []}

    _WEEKDAYS_RU = ["понедельник", "вторник", "среда", "четверг", "пятница", "суббота", "воскресенье"]
    _MONTHS_RU = [
        "января", "февраля", "марта", "апреля", "мая", "июня",
        "июля", "августа", "сентября", "октября", "ноября", "декабря",
    ]

    async def execute(self) -> SkillResult:  # type: ignore[override]
        now = datetime.now()
        weekday = self._WEEKDAYS_RU[now.weekday()]
        month = self._MONTHS_RU[now.month - 1]
        text = f"{weekday}, {now.day} {month} {now.year}"
        return SkillResult(True, text, {"date": now.date().isoformat(), "weekday": weekday})


# ---- Погода через Open-Meteo (без ключа) ---- #

# Координаты популярных городов чтобы не делать лишний геокодинг каждый раз.
_CITY_COORDS: dict[str, tuple[float, float]] = {
    "бишкек": (42.8746, 74.5698),
    "алматы": (43.2389, 76.8897),
    "москва": (55.7558, 37.6176),
    "ош": (40.5285, 72.7985),
}


class GetWeatherSkill(Skill):
    name = "get_weather"
    description = (
        "Получить погоду для города. Используй когда пользователь спрашивает 'какая погода', "
        "'сколько градусов', 'будет ли дождь'."
    )
    parameters = {
        "type": "object",
        "properties": {
            "city": {
                "type": "string",
                "description": "Название города. Например: Бишкек, Алматы, Москва.",
            }
        },
        "required": ["city"],
    }

    async def execute(self, city: str) -> SkillResult:  # type: ignore[override]
        city_norm = city.strip().lower()
        coords = _CITY_COORDS.get(city_norm)

        async with httpx.AsyncClient(timeout=10.0) as client:
            if coords is None:
                # Геокодинг через Open-Meteo
                geo = await client.get(
                    "https://geocoding-api.open-meteo.com/v1/search",
                    params={"name": city, "count": 1, "language": "ru"},
                )
                data = geo.json()
                results = data.get("results") or []
                if not results:
                    return SkillResult(False, f"Не нашёл город '{city}'")
                coords = (results[0]["latitude"], results[0]["longitude"])

            lat, lon = coords
            r = await client.get(
                "https://api.open-meteo.com/v1/forecast",
                params={
                    "latitude": lat,
                    "longitude": lon,
                    "current": "temperature_2m,apparent_temperature,relative_humidity_2m,wind_speed_10m,weather_code",
                    "timezone": "auto",
                },
            )
            cur = r.json().get("current", {})

        temp = cur.get("temperature_2m")
        feels = cur.get("apparent_temperature")
        wind = cur.get("wind_speed_10m")
        code = cur.get("weather_code", 0)
        desc = _wmo_description(int(code))

        msg = f"В городе {city}: {desc}, {temp}°C (ощущается как {feels}°C), ветер {wind} км/ч."
        return SkillResult(True, msg, cur)


def _wmo_description(code: int) -> str:
    """WMO weather codes → русский текст. https://open-meteo.com/en/docs"""
    table = {
        0: "ясно", 1: "в основном ясно", 2: "переменная облачность", 3: "пасмурно",
        45: "туман", 48: "иней",
        51: "лёгкая морось", 53: "морось", 55: "сильная морось",
        61: "лёгкий дождь", 63: "дождь", 65: "сильный дождь",
        66: "лёгкий ледяной дождь", 67: "ледяной дождь",
        71: "лёгкий снег", 73: "снег", 75: "сильный снег", 77: "снежная крупа",
        80: "ливни", 81: "сильные ливни", 82: "очень сильные ливни",
        85: "снегопад", 86: "сильный снегопад",
        95: "гроза", 96: "гроза с градом", 99: "сильная гроза с градом",
    }
    return table.get(code, "погода неизвестна")
