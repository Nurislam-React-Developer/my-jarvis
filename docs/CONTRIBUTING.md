# 🤝 Contributing to Jarvis

Thanks for taking the time to contribute. This guide covers how to add a new
skill, how to run the tests, and the commit message convention.

---

## 🧰 Getting set up

```bash
make setup                  # create .venv and install dependencies
source .venv/bin/activate
make check                  # diagnose your environment (Python, .env, deps)
```

The project targets **Python 3.11+** on **macOS (Apple Silicon)**.

---

## ➕ Adding a new skill

A skill is a small async class that the LLM can call as a tool. Adding one is
three steps: write the class, register it, expose it in config.

### 1. Write the skill class

Create or extend a module under `src/jarvis/skills/`. Subclass `Skill` and
define the class attributes `name`, `description`, `parameters`, plus an async
`execute` method that returns a `SkillResult`.

```python
# src/jarvis/skills/example.py
from __future__ import annotations

from .base import Skill, SkillResult


class GreetUserSkill(Skill):
    name = "greet_user"
    description = (
        "Greet the user by name. Use when the user asks to be greeted "
        "or introduces themselves."
    )
    # JSON Schema describing the arguments the LLM must provide.
    parameters = {
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "The user's name."}
        },
        "required": ["name"],
    }

    async def execute(self, name: str) -> SkillResult:  # type: ignore[override]
        return SkillResult(True, f"Hello, {name}!", {"name": name})
```

### Skill file structure

Each skill class must define:

| Attribute | Type | Purpose |
| --- | --- | --- |
| `name` | `str` | Unique tool name the LLM calls (snake_case). Must match the key in `config/skills.yaml`. |
| `description` | `str` | When-to-use guidance for the LLM. Be explicit; it drives tool selection. |
| `parameters` | `dict` | JSON Schema (`type`/`properties`/`required`) for the arguments. Use `{"type": "object", "properties": {}, "required": []}` for no-arg skills. |
| `execute(self, **kwargs)` | `async` | The implementation. Must return `SkillResult(success, message, data)`. |
| `requires_confirmation` | `bool` | Optional. `True` for destructive actions; can also be set from `skills.yaml`. |

`SkillResult` fields: `success: bool`, `message: str` (spoken back to the user),
`data: dict` (optional structured payload).

### 2. Register the skill

Add your class to `ALL_SKILL_CLASSES` in
[`src/jarvis/skills/registry.py`](../src/jarvis/skills/registry.py):

```python
from .example import GreetUserSkill

ALL_SKILL_CLASSES: list[type[Skill]] = [
    # ...existing skills...
    GreetUserSkill,
]
```

### 3. Expose it in config

Add an entry under `skills:` in [`config/skills.yaml`](../config/skills.yaml):

```yaml
  greet_user:   { enabled: true }
```

Any extra keys (besides `enabled` and `requires_confirmation`) that match your
`__init__` parameters are passed to the constructor, so you can make skills
configurable from YAML.

### 4. Verify

```bash
make lint        # ruff check + format
make test        # run the suite
python -m jarvis # try it: "Jarvis, greet John"
```

---

## 🧪 Running the tests

```bash
make test            # or: pytest -q
pytest tests/test_skills.py -q          # a single file
pytest -k weather -q                    # by keyword
```

Add tests under `tests/` for new behavior. Async tests work out of the box
(`asyncio_mode = "auto"` is set in `pyproject.toml`).

---

## 🎨 Code style

- Formatting and linting via **ruff** (config in `pyproject.toml`).
- Run `make lint` before pushing; CI runs `ruff check` and `ruff format --check`.
- Keep skill `description` text in the language users will speak to Jarvis.

---

## 📝 Commit message convention

This project follows [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<optional scope>): <short summary>
```

Common types:

| Type | Use for |
| --- | --- |
| `feat` | A new feature or skill |
| `fix` | A bug fix |
| `docs` | Documentation only |
| `chore` | Tooling, config, maintenance |
| `refactor` | Code change that neither fixes a bug nor adds a feature |
| `test` | Adding or fixing tests |

Examples:

```
feat(skills): add greet_user skill
fix(tts): handle empty input in xtts cache key
docs: clarify wake-word threshold tuning
```

### Branch + PR workflow

1. Branch off `master`: `git checkout -b feat/my-skill`
2. Commit in small, focused steps.
3. Open a PR to `master`. CI must be green (lint + tests).
