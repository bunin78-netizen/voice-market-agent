"""Рыночные данные: публичные эндпоинты Binance + индикаторы. Ключи не нужны."""
from __future__ import annotations

from dataclasses import dataclass, field

import requests

SPOT = "https://api.binance.com"
FUTURES = "https://fapi.binance.com"

ALIASES = {
    "BTC": "BTCUSDT", "BITCOIN": "BTCUSDT", "БИТКОИН": "BTCUSDT", "БТС": "BTCUSDT",
    "ETH": "ETHUSDT", "ETHEREUM": "ETHUSDT", "ЭФИР": "ETHUSDT", "ЭФИРИУМ": "ETHUSDT",
    "SOL": "SOLUSDT", "SOLANA": "SOLUSDT", "СОЛ": "SOLUSDT", "СОЛАНА": "SOLUSDT",
    "BNB": "BNBUSDT", "XRP": "XRPUSDT", "ADA": "ADAUSDT", "DOGE": "DOGEUSDT",
}

TIMEOUT = 15


class MarketError(RuntimeError):
    pass


def normalize_symbol(raw: str) -> str:
    s = (raw or "").strip().upper().replace("/", "").replace("-", "").replace(" ", "")
    if not s:
        raise MarketError("пустой тикер")
    if s in ALIASES:
        return ALIASES[s]
    if s.endswith("USDT"):
        return s
    return s + "USDT"


def _get(url: str, params: dict) -> object:
    for base in (SPOT, FUTURES):  # спот-тикер либо фьючерсный (CLUSDT, XAUUSDT, SPYUSDT)
        try:
            r = requests.get(base + url, params=params, timeout=TIMEOUT)
            if r.status_code == 200:
                return r.json()
            last = f"{base}{url} → {r.status_code}"
        except requests.RequestException as e:  # noqa: PERF203
            last = f"{base}{url} → {e}"
    raise MarketError(f"данные недоступны: {last}")


@dataclass
class Candle:
    open: float
    high: float
    low: float
    close: float
    volume: float
    open_time: int


def klines(symbol: str, interval: str = "1h", limit: int = 200) -> list[Candle]:
    raw = _get("/api/v3/klines", {"symbol": symbol, "interval": interval, "limit": limit})
    return [Candle(float(c[1]), float(c[2]), float(c[3]), float(c[4]), float(c[5]), int(c[0])) for c in raw]


def price(symbol: str) -> float:
    data = _get("/api/v3/ticker/price", {"symbol": symbol})
    return float(data["price"])


def sma(values: list[float], period: int = 20) -> float:
    if len(values) < period:
        raise MarketError("мало данных для SMA")
    return sum(values[-period:]) / period


def rsi(values: list[float], period: int = 14) -> float:
    if len(values) < period + 1:
        raise MarketError("мало данных для RSI")
    gains, losses = 0.0, 0.0
    for i in range(1, period + 1):
        delta = values[i] - values[i - 1]
        gains += max(delta, 0.0)
        losses += max(-delta, 0.0)
    avg_gain, avg_loss = gains / period, losses / period
    for i in range(period + 1, len(values)):
        delta = values[i] - values[i - 1]
        avg_gain = (avg_gain * (period - 1) + max(delta, 0.0)) / period
        avg_loss = (avg_loss * (period - 1) + max(-delta, 0.0)) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100 - 100 / (1 + rs)


def bollinger(values: list[float], period: int = 20, mult: float = 2.0) -> tuple[float, float, float]:
    if len(values) < period:
        raise MarketError("мало данных для BB")
    window = values[-period:]
    mid = sum(window) / period
    var = sum((v - mid) ** 2 for v in window) / period
    sd = var ** 0.5
    return mid - mult * sd, mid, mid + mult * sd


@dataclass
class Indicators:
    symbol: str
    interval: str
    close: float = 0.0
    change_pct: float = 0.0
    sma20: float = 0.0
    rsi14: float = 0.0
    bb_low: float = 0.0
    bb_mid: float = 0.0
    bb_high: float = 0.0
    bb_position_pct: float = 0.0
    volume_ratio: float = 0.0
    candle: Candle | None = None
    candles: list[Candle] = field(default_factory=list)

    def as_text(self) -> str:
        trend = "выше SMA20" if self.close > self.sma20 else "ниже SMA20"
        if self.rsi14 >= 70:
            rsi_state = "перекупленность"
        elif self.rsi14 <= 30:
            rsi_state = "перепроданность"
        else:
            rsi_state = "нейтрально"
        return (
            f"{self.symbol} @ {self.close:,.2f} ({self.change_pct:+.2f}% за последнюю свечу), "
            f"таймфрейм {self.interval}. Цена {trend} (SMA20 {self.sma20:,.2f}). "
            f"RSI14 {self.rsi14:.1f} — {rsi_state}. "
            f"Полосы Боллинджера: {self.bb_low:,.2f} / {self.bb_mid:,.2f} / {self.bb_high:,.2f}, "
            f"цена в канале на {self.bb_position_pct:.0f}%. "
            f"Объём к среднему: {self.volume_ratio:.2f}x."
        )


def indicators(symbol_raw: str, interval: str = "1h") -> Indicators:
    symbol = normalize_symbol(symbol_raw)
    candles = klines(symbol, interval, limit=200)
    if len(candles) < 30:
        raise MarketError(f"недостаточно свечей по {symbol}")
    closes = [c.close for c in candles]
    vols = [c.volume for c in candles]
    last, prev = candles[-1], candles[-2]

    low, mid, high = bollinger(closes)
    rng = high - low
    ind = Indicators(
        symbol=symbol,
        interval=interval,
        close=last.close,
        change_pct=(last.close - prev.close) / prev.close * 100 if prev.close else 0.0,
        sma20=sma(closes, 20),
        rsi14=rsi(closes, 14),
        bb_low=low, bb_mid=mid, bb_high=high,
        bb_position_pct=((last.close - low) / rng * 100) if rng else 50.0,
        volume_ratio=last.volume / (sum(vols[-21:-1]) / 20) if len(vols) > 21 else 1.0,
        candle=last,
        candles=candles,
    )
    return ind


def fear_greed() -> dict:
    try:
        r = requests.get("https://api.alternative.me/fng/?limit=1", timeout=TIMEOUT)
        r.raise_for_status()
        item = r.json()["data"][0]
        return {"value": int(item["value"]), "classification": item["value_classification"]}
    except Exception as e:  # noqa: BLE001
        return {"error": str(e)[:120]}


def snapshot(symbols: tuple[str, ...] = ("BTCUSDT", "ETHUSDT", "SOLUSDT")) -> list[str]:
    out = []
    for s in symbols:
        try:
            ind = indicators(s, "1h")
            out.append(f"{ind.symbol}: {ind.close:,.2f} ({ind.change_pct:+.2f}%), RSI {ind.rsi14:.0f}")
        except MarketError as e:
            out.append(f"{s}: нет данных ({e})")
    return out
