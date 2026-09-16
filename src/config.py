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
TTS_MODEL = env("TTS_MODEL", "eleven_flash_v2_5")
TTS_MAX_CHARS = int(env("TTS_MAX_CHARS", "450"))  # сколько символов озвучивать
STT_MODE = env("STT_MODE", "assemblyai")
STT_LANGUAGE = env("STT_LANGUAGE", "")        # пусто = авто-определение языка
STT_KEYTERMS = [w.strip() for w in env(
    "STT_KEYTERMS",
    "эфир,биткоин,солана,график,таймфрейм,дневной график,RSI,полосы Боллинджера,"
    "индекс страха и жадности,цена,объём").split(",") if w.strip()]
DEFAULT_INTERVAL = env("DEFAULT_INTERVAL", "1h")

TMP_DIR = ROOT / "tmp"
TMP_DIR.mkdir(exist_ok=True)

SUPPORTED_INTERVALS = ("15m", "1h", "4h", "1d")
