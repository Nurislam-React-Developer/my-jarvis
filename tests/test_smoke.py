"""Smoke-тесты: проверка что пакет импортируется и конфиг читается."""
from __future__ import annotations


def test_package_imports() -> None:
    import jarvis
    assert jarvis.__version__


def test_config_loads() -> None:
    from jarvis.config import load_config
    cfg = load_config()
    assert cfg.assistant_name
    assert cfg.stt.engine == "whisper"


def test_skill_registry_empty() -> None:
    from jarvis.skills.registry import build_default_registry
    reg = build_default_registry()
    assert reg.all() == []
