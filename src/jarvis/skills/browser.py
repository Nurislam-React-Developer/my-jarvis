"""Скиллы веб-браузера и поиска."""
from __future__ import annotations

import urllib.parse

from ._macos import run_shell
from .base import Skill, SkillResult


class WebSearchSkill(Skill):
    name = "web_search"
    description = "Найти что-либо в Google в браузере по умолчанию."
    parameters = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Поисковый запрос"}
        },
        "required": ["query"],
    }

    async def execute(self, query: str) -> SkillResult:  # type: ignore[override]
        url = "https://www.google.com/search?q=" + urllib.parse.quote_plus(query)
        await run_shell("open", url)
        return SkillResult(True, f"Ищу в Google: {query}", {"url": url})


class OpenURLSkill(Skill):
    name = "open_url"
    description = "Открыть URL в браузере. Используй когда пользователь говорит 'открой сайт ...'."
    parameters = {
        "type": "object",
        "properties": {
            "url": {"type": "string", "description": "URL вида https://..."}
        },
        "required": ["url"],
    }

    async def execute(self, url: str) -> SkillResult:  # type: ignore[override]
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        await run_shell("open", url)
        return SkillResult(True, f"Открыл {url}")


class YouTubeSearchSkill(Skill):
    name = "youtube_search"
    description = "Найти видео на YouTube."
    parameters = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Что искать на YouTube"}
        },
        "required": ["query"],
    }

    async def execute(self, query: str) -> SkillResult:  # type: ignore[override]
        url = "https://www.youtube.com/results?search_query=" + urllib.parse.quote_plus(query)
        await run_shell("open", url)
        return SkillResult(True, f"Ищу на YouTube: {query}", {"url": url})


class WikiSearchSkill(Skill):
    name = "wiki_search"
    description = "Найти статью в Wikipedia."
    parameters = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Что искать в Wikipedia"},
            "lang": {"type": "string", "description": "Язык: ru или en", "default": "ru"},
        },
        "required": ["query"],
    }

    async def execute(self, query: str, lang: str = "ru") -> SkillResult:  # type: ignore[override]
        url = f"https://{lang}.wikipedia.org/w/index.php?search=" + urllib.parse.quote_plus(query)
        await run_shell("open", url)
        return SkillResult(True, f"Открыл Wikipedia: {query}", {"url": url})
