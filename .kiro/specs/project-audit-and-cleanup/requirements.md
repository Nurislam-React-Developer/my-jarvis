# Requirements Document

## Introduction

Цель спека — провести полный аудит репозитория Jarvis и привести его к состоянию, в
котором каждый файл, модуль и ассет либо реально используется в рантайме / в тестах /
в опциональной конфигурации, либо удалён. Аудит покрывает три плоскости:

1. **Код** — найти модули и методы, которые объявлены, но никогда не вызываются и
   не имплементированы (заглушки `raise NotImplementedError("Phase 2")`,
   мёртвые поля конфига и т.п.) и удалить их.
2. **Ассеты** — найти каталоги и файлы, оставшиеся от прошлой архитектуры
   (например, `assets/wake_words/` под Picovoice .ppn-модели, которые более не
   используются, поскольку wake-word работает на openwakeword) и убрать их.
3. **Документация** — устранить расхождения между `docs/ARCHITECTURE.md`,
   `docs/SKILLS.md`, `docs/ROADMAP.md` и фактической реализацией (Porcupine →
   openwakeword, silero-vad → faster-whisper VAD + energy RMS, Anthropic Claude
   → единственный openai_llm.py через OpenAI-совместимый клиент к
   AIHubMix/Mistral/Gemini, реальный список скиллов и т.д.).

Каждое удаление обязано сопровождаться явным доказательством неиспользования
(grep по импортам, отсутствие вызовов, отсутствие файла на диске для конфиг-полей,
которые ссылаются на путь) и быть помещено в отдельный коммит, чтобы было легко
сделать revert. Итог — артефакт `docs/AUDIT.md` с таблицей «модуль/ассет → статус →
действие → доказательство».

### Что НЕ входит в этот спек

Спек **не пересекается** со смежным спеком
`.kiro/specs/security-and-cleanup-hardening/`, который уже закрывает следующие темы
и они **не дублируются** здесь:

- защита `.env` (chmod 600, gitleaks, pre-commit, secret-scan CI),
- актуализация `.env.example` под фактический набор ключей
  (AIHUBMIX/MISTRAL/GOOGLE/ELEVENLABS),
- удаление мёртвых ссылок на ANTHROPIC_API_KEY / PICOVOICE_ACCESS_KEY из
  пользовательских инструкций по ключам,
- закрепление точных версий зависимостей (lock-файл) и хранение крупных бинарных
  ассетов через Git LFS — это явные out-of-scope в обоих спеках,
- гигиена логирования (запрет тел LLM-сообщений в INFO).

Любые предложения, относящиеся к этим темам, должны быть отправлены в тот спек или
оставлены в Out-of-Scope (см. Requirement 10).

## Glossary

- **Jarvis** — основной голосовой ассистент, корневой Python-пакет `jarvis` в
  `src/jarvis/`.
- **Live_Code** — модуль, функция или метод, у которого есть хотя бы один входящий
  вызов или импорт из `src/jarvis/**`, `tests/**`, `scripts/**` или из
  конфигурационного файла, который реально читается рантаймом
  (`config/config.yaml`, `config/skills.yaml`, `.env.example`).
- **Dead_Code** — модуль, функция или метод, который удовлетворяет всем трём
  условиям одновременно: (а) не имеет ни одного входящего вызова/импорта в
  `src/jarvis/**`, `tests/**`, `scripts/**`, (б) не имеет имплементации (тело —
  `raise NotImplementedError` или эквивалентная заглушка) либо описывает
  неактивное поле конфига, на которое нет читателя в коде, (в) не упомянут как
  публичный API ни в одном документе из `docs/**`, который описывает текущую
  версию.
- **Vestigial_Asset** — файл, каталог или ссылка на путь, оставшийся от прошлой
  архитектуры (например, каталог под `.ppn`-модели Picovoice при том, что
  wake-word уже работает на openwakeword) и не имеющий ни одного читателя в
  `Live_Code`.
