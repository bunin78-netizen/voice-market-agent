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
               out: str | Path | None = None, as_voice: bool = False) -> Path:
    """Озвучивает текст, возвращает путь к mp3 (или к OGG/Opus, если as_voice=True).

    Telegram для голосовых сообщений ждёт OGG/Opus, поэтому при as_voice
    результат конвертируется через ffmpeg.
    """
    if not available():
        raise TTSError("TTS недоступен: нет ELEVENLABS_API_KEY или CLI sag")
    text = (text or "").strip()
    if not text:
        raise TTSError("пустой текст")
    if len(text) > 900:
        text = text[:900].rsplit(" ", 1)[0] + "…"

    out = Path(out) if out else config.TMP_DIR / ("reply.ogg" if as_voice else "reply.mp3")
    mp3 = out.with_suffix(".mp3")
    cmd = ["sag", "speak", "--output", str(mp3), "--no-play",
           "--model-id", config.TTS_MODEL,
           "-v", voice or config.TTS_VOICE, text]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0 or not mp3.exists():
        raise TTSError(f"sag упал: {(proc.stderr or proc.stdout).strip()[:300]}")

    if not as_voice:
        return mp3
    return to_opus(mp3, out)


def to_opus(src: str | Path, dst: str | Path | None = None) -> Path:
    """MP3 → OGG/Opus для голосовых сообщений Telegram."""
    exe = shutil.which("ffmpeg")
    if not exe:
        raise TTSError("ffmpeg не найден — не могу собрать голосовое сообщение")
    src = Path(src)
    dst = Path(dst) if dst else src.with_suffix(".ogg")
    proc = subprocess.run(
        [exe, "-y", "-loglevel", "error", "-i", str(src),
         "-c:a", "libopus", "-b:a", "48k", "-ar", "48000", "-ac", "1", str(dst)],
        capture_output=True, text=True)
    if proc.returncode != 0 or not dst.exists():
        raise TTSError(f"ffmpeg не собрал opus: {proc.stderr.strip()[:300]}")
    return dst
