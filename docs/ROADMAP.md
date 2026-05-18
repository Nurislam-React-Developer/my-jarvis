# 🛣️ Дорожная карта Jarvis

Версионирование по фазам. Каждая фаза = рабочая версия, можно использовать.

---

## Phase 0 — Foundation (текущая фаза)

**Цель:** заложить структуру проекта, документацию, скелет кода.

- [x] Создать структуру папок
- [x] README.md
- [x] ARCHITECTURE.md
- [x] ROADMAP.md (этот файл)
- [x] SKILLS.md
- [x] SETUP.md
- [x] requirements.txt
- [x] config.yaml + .env.example
- [x] .gitignore
- [x] Скелет Python модулей (заглушки с правильными интерфейсами)
- [x] scripts/setup.sh

**Артефакт:** проект клонируется и `setup.sh` отрабатывает без ошибок.

---

## Phase 1 — MVP v0.1: Voice Loop (push-to-talk)

**Цель:** базовый цикл "нажал → сказал → услышал ответ".

- [ ] `audio/recorder.py` — запись с микрофона по hotkey (например, пробел)
- [ ] `stt/whisper_stt.py` — faster-whisper транскрипция
- [ ] `brain/claude.py` — простой чат с Claude (без tools пока)
- [ ] `tts/say_tts.py` — озвучка через macOS `say`
- [ ] `core/assistant.py` — orchestrator склеивающий всё
- [ ] `main.py` — CLI запуск
- [ ] `config.py` — загрузка конфига
- [ ] Логирование через loguru

**Артефакт:** запустил `python -m jarvis`, нажал пробел, сказал "Привет, как дела?",
получил голосом ответ.

**Время:** 2-3 часа.

---

## Phase 2 — MVP v0.2: Wake Word + базовые скиллы

**Цель:** активация голосом + первые реальные команды.

- [ ] Получить Picovoice access key, создать кастомную "Джарвис" модель на их сайте
- [ ] `audio/wake_word.py` — Porcupine интеграция
- [ ] `audio/vad.py` — silero-vad для определения конца речи
- [ ] `core/state.py` — история диалога (последние 20 сообщений)
- [ ] `skills/base.py` — базовый класс Skill
- [ ] `skills/registry.py` — регистрация и описание для LLM
- [ ] Первые скиллы:
  - [ ] `skills/info.py` — `get_time`, `get_date`
  - [ ] `skills/apps.py` — `open_app(name)`, `close_app(name)`
  - [ ] `skills/browser.py` — `web_search(query)`, `open_url(url)`
- [ ] Function calling в `brain/claude.py`

**Артефакт:** "Джарвис, открой Spotify" → открывает.

**Время:** 1 день.

---

## Phase 3 — MVP v1.0: Полный набор скиллов

**Цель:** Jarvis действительно полезен в быту.

- [ ] `skills/system.py` — громкость, яркость, lock, sleep
- [ ] `skills/music.py` — Spotify управление через AppleScript
- [ ] `skills/messages.py` — отправка в Telegram (Telegram Desktop URL scheme) и iMessage
- [ ] `skills/calendar.py` — чтение событий из Calendar.app, создание
- [ ] `skills/weather.py` — Open-Meteo API (без ключа)
- [ ] `skills/notes.py` — добавление заметок в Notes.app
- [ ] `skills/clipboard.py` — "запомни это", "скопируй в буфер"
- [ ] `skills/files.py` — открыть файл/папку, поиск по Spotlight
- [ ] Лучший системный промпт (Jarvis persona)
- [ ] Conversation context truncation (token budget)

**Артефакт:** Jarvis выполняет 15+ типов команд естественным языком.

**Время:** 2-3 дня.

---

## Phase 4 — Polish: Tony Stark Mode

**Цель:** чтобы это было приятно использовать каждый день.

- [ ] `tts/elevenlabs_tts.py` — премиум голос
- [ ] Звуки активации (`assets/wake.wav`, `assets/done.wav`)
- [ ] Tray icon (rumps) — иконка в menu bar
- [ ] Hotkey активации (Cmd+Shift+J) как альтернатива wake word
- [ ] Streaming TTS (озвучивать пока LLM ещё генерит)
- [ ] Прерывание ("Стоп, Джарвис")
- [ ] Notification Center интеграция
- [ ] Auto-start при логине (LaunchAgent)

**Артефакт:** Jarvis всегда в трее, реагирует на "Джарвис" из любой точки macOS.

**Время:** 1 неделя по вечерам.

---

## Phase 5 — Advanced

**Цель:** уникальные фичи, аналогов которым нет.

- [ ] Локальный LLM через Ollama (Llama 3.1 8B / Qwen2.5)
- [ ] RAG над твоими файлами (заметки, Drive)
- [ ] Long-term memory (SQLite + embeddings)
- [ ] Скрипты-сценарии: "Утренний режим" = погода + календарь + плейлист
- [ ] Webhook интеграции (Home Assistant, IFTTT)
- [ ] Vision: скриншот → "что на экране?"
- [ ] Whisper streaming (real-time транскрипция)

**Время:** по желанию, недели.

---

## Phase 6 — UI (опционально)

- [ ] Tauri/Electron оверлей в стиле Iron Man HUD
- [ ] Визуализация speech (waveform)
- [ ] Карточки результатов

---

## Метрики успеха по фазам

| Версия | Что должно работать                                         | Кому показать      |
| ------ | ----------------------------------------------------------- | ------------------ |
| v0.1   | Голосовой чат: говоришь — отвечает                          | Себе               |
| v0.2   | "Джарвис, открой YouTube"                                   | Себе               |
| v1.0   | 15+ команд, естественный язык, контекст                     | Друзьям            |
| v1.5   | Tony Stark mode, ElevenLabs, всегда в трее                  | Записать видео     |
| v2.0   | Локальный LLM, RAG, long-term memory                        | На GitHub публично |
