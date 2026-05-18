# 🤖 Jarvis — Personal Voice Assistant for macOS

> *"Sometimes you gotta run before you can walk."* — Tony Stark

Offline-first голосовой помощник для macOS, вдохновлённый Джарвисом из Iron Man.
Понимает русский и английский, выполняет команды на компьютере, общается через LLM.

**Платформа:** macOS Apple Silicon (M1/M2/M3/M4)
**Язык:** Python 3.11+
**Лицензия:** MIT (личный проект)

---

## ✨ Возможности

- 🎙️ **Wake word** — активация по фразе "Джарвис" / "Hey Jarvis"
- 🗣️ **Понимает речь** — Whisper локально (offline, бесплатно)
- 🧠 **Умный мозг** — Claude / OpenAI с function calling
- 🔊 **Отвечает голосом** — macOS `say` или ElevenLabs (премиум-голос)
- 🎯 **Управляет Mac** — открывает приложения, пишет сообщения, читает почту, ставит музыку
- 🔌 **Расширяемые скиллы** — легко добавлять новые команды
- 🔒 **Privacy-first** — STT работает локально, наружу уходит только запрос к LLM

---

## 🗂️ Структура проекта

```
jarvis/
├── README.md                  ← ты здесь
├── docs/                      ← документация
│   ├── ARCHITECTURE.md        ← как всё устроено
│   ├── ROADMAP.md             ← план разработки по фазам
│   ├── SKILLS.md              ← список скиллов и как добавить свой
│   └── SETUP.md               ← полная установка
├── src/jarvis/                ← исходный код
│   ├── main.py                ← точка входа
│   ├── config.py              ← загрузка конфига
│   ├── core/                  ← оркестратор, состояние, логи
│   ├── audio/                 ← запись микрофона, wake word, VAD
│   ├── stt/                   ← speech-to-text (Whisper)
│   ├── tts/                   ← text-to-speech (say / ElevenLabs)
│   ├── brain/                 ← LLM клиент + промпты
│   └── skills/                ← скиллы (open app, music, msg...)
├── config/
│   ├── config.yaml            ← основные настройки
│   └── skills.yaml            ← включение/выключение скиллов
├── tests/                     ← unit-тесты
├── scripts/                   ← setup, install_deps
├── assets/                    ← звуки активации, иконки
├── .env.example               ← шаблон переменных окружения
├── .gitignore
├── pyproject.toml
└── requirements.txt
```

---

## 🚀 Быстрый старт

```bash
# 1. Системные зависимости (Homebrew, portaudio, ffmpeg)
./scripts/setup.sh

# 2. Python окружение и зависимости
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 3. Скопировать .env и вписать API ключи
cp .env.example .env
# открой .env и заполни ANTHROPIC_API_KEY / PICOVOICE_ACCESS_KEY

# 4. Запуск
python -m jarvis
```

Подробная инструкция — [docs/SETUP.md](docs/SETUP.md).

---

## 🧠 Технологии

| Компонент       | Технология                          | Зачем                     |
| --------------- | ----------------------------------- | ------------------------- |
| Wake word       | [Picovoice Porcupine](https://picovoice.ai/) | "Джарвис" триггер         |
| Speech-to-Text  | [faster-whisper](https://github.com/SYSTRAN/faster-whisper) | Whisper на M-чипе         |
| LLM brain       | Anthropic Claude / OpenAI           | Понимание + function call |
| Text-to-Speech  | macOS `say` / ElevenLabs API        | Озвучка ответа            |
| Действия        | AppleScript + shell + Shortcuts.app | Управление Mac            |

---

## 🛣️ Дорожная карта

См. [docs/ROADMAP.md](docs/ROADMAP.md). Кратко:

- **v0.1** — Push-to-talk диалог: голос → текст → LLM → ответ голосом
- **v0.2** — Wake word "Джарвис" + базовые скиллы (открыть приложение, поиск)
- **v0.3** — Function calling, расширенные скиллы (сообщения, календарь, музыка)
- **v1.0** — Tray app, hotkeys, ElevenLabs голос, conversation memory
- **v2.0** — Visual GUI, локальный LLM (Llama via Ollama), кастомные сценарии

---

## 📜 Лицензия

MIT — для личного использования.

## 👤 Автор

Nurislam Abdimalikov, Кыргызстан
