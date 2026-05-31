# 📝 Changelog

All notable changes to this project are documented here.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [0.3.0] — 2026-05-19

### Added
- XTTS-v2 voice cloning (`tts/xtts_tts.py`) on MPS with sentence streaming and on-disk cache.
- Text normalization for speech (`tts/_text_normalize.py`): numbers, units, and times rendered speech-ready.
- New skills: world clock (`get_time_in_city`), Chrome tab closing (`close_browser_tab`), screen analysis (`analyze_screen`).
- Actor voice reactions on wake / greet / goodbye (`audio/reactions.py`).

### Changed
- Wake word now runs three models in parallel with a sliding max-of-N window for steadier triggering.
- Whisper STT initial prompt enriched with common command vocabulary to reduce hallucinations.
- Documentation refreshed to match the real CLI project.

---

## [0.2.0] — 2026-05-19

### Added
- Security hardening: `.env` enforced to chmod 600, pre-commit hooks + gitleaks, CI lint and secret-scan workflows.
- `scripts/check_env.sh` environment diagnostics.

### Changed
- CI dependency split via `requirements-ci.txt` (no macOS-only or heavy ML packages).

### Removed
- Dead code: `vad.py` stub, `record_until_silence`, unused `SoundsConfig`, `wake_words/` directory.
- Stale docs and one-shot scripts.

---

## [0.1.0] — 2026-05

### Added
- Core async voice loop: record → STT → LLM → TTS (`core/assistant.py`).
- Wake word detection via openWakeWord (`audio/wake_word.py`) plus global `⌘+⇧+J` hotkey (`audio/hotkey.py`).
- Local STT with faster-whisper (`stt/whisper_stt.py`).
- OpenAI-compatible LLM brain with function calling (`brain/openai_llm.py`), supporting Mistral / AIHubMix / Gemini.
- macOS `say` TTS fallback (`tts/say_tts.py`).
- 33 native skills: apps, browser, system, music, notes, clipboard, files, info, timers, and long-term memory (SQLite).
- Config via `config/config.yaml` and `config/skills.yaml`; secrets via `.env`.
- `scripts/setup.sh` for system dependency installation.

[0.3.0]: https://github.com/Nurislam-React-Developer/my-jarvis/releases/tag/v0.3.0
[0.2.0]: https://github.com/Nurislam-React-Developer/my-jarvis/releases/tag/v0.2.0
[0.1.0]: https://github.com/Nurislam-React-Developer/my-jarvis/releases/tag/v0.1.0
