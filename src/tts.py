"""Синтез речи. Основной путь — ElevenLabs через CLI `sag`."""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from . import config


class TTSError(RuntimeError):
    pass


def available() -> bool:
    return bool(config.ELEVENLABS_API_KEY) and shutil.which("sag") is not None


def synthesize(text: str, voice: str | None = None,
               out: str | Path | None = None) -> Path:
    """Озвучивает текст, возвращает путь к mp3. Ответ агента может быть длинным — обрезаем."""
    if not available():
        raise TTSError("TTS недоступен: нет ELEVENLABS_API_KEY или CLI sag")
    text = (text or "").strip()
    if not text:
        raise TTSError("пустой текст")
    if len(text) > 900:
        text = text[:900].rsplit(" ", 1)[0] + "…"

    out = Path(out) if out else config.TMP_DIR / "reply.mp3"
    cmd = ["sag", "speak", "--output", str(out), "--no-play",
           "-v", voice or config.TTS_VOICE, text]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0 or not out.exists():
        raise TTSError(f"sag упал: {(proc.stderr or proc.stdout).strip()[:300]}")
    return out
