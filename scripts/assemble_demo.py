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
    if len(cues) > 5 and outs:
        anchors[6] = outs[0] + 0.6
    if len(cues) > 6 and len(ins) > 1:
        anchors[7] = ins[1] + 0.6
    if len(cues) > 7 and len(outs) > 1:
        anchors[8] = outs[1] + 0.6
    if len(cues) > 8 and len(ins) > 2:
        anchors[9] = max(ins[2] - cues[8]["duration"] - 1.0, 0.0)
    if len(cues) > 9 and len(ins) > 2:
        anchors[10] = ins[2] + 0.6
    if len(cues) > 10 and len(outs) > 2:
        anchors[11] = outs[2] + 0.6

    prev_end = 0.0
    for i, cue in enumerate(cues, start=1):
        if i in anchors:
            cue["start"] = round(max(anchors[i], prev_end + 0.4), 2)
        prev_end = cue["start"] + cue["duration"]
    return cues


def collect_bot_voice(bdir: Path, zero: float | None, before: float | None = None) -> list[tuple[Path, float]]:
    """Голосовые ответы бота: (файл, смещение в секундах от старта записи)."""
    out: list[tuple[Path, float]] = []
    if not bdir.is_dir() or zero is None:
        return out
    for f in sorted(bdir.glob("*.ogg")):
        try:
            ts = float(f.stem)
        except ValueError:
            continue
        if ts >= zero - 5 and (before is None or ts - zero <= before):
            out.append((f, round(ts - zero, 2)))
    return out


def avoid_overlap(cues: list[dict], spoken: list[tuple[float, float]],
                  gap: float = 0.5, min_gap: float = 0.4) -> list[dict]:
    """Закадровый текст не должен звучать одновременно с голосом бота — иначе речь «двоится»."""
    if not spoken:
        return cues
    cues = sorted(cues, key=lambda c: c["start"])
    prev_end = 0.0
    for cue in cues:
        start = max(cue["start"], prev_end + min_gap)
        for bs, be in spoken:
            if start < be and start + cue["duration"] > bs:
                start = be + gap
        cue["start"] = round(start, 2)
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


