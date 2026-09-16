#!/usr/bin/env python3
"""Генерирует озвучку демо (русский текст) через ElevenLabs.

Каждая реплика — отдельный файл, чтобы потом расставить их по времени в видео.

Запуск:
    python3 scripts/make_narration.py                 # голос по умолчанию (Eric)
    python3 scripts/make_narration.py --voice George  # другой голос
    python3 scripts/make_narration.py --list          # список голосов
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src import config  # noqa: E402
from src.tts import VOICE_IDS  # noqa: E402

# Реплики закадрового голоса: (момент в видео, секунда, текст)
CUES: list[dict] = [
    {"at": "00:04", "text": "Рыночную сводку обычно смотрят глазами: терминал, график, индикаторы.",
     "en": "Market updates usually mean staring at a terminal, a chart, a few indicators."},
    {"at": "00:12", "text": "А если руки заняты — за рулём или в работе — эти десять минут просто теряются.",
     "en": "But when your hands are busy — driving or working — those ten minutes are simply lost."},
    {"at": "00:22", "text": "Я собрал агента, которому не нужен интерфейс. Только голос: отправляю "
                           "голосовое сообщение в Telegram — дальше он делает всё сам.",
     "en": "So I built an agent that needs no interface — just your voice. I send a voice "
           "message to Telegram and it does the rest."},
    {"at": "00:32", "text": "Смотрите.",
     "en": "Let me show you."},
    {"at": "00:45", "text": "Первое — распознавание. AssemblyAI превращает запись в текст, "
                           "устойчиво к терминам вроде RSI и Боллинджера.",
     "en": "First, speech recognition. AssemblyAI turns the recording into text, reliably "
           "handling terms like RSI and Bollinger Bands."},
    {"at": "00:54", "text": "Дальше модель сама решает, какие данные ей нужны: цена, RSI, "
                           "скользящая средняя, линии Боллинджера.",
     "en": "Then the model decides which data it needs: price, RSI, moving average, "
           "Bollinger Bands."},
    {"at": "01:06", "text": "Ответ приходит голосом — слушать можно, не глядя в экран. "
                           "И текстом, чтобы можно было перечитать.",
     "en": "The answer comes back as voice — listen without looking at the screen — "
           "and as text you can re-read."},
    {"at": "01:21", "text": "Теперь про график. Я не подсказываю, какой инструмент вызвать — "
                           "это решает сама модель.",
     "en": "Now a chart. I am not telling it which tool to call — the model decides."},
    {"at": "01:30", "text": "Свечи, SMA20, линии Боллинджера и панель RSI. "
                           "График построен прямо в момент запроса.",
     "en": "Candles, SMA20, Bollinger Bands and an RSI panel — built on demand."},
    {"at": "01:55", "text": "Под капотом — AssemblyAI для речи, языковая модель с вызовами "
                           "инструментов и Telegram как интерфейс.",
     "en": "Under the hood: AssemblyAI for speech, an LLM with tool calling, "
           "and Telegram as the interface."},
    {"at": "02:10", "text": "И ещё один инструмент — индекс страха и жадности рынка.",
     "en": "One more tool: the market Fear and Greed index."},
    {"at": "02:45", "text": "Код открыт, ссылка в описании. Спасибо.",
     "en": "The code is open source — link in the description. Thank you."},
]

OUT_DIR = ROOT / "tmp" / "narration"
MODEL = "eleven_multilingual_v2"  # лучшее качество для русского


def seconds(stamp: str) -> float:
    m, s = stamp.split(":")
    return int(m) * 60 + int(s)


def duration(path: Path) -> float:
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=nw=1:nk=1", str(path)], capture_output=True, text=True).stdout
        return float(out.strip())
    except Exception:  # noqa: BLE001
        return 0.0


def synth(text: str, voice_id: str, dest: Path) -> None:
    r = requests.post(f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}",
                      json={"text": text, "model_id": MODEL},
                      headers={"xi-api-key": config.ELEVENLABS_API_KEY},
                      params={"output_format": "mp3_44100_128"}, timeout=120)
    if r.status_code >= 300:
        raise RuntimeError(f"{r.status_code}: {r.text[:200]}")
    dest.write_bytes(r.content)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--voice", default="Eric", help="имя голоса или voice_id")
    ap.add_argument("--list", action="store_true", help="показать доступные голоса")
    args = ap.parse_args()

    if args.list:
        for name in sorted(VOICE_IDS):
            print(f"  {name}")
        return 0

    voice_id = VOICE_IDS.get(args.voice.lower(), args.voice if len(args.voice) > 15 else None)
    if not voice_id:
        print(f"❌ неизвестный голос «{args.voice}»; список: python3 scripts/make_narration.py --list")
        return 1
    if not config.ELEVENLABS_API_KEY:
        print("❌ ELEVENLABS_API_KEY не задан")
        return 1

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    plan = []
    total = 0.0
    print(f"голос: {args.voice} ({voice_id}), модель: {MODEL}\n")
    for i, cue in enumerate(CUES, 1):
        dest = OUT_DIR / f"{i:02d}.mp3"
        synth(cue["text"], voice_id, dest)
        dur = duration(dest)
        total += dur
        start = seconds(cue["at"])
        end = start + dur
        plan.append({"file": dest.name, "start": start, "duration": round(dur, 2),
                     "text": cue["text"], "en": cue.get("en", "")})
        print(f"  {cue['at']}  {dur:5.1f}c  →  {end//60:02.0f}:{end%60:04.1f}  {cue['text'][:52]}…")

    (OUT_DIR / "plan.json").write_text(
        json.dumps({"voice": args.voice, "model": MODEL, "cues": plan},
                   ensure_ascii=False, indent=2), encoding="utf-8")
    last = plan[-1]["start"] + plan[-1]["duration"]
    print(f"\nвсего реплик: {len(plan)}, длительность речи {total:.1f}c, "
          f"последняя заканчивается на {last//60:.0f}:{last%60:04.1f}")
    print(f"план: {OUT_DIR / 'plan.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
