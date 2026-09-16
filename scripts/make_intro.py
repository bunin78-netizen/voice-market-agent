#!/usr/bin/env python3
"""Заставка для демо: аватар бота + название.

Собирает PNG-кадр под размер видео (по умолчанию 1360x722), который потом
превращается в первые секунды ролика.

Запуск:
    python3 scripts/make_intro.py --avatar <путь к аватарке>
    python3 scripts/make_intro.py --avatar avatar.jpg --title "Voice Market Agent" --sub "@VoiceMarketAgentBot"
"""
from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

BG = (13, 17, 23)          # #0d1117 — как у графиков
FG = (201, 209, 217)       # текст
ACCENT = (88, 166, 255)    # ссылка
MUTED = (139, 148, 158)

FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONT_REG = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"


def load_font(path: str, size: int) -> ImageFont.FreeTypeFont:
    try:
        return ImageFont.truetype(path, size)
    except OSError:
        return ImageFont.load_default(size)


def circle_avatar(src: Path, size: int) -> Image.Image:
    """Квадратную аватарку превращаем в круг с мягким кантом."""
    im = Image.open(src).convert("RGB")
    side = min(im.size)
    im = im.crop(((im.width - side) // 2, (im.height - side) // 2,
                  (im.width + side) // 2, (im.height + side) // 2))
    im = im.resize((size, size), Image.LANCZOS)

    mask = Image.new("L", (size * 4, size * 4), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, size * 4 - 1, size * 4 - 1), fill=255)
    mask = mask.resize((size, size), Image.LANCZOS)

    out = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    out.paste(im, (0, 0), mask)
    return out


def centered(draw: ImageDraw.ImageDraw, text: str, font, y: int, width: int,
             fill) -> None:
    left, top, right, bottom = draw.textbbox((0, 0), text, font=font)
    draw.text(((width - (right - left)) / 2 - left, y), text, font=font, fill=fill)


def build(avatar: Path, out: Path, width: int, height: int,
          title: str, sub: str, avatar_size: int) -> Path:
    img = Image.new("RGB", (width, height), BG)
    draw = ImageDraw.Draw(img)

    av = circle_avatar(avatar, avatar_size)
    ax, ay = (width - avatar_size) // 2, int(height * 0.16)
    # тонкое кольцо вокруг аватара
    draw.ellipse((ax - 6, ay - 6, ax + avatar_size + 5, ay + avatar_size + 5),
                 outline=(48, 54, 61), width=3)
    img.paste(av, (ax, ay), av)

    f_title = load_font(FONT_BOLD, 54)
    f_sub = load_font(FONT_REG, 30)
    centered(draw, title, f_title, ay + avatar_size + 48, width, FG)
    centered(draw, sub, f_sub, ay + avatar_size + 122, width, ACCENT)

    img.save(out)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--avatar", required=True)
    ap.add_argument("--out", default="tmp/intro.png")
    ap.add_argument("--width", type=int, default=1360)
    ap.add_argument("--height", type=int, default=722)
    ap.add_argument("--title", default="Voice Market Agent")
    ap.add_argument("--sub", default="@VoiceMarketAgentBot")
    ap.add_argument("--avatar-size", type=int, default=280)
    args = ap.parse_args()

    root = Path(__file__).resolve().parent.parent
    avatar = Path(args.avatar).expanduser()
    if not avatar.exists():
        print(f"❌ нет файла аватарки: {avatar}")
        return 1
    out = Path(args.out)
    if not out.is_absolute():
        out = root / out
    out.parent.mkdir(parents=True, exist_ok=True)

    build(avatar, out, args.width, args.height, args.title, args.sub, args.avatar_size)
    print(f"✅ заставка: {out} ({args.width}x{args.height})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
