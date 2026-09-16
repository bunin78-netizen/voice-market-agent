"""Конфигурация проекта: читает .env проекта и общий .secrets.env воркспейса."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
WORKSPACE_SECRETS = Path.home() / ".openclaw" / "workspace" / ".secrets.env"

load_dotenv(ROOT / ".env")
if WORKSPACE_SECRETS.exists():
    # не перезаписываем уже заданные значения
    load_dotenv(WORKSPACE_SECRETS, override=False)


def env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


TELEGRAM_BOT_TOKEN = env("TELEGRAM_BOT_TOKEN")
ASSEMBLYAI_API_KEY = env("ASSEMBLYAI_API_KEY")
DEEPSEEK_API_KEY = env("DEEPSEEK_API_KEY")
OPENROUTER_API_KEY = env("OPENROUTER_API_KEY")
ELEVENLABS_API_KEY = env("ELEVENLABS_API_KEY")

LLM_MODEL = env("LLM_MODEL", "deepseek-chat")
TTS_VOICE = env("TTS_VOICE", "Eric")
TTS_ENABLED = env("TTS_ENABLED", "1") not in ("0", "false", "no")
STT_MODE = env("STT_MODE", "assemblyai")
DEFAULT_INTERVAL = env("DEFAULT_INTERVAL", "1h")

TMP_DIR = ROOT / "tmp"
TMP_DIR.mkdir(exist_ok=True)

SUPPORTED_INTERVALS = ("15m", "1h", "4h", "1d")
