"""Конвертация аудио: голосовые Telegram приходят в OGG/Opus, STT хочет WAV 16 kHz mono."""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from .config import TMP_DIR


class AudioError(RuntimeError):
    pass


def _ffmpeg() -> str:
    exe = shutil.which("ffmpeg")
    if not exe:
        raise AudioError("ffmpeg не найден в PATH")
    return exe


def to_wav16k(src: str | Path, dst: str | Path | None = None) -> Path:
    """OGG/Opus/MP3 → WAV 16 kHz mono PCM. Возвращает путь к WAV."""
    src = Path(src)
    if not src.exists():
        raise AudioError(f"нет файла: {src}")
    dst = Path(dst) if dst else TMP_DIR / (src.stem + "_16k.wav")

    cmd = [
        _ffmpeg(), "-y", "-loglevel", "error",
        "-i", str(src),
        "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le",
        str(dst),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0 or not dst.exists():
        raise AudioError(f"ffmpeg упал: {proc.stderr.strip()[:400]}")
    return dst


def duration_seconds(path: str | Path) -> float:
    """Длительность файла в секундах (через ffprobe, 0.0 если не удалось)."""
    probe = shutil.which("ffprobe")
    if not probe:
        return 0.0
    proc = subprocess.run(
        [probe, "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True, text=True,
    )
    try:
        return float(proc.stdout.strip())
    except ValueError:
        return 0.0