- **One_Shot_Script** — скрипт в `scripts/`, разработанный под однократный запуск
  для генерации артефакта (например, `_build_master_ref.py` собирает
  `actor_master.wav` из demucs-выгрузки) и не вызываемый ни из CI, ни из
  пользовательских инструкций (`README.md`, `docs/SETUP.md`).
- **Optional_Component** — компонент, который активируется только при определённой
  конфигурации (например, F5-TTS активируется при `tts.engine: f5tts`,
  ElevenLabs — при `tts.engine: elevenlabs`, ассеты `jarvis-clean/` — только
  как референс для F5-TTS) и **не должен удаляться**, но обязан быть явно
  помечен как опциональный в документации.
- **Documentation_Drift** — расхождение между утверждением в документе из `docs/**`
  и фактической реализацией в `src/jarvis/**` или `requirements.txt`.
- **Audit_Report** — артефакт `docs/AUDIT.md` с таблицей «модуль/ассет → статус
  (Live/Dead/Vestigial/Optional) → действие (keep/remove/document) →
  доказательство». Создаётся в рамках этого спека и обновляется при каждом
  крупном рефакторинге.
- **Безопасное удаление** — удаление, которое сопровождается (а) прохождением
  существующего pytest-набора, (б) успешным импортом `jarvis.main` без сетевых
  ключей в окружении, (в) отдельным git-коммитом с описанием доказательства
  неиспользования.

## Requirements

### Requirement 1: Удаление однозначно мёртвого кода

**User Story:** Как разработчик, я хочу, чтобы из репозитория исчезли модули и
методы, которые никогда не вызываются и состоят только из `raise
NotImplementedError`, чтобы новые контрибьюторы не путали их с актуальным API и
не тратили время на их «доделывание».

#### Acceptance Criteria

1. THE Audit_Process SHALL проверять каждый кандидат на удаление по трём
   критериям из определения Dead_Code и фиксировать результат проверки
   (вердикт + ссылки на grep-результаты) в `docs/AUDIT.md`.
2. WHEN кандидатом является модуль `src/jarvis/audio/vad.py`, THE Audit_Process
   SHALL подтвердить отсутствие импорта `jarvis.audio.vad` и подстроки
   `from .vad` во всех файлах `src/jarvis/**` и `tests/**` и затем удалить файл
   целиком.
3. WHEN кандидатом является метод `Recorder.record_until_silence` в
   `src/jarvis/audio/recorder.py`, THE Audit_Process SHALL подтвердить
   отсутствие вызовов `record_until_silence` во всех файлах `src/jarvis/**` и
   `tests/**` и затем удалить определение метода вместе с его комментарием
   «Phase 2».
4. WHEN кандидатом является класс `SoundsConfig` и поле `Config.sounds` в
   `src/jarvis/config.py`, THE Audit_Process SHALL подтвердить, что (а) ни в
   одном файле `src/jarvis/**` нет обращений `cfg.sounds`, `config.sounds`,
   `self.config.sounds`, и (б) на диске отсутствуют файлы, на которые ссылаются
   значения по умолчанию (`assets/sounds/wake.wav`, `assets/sounds/done.wav`,
   `assets/sounds/error.wav`), и затем удалить класс `SoundsConfig`, поле
   `Config.sounds` и блок `sounds:` из `config/config.yaml`.
5. WHILE удаление выполняется, THE Audit_Process SHALL фиксировать каждое
   удаление в отдельном git-коммите с заголовком в формате
   `chore(audit): remove <artifact>` и телом, содержащим вывод grep-проверок
   из критериев 2–4.
6. IF после удаления любого артефакта pytest-набор `pytest -q` или
   `python -c "import jarvis.main"` падает, THEN THE Audit_Process SHALL
   откатить соответствующий коммит и зафиксировать причину в `docs/AUDIT.md`
   как «keep — runtime regression», после чего artefact переходит в категорию
   Live_Code.

