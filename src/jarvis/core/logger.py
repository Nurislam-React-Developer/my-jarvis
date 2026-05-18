"""Настройка логирования через loguru."""
from __future__ import annotations

import sys
from pathlib import Path

from loguru import logger

from jarvis.config import LoggingConfig, PROJECT_ROOT


def setup_logging(cfg: LoggingConfig) -> None:
    logger.remove()
    logger.add(
        sys.stderr,
        level=cfg.level,
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | "
               "<cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>",
    )

    log_path = Path(cfg.file)
    if not log_path.is_absolute():
        log_path = PROJECT_ROOT / log_path
    log_path.parent.mkdir(parents=True, exist_ok=True)

    logger.add(
        log_path,
        level=cfg.level,
        rotation=cfg.rotation,
        retention=cfg.retention,
        encoding="utf-8",
    )
