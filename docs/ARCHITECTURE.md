# 🏗️ Архитектура Jarvis

## Принципы

1. **Модульность** — каждый компонент изолирован за интерфейсом, легко заменять (например, Whisper → Vosk).
2. **Async-first** — основной цикл на `asyncio`, чтобы не блокировать запись микрофона на TTS.
3. **Privacy by default** — STT локально; в облако уходит **только** текст пользователя в LLM.
4. **Расширяемость через skills** — каждая команда (открыть приложение, погода) — отдельный класс с декларативным описанием для LLM (function calling).
5. **Конфигурация без перекомпиляции** — все настройки в `config/config.yaml` + `.env`.

---

## Высокоуровневая схема

```
┌─────────────┐
│   Микрофон  │
└──────┬──────┘
       │ PCM audio
       ▼
┌─────────────────┐         ┌───────────────────┐
│  WakeWordEngine │◄────────│  Porcupine model  │
│  (Porcupine)    │         │  "jarvis_ru.ppn"  │
└──────┬──────────┘         └───────────────────┘
       │ wake detected
       ▼
┌─────────────────┐
│  Recorder + VAD │  ← пишет до тишины (silero-vad)
└──────┬──────────┘
       │ wav buffer
       ▼
┌─────────────────┐
│   STT Engine    │  ← faster-whisper (small/medium)
│   (Whisper)     │
└──────┬──────────┘
       │ text "Поставь Spotify"
       ▼
┌─────────────────┐         ┌───────────────────┐
│   Brain (LLM)   │◄────────│  SkillRegistry    │
│   Claude/OpenAI │────────►│  (tool schemas)   │
└──────┬──────────┘         └─────────┬─────────┘
       │ tool_use call               │ exec
       ▼                             ▼
┌─────────────────┐         ┌───────────────────┐
│  Skill Executor │────────►│  AppleScript /    │
│                 │         │  shell / API      │
└──────┬──────────┘         └───────────────────┘
       │ result
       ▼
┌─────────────────┐
│   TTS Engine    │  ← say / ElevenLabs
└──────┬──────────┘
       │ audio
       ▼
┌─────────────┐
│   Колонки   │
└─────────────┘
```

---

## Модули

### `core/` — Оркестратор

| Файл           | Роль                                                              |
| -------------- | ----------------------------------------------------------------- |
| `assistant.py` | Главный цикл: wake → record → STT → brain → skills → TTS          |
| `state.py`     | История диалога, текущая сессия, контекст разговора               |
| `logger.py`    | Структурированное логирование (loguru)                            |
| `events.py`    | Шина событий между модулями (опц.)                                |

### `audio/` — Работа со звуком

| Файл           | Роль                                                              |
| -------------- | ----------------------------------------------------------------- |
| `recorder.py`  | `sounddevice` запись, кольцевой буфер                             |
| `wake_word.py` | Обёртка над Picovoice Porcupine                                   |
| `vad.py`       | Voice Activity Detection (silero-vad) — режет тишину              |

### `stt/` — Распознавание речи

| Файл              | Роль                                          |
| ----------------- | --------------------------------------------- |
| `base.py`         | Интерфейс `BaseSTT.transcribe(wav) -> text`   |
| `whisper_stt.py`  | Реализация через `faster-whisper`             |

### `tts/` — Озвучка

| Файл               | Роль                                                  |
| ------------------ | ----------------------------------------------------- |
| `base.py`          | Интерфейс `BaseTTS.speak(text)`                       |
| `say_tts.py`       | macOS встроенный `say` (бесплатно, мгновенно)         |
| `elevenlabs_tts.py`| ElevenLabs API (премиум голос)                        |

### `brain/` — LLM

| Файл           | Роль                                                              |
| -------------- | ----------------------------------------------------------------- |
| `base.py`      | Интерфейс `BaseLLM.chat(messages, tools) -> response`             |
| `claude.py`    | Anthropic Claude SDK, поддержка `tool_use`                        |
| `openai_llm.py`| OpenAI SDK, поддержка `function_call` / tools                     |
| `prompts.py`   | Системный промпт Джарвиса, persona                                |

