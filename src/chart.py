"""Свечной график с SMA20, полосами Боллинджера и панелью RSI. Тёмная тема."""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates  # noqa: E402
from matplotlib import pyplot as plt  # noqa: E402

from .config import TMP_DIR  # noqa: E402
from .market import Indicators  # noqa: E402

BG = "#0d1117"
FG = "#c9d1d9"
GRID = "#21262d"


def make_chart(ind: Indicators, out: str | Path | None = None) -> Path:
    out = Path(out) if out else TMP_DIR / f"{ind.symbol}_{ind.interval}.png"
    candles = ind.candles
    closes = [c.close for c in candles]
    times = [mdates.date2num(__import__("datetime").datetime.utcfromtimestamp(c.open_time / 1000)) for c in candles]

    fig, (ax, ax_rsi) = plt.subplots(
        2, 1, figsize=(11, 6.5), dpi=110, sharex=True,
        gridspec_kw={"height_ratios": [3, 1], "hspace": 0.06},
    )
    fig.patch.set_facecolor(BG)
    for a in (ax, ax_rsi):
        a.set_facecolor(BG)
        a.grid(color=GRID, linewidth=0.6)
        a.tick_params(colors=FG, labelsize=8)
        for spine in a.spines.values():
            spine.set_color(GRID)

    # свечи
    width = 0.6 / 24
    for t, c in zip(times, candles):
        color = "#26a69a" if c.close >= c.open else "#ef5350"
        ax.vlines(t, c.low, c.high, color=color, linewidth=0.8)
        ax.vlines(t, min(c.open, c.close), max(c.open, c.close), color=color, linewidth=3.2)

    # SMA20 и полосы Боллинджера
    sma_series, rsi_like = [], []
    for i in range(19, len(closes)):
        sma_series.append(sum(closes[i - 19:i + 1]) / 20)
    ax.plot(times[19:], sma_series, color="#58a6ff", linewidth=1.2, label="SMA20")

    low_line = [ind.bb_low] * len(times)
    high_line = [ind.bb_high] * len(times)
    ax.plot(times, low_line, color="#d29922", linewidth=0.9, linestyle="--", label="BB")
    ax.plot(times, high_line, color="#d29922", linewidth=0.9, linestyle="--")
    ax.fill_between(times, low_line, high_line, color="#d29922", alpha=0.06)

    ax.axhline(ind.close, color="#8b949e", linewidth=0.7, linestyle=":")
    ax.annotate(f"{ind.close:,.2f}", xy=(times[-1], ind.close), xytext=(6, 0),
                textcoords="offset points", color=FG, fontsize=9, va="center")
    ax.set_title(f"{ind.symbol} · {ind.interval} · RSI {ind.rsi14:.0f} · "
                 f"BB {ind.bb_position_pct:.0f}%", color=FG, fontsize=11, loc="left")
    ax.legend(facecolor=BG, edgecolor=GRID, labelcolor=FG, fontsize=8, loc="upper left")

    # RSI
    from .market import rsi as rsi_fn  # локальный импорт, чтобы не плодить циклы

    for i in range(14, len(closes)):
        rsi_like.append(rsi_fn(closes[:i + 1], 14))
    ax_rsi.plot(times[14:], rsi_like, color="#bc8cff", linewidth=1.1)
    ax_rsi.axhline(70, color="#ef5350", linewidth=0.7, linestyle="--")
    ax_rsi.axhline(30, color="#26a69a", linewidth=0.7, linestyle="--")
    ax_rsi.set_ylim(0, 100)
    ax_rsi.set_ylabel("RSI", color=FG, fontsize=8)

    ax_rsi.xaxis.set_major_formatter(mdates.DateFormatter("%d %b %H:%M"))
    fig.autofmt_xdate(rotation=0, ha="center")
    fig.tight_layout()
    fig.savefig(out, facecolor=BG)
    plt.close(fig)
    return out
