# ⚙️ Setup — Полная установка Jarvis

Гайд для свежей машины macOS Apple Silicon (M1/M2/M3/M4).

---

## 0. Требования

- macOS 13+ (Ventura или новее)
- Apple Silicon (M-чип) — на Intel тоже работает, но Whisper будет медленнее
- ~5 ГБ свободного места (Whisper модели)
- Микрофон и колонки/наушники

---

## 1. Системные зависимости

### Homebrew (если ещё нет)

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

### Пакеты

```bash
brew install python@3.11 portaudio ffmpeg
```

- `python@3.11` — стабильная версия для всех зависимостей
- `portaudio` — нужен для `sounddevice` (запись с микрофона)
- `ffmpeg` — нужен Whisper-у для декодирования аудио

Или одной командой:

```bash
./scripts/setup.sh
```

---

## 2. Python окружение

```bash
cd ~/jarvis
python3.11 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

Первый запуск faster-whisper скачает модель `small` (~500 МБ) в `~/.cache/huggingface/`.

---

## 3. Разрешения macOS

Mac попросит разрешения когда Jarvis впервые попытается:

| Что               | Где разрешить                                                       |
| ----------------- | ------------------------------------------------------------------- |
| Микрофон          | System Settings → Privacy & Security → Microphone                   |
| Accessibility     | System Settings → Privacy & Security → Accessibility (для AppleScript) |
| Automation        | System Settings → Privacy & Security → Automation                   |
| Full Disk Access  | (опционально, для чтения почты/календаря)                           |

> Совет: добавь Terminal (или iTerm/VSCode откуда запускаешь) во все эти разделы заранее.

---

## 4. API ключи

```bash
cp .env.example .env
```

Открой `.env` и заполни:

### Anthropic Claude (рекомендую)
1. Регистрация: https://console.anthropic.com/
2. API Keys → Create Key → скопировать в `ANTHROPIC_API_KEY`
3. Положи $5 на баланс — хватит на месяц активного использования

### OpenAI (альтернатива)
1. https://platform.openai.com/api-keys
2. Скопировать в `OPENAI_API_KEY`

### Picovoice (для wake word, нужно с v0.2)
1. https://console.picovoice.ai/ — бесплатный personal account
2. AccessKey → `PICOVOICE_ACCESS_KEY`
3. Создать кастомную wake word "Джарвис":
   - Picovoice Console → Porcupine → Train Wake Word
   - Language: Russian
   - Phrase: "Джарвис"
   - Скачать `.ppn` файл → положить в `assets/wake_words/jarvis_ru.ppn`

### ElevenLabs (опционально, для премиум-голоса)
1. https://elevenlabs.io/
2. Profile → API Key → `ELEVENLABS_API_KEY`
3. Выбрать Voice ID понравившегося голоса → `ELEVENLABS_VOICE_ID`

---

## 5. Конфиг

`config/config.yaml` — основные настройки. Дефолты подобраны разумно, можно не трогать на старте.

Что менять:
- `language: ru` или `en`
- `tts.engine: say` (бесплатно) или `elevenlabs` (премиум)
- `stt.model: small` — баланс качества/скорости. На M3 `medium` тоже летает.
- `brain.engine: claude` или `openai`

---

## 6. Запуск

```bash
source .venv/bin/activate
python -m jarvis
```

В версии v0.1 — push-to-talk: нажми и держи пробел чтобы говорить.
В версии v0.2+ — скажи "Джарвис ..." и он отреагирует.

---

## 7. Траблшутинг

### `OSError: PortAudio library not found`
```bash
brew install portaudio
pip install --force-reinstall sounddevice
```

### `RuntimeError: cannot find ffmpeg`
```bash
brew install ffmpeg
```

### Whisper медленный
- Используй модель `small` или `tiny` вместо `medium/large`
- Проверь что `device: auto` в конфиге (на M-чипе использует MPS/Metal через CTranslate2)

### Микрофон не слышно
- System Settings → Privacy → Microphone → разрешить терминалу
- Проверь дефолтный input в System Settings → Sound

### `say: command not found`
Маловероятно на macOS, но: переустанови Command Line Tools `xcode-select --install`.

### AppleScript: `not authorized to send Apple events`
System Settings → Privacy & Security → Automation → разреши терминалу управлять нужным приложением.

---

## 8. Обновление

```bash
git pull
source .venv/bin/activate
pip install -r requirements.txt --upgrade
```

---

## 9. Удаление

```bash
rm -rf ~/jarvis ~/.cache/huggingface/hub/models--Systran--faster-whisper-*
```
