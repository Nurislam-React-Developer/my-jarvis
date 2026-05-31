# 🤖 Jarvis — Personal Voice Assistant for macOS

[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](#-license)
[![Platform: macOS](https://img.shields.io/badge/platform-macOS%20(Apple%20Silicon)-lightgrey.svg)](#)
[![CI](https://github.com/Nurislam-React-Developer/my-jarvis/actions/workflows/ci.yml/badge.svg)](https://github.com/Nurislam-React-Developer/my-jarvis/actions/workflows/ci.yml)

A privacy-first voice assistant for macOS that listens in the background, wakes on "Jarvis",
and replies in a cloned actor voice (XTTS-v2) while controlling your Mac.

---

## ✨ Features

| Capability | What it does |
| --- | --- |
| 🎙️ Wake word | Three openWakeWord models in parallel (`hey_jarvis`, `alexa`, `hey_mycroft`) with a sliding max-of-N window; `⌘+⇧+J` hotkey fallback |
| 🗣️ Speech-to-Text | Local `faster-whisper` (beam search 5), no audio leaves the machine |
| 🧠 LLM brain | OpenAI-compatible client (Mistral / AIHubMix / Gemini) with function calling and a Jarvis persona |
| 🔊 Text-to-Speech | XTTS-v2 voice cloning on MPS with sentence streaming, on-disk cache, and number/unit normalization; macOS `say` fallback |
| 🎯 33 native skills | Apps, browser, system, music, notes, clipboard, files, vision, timers, long-term memory |
| 🧠 Long-term memory | `remember` / `recall` / `forget` backed by SQLite |
| 👁️ Vision | Describe the current screen via a multimodal LLM |
| 🔐 Security | `.env` chmod 600, pre-commit + gitleaks, CI lint and secret-scan |

---

## 🚀 Quick Start

```bash
./scripts/setup.sh                       # 1. system deps (brew, portaudio, ffmpeg) + venv
source .venv/bin/activate                # 2. activate the virtualenv
cp .env.example .env                     # 3. add ONE LLM key (Mistral / AIHubMix / Gemini)
bash scripts/check_env.sh                # 4. verify environment
python -m jarvis                         # 5. run
```

First run downloads XTTS-v2 (~1.8 GB) and Whisper-small (~500 MB) once. Full guide: [`docs/SETUP.md`](docs/SETUP.md).

---

## 🧠 Tech Stack

| Layer | Technology | Location |
| --- | --- | --- |
| Wake word | [openWakeWord](https://github.com/dscripka/openWakeWord) | `audio/wake_word.py` |
| STT | [faster-whisper](https://github.com/SYSTRAN/faster-whisper) | `stt/whisper_stt.py` |
| LLM | OpenAI-compatible (Mistral / AIHubMix / Gemini) | `brain/openai_llm.py` |
| TTS | [Coqui XTTS-v2](https://github.com/coqui-ai/TTS) + macOS `say` | `tts/xtts_tts.py`, `tts/say_tts.py` |
| Vision | OpenAI-compatible vision model | `skills/vision.py` |
| macOS glue | AppleScript + screencapture + afplay | `skills/_macos.py` |

---

## 🛣️ Roadmap

Tracked in [`TASKS.md`](TASKS.md) (todo / in progress / done) and phased in [`docs/ROADMAP.md`](docs/ROADMAP.md).
Version history lives in [`CHANGELOG.md`](CHANGELOG.md).

---

## 🤝 Contributing

Contributions are welcome. See [`docs/CONTRIBUTING.md`](docs/CONTRIBUTING.md) for how to add a skill,
run the tests, and the commit message convention. In short:

```bash
make setup        # one-time environment setup
make test         # run the test suite
make lint         # ruff lint + format check
```

---

## 📜 License

MIT — personal project. Author: Nurislam Abdimalikov, Kyrgyzstan.