### Requirement 2: Удаление вестиджиал-ассетов

**User Story:** Как разработчик, я хочу, чтобы каталоги ассетов содержали только
реально используемые файлы, чтобы не возникало вопросов вида «зачем нужен
`assets/wake_words/`, если wake-word работает на openwakeword».

#### Acceptance Criteria

1. WHEN кандидатом является каталог `assets/wake_words/`, THE Audit_Process
   SHALL подтвердить, что (а) `config/config.yaml` содержит
   `wake_word.engine: openwakeword` и не содержит ссылок на путь
   `assets/wake_words`, (б) ни в одном файле `src/jarvis/**` нет ссылок на
   `assets/wake_words` или на расширение `.ppn`, (в) каталог содержит только
   `.gitkeep` и не содержит ни одного файла моделей, и затем удалить каталог
   целиком вместе с записями `assets/wake_words/*.ppn` и
   `!assets/wake_words/.gitkeep` в `.gitignore`.
2. WHEN каталог `assets/sounds/voices/jarvis-og/` рассматривается как кандидат,
   THE Audit_Process SHALL подтвердить, что он используется как fallback в
   `VoiceReactions._find_files` (из `src/jarvis/audio/reactions.py`), и
   пометить его как Live_Code в `docs/AUDIT.md` без удаления.
3. WHEN каталог `assets/sounds/voices/jarvis-remaster/` рассматривается как
   кандидат, THE Audit_Process SHALL подтвердить, что он указан в
   `config/config.yaml` → `reactions.pack_dir` и читается
   `VoiceReactions.__init__`, и пометить его как Live_Code в `docs/AUDIT.md`
   без удаления.
4. WHERE каталог `assets/sounds/voices/jarvis-clean/` используется только как
   референс для F5-TTS (`tts.engine: f5tts`), THE Audit_Process SHALL
   классифицировать его как Optional_Component, описать это в `docs/AUDIT.md`
   и не удалять без явного подтверждения пользователя в обсуждении этого
   спека.
5. IF в `assets/` обнаружен любой пустой подкаталог, который содержит только
   `.gitkeep` и при этом ни в одном Live_Code нет ссылки на этот каталог,
   THEN THE Audit_Process SHALL предложить удаление и оформить решение
   отдельным пунктом в `docs/AUDIT.md`.

### Requirement 3: Решение по одноразовым скриптам

**User Story:** Как разработчик, я хочу, чтобы скрипты, использованные один раз
для генерации артефактов, были либо удалены, либо явно помечены как «one-shot»,
чтобы я мог отличить их от скриптов, которые пользователь должен запускать
регулярно.

#### Acceptance Criteria

1. WHEN кандидатом является `scripts/_build_master_ref.py`, THE Audit_Process
   SHALL подтвердить, что (а) скрипт не упомянут в `README.md`, `docs/SETUP.md`,
   `.github/workflows/*.yml`, `pyproject.toml` (`[project.scripts]`), и
   (б) импортируемые им пакеты (`librosa`, `soundfile`) не оба присутствуют в
   `requirements.txt` (`librosa` — нет в `requirements.txt`).
2. WHEN кандидатом является `scripts/_transcribe_master.py`, THE Audit_Process
   SHALL применить ту же проверку, что в критерии 1 (отсутствие в `README.md`,
   `docs/SETUP.md`, CI и `pyproject.toml`; `librosa` отсутствует в
   `requirements.txt`).
3. THE Audit_Process SHALL для каждого One_Shot_Script предложить два варианта в
   `docs/AUDIT.md`: (a) удалить файл, (b) сохранить с добавлением заголовочного
   комментария вида «One-shot: запускался однократно для генерации
   `<имя_артефакта>`. Не требуется в обычном workflow. Зависит от librosa,
   которая не указана в requirements.txt». Решение между (a) и (b) принимается
   на ревью этого спека пользователем и фиксируется в `docs/AUDIT.md`.
