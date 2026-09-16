#!/usr/bin/env python3
"""Собирает финальное демо: запись экрана + закадровая озвучка по таймингам.

Запуск:
    python3 scripts/assemble_demo.py --video ~/Videos/silent.mp4
    python3 scripts/assemble_demo.py --video rec.mp4 --out demo.mp4 --subs docs/demo-subtitles-en.srt

Запись экрана при этом должна быть БЕЗ голоса — озвучку добавляет скрипт.
Звук самой записи (голос бота из динамиков/монитора) сохраняется и микшируется.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_NARRATION = ROOT / "tmp" / "narration"


def has_audio(path: Path) -> bool:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries",
         "stream=index", "-of", "csv=p=0", str(path)],
        capture_output=True, text=True).stdout.strip()
    return bool(out)


def duration(path: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nw=1:nk=1", str(path)], capture_output=True, text=True).stdout
    try:
        return float(out.strip())
    except ValueError:
        return 0.0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", required=True, help="запись экрана (без озвучки)")
    ap.add_argument("--narration", default=str(DEFAULT_NARRATION), help="каталог с репликами и plan.json")
    ap.add_argument("--out", default="", help="итоговый файл (по умолчанию рядом с видео, с суффиксом -final)")
    ap.add_argument("--subs", default="", help="SRT для вшивания в кадр (необязательно)")
    ap.add_argument("--voice-gain", type=float, default=1.0, help="громкость озвучки")
    ap.add_argument("--screen-gain", type=float, default=0.85, help="громкость звука записи")
    args = ap.parse_args()

    video = Path(args.video).expanduser()
    if not video.exists():
        print(f"❌ нет файла {video}")
        return 1

    narr_dir = Path(args.narration)
    plan_file = narr_dir / "plan.json"
    if not plan_file.exists():
        print(f"❌ нет {plan_file} — сначала сгенерируй озвучку: "
              f"python3 scripts/make_narration.py --voice Eric")
        return 1
    plan = json.loads(plan_file.read_text(encoding="utf-8"))
    cues = [c for c in plan.get("cues", []) if (narr_dir / c["file"]).exists()]
    if not cues:
        print("❌ в плане нет доступных файлов реплик")
        return 1

    out = Path(args.out).expanduser() if args.out else video.with_name(video.stem + "-final.mp4")
    vid_dur = duration(video)
    speech_end = max(c["start"] + c["duration"] for c in cues)
    print(f"видео: {vid_dur:.1f}c | речь заканчивается на {speech_end:.1f}c")
    if vid_dur and speech_end > vid_dur:
        print(f"⚠️  речь длиннее видео на {speech_end - vid_dur:.1f}c — "
              f"последние реплики обрежутся (или подрежь их в plan.json)")

    if not shutil.which("ffmpeg"):
        print("❌ ffmpeg не найден")
        return 1

    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(video)]
    for cue in cues:
        cmd += ["-i", str(narr_dir / cue["file"])]

    filters, mix_inputs = [], []
    screen_has_audio = has_audio(video)
    if screen_has_audio:
        filters.append(f"[0:a]volume={args.screen_gain}[scr]")
        mix_inputs.append("[scr]")
    for idx, cue in enumerate(cues, start=1):
        delay = int(cue["start"] * 1000)
        filters.append(f"[{idx}:a]adelay={delay}|{delay},volume={args.voice_gain}[n{idx}]")
        mix_inputs.append(f"[n{idx}]")
    filters.append("".join(mix_inputs) + f"amix=inputs={len(mix_inputs)}:normalize=0:dropout_transition=0[aout]")

    if args.subs:
        subs = Path(args.subs)
        if not subs.exists():
            print(f"❌ нет файла субтитров {subs}")
            return 1
        # экранирование пути для фильтра subtitles
        esc = str(subs).replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")
        filters.append(f"[0:v]subtitles='{esc}'[vout]")
        cmd += ["-filter_complex", ";".join(filters),
                "-map", "[vout]", "-map", "[aout]",
                "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p"]
    else:
        cmd += ["-filter_complex", ";".join(filters),
                "-map", "0:v", "-map", "[aout]", "-c:v", "copy"]

    cmd += ["-c:a", "aac", "-b:a", "192k", "-shortest", str(out)]

    print("…сборка")
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        print("❌ ffmpeg упал:\n", proc.stderr.strip()[:800])
        return 1

    print(f"✅ готово: {out}")
    print(f"   длительность {duration(out):.1f}c, размер {out.stat().st_size // 1024 // 1024} МБ")
    print(f"   проверь: ffplay -autoexit \"{out}\"")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
