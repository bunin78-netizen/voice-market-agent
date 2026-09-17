#!/usr/bin/env python3
"""Ставит окно Telegram на нужный монитор и растягивает его.

Зачем: качество записи зависит от размера окна. Если чат открыт в маленьком
плавающем окне (1010×522), видео получится мягким — YouTube растянет его до 1080p.
Этот скрипт разворачивает чат на главном мониторе, чтобы запись шла в полном размере.

Запуск (нужен python из venv с python-xlib):
    /tmp/xlibvenv/bin/python scripts/arrange_window.py
    /tmp/xlibvenv/bin/python scripts/arrange_window.py --list
"""
from __future__ import annotations

import argparse
import sys

try:
    from Xlib import X, display, protocol
except ImportError:
    print("❌ нужен python-xlib. Создай venv и поставь: "
          "python3 -m venv /tmp/xlibvenv && /tmp/xlibvenv/bin/pip install python-xlib")
    raise SystemExit(1)


def windows(d):
    """Список видимых окон верхнего уровня с именами."""
    root = d.screen().root
    out = []
    for w in root.query_tree().children:
        try:
            attrs = w.get_attributes()
            if attrs.map_state != X.IsViewable:
                continue
            geo = w.get_geometry()
            name = ""
            try:
                name = w.get_wm_name() or ""
            except Exception:  # noqa: BLE001
                pass
            if not name:
                try:
                    prop = w.get_full_property(d.intern_atom("_NET_WM_NAME"), X.AnyPropertyType)
                    name = prop.value.decode("utf-8", "replace") if prop else ""
                except Exception:  # noqa: BLE001
                    pass
            try:
                wm_class = (w.get_wm_class() or ("", ""))[1]
            except Exception:  # noqa: BLE001
                wm_class = ""
            out.append((w, name, geo.width, geo.height, geo.x, geo.y, wm_class))
        except Exception:  # noqa: BLE001
            continue
    return out


def find_target(ws, needle: str):
    """Ищем окно ЧАТА Telegram: по классу окна, а не только по заголовку.

    Важно: в заголовке браузера тоже может быть «Voice Market Agent» —
    например, открытая страница хакатона, поэтому фильтруем по WM_CLASS.
    """
    tg = [w for w in ws if "telegram" in (w[6] or "").lower() and "media viewer" not in w[1].lower()]
    by_name = [w for w in tg if needle.lower() in w[1].lower()]
    pool = by_name or tg
    return max(pool, key=lambda w: w[2] * w[3]) if pool else None


def move_resize(d, win, x: int, y: int, w: int, h: int) -> None:
    root = d.screen().root
    atom = d.intern_atom("_NET_MOVERESIZE_WINDOW")
    data = (32, [0 | (0xF << 8), x, y, w, h])
    ev = protocol.event.ClientMessage(window=win, client_type=atom, data=data)
    root.send_event(ev, event_mask=X.SubstructureRedirectMask | X.SubstructureNotifyMask)
    d.flush()
    d.sync()
    win.configure(x=x, y=y, width=w, height=h)
    d.flush()
    d.sync()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--title", default="Voice Market Agent", help="часть заголовка окна")
    ap.add_argument("--x", type=int, default=1360)     # начало главного монитора
    ap.add_argument("--y", type=int, default=0)
    ap.add_argument("--w", type=int, default=1920)
    ap.add_argument("--h", type=int, default=1080)
    ap.add_argument("--list", action="store_true", help="только показать окна")
    args = ap.parse_args()

    d = display.Display()
    ws = windows(d)
    if args.list:
        for item in sorted(ws, key=lambda t: -t[2] * t[3]):
            print(f"  {item[2]:5}x{item[3]:<5} +{item[4]}+{item[5]}  [{item[6][:18]:18}] {item[1][:50]}")
        return 0

    target = find_target(ws, args.title)
    if not target:
        print(f"❌ окно с «{args.title}» не найдено")
        return 1
    win, name, w0, h0, x0, y0, wclass = target
    print(f"нашёл: «{name[:50]}» — {w0}x{h0}+{x0}+{y0}")

    margin = 8
    move_resize(d, win, args.x + margin, args.y + margin,
                args.w - margin * 2, args.h - margin * 2)
    d.sync()

    ws2 = windows(d)
    for item in ws2:
        w, _n, w2, h2, x2, y2 = item[0], item[1], item[2], item[3], item[4], item[5]
        if w == win:
            print(f"теперь: {w2}x{h2}+{x2}+{y2}")
            if h2 >= 900:
                print("✅ окно большое — запись будет в полном размере")
            else:
                print("⚠️  окно всё ещё меньше 900 px по высоте — возможно, оконный менеджер не дал растянуть")
            break
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