4. WHERE сохраняется хотя бы один One_Shot_Script, THE Audit_Process SHALL
   обеспечить, что префикс имени файла начинается с `_`, чтобы визуально
   отличать его от регулярных скриптов (`setup.sh`, `check_env.sh`).

### Requirement 4: Привести docs/ARCHITECTURE.md в соответствие с реальной архитектурой

**User Story:** Как новый контрибьютор, я хочу, чтобы `docs/ARCHITECTURE.md`
описывал ту систему, которая реально работает, чтобы я не тратил время на
изучение Porcupine, silero-vad и Anthropic Claude, которых в проекте нет.

#### Acceptance Criteria

1. THE Documentation_Sync SHALL заменить в `docs/ARCHITECTURE.md` все упоминания
   Picovoice Porcupine и файла `jarvis_ru.ppn` на openwakeword с pretrained
   моделью `hey_jarvis` (имя из `config/config.yaml` →
   `wake_word.keyword`).
2. THE Documentation_Sync SHALL заменить в `docs/ARCHITECTURE.md` все упоминания
   silero-vad на фактическую реализацию VAD: встроенный
   `faster-whisper.vad_filter=True` для распознавания и energy-based RMS-фильтр
   в `src/jarvis/audio/wake_word.py` для определения конца фразы.
3. THE Documentation_Sync SHALL удалить из `docs/ARCHITECTURE.md` упоминание
   `brain/claude.py` и Anthropic SDK и описать единственный фактический клиент
   `brain/openai_llm.py`, который используется для всех движков (`aihubmix`,
   `mistral`, `gemini`) через OpenAI-совместимый интерфейс.
4. THE Documentation_Sync SHALL заменить пример `.env` в `docs/ARCHITECTURE.md`
   на актуальный набор ключей из `.env.example` (`AIHUBMIX_API_KEY`,
   `MISTRAL_API_KEY`, `GOOGLE_API_KEY`, `ELEVENLABS_API_KEY`,
   `ELEVENLABS_VOICE_ID`) и удалить устаревшие
   `ANTHROPIC_API_KEY`/`OPENAI_API_KEY`/`PICOVOICE_ACCESS_KEY`.
5. THE Documentation_Sync SHALL обновить таблицу скиллов в `docs/ARCHITECTURE.md`
   так, чтобы перечисление файлов в `src/jarvis/skills/` совпадало с фактом:
   `apps.py`, `browser.py`, `clipboard.py`, `files.py`, `info.py`, `music.py`,
   `notes.py`, `system.py`, `vision.py`, `base.py`, `registry.py`, `_macos.py`.
6. THE Documentation_Sync SHALL обновить блок «Зависимости» в
   `docs/ARCHITECTURE.md` так, чтобы перечисление совпадало с фактическим
   `requirements.txt` (openwakeword, onnxruntime, scipy, scikit-learn,
   faster-whisper, sounddevice, numpy, openai, elevenlabs, pyobjc-core,
   pyobjc-framework-Cocoa, loguru, pyyaml, python-dotenv, pydantic, httpx,
   pynput, pytest, pytest-asyncio) и не упоминать `pvporcupine`, `silero-vad`,
   `anthropic`.
7. THE Documentation_Sync SHALL обновить пример `config/config.yaml` в
   `docs/ARCHITECTURE.md` так, чтобы он совпадал по ключам верхнего уровня с
   фактическим `config/config.yaml` (включая `assistant_name`, `wake_word`,
   `push_to_talk`, `tts.f5tts`, `reactions`).
8. IF после правки `docs/ARCHITECTURE.md` в файле осталось хотя бы одно
   утверждение, не подтверждаемое исходным кодом или конфигом, THEN THE
   Documentation_Sync SHALL зафиксировать его в `docs/AUDIT.md` в разделе
   «Documentation_Drift — open» с указанием файла и строки.

### Requirement 5: Привести docs/SKILLS.md в соответствие с реальной реализацией скиллов

