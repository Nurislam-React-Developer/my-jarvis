"""Хелперы для интеграции с macOS: AppleScript, shell."""
from __future__ import annotations

import asyncio


async def run_applescript(script: str, timeout: float = 10.0) -> tuple[int, str, str]:
    """Запустить AppleScript. Возвращает (returncode, stdout, stderr)."""
    proc = await asyncio.create_subprocess_exec(
        "osascript", "-e", script,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        out, err = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        proc.kill()
        return 124, "", "timeout"
    return proc.returncode or 0, out.decode(errors="ignore").strip(), err.decode(errors="ignore").strip()


async def run_shell(*args: str, timeout: float = 10.0) -> tuple[int, str, str]:
    """Запустить shell-команду. Возвращает (returncode, stdout, stderr)."""
    proc = await asyncio.create_subprocess_exec(
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        out, err = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        proc.kill()
        return 124, "", "timeout"
    return proc.returncode or 0, out.decode(errors="ignore").strip(), err.decode(errors="ignore").strip()