def write_srt(cues: list[dict], en_texts: list[str], out: Path) -> Path | None:
    """Субтитры с точными таймингами из собранного видео."""
    if not en_texts:
        return None
    lines, idx = [], 0
    for i, cue in enumerate(cues):
        en = en_texts[i] if i < len(en_texts) else ""
        if not en:
            continue
        idx += 1
        def ts(t: float) -> str:
            h, rem = divmod(max(t, 0.0), 3600)
            m, s = divmod(rem, 60)
            return f"{int(h):02d}:{int(m):02d}:{s:06.3f}".replace(".", ",")
        start, end = cue["start"], cue["start"] + cue["duration"]
        lines.append(f"{idx}\n{ts(start)} --> {ts(end)}\n{en}\n")
    if not lines:
        return None
    path = out.with_suffix(".en.srt")
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def build_with_card(video: Path, card_png: Path, seconds: float) -> Path | None:
    """Приклеивает заставку в начало; маркер старта сдвигается на её длину."""
    zero = start_marker(video)
    if zero is None or not card_png.exists():
        return None
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v", "-show_entries",
         "stream=width,height,r_frame_rate", "-of", "csv=p=0", str(video)],
        capture_output=True, text=True).stdout.strip().strip(",")
    parts = probe.split(",")
    if len(parts) < 2:
        return None
    w, h = parts[0], parts[1]
    fps = parts[2].split("/")[0] if len(parts) > 2 and parts[2] else "25"

    work = video.parent / (video.stem + "-intro")
    work.mkdir(exist_ok=True)
    card = work / "card.mp4"
    card_cmd = [
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-loop", "1", "-t", f"{seconds}", "-i", str(card_png),
        "-f", "lavfi", "-t", f"{seconds}", "-i", "anullsrc=r=48000:cl=mono",
        "-vf", f"scale={w}:{h}:force_original_aspect_ratio=decrease,"
               f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:color=0x0d1117",
        "-r", fps, "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
        "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k", "-ar", "48000", "-ac", "1",
        "-shortest", str(card),
    ]
    if subprocess.run(card_cmd, capture_output=True).returncode != 0:
        print("⚠️  не удалось сделать заставку")
        return None

    combined = work / "combined.mp4"
    # склейка фильтром (а не concat-демультиплексором): он выравнивает таймстемпы
    res = subprocess.run([
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-i", str(card), "-i", str(video),
        "-filter_complex", "[0:v][0:a][1:v][1:a]concat=n=2:v=1:a=1[v][a]",
        "-map", "[v]", "-map", "[a]",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", str(combined),
    ], capture_output=True, text=True)
    if res.returncode == 0 and combined.exists() and combined.stat().st_size > 10000:
        (combined.parent / (combined.name + ".start")).write_text(str(zero - seconds))
        print(f"🎬 заставка добавлена: {seconds:.0f} c")
        return combined
    print("⚠️  склейка с заставкой не удалась:", res.stderr.strip()[:200])
    return None


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
    ap.add_argument("--crop-top", type=int, default=0, help="срезать N пикселей сверху (мигающая полоса)")
    ap.add_argument("--intro-card", default="", help="PNG-заставка в начале видео")
    ap.add_argument("--outro-card", default="", help="PNG-финальный кадр, если речи длиннее видео")
    ap.add_argument("--intro-seconds", type=float, default=5.0, help="сколько показывать заставку")
    ap.add_argument("--voice-before", type=float, default=0.0,
                    help="брать из архива только ответы, начавшиеся до этой секунды")
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

    if args.intro_card:
        card_png = Path(args.intro_card).expanduser()
        combined = build_with_card(video, card_png, args.intro_seconds)
        if combined:
            video = combined
        else:
            print("⚠️  продолжаю без заставки")

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

    zero = start_marker(video)
    bot_voice = (collect_bot_voice(Path(args.bot_voice).expanduser(), zero,
                                   args.voice_before or None)
                 if args.bot_voice else [])
    if bot_voice:
        print("🔊 голос бота из архива:")
        for f, off in bot_voice:
            print(f"   {int(off)//60:02d}:{off%60:05.2f}  {f.name}")

    if args.events_file and events_override and zero is not None:
        cues = align_cues(cues, events_override, zero, duration(video))
        print("🎯 реплики привязаны к событиям (из файла):")
        for c in cues:
            print(f"   {int(c['start'])//60:02d}:{c['start']%60:05.2f}  {c['text'][:48]}…")
    elif args.align_log:
        log_path = Path(args.align_log).expanduser()
        if not log_path.exists():
            print(f"❌ нет лога {log_path} — выравнивание по событиям пропущено")
        elif zero is None:
            print(f"⚠️  нет маркера старта ({video.name}.start) — "
                  f"выравнивание пропущено, беру тайминги из плана")
        else:
            events = parse_events(log_path)
            fresh = [(k, tt) for k, tt in events if tt >= zero - 1]
            cues = align_cues(cues, fresh, zero, duration(video))
            print("🎯 реплики привязаны к событиям бота:")
            for c in cues:
                print(f"   {int(c['start'])//60:02d}:{c['start']%60:05.2f}  {c['text'][:48]}…")

    out = Path(args.out).expanduser() if args.out else video.with_name(video.stem + "-final.mp4")
    vid_dur = duration(video)
    # после выравнивания разводим закадровый текст с голосом бота
    spoken_spans = []
    for f, off in bot_voice:
        d = duration(f)
        if d > 0:
            spoken_spans.append((off, off + d))
    cues = avoid_overlap(cues, spoken_spans)
    fitted = fit_to_duration(cues, vid_dur)
    cues = avoid_overlap(cues, spoken_spans)
    # учитываем и закадровый текст, и голос бота: что из них длиннее — то и задаёт конец
    narration_end = max((c["start"] + c["duration"] for c in cues), default=0.0)
    voice_end = max((e for _, e in spoken_spans), default=0.0)
    speech_end = max(narration_end, voice_end)
    overhang = max(0.0, speech_end + 0.5 - (vid_dur or 0.0))
    pad = overhang if overhang > 0.4 else 0.0
    crop = f"crop=iw:ih-{args.crop_top}:0:{args.crop_top}," if args.crop_top else ""
    if crop:
        print(f"✂️  срезаю верхние {args.crop_top}px")
    outro_img = Path(args.outro_card).expanduser() if args.outro_card else None
    use_outro = bool(outro_img and outro_img.exists() and pad > 0.4)
    print("🎙  голос бота:", ", ".join(f"{int(s)//60:02d}:{s%60:04.1f}–{int(e)//60:02d}:{e%60:04.1f}"
                                       for s, e in spoken_spans) or "нет")
    print(f"видео: {vid_dur:.1f}c | текст до {narration_end:.1f}c | голос бота до {voice_end:.1f}c")
    if pad:
        print(f"🧊 не хватает {pad:.1f}c — "
              + ("покажу финальный кадр" if use_outro else "последний кадр замрёт"))

    if not shutil.which("ffmpeg"):
        print("❌ ffmpeg не найден")
        return 1

    # голосовые ответы бота уже собраны выше
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(video)]
    for cue in cues:
        cmd += ["-i", str(narr_dir / cue["file"])]
    for f, _ in bot_voice:
        cmd += ["-i", str(f)]

    outro_idx = None
    if use_outro:
        outro_idx = 1 + len(cues) + len(bot_voice)
        cmd += ["-loop", "1", "-t", f"{pad:.3f}", "-i", str(outro_img)]

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

    if use_outro and outro_idx is not None:
        filters.append(f"[0:v]{crop}format=yuv420p,fps=25[vmain]")
        filters.append(f"[{outro_idx}:v]{crop}fps=25,format=yuv420p,setpts=PTS-STARTPTS[vcard]")
        filters.append("[vmain][vcard]concat=n=2:v=1:a=0[vpad]")
        print(f"🎬 в конце — финальный кадр на {pad:.1f}c")
        cmd += ["-filter_complex", ";".join(filters),
                "-map", "[vpad]", "-map", "[aout]",
                "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p"]
    elif not burn and pad:
        filters.append(f"[0:v]{crop}tpad=stop_mode=clone:stop_duration={pad:.3f}[vpad]")
        cmd += ["-filter_complex", ";".join(filters),
                "-map", "[vpad]", "-map", "[aout]",
                "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p"]
    elif burn and subs_path:
        esc = str(subs_path).replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")
        filters.append(f"[0:v]subtitles='{esc}'[vout]")
        cmd += ["-filter_complex", ";".join(filters),
                "-map", "[vout]", "-map", "[aout]",
                "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p"]
    elif not pad:
        if subs_path:
            print("ℹ️  фильтра subtitles в этой сборке ffmpeg нет — субтитры пойдут дорожкой mov_text")
        if crop:
            filters.append(f"[0:v]{crop}trim=end={vid_dur:.3f},setpts=PTS-STARTPTS[vcrop]")
            cmd += ["-filter_complex", ";".join(filters),
                    "-map", "[vcrop]", "-map", "[aout]",
                    "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p"]
        else:
            cmd += ["-filter_complex", ";".join(filters),
                    "-map", "0:v", "-map", "[aout]", "-c:v", "copy"]

    cmd += ["-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", "-shortest"]
    if subs_idx is not None:
        cmd += ["-map", f"{subs_idx}:0", "-c:s", "mov_text", "-metadata:s:s:0", "language=eng"]
        if vid_dur:
            cmd += ["-t", f"{vid_dur:.3f}"]
    tmp_out = out.with_name(out.stem + ".part" + out.suffix)
    cmd += [str(tmp_out)]

    print("…сборка")
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        print("❌ ffmpeg упал:\n", proc.stderr.strip()[:800])
        return 1

    tmp_out.replace(out)  # атомарная подмена: плеер не увидит недописанный файл
    srt = write_srt(cues, [c.get("en", "") for c in plan.get("cues", [])], out)
    print(f"✅ готово: {out}")
    if srt:
        print(f"   субтитры с точными таймингами: {srt}")
    print(f"   длительность {duration(out):.1f}c, размер {out.stat().st_size // 1024 // 1024} МБ")
    print(f"   проверь: ffplay -autoexit \"{out}\"")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
