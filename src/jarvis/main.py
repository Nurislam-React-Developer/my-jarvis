"""CLI запуск Jarvis."""
from __future__ import annotations

import asyncio
import sys

from jarvis.config import load_config
from jarvis.core.assistant import Assistant
from jarvis.core.logger import setup_logging


def cli() -> None:
    """Синхронная обёртка над async main."""
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Пока!")
        sys.exit(0)


async def main() -> None:
    config = load_config()
    setup_logging(config.logging)

    assistant = Assistant(config)
    await assistant.run()