**User Story:** Как разработчик скилла, я хочу, чтобы `docs/SKILLS.md`
показывал реальный формат tool-схем (OpenAI function-calling) и реальный список
зарегистрированных скиллов, чтобы написанный по гайду скилл сразу подключался
без переписывания.

#### Acceptance Criteria

1. THE Documentation_Sync SHALL заменить в `docs/SKILLS.md` пример
   `to_tool_schema()` с Anthropic-подобным форматом (`{"name", "description",
   "input_schema"}`) на фактический формат OpenAI function-calling
   (`{"type": "function", "function": {"name", "description", "parameters"}}`),
   соответствующий реализации `Skill.to_tool_schema()` в
   `src/jarvis/skills/base.py`.
2. THE Documentation_Sync SHALL обновить каталог скиллов в `docs/SKILLS.md` так,
   чтобы каждый перечисленный там скилл был либо классом из
   `ALL_SKILL_CLASSES` в `src/jarvis/skills/registry.py`, либо явно помечен
   как «planned, not implemented yet».
3. WHEN скилл присутствует в `config/skills.yaml` со значением `enabled: false`
   и без соответствующего класса в `ALL_SKILL_CLASSES` (например,
   `send_telegram`, `send_imessage`, `read_unread_mail`, `sleep_mac`,
   `create_event`), THE Documentation_Sync SHALL пометить его в
   `docs/SKILLS.md` как «planned» и указать, что включение `enabled: true`
   приведёт к ошибке регистрации.
4. THE Documentation_Sync SHALL обновить раздел «Как добавить свой скилл» в
   `docs/SKILLS.md` так, чтобы шаги ссылались на фактическую константу
   `ALL_SKILL_CLASSES` (а не вымышленный `DEFAULT_SKILLS`) в
   `src/jarvis/skills/registry.py`.
5. THE Documentation_Sync SHALL добавить в раздел «Тестирование скилла без LLM»
   ссылку на существующий smoke-тест
   `tests/test_smoke.py::test_skill_registry_not_empty` как образец проверки
   регистрации.

### Requirement 6: Привести docs/ROADMAP.md в соответствие с фактическим прогрессом

**User Story:** Как читатель, я хочу, чтобы `docs/ROADMAP.md` отражал реальный
прогресс проекта, чтобы по чек-листу было видно, что уже сделано, а что нет.

#### Acceptance Criteria

1. THE Documentation_Sync SHALL пометить в `docs/ROADMAP.md` все пункты Phase 1
   как выполненные (`[x]`) при условии, что фактическая реализация присутствует
   в `src/jarvis/**` (push-to-talk через `Recorder.record_push_to_talk`,
   `WhisperSTT`, `OpenAIBrain`, `SayTTS`, `Assistant.run`, `cli`,
   `load_config`, `setup_logging`).
2. THE Documentation_Sync SHALL пометить в `docs/ROADMAP.md` все пункты Phase 2
   как выполненные (`[x]`) при условии, что фактическая реализация присутствует
   (`WakeWordListener` на openwakeword, energy VAD,
   `ConversationState.add/to_llm_messages`, `Skill`, `SkillRegistry`,
   `GetTimeSkill`, `GetDateSkill`, `OpenAppSkill`, `CloseAppSkill`,
   `WebSearchSkill`, `OpenURLSkill`, function calling в
   `Assistant._chat_with_tools`).
3. THE Documentation_Sync SHALL заменить упоминания Picovoice access key и
   «.ppn модели» в Phase 2 на actual openwakeword setup (без регистрации, без
   API-ключа).
4. THE Documentation_Sync SHALL удалить или переписать из Phase 4 пункт «Звуки
   активации (`assets/wake.wav`, `assets/done.wav`)», поскольку соответствующий
   `SoundsConfig` удаляется в рамках Requirement 1, а звуковые реакции
   реализованы через `VoiceReactions` и каталог
   `assets/sounds/voices/jarvis-remaster/`.
