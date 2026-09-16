"""Синтез речи: ElevenLabs напрямую по REST, с откатом на CLI `sag`.

Прямой REST-вызов выбран основным: он не делает лишний запрос за списком голосов
(именно на нём CLI `sag` падал по таймауту) и даёт нам контроль над таймаутами и повторами.
"""
from __future__ import annotations

import shutil
import subprocess
import time
from pathlib import Path

import requests

from . import config

API = "https://api.elevenlabs.io/v1"
TIMEOUT = 60
RETRIES = 2

# человекочитаемое имя → voice_id (премиум-голоса ElevenLabs)
VOICE_IDS = {
    "roger": "CwhRBWXzGAHq8TQ4Fs17",
    "sarah": "EXAVITQu4vr4xnSDxMaL",
    "laura": "FGY2WhTYpPnrIDTdsKH5",
    "charlie": "IKne3meq5aSn9XLyUdCD",
    "george": "JBFqnCBsd6RMkjVDRZzb",
    "callum": "N2lVS1w4EtoT3dr4eOWO",
    "river": "SAz9YHcvj6GT2YYXdXww",
    "harry": "SOYHLrjzK2X1ezoPC6cr",
    "liam": "TX3LPaxmHKxFdv7VOQHJ",
    "alice": "Xb7hH8MSUJpSbSDYk0k2",
    "matilda": "XrExE9yKIg1WjnnlVkGX",
    "will": "bIHbv24MWmeRgasZH58o",
    "jessica": "cgSgspJ2msm6clMCkdW9",
    "eric": "cjVigY5qzO86Huf0OWal",
}
DEFAULT_VOICE = "cjVigY5qzO86Huf0OWal"  # Eric


class TTSError(RuntimeError):
    pass


def available() -> bool:
    return bool(config.ELEVENLABS_API_KEY or shutil.which("sag"))


def resolve_voice(voice: str | None) -> str:
    """Имя голоса или готовый voice_id → voice_id."""
    v = (voice or config.TTS_VOICE or "").strip()
    if not v:
        return DEFAULT_VOICE
    if v in VOICE_IDS:  # уже id
        return v
    return VOICE_IDS.get(v.lower(), DEFAULT_VOICE)


def _rest(text: str, voice_id: str, out: Path) -> Path:
    """POST /v1/text-to-speech/{voice_id} с повторами."""
    url = f"{API}/text-to-speech/{voice_id}"
    payload = {"text": text, "model_id": config.TTS_MODEL}
    headers = {"xi-api-key": config.ELEVENLABS_API_KEY, "Content-Type": "application/json"}
    last: Exception | None = None
    for attempt in range(1, RETRIES + 1):
        try:
            r = requests.post(url, json=payload, headers=headers,
                              params={"output_format": "mp3_44100_128"}, timeout=TIMEOUT)
            if r.status_code >= 300:
                raise TTSError(f"ElevenLabs {r.status_code}: {r.text[:200]}")
            out.write_bytes(r.content)
            return out
        except Exception as e:  # noqa: BLE001
            last = e
            if attempt < RETRIES:
                time.sleep(1.5 * attempt)
    raise TTSError(f"REST-синтез не удался: {str(last)[:200]}")


def _sag(text: str, voice: str | None, out: Path) -> Path:
    """Резервный путь — CLI sag."""
    exe = shutil.which("sag")
    if not exe:
        raise TTSError("sag не найден")
    cmd = [exe, "speak", "--output", str(out), "--no-play",
           "--model-id", config.TTS_MODEL, "-v", voice or config.TTS_VOICE, text]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0 or not out.exists():
        raise TTSError(f"sag упал: {(proc.stderr or proc.stdout).strip()[:200]}")
    return out


def shorten_for_voice(text: str, limit: int) -> str:
    """Оставляем целые предложения: длинную озвучку слушать неудобно."""
    if len(text) <= limit:
        return text
    cut = text[:limit]
    for sep in (". ", "! ", "? ", "… "):
        pos = cut.rfind(sep)
        if pos > limit * 0.5:
            return cut[:pos + 1].strip()
    return cut.rsplit(" ", 1)[0].strip() + "…"

def synthesize(text: str, voice: str | None = None,
               out: str | Path | None = None, as_voice: bool = False) -> Path:
    """Озвучивает текст. as_voice=True → OGG/Opus для голосового сообщения Telegram."""
    text = (text or "").strip()
    if not text:
        raise TTSError("пустой текст")
    text = shorten_for_voice(text, config.TTS_MAX_CHARS)

    out = Path(out) if out else config.TMP_DIR / ("reply.ogg" if as_voice else "reply.mp3")
    mp3 = out.with_suffix(".mp3")

    errors = []
    if config.ELEVENLABS_API_KEY:
        try:
            _rest(text, resolve_voice(voice), mp3)
        except TTSError as e:
            errors.append(str(e))
    if not mp3.exists() or mp3.stat().st_size < 1000:
        try:
            _sag(text, voice, mp3)
        except TTSError as e:
            errors.append(str(e))
            raise TTSError("; ".join(errors)[:300]) from None

    return to_opus(mp3, out) if as_voice else mp3


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
