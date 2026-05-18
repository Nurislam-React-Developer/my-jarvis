# 🔌 Skills — Команды, которые умеет Jarvis

Skill = одна способность Jarvis (например, "открыть приложение", "узнать погоду").
Каждый skill описан как Python-класс и предоставляет JSON Schema для LLM function calling.

---

## Принцип работы

1. Все скиллы регистрируются в `SkillRegistry` при старте.
2. Registry генерирует список `tools` для LLM (формат Anthropic / OpenAI).
3. LLM сам решает какой скилл вызвать на основе пользовательского запроса.
4. `SkillExecutor` вызывает `skill.execute(**params)` и возвращает результат обратно в LLM.
5. LLM получает результат и формулирует ответ голосом.

---

## Базовый класс

```python
# src/jarvis/skills/base.py
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

@dataclass
class SkillResult:
    success: bool
    message: str
    data: dict[str, Any] = field(default_factory=dict)


class Skill(ABC):
    name: str                   # snake_case, например "open_app"
    description: str            # описание для LLM
    parameters: dict            # JSON Schema параметров
    enabled: bool = True
    requires_confirmation: bool = False

    @abstractmethod
    async def execute(self, **kwargs) -> SkillResult: ...

    def to_tool_schema(self) -> dict:
        """Формат для Anthropic tool / OpenAI function."""
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.parameters,
        }
```

---

## Пример скилла: открыть приложение

```python
# src/jarvis/skills/apps.py
import subprocess
from .base import Skill, SkillResult


class OpenAppSkill(Skill):
    name = "open_app"
    description = (
        "Открыть приложение на macOS по имени. "
        "Например: Spotify, Telegram, Chrome, VSCode, Notes."
    )
    parameters = {
        "type": "object",
        "properties": {
            "app_name": {
                "type": "string",
                "description": "Имя приложения как в Launchpad",
            }
        },
        "required": ["app_name"],
    }

    async def execute(self, app_name: str) -> SkillResult:
        try:
            subprocess.run(["open", "-a", app_name], check=True)
            return SkillResult(True, f"Открыл {app_name}")
        except subprocess.CalledProcessError as e:
            return SkillResult(False, f"Не нашёл приложение {app_name}: {e}")
```

---

## Каталог скиллов (план)

### `info` — Базовая информация
| Скилл           | Что делает                              |
| --------------- | --------------------------------------- |
| `get_time`      | Текущее время                           |
| `get_date`      | Сегодняшняя дата                        |
| `get_weather`   | Погода по городу (Open-Meteo API)       |

### `apps` — Управление приложениями
| Скилл           | Что делает                              |
| --------------- | --------------------------------------- |
| `open_app`      | Открыть приложение                      |
| `close_app`     | Закрыть приложение (`osascript quit`)   |
| `switch_app`    | Переключиться на приложение             |
| `list_running`  | Что сейчас запущено                     |

### `browser` — Браузер и веб
| Скилл              | Что делает                              |
| ------------------ | --------------------------------------- |
| `web_search`       | Поиск в Google в дефолтном браузере     |
| `open_url`         | Открыть URL                             |
| `youtube_search`   | Найти на YouTube                        |
| `wiki_search`      | Найти в Wikipedia                       |

### `system` — Управление macOS
| Скилл           | Что делает                              |
| --------------- | --------------------------------------- |
| `set_volume`    | Громкость 0-100                         |
| `set_brightness`| Яркость 0-100                           |
| `lock_screen`   | Заблокировать экран                     |
| `sleep`         | Усыпить Mac                             |
| `take_screenshot`| Скриншот в `~/Desktop`                 |

### `music` — Музыка
| Скилл           | Что делает                              |
| --------------- | --------------------------------------- |
| `play_music`    | Включить музыку (Spotify/Music.app)     |
| `pause_music`   | Пауза                                   |
| `next_track`    | Следующий трек                          |
| `prev_track`    | Предыдущий трек                         |
| `current_song`  | Что сейчас играет                       |

### `messages` — Сообщения
| Скилл               | Что делает                                  |
| ------------------- | ------------------------------------------- |
| `send_telegram`     | Отправить сообщение в Telegram (URL scheme) |
| `send_imessage`     | Отправить iMessage через AppleScript        |
| `read_unread_mail`  | Прочитать непрочитанные письма из Mail.app  |

### `calendar` — Календарь
| Скилл               | Что делает                              |
| ------------------- | --------------------------------------- |
| `get_today_events`  | События на сегодня                      |
| `get_tomorrow_events`| События на завтра                      |
| `create_event`      | Создать встречу                         |

### `notes` — Заметки и буфер
| Скилл           | Что делает                              |
| --------------- | --------------------------------------- |
| `create_note`   | Создать заметку в Notes.app             |
| `copy_to_clipboard` | Скопировать текст в буфер           |
| `read_clipboard`| Прочитать буфер                         |

### `files` — Файлы
| Скилл              | Что делает                              |
| ------------------ | --------------------------------------- |
| `open_path`        | Открыть файл/папку в Finder             |
| `spotlight_search` | Поиск через Spotlight (`mdfind`)        |

---

## Как добавить свой скилл — чеклист

1. **Создать файл** `src/jarvis/skills/my_skill.py`.
2. **Унаследоваться** от `Skill`, заполнить `name`, `description`, `parameters`.
3. **Реализовать** `async def execute(**kwargs) -> SkillResult`.
4. **Зарегистрировать** в `src/jarvis/skills/registry.py` (импорт + добавить в `DEFAULT_SKILLS`).
5. **Включить/выключить** в `config/skills.yaml`.
6. **Тест** `tests/skills/test_my_skill.py`.

---

## Конвенции

- `name` — `snake_case`, глагол + объект: `open_app`, `set_volume`, `get_weather`.
- `description` — на английском, чтобы LLM лучше распознавал tool. Параметры можно по-русски.
- Всегда возвращай `SkillResult` — никаких голых исключений наружу.
- Долгие операции (>1 сек) пиши через `asyncio` чтобы не блокировать main loop.
- Для AppleScript — выноси скрипты в `src/jarvis/skills/applescripts/*.applescript`.
- Опасные операции (удалить, отправить деньги) — выставляй `requires_confirmation = True`.

---

## Тестирование скилла без LLM

```python
# tests/skills/test_apps.py
import pytest
from jarvis.skills.apps import OpenAppSkill

@pytest.mark.asyncio
async def test_open_app():
    skill = OpenAppSkill()
    result = await skill.execute(app_name="Calculator")
    assert result.success
```
