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
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_NARRATION = ROOT / "tmp" / "narration"


# ---------------------------------------------------------------- выравнивание по логу
LOG_TS = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}),(\d{3}) INFO .*EVENT (voice_in|reply_out)")


def parse_events(log_path: Path) -> list[tuple[str, float]]:
    """Возвращает [(тип, epoch_seconds)] из лога бота."""
    import datetime as _dt
    events = []
    for line in log_path.read_text(encoding="utf-8", errors="replace").splitlines():
        m = LOG_TS.match(line)
        if not m:
            continue
        dt = _dt.datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S")
        events.append((m.group(3), dt.timestamp() + int(m.group(2)) / 1000))
    return events


def start_marker(video: Path) -> float | None:
    for cand in (video.with_suffix(video.suffix + ".start"),
                 video.with_suffix(".start"),
                 video.with_name(video.stem + ".start")):
        if cand.exists():
            try:
                return float(cand.read_text().strip())
            except ValueError:
                return None
    return None


def align_cues(cues: list[dict], events: list[tuple[str, float]],
               zero: float, video_dur: float) -> list[dict]:
    """Расставляет реплики по фактическим событиям бота (а не по секундомеру)."""
    ins = [t - zero for kind, t in events if kind == "voice_in"]
    outs = [t - zero for kind, t in events if kind == "reply_out"]
    if not ins:
        return cues

    first_in = ins[0]
    intro = cues[:4]
    # вступление укладываем перед первым голосовым
    total_intro = sum(c["duration"] for c in intro) + 0.6 * (len(intro) - 1)
    start_intro = max(2.0, first_in - total_intro - 1.0)
    cursor = start_intro
    for c in intro:
        c["start"] = round(cursor, 2)
        cursor += c["duration"] + 0.6

    def after(idx_list, t, min_gap=0.6):
        return (idx_list[len(idx_list) - 1] if False else t)

    anchors: dict[int, float] = {}
    if len(cues) > 4 and ins:
        anchors[5] = first_in + 0.6
    if len(cues) > 5 and ins:
        anchors[6] = first_in + 4.5
    if len(cues) > 6 and outs:
        anchors[7] = outs[0] + 0.6
    if len(cues) > 7 and len(ins) > 1:
        anchors[8] = ins[1] + 0.6
    if len(cues) > 8 and len(outs) > 1:
        anchors[9] = outs[1] + 0.6
    if len(cues) > 9 and len(ins) > 2:
        anchors[10] = ins[2] + 0.6
    if len(cues) > 10 and len(outs) > 2:
        anchors[11] = outs[2] + 0.6
    if len(cues) > 11 and outs:
        anchors[12] = outs[-1] + 8.0
    if len(cues) > 12 and outs:
        anchors[13] = max(outs[-1] + 20.0, (video_dur or 0) - 4.0)

    prev_end = 0.0
    for i, cue in enumerate(cues, start=1):
        if i in anchors:
            cue["start"] = round(max(anchors[i], prev_end + 0.4), 2)
        prev_end = cue["start"] + cue["duration"]
    return cues


def fit_to_duration(cues: list[dict], video_dur: float, min_gap: float = 0.4,
                    tail: float = 0.5) -> list[dict]:
    """Если речь длиннее видео — пропорционально сжимаем паузы, чтобы всё уместилось."""
    if not video_dur or not cues:
        return cues
    last_end = max(c["start"] + c["duration"] for c in cues)
    limit = video_dur - tail
    if last_end <= limit:
        return cues
    factor = max(0.35, (limit - sum(c["duration"] for c in cues)) /
                 max(0.1, last_end - sum(c["duration"] for c in cues)))
    prev_end = -min_gap
    for cue in cues:
        cue["start"] = round(max(cue["start"] * factor, prev_end + min_gap), 2)
        prev_end = cue["start"] + cue["duration"]
    return cues