5. WHERE раздел Phase 3 содержит скиллы, которые уже реализованы (`set_volume`,
   `lock_screen`, `take_screenshot`, `play_music`, `pause_music`, `next_track`,
   `prev_track`, `current_song`, `create_note`, `copy_to_clipboard`,
   `read_clipboard`, `open_path`, `spotlight_search`, `analyze_screen`), THE
   Documentation_Sync SHALL пометить их как `[x]`, а нереализованные
   (`send_telegram`, `send_imessage`, `get_today_events`, `create_event`,
   `get_weather` в части реальной интеграции) оставить как `[ ]`.

### Requirement 7: Создать и сопровождать docs/AUDIT.md

**User Story:** Как мейнтейнер, я хочу иметь единый артефакт-таблицу, в которой
для каждого модуля и ассета зафиксировано «используется/не используется/
опционально» и доказательство, чтобы при следующем рефакторинге не повторять ту
же работу с нуля.

#### Acceptance Criteria

1. THE Audit_Process SHALL создать файл `docs/AUDIT.md` со структурой:
   (а) Introduction (цель, дата проведения аудита, ссылка на этот спек),
   (б) Methodology (какие grep-паттерны и проверки использовались),
   (в) Inventory — таблица «путь → категория (Live/Dead/Vestigial/
   One_Shot/Optional) → действие (keep/remove/document) → доказательство
   (ссылка на grep-результат, на коммит, на конфиг)»,
   (г) Open Documentation_Drift — список незакрытых расхождений (если есть).
2. THE Audit_Process SHALL включить в Inventory как минимум следующие
   артефакты: `src/jarvis/audio/vad.py`, `Recorder.record_until_silence`,
   `SoundsConfig`/`Config.sounds`, `assets/wake_words/`,
   `assets/sounds/voices/jarvis-clean/`, `assets/sounds/voices/jarvis-og/`,
   `assets/sounds/voices/jarvis-remaster/`, `scripts/_build_master_ref.py`,
   `scripts/_transcribe_master.py`, `src/jarvis/tts/f5_tts.py`,
   `src/jarvis/tts/elevenlabs_tts.py`, `src/jarvis/tts/_text_utils.py`.
3. WHEN артефакт классифицирован как Optional_Component, THE Audit_Process SHALL
   указать в столбце «доказательство» ссылку на ключ конфига
   (`config/config.yaml` → `tts.engine`) и условие активации
   (`tts.engine == "f5tts"` для F5-TTS, `tts.engine == "elevenlabs"` для
   ElevenLabs).
4. THE Audit_Process SHALL связать `docs/AUDIT.md` с README.md через короткое
   упоминание в разделе «Структура проекта» с ссылкой
   `[docs/AUDIT.md](docs/AUDIT.md) — карта используемого/неиспользуемого кода`.

### Requirement 8: Тесты, гарантирующие отсутствие регрессии после удалений

**User Story:** Как мейнтейнер, я хочу, чтобы каждый коммит-удаление прогонял
автоматические проверки, гарантирующие, что после удаления пакет всё ещё
импортируется и тесты проходят, чтобы случайно не сломать рантайм.

#### Acceptance Criteria

1. WHEN выполняется коммит-удаление в рамках этого спека, THE Audit_Process
   SHALL прогонять локально команду `pytest -q` и фиксировать в теле коммита
   полный exit code и краткое summary (количество прошедших тестов).
2. WHEN выполняется коммит-удаление, THE Audit_Process SHALL прогонять
   `python -c "import jarvis.main"` в окружении без сетевых ключей (при
   удалённых из окружения `AIHUBMIX_API_KEY`, `MISTRAL_API_KEY`,
   `GOOGLE_API_KEY`, `ELEVENLABS_API_KEY`) и убеждаться, что импорт проходит
   без ошибок.
