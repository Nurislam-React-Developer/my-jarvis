#!/usr/bin/env bash
# ============================================================
# Jarvis — установка системных зависимостей на macOS.
# Идемпотентно: можно запускать повторно.
# ============================================================
set -euo pipefail

echo "🚀 Jarvis setup starting..."

# --- 1. Homebrew ---
if ! command -v brew >/dev/null 2>&1; then
    echo "📦 Homebrew не найден, устанавливаю..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
else
    echo "✅ Homebrew уже установлен"
fi

# --- 2. Системные пакеты ---
echo "📦 Устанавливаю brew пакеты..."
brew install python@3.11 portaudio ffmpeg || true

# --- 3. Python venv ---
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR"

if [ ! -d ".venv" ]; then
    echo "🐍 Создаю venv (.venv)..."
    python3.11 -m venv .venv
else
    echo "✅ venv уже существует"
fi

# shellcheck disable=SC1091
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# --- 4. .env ---
if [ ! -f ".env" ]; then
    cp .env.example .env
    echo "📝 Создал .env из шаблона — заполни API ключи"
else
    echo "✅ .env уже существует"
fi
chmod 600 .env
echo "🔒 Права на .env установлены: 600"

# --- 5. Папки для логов и моделей ---
mkdir -p logs assets/sounds assets/recordings

echo ""
echo "✨ Готово!"
echo "   Активируй venv:  source .venv/bin/activate"
echo "   Запуск:          python -m jarvis"
echo "💡 Установи pre-commit хуки: pip install pre-commit && pre-commit install"