def has_filter(name: str) -> bool:
    out = subprocess.run(["ffmpeg", "-hide_banner", "-filters"], capture_output=True, text=True).stdout
    return any(line.split()[1:2] == [name] for line in out.splitlines() if len(line.split()) > 2)


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
    ap.add_argument("--align-log", default="", help="лог бота: привязать реплики к фактическим событиям")
    ap.add_argument("--bot-voice", default="", help="каталог с голосовыми ответами бота (имя файла = epoch секунд)")
    ap.add_argument("--events-file", default="", help="файл событий «тип epoch» (если лог недоступен)")
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

    events_override: list[tuple[str, float]] = []
    if args.events_file:
        for line in Path(args.events_file).expanduser().read_text().splitlines():
            parts = line.split()
            if len(parts) == 2 and parts[0] in ("voice_in", "reply_out"):
                events_override.append((parts[0], float(parts[1])))

    if args.align_log or events_override:
        log_path = Path(args.align_log).expanduser()
        zero = start_marker(video)
        if events_override and zero is not None:
            cues = align_cues(cues, events_override, zero, duration(video))
            print("🎯 реплики привязаны к событиям (из файла):")
            for c in cues:
                print(f"   {int(c['start'])//60:02d}:{c['start']%60:05.2f}  {c['text'][:48]}…")
        elif not log_path.exists():
            print(f"❌ нет лога {log_path} — выравнивание по событиям пропущено")
        elif zero is None:
            print(f"⚠️  нет маркера старта ({video.name}.start) — "
                  f"выравнивание по событиям пропущено, беру тайминги из плана")
        else:
            events = parse_events(log_path)
            fresh = [(k, t) for k, t in events if t >= zero - 1]
            cues = align_cues(cues, fresh, zero, duration(video))
            print("🎯 реплики привязаны к событиям бота:")
            for c in cues:
                print(f"   {int(c['start'])//60:02d}:{c['start']%60:05.2f}  {c['text'][:48]}…")

    out = Path(args.out).expanduser() if args.out else video.with_name(video.stem + "-final.mp4")
    vid_dur = duration(video)
    fitted = fit_to_duration(cues, vid_dur)
    if fitted is not cues:
        print("⏱  речь не помещалась — паузы сжаты автоматически")
    speech_end = max(c["start"] + c["duration"] for c in cues)
    print(f"видео: {vid_dur:.1f}c | речь заканчивается на {speech_end:.1f}c")
    if vid_dur and speech_end > vid_dur:
        print(f"⚠️  речь длиннее видео на {speech_end - vid_dur:.1f}c — "
              f"последние реплики обрежутся (или подрежь их в plan.json)")

    if not shutil.which("ffmpeg"):
        print("❌ ffmpeg не найден")
        return 1

    # голосовые ответы бота: берём из архива, а не из записи звука системы
    bot_voice: list[tuple[Path, float]] = []
    if args.bot_voice:
        bdir = Path(args.bot_voice).expanduser()
        zero_b = start_marker(video)
        if bdir.is_dir() and zero_b is not None:
            for f in sorted(bdir.glob("*.ogg")):
                try:
                    ts = float(f.stem)
                except ValueError:
                    continue
                if ts >= zero_b - 5:
                    bot_voice.append((f, round(ts - zero_b, 2)))
            if bot_voice:
                print("🔊 голос бота из архива:")
                for f, off in bot_voice:
                    print(f"   {int(off)//60:02d}:{off%60:05.2f}  {f.name}")

    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(video)]
    for cue in cues:
        cmd += ["-i", str(narr_dir / cue["file"])]
    for f, _ in bot_voice:
        cmd += ["-i", str(f)]

    subs_path = Path(args.subs).expanduser() if args.subs else None
    burn = bool(subs_path) and has_filter("subtitles")
    subs_idx = None
    if subs_path and not burn:
        if not subs_path.exists():
            print(f"❌ нет файла субтитров {subs_path}")
            return 1
        subs_idx = 1 + len(cues) + len(bot_voice)
        cmd += ["-i", str(subs_path)]

    filters, mix_inputs = [], []
    screen_has_audio = has_audio(video)
    if screen_has_audio:
        filters.append(f"[0:a]volume={args.screen_gain}[scr]")
        mix_inputs.append("[scr]")
    for idx, cue in enumerate(cues, start=1):
        delay = int(cue["start"] * 1000)
        filters.append(f"[{idx}:a]adelay={delay}|{delay},volume={args.voice_gain}[n{idx}]")
        mix_inputs.append(f"[n{idx}]")
    base = len(cues) + 1
    for k, (f, off) in enumerate(bot_voice):
        idx = base + k
        ms = int(off * 1000)
        filters.append(f"[{idx}:a]adelay={ms}|{ms},volume=1.0[bot{k}]")
        mix_inputs.append(f"[bot{k}]")
    filters.append("".join(mix_inputs) + f"amix=inputs={len(mix_inputs)}:normalize=0:dropout_transition=0[aout]")

    if burn and subs_path:
        esc = str(subs_path).replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")
        filters.append(f"[0:v]subtitles='{esc}'[vout]")
        cmd += ["-filter_complex", ";".join(filters),
                "-map", "[vout]", "-map", "[aout]",
                "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p"]
    else:
        if subs_path:
            print("ℹ️  фильтра subtitles в этой сборке ffmpeg нет — субтитры пойдут дорожкой mov_text")
        cmd += ["-filter_complex", ";".join(filters),
                "-map", "0:v", "-map", "[aout]", "-c:v", "copy"]

    cmd += ["-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", "-shortest"]
    if subs_idx is not None:
        cmd += ["-map", f"{subs_idx}:0", "-c:s", "mov_text", "-metadata:s:s:0", "language=eng"]
        # дорожка субтитров бывает длиннее видео — подрезаем, иначе часть плееров ругается
        if vid_dur:
            cmd += ["-t", f"{vid_dur:.3f}"]
    cmd += [str(out)]

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
