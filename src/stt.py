"""Распознавание речи.

Основной путь — AssemblyAI (upload → transcript → polling), как требует хакатон.
Запасной путь — локальный whisper CLI, чтобы пайплайн можно было отлаживать без ключей.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

import requests

from . import config

AAI_BASE = "https://api.assemblyai.com/v2"
AAI_STREAMING = "wss://streaming.assemblyai.com/v3/ws"


class STTError(RuntimeError):
    pass


@dataclass
class Transcript:
    text: str
    language: str | None
    duration: float | None
    provider: str


# ------------------------------------------------------------------ AssemblyAI
def _aai_headers() -> dict[str, str]:
    if not config.ASSEMBLYAI_API_KEY:
        raise STTError("ASSEMBLYAI_API_KEY не задан")
    return {"authorization": config.ASSEMBLYAI_API_KEY}


def upload(path: str | Path) -> str:
    """Заливает локальный файл в AssemblyAI, возвращает upload_url."""
    data = Path(path).read_bytes()
    r = requests.post(f"{AAI_BASE}/upload", headers=_aai_headers(), data=data, timeout=180)
    if r.status_code >= 300:
        raise STTError(f"upload {r.status_code}: {r.text[:300]}")
    return r.json()["upload_url"]


def transcribe_assemblyai(
    path: str | Path,
    language: str | None = None,
    poll_interval: float = 1.5,
    timeout: float = 180.0,
) -> Transcript:
    """Файловое распознавание. language=None → авто-детект языка."""
    audio_url = upload(path)
    payload: dict = {
        "audio_url": audio_url,
        # API v2 принимает список моделей в порядке приоритета (старое поле speech_model удалено)
        "speech_models": ["universal-3-5-pro", "universal-2"],
        "punctuate": True,
        "format_text": True,
    }
    if language:
        payload["language_code"] = language
    else:
        payload["language_detection"] = True

    r = requests.post(f"{AAI_BASE}/transcript", headers=_aai_headers(), json=payload, timeout=60)
    if r.status_code >= 300:
        raise STTError(f"transcript {r.status_code}: {r.text[:300]}")
    job = r.json()
    job_id = job["id"]

    deadline = time.time() + timeout
    while time.time() < deadline:
        s = requests.get(f"{AAI_BASE}/transcript/{job_id}", headers=_aai_headers(), timeout=60)
        s.raise_for_status()
        data = s.json()
        status = data.get("status")
        if status == "completed":
            return Transcript(
                text=(data.get("text") or "").strip(),
                language=data.get("language_code"),
                duration=(data.get("audio_duration") or None),
                provider="assemblyai",
            )
        if status == "error":
            raise STTError(f"AssemblyAI error: {data.get('error')}")
        time.sleep(poll_interval)

    raise STTError(f"таймаут распознавания ({timeout:.0f}s), job={job_id}")


# ------------------------------------------------------------------ whisper (dev)
def transcribe_whisper(path: str | Path, model: str = "base") -> Transcript:
    """Локальный whisper CLI — только для разработки и оффлайн-тестов."""
    exe = shutil.which("whisper")
    if not exe:
        raise STTError("whisper CLI не найден (используется только как dev-fallback)")
    out_dir = Path(config.TMP_DIR) / "whisper"
    out_dir.mkdir(parents=True, exist_ok=True)
    cmd = [exe, str(path), "--model", model, "--output_format", "json",
           "--output_dir", str(out_dir), "--language", "auto", "--fp16", "False"]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise STTError(f"whisper упал: {proc.stderr.strip()[:400]}")
    js = out_dir / (Path(path).stem + ".json")
    if not js.exists():
        raise STTError("whisper не создал json")
    data = json.loads(js.read_text(encoding="utf-8"))
    return Transcript(text=data.get("text", "").strip(),
                      language=data.get("language"), duration=None, provider="whisper")


# ------------------------------------------------------------------ фасад
def transcribe(path: str | Path, language: str | None = None) -> Transcript:
    if config.STT_MODE == "whisper":
        return transcribe_whisper(path)
    return transcribe_assemblyai(path, language=language)
