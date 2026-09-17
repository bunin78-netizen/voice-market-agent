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
# anchor — к какому событию привязывать реплику:
#   intro | q1 | a1 | q2 | a2 | pre_q3 | q3 | a3 | end
CUES: list[dict] = [
    {"anchor": "intro", "text": "Рыночную сводку обычно смотрят глазами: терминал, график, индикаторы.",
     "en": "Market updates usually mean staring at a terminal, a chart, a few indicators."},
    {"anchor": "intro", "text": "Агенту достаточно голоса: отправляю голосовое сообщение в Telegram — "
                                 "дальше он делает всё сам.",
     "en": "This agent needs only your voice: I send a voice message to Telegram and it does the rest."},
    {"anchor": "q1", "text": "Спрашиваю: что с биткоином сегодня?",
     "en": "I ask: what is Bitcoin doing today?"},
    {"anchor": "a1", "text": "Ответ голосом, цифры текстом — и график, построенный в момент запроса.",
     "en": "A spoken answer, the numbers in writing, and a chart built on the spot."},
    {"anchor": "q2", "text": "Теперь про Solana: как дела в сети?",
     "en": "Now Solana: how is the network doing?"},
    {"anchor": "a2", "text": "Агент сам обратился к блокчейну через публичный RPC: слот, эпоха, "
                             "скорость сети — всё из первых рук.",
     "en": "The agent queries the blockchain itself over a public RPC: slot, epoch and "
           "network throughput, straight from the source."},
    {"anchor": "pre_q3", "text": "Под капотом — AssemblyAI для распознавания речи, языковая модель "
                                 "с вызовами инструментов и Telegram как интерфейс.",
     "en": "Under the hood: AssemblyAI for speech recognition, an LLM with tool calling, "
           "and Telegram as the interface."},
    {"anchor": "q3", "text": "И последний вопрос — сколько SOL на кошельке.",
     "en": "And the last question: how much SOL is in the wallet."},
    {"anchor": "a3", "text": "Баланс прочитан прямо из блокчейна — без ключей и посредников.",
     "en": "The balance is read straight from the blockchain, with no keys and no middlemen."},
    {"anchor": "end", "text": "Код открыт, ссылка в описании.",
     "en": "The code is open source — link in the description."},
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
        plan.append({"file": dest.name, "start": 0.0, "duration": round(dur, 2),
                     "text": cue["text"], "en": cue.get("en", ""),
                     "anchor": cue.get("anchor", "")})
        print(f"  {cue.get('anchor',''):8} {dur:5.1f}c  {cue['text'][:58]}…")

    (OUT_DIR / "plan.json").write_text(
        json.dumps({"voice": args.voice, "model": MODEL, "cues": plan},
                   ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nвсего реплик: {len(plan)}, длительность речи {total:.1f}c")
    print(f"план: {OUT_DIR / 'plan.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
