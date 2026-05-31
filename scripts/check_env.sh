#!/usr/bin/env bash
# ============================================================
# scripts/check_env.sh — Jarvis environment diagnostics.
# Colored ✅ / ❌ / ⚠️  report covering Python, .env, system
# tools and the virtualenv. Exit 0 if no hard failures, else 1.
# ============================================================
set -u

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

# --- Colors (disabled when stdout is not a TTY) ---
if [ -t 1 ]; then
    GREEN="$(printf '\033[32m')"
    RED="$(printf '\033[31m')"
    YELLOW="$(printf '\033[33m')"
    BOLD="$(printf '\033[1m')"
    RESET="$(printf '\033[0m')"
else
    GREEN="" ; RED="" ; YELLOW="" ; BOLD="" ; RESET=""
fi

issues=0
warnings=0

ok()   { echo "${GREEN}✅ $1${RESET}"; }
fail() { echo "${RED}❌ $1${RESET}"; issues=$((issues + 1)); }
warn() { echo "${YELLOW}⚠️  $1${RESET}"; warnings=$((warnings + 1)); }

# Required keys in .env (at least one LLM key must be filled).
REQUIRED_KEYS=(AIHUBMIX_API_KEY MISTRAL_API_KEY GOOGLE_API_KEY)

# --- 1. Python version >= 3.11 ---
check_python() {
    local py
    py="$(command -v python3.11 || command -v python3 || true)"
    if [ -z "$py" ]; then
        fail "Python not found (need >= 3.11)"
        return
    fi

    local ver
    ver="$("$py" -c 'import sys; print("%d.%d" % sys.version_info[:2])' 2>/dev/null)"
    local major="${ver%%.*}"
    local minor="${ver##*.}"

    if [ "$major" -gt 3 ] || { [ "$major" -eq 3 ] && [ "$minor" -ge 11 ]; }; then
        ok "Python ${ver} (>= 3.11)"
    else
        fail "Python ${ver} is too old (need >= 3.11)"
    fi
}

# --- 2. .env present ---
check_env_file() {
    if [ -f ".env" ]; then
        ok ".env found"
    else
        fail ".env not found — run scripts/setup.sh"
    fi
}

# --- 3. .env permissions (macOS: stat -f "%Lp") ---
check_env_perms() {
    [ -f ".env" ] || return
    local perms
    perms="$(stat -f "%Lp" .env 2>/dev/null || stat -c "%a" .env 2>/dev/null)"
    if [ "$perms" = "600" ]; then
        ok ".env permissions: 600"
    else
        warn ".env permissions are ${perms}, expected 600 (run: chmod 600 .env)"
    fi
}

# --- 4. Required keys present and non-empty in .env ---
check_env_keys() {
    [ -f ".env" ] || return
    local found=0
    for key in "${REQUIRED_KEYS[@]}"; do
        local val
        val="$(grep -E "^${key}=" .env 2>/dev/null | head -n1 | cut -d= -f2- | tr -d '[:space:]')"
        if [ -n "$val" ]; then
            ok "${key} is set"
            found=$((found + 1))
        else
            warn "${key} is empty"
        fi
    done
    if [ "$found" -eq 0 ]; then
        fail "No LLM key set — fill at least one of: ${REQUIRED_KEYS[*]}"
    fi
}

# --- 5. portaudio installed ---
check_portaudio() {
    if command -v brew >/dev/null 2>&1 && brew list portaudio >/dev/null 2>&1; then
        ok "portaudio installed"
    elif [ -f "/opt/homebrew/lib/libportaudio.dylib" ] || [ -f "/usr/local/lib/libportaudio.dylib" ]; then
        ok "portaudio installed"
    else
        warn "portaudio not found (run: brew install portaudio)"
    fi
}

# --- 6. ffmpeg installed ---
check_ffmpeg() {
    if command -v ffmpeg >/dev/null 2>&1; then
        ok "ffmpeg installed"
    else
        warn "ffmpeg not found (run: brew install ffmpeg)"
    fi
}

# --- 7. .venv exists ---
check_venv() {
    if [ -d ".venv" ] && [ -x ".venv/bin/python" ]; then
        ok ".venv exists"
    else
        fail ".venv not found — run scripts/setup.sh or make setup"
    fi
}

# --- Run ---
echo "${BOLD}🔍 Jarvis environment check${RESET} (repo: ${REPO_ROOT})"
echo ""

check_python
check_env_file
check_env_perms
check_env_keys
check_portaudio
check_ffmpeg
check_venv

echo ""

# --- Summary ---
if [ "$issues" -eq 0 ]; then
    if [ "$warnings" -eq 0 ]; then
        echo "${GREEN}✅ Environment OK${RESET}"
    else
        echo "${YELLOW}✅ Environment usable (${warnings} warning(s))${RESET}"
    fi
    exit 0
else
    echo "${RED}❌ ${issues} issue(s), ${warnings} warning(s) found${RESET}"
    exit 1
fi