### `skills/` — Команды

| Файл           | Роль                                                              |
| -------------- | ----------------------------------------------------------------- |
| `base.py`      | `Skill` — базовый класс с `name`, `description`, `parameters`, `execute()` |
| `registry.py`  | Регистр всех скиллов, генерация `tools` JSON для LLM              |
| `apps.py`      | `OpenApp`, `CloseApp`, `SwitchApp`                                |
| `browser.py`   | `WebSearch`, `OpenURL`                                            |
| `system.py`    | `SetVolume`, `SetBrightness`, `Lock`, `Sleep`                     |
| `messages.py`  | `SendMessage` (Telegram/iMessage)                                 |
| `calendar.py`  | `GetEvents`, `CreateEvent`                                        |
| `music.py`     | `PlayMusic`, `PauseMusic`, `NextTrack`                            |
| `weather.py`   | `GetWeather`                                                      |
| `info.py`      | `GetTime`, `GetDate`                                              |

---

## Поток данных (пример)

Пользователь: *"Джарвис, поставь музыку на Spotify"*

1. **Wake word** — Porcupine ловит "Джарвис" → trigger
2. **Recorder** — пишет следующие 5 сек или до тишины (VAD)
3. **STT** — faster-whisper → `"Поставь музыку на Spotify"`
4. **Brain** — Claude получает:
   ```json
   {
     "messages": [{"role": "user", "content": "Поставь музыку на Spotify"}],
     "tools": [{"name": "play_music", ...}, {"name": "open_app", ...}]
   }
   ```
   Возвращает: `tool_use(name="play_music", input={"app": "spotify"})`
5. **Skill executor** — `MusicSkill.execute(app="spotify")` → AppleScript:
   ```applescript
   tell application "Spotify" to play
   ```
6. **Brain** — Claude получает результат, генерит текст: *"Включаю музыку, сэр"*
7. **TTS** — `say "Включаю музыку, сэр"` → колонки

---

## Async модель

```python
# Псевдокод главного цикла
async def main_loop():
    async with AudioStream() as stream:
        while True:
            await wake_word.wait_for_trigger(stream)
            audio = await recorder.record_until_silence(stream)
            text = await stt.transcribe(audio)
            response = await brain.chat(text, history)
            if response.tool_calls:
                results = await asyncio.gather(*[
                    skills.execute(call) for call in response.tool_calls
                ])
                response = await brain.chat_with_results(results)
            await tts.speak(response.text)
            history.append(text, response)
```

---

## Конфигурация

`config/config.yaml`:
```yaml
language: ru                    # ru | en
hotword: jarvis                 # путь к .ppn модели
stt:
  engine: whisper
  model: small                  # tiny | base | small | medium | large
  device: auto                  # auto | cpu | mps
tts:
  engine: say                   # say | elevenlabs
  voice: Yuri                   # для say
  speed: 1.0
brain:
  engine: claude                # claude | openai
  model: claude-sonnet-4-5
  max_history: 20
  temperature: 0.7
audio:
  sample_rate: 16000
  vad_threshold: 0.5
  silence_duration: 1.5         # сек
log_level: INFO
```

`.env`:
```
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
PICOVOICE_ACCESS_KEY=...
ELEVENLABS_API_KEY=...
```

---

## Зависимости (Python)

См. `requirements.txt`. Основные:
- `faster-whisper` — STT
- `sounddevice` + `numpy` — звук
- `pvporcupine` — wake word
- `silero-vad` — VAD
- `anthropic` / `openai` — LLM
- `pyobjc-core` + `pyobjc-framework-Cocoa` — macOS интеграция
- `loguru` — логи
- `pyyaml` + `python-dotenv` — конфиг
- `pytest` — тесты

---

## Расширение

Добавить новый скилл — три шага:
1. Создать `src/jarvis/skills/my_skill.py` наследуя `Skill`.
2. Реализовать `execute(**params)` и описать `parameters` JSON Schema.
3. Зарегистрировать в `src/jarvis/skills/registry.py` или включить через `config/skills.yaml`.

См. [SKILLS.md](SKILLS.md) для примеров.
