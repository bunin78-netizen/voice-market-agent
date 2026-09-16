#!/usr/bin/env python3
"""Вырезает простой из записи демо: статичные куски экрана сжимаются.

Что делает:
  1. ищет окна, где картинка не меняется дольше N секунд (агент думает, никто не нажимает);
  2. оставляет от каждого окна короткий «вздох», остальное вырезает;
  3. не трогает вступление до первого голосового и моменты, когда звучит голос бота;
  4. сохраняет новое видео и файл событий с пересчитанными временами.

Запуск:
    python3 scripts/trim_idle.py --video <запись.mp4> [--log tmp/bot.log]
"""
from __future__ import annotations

import argparse
import re
import statistics
import subprocess
import sys
import datetime as dt
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
W, H = 272, 144          # размер для анализа (быстро и достаточно)
FPS = 2.0                # частота анализа
STATIC_DIFF = 1.2        # средняя разница яркости, ниже которой считаем кадр статичным
MIN_IDLE = 6.0           # окно короче — не трогаем
KEEP = 1.8               # сколько секунд оставлять от окна

LOG_PAT = re.compile(
    r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}),(\d{3}) INFO .*EVENT (voice_in|reply_out|voice_saved)")


def duration(path: Path) -> float:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                          "-of", "default=nw=1:nk=1", str(path)],
                         capture_output=True, text=True).stdout
    try:
        return float(out.strip())
    except ValueError:
        return 0.0


def frames_gray(path: Path) -> list[bytes]:
    raw = subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", str(path),
         "-vf", f"fps={FPS},scale={W}:{H},format=gray", "-f", "rawvideo", "-"],
        capture_output=True).stdout
    n = len(raw) // (W * H)
    return [raw[i * W * H:(i + 1) * W * H] for i in range(n)]


def static_windows(video: Path) -> list[tuple[float, float]]:
    fr = frames_gray(video)
    if len(fr) < 4:
        return []
    diffs = []
    for i in range(1, len(fr)):
        a, b = fr[i - 1], fr[i]
        diffs.append(sum(abs(a[j] - b[j]) for j in range(0, len(a), 7)) / (len(a) // 7))
    windows, start = [], None
    for i, d in enumerate(diffs, start=1):
        if d < STATIC_DIFF:
            if start is None:
                start = i - 1
        else:
            if start is not None and (i - start) / FPS >= MIN_IDLE:
                windows.append((start / FPS, i / FPS))
            start = None
    if start is not None and (len(diffs) - start) / FPS >= MIN_IDLE:
        windows.append((start / FPS, len(diffs) / FPS))
    return windows


def parse_events(log_path: Path, zero: float) -> list[tuple[str, float]]:
    out = []
    for line in log_path.read_text(encoding="utf-8", errors="replace").splitlines():
        m = LOG_PAT.match(line)
        if not m:
            continue
        t = dt.datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S").timestamp() + int(m.group(2)) / 1000
        out.append((m.group(3), t - zero))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", required=True)
    ap.add_argument("--log", default=str(ROOT / "tmp" / "bot.log"))
    ap.add_argument("--out", default="")
    ap.add_argument("--events-out", default="")
    ap.add_argument("--max-cut", type=float, default=6.0,
                    help="сколько секунд максимум вырезать из одного окна")
    args = ap.parse_args()

    video = Path(args.video).expanduser()
    if not video.exists():
        print(f"❌ нет файла {video}")
        return 1
    marker = video.with_suffix(video.suffix + ".start")
    if not marker.exists():
        print(f"❌ нет маркера старта {marker}")
        return 1
    zero = float(marker.read_text().strip())
    total = duration(video)

    # берём только события этого дубля (остальное в логе — от прошлых записей)
    events = [(k, t) for k, t in parse_events(Path(args.log), zero) if t >= -1.0]
    ins = [t for k, t in events if k == "voice_in"]
    outs = [t for k, t in events if k == "reply_out"]
    if not ins:
        print("❌ в логе нет событий этого дубля")
        return 1

    # где нельзя резать: до первого вопроса и вокруг голосовых ответов бота
    protect = [(0.0, ins[0] + 3.0)]
    for k, t in events:
        if k == "voice_saved":
            protect.append((t - 1.0, t + 25.0))
    protect.append((outs[-1] - 12.0, total))   # не трогаем показ последнего ответа

    def protected(a: float, b: float) -> bool:
        return any(a < pe and b > ps for ps, pe in protect)

    windows = static_windows(video)
    cuts: list[tuple[float, float]] = []
    for a, b in windows:
        if b - a <= KEEP + 0.6:
            continue
        ca, cb = a + KEEP, min(b, a + KEEP + args.max_cut)  # режем не всё окно, а часть
        if protected(ca, cb):
            continue
        cuts.append((round(ca, 2), round(cb, 2)))

    if not cuts:
        print("нечего вырезать — статичных окон не нашлось")
        return 0

    saved = sum(b - a for a, b in cuts)
    print(f"вырезаю простой: {len(cuts)} окон, {saved:.1f} c")
    for a, b in cuts:
        print(f"   {int(a)//60:02d}:{a%60:04.1f} – {int(b)//60:02d}:{b%60:04.1f}  ({b-a:.1f} c)")

    # карта времени: t -> t минус всё, что вырезано раньше
    def shift(t: float) -> float:
        return round(t - sum(max(0.0, min(t, b) - a) for a, b in cuts if t > a), 3)

    keep: list[tuple[float, float]] = []
    pos = 0.0
    for a, b in cuts:
        keep.append((pos, a))
        pos = b
    keep.append((pos, total))

    parts, inputs = [], []
    for idx, (a, b) in enumerate(keep):
        parts.append(f"[0:v]trim=start={a:.3f}:end={b:.3f},setpts=PTS-STARTPTS[v{idx}]")
        inputs.append(f"[v{idx}]")
    filters = ";".join(parts) + ";" + "".join(inputs) + f"concat=n={len(keep)}:v=1:a=0[v]"

    out = Path(args.out).expanduser() if args.out else video.with_name(video.stem + "-trim.mp4")
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(video),
           "-filter_complex", filters, "-map", "[v]",
           "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
           "-movflags", "+faststart", str(out)]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        print("❌ ffmpeg упал:", res.stderr.strip()[:300])
        return 1

    out.with_suffix(out.suffix + ".start").write_text(str(zero))
    events_out = Path(args.events_out) if args.events_out else out.with_name(out.stem + "-events.txt")
    lines = [f"{k} {shift(t):.3f}" for k, t in events if shift(t) > 0]
    events_out.write_text("\n".join(lines) + "\n", encoding="utf-8")

    # голосовые ответы бота лежат под именами epoch — копируем с новыми временами
    voice_src = ROOT / "tmp" / "voice-replies"
    voice_dst = ROOT / "tmp" / "voice-replies-trim"
    copied = 0
    if voice_src.is_dir():
        voice_dst.mkdir(exist_ok=True)
        for f in voice_dst.glob("*.ogg"):
            f.unlink()
        for k, t0 in events:
            if k != "voice_saved":
                continue
            src = voice_src / f"{int(zero + t0)}.ogg"
            if src.exists():
                dst = voice_dst / f"{int(zero + shift(t0))}.ogg"
                dst.write_bytes(src.read_bytes())
                copied += 1

    print(f"✅ получилось: {out} ({duration(out):.1f} c было {total:.1f} c)")
    if copied:
        print(f"   голосовые ответы скопированы с новыми временами: {voice_dst} ({copied} шт.)")
    print(f"   события с новыми временами: {events_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