3. THE Audit_Process SHALL добавить в `tests/test_config.py` (или новый
   `tests/test_config_drift.py`) тест, который убеждается, что у модели
   `Config` отсутствует поле `sounds` (если Requirement 1 выполнен) и что
   `config/config.yaml` не содержит ключа верхнего уровня `sounds:`.
4. THE Audit_Process SHALL добавить в `tests/test_smoke.py` (или новый
   `tests/test_audit_invariants.py`) тест, который убеждается, что модуль
   `jarvis.audio.vad` отсутствует (`pytest.importorskip` либо `with
   pytest.raises(ModuleNotFoundError)`), если Requirement 1.2 выполнен.
5. IF любой из тестов в критериях 1–4 падает, THEN THE Audit_Process SHALL
   прервать удаление и зафиксировать причину в `docs/AUDIT.md`.

### Requirement 9: Гранулярность коммитов и обратимость

**User Story:** Как мейнтейнер, я хочу, чтобы каждое удаление было самостоятельным
коммитом с понятным сообщением и доказательством в теле, чтобы при необходимости
можно было сделать `git revert <hash>` и не зацепить остальные изменения.

#### Acceptance Criteria

1. THE Audit_Process SHALL оформлять каждое удаление модуля или каталога
   отдельным git-коммитом, не объединяя несколько удалений в один коммит.
2. THE Audit_Process SHALL использовать формат заголовка коммита
   `chore(audit): remove <artifact>` для удалений и
   `docs(audit): sync <document>` для правок документации.
3. THE Audit_Process SHALL включать в тело коммита блок «Доказательство»
   (grep-команда + её вывод или ссылка на строку в `docs/AUDIT.md`) и блок
   «Verification» (`pytest -q` summary, `python -c "import jarvis.main"` exit
   code).
4. WHERE правка документации затрагивает несколько разделов одного файла, THE
   Audit_Process SHALL объединять их в один коммит при условии, что все они
   относятся к одному документу (например, `docs(audit): sync ARCHITECTURE.md`
   может покрывать разом замены Porcupine, silero-vad и Anthropic).
5. IF после серии коммитов потребовалось откатить удаление, THEN THE
   Audit_Process SHALL делать `git revert <hash>` без перезаписи истории и
   обновлять статус артефакта в `docs/AUDIT.md` с «removed» на «keep —
   reverted».

### Requirement 10: Out of Scope

**User Story:** Как ревьюер этого спека, я хочу видеть явный список того, что в
этой итерации НЕ делается, чтобы не возвращаться к этим вопросам в обсуждении и
чтобы они не размывали фокус.

#### Acceptance Criteria

1. THE Audit_Process SHALL зафиксировать в Introduction `docs/AUDIT.md`
   следующие out-of-scope темы и не выполнять по ним никаких действий в рамках
   этого спека:
   - закрепление точных версий зависимостей (lock-файл, `pip-tools`,
     `uv lock`),
   - перевод крупных бинарных ассетов в Git LFS,
   - переписывание git-истории (`git filter-repo`),
   - усиление гигиены логирования (запрет тел LLM в INFO),
   - добавление новых TTS/STT/LLM движков,
   - добавление новых скиллов,
   - изменение поведения существующих скиллов,
   - покрытие property-based тестами (PBT) — не входит в спек, поскольку
     удаления и правки документации не имеют интересных свойств для PBT.
2. WHERE кандидат на изменение пересекается с уже закрытым спеком
   `.kiro/specs/security-and-cleanup-hardening/` (например, актуализация
   `.env.example` под фактический набор ключей, gitleaks, pre-commit), THE
   Audit_Process SHALL не дублировать соответствующий пункт и сослаться на
   тот спек в `docs/AUDIT.md`.
3. IF в ходе аудита обнаружен новый класс проблем, не покрытый ни этим спеком,
   ни `security-and-cleanup-hardening`, THEN THE Audit_Process SHALL
   зафиксировать его в разделе «Open Documentation_Drift» или «Future Work»
   `docs/AUDIT.md` без выполнения действий и без расширения скоупа этого
   спека.
