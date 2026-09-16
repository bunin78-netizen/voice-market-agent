#!/usr/bin/env python3
"""Оффлайн/полуживой smoke-тест пайплайна.

Проверяет по шагам, не требуя Telegram:
  1. рыночные данные Binance            (живая сеть)
  2. индикаторы и текстовая сводка      (живая сеть)
  3. построение графика                 (локально)
  4. диспетчер инструментов             (локально)
  5. цикл агента с заглушкой LLM        (локально, без ключей)
  6. AssemblyAI (если задан ключ)       (опционально)
  7. TTS через sag (если доступен)      (опционально)

Запуск:  python scripts/smoke_test.py
"""
from __future__ import annotations

import sys
import wave
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import config, market, tools  # noqa: E402
from src.agent import answer  # noqa: E402
from src.chart import make_chart  # noqa: E402

OK, FAIL = "✅", "❌"
results: list[tuple[str, bool, str]] = []


def check(name: str, fn) -> None:
    try:
        detail = fn() or ""
        results.append((name, True, str(detail)))
        print(f"{OK} {name} {detail}")
    except Exception as e:  # noqa: BLE001
        results.append((name, False, str(e)[:300]))
        print(f"{FAIL} {name} — {e}")


# 1–2. рыночные данные
def t_market():
    ind = market.indicators("BTC", "1h")
    assert ind.close > 0, "цена не получена"
    txt = ind.as_text()
    assert "RSI" in txt and "SMA20" in txt
    return f"BTC {ind.close:,.0f}, RSI {ind.rsi14:.0f}"


def t_snapshot():
    rows = market.snapshot()
    assert len(rows) >= 2, rows
    return "; ".join(r.split(",")[0] for r in rows)


def t_fear_greed():
    fg = market.fear_greed()
    assert "value" in fg or "error" in fg
    return fg.get("classification", fg.get("error", ""))[:40]


# 3. график
def t_chart():
    ind = market.indicators("ETH", "4h")
    path = make_chart(ind)
    size = Path(path).stat().st_size
    assert size > 20_000, f"подозрительно маленький файл: {size}b"
    return f"{Path(path).name} ({size // 1024} KB)"


# 4. инструменты
def t_tools():
    price = tools.execute("get_price", {"symbol": "SOL"})
    assert "price" in price, price
    ind = tools.execute("get_indicators", {"symbol": "BTC", "interval": "1h"})
    assert "RSI" in ind, ind[:120]
    bad = tools.execute("nope", {})
    assert "error" in bad
    return "get_price / get_indicators / unknown-tool"


# 5. цикл агента на заглушке LLM
def t_agent_loop():
    from src import agent as agent_mod
    from src.llm import LLMReply

    calls = {"n": 0}

    def fake_chat(messages, tools=None, temperature=0.2):  # noqa: ARG001
        calls["n"] += 1
        if calls["n"] == 1:
            return LLMReply(content="", tool_calls=[
                {"id": "call_1", "name": "get_indicators",
                 "args": {"symbol": "BTC", "interval": "1h"}}], raw={})
        return LLMReply(content="Биткоин выше SMA20, RSI нейтральный.", tool_calls=[], raw={})

    agent_mod.chat = fake_chat
    res = answer("что с биткоином?")
    assert "Биткоин" in res.text, res.text
    assert res.trace and res.trace[0].startswith("get_indicators"), res.trace
    return f"2 вызова LLM, trace={res.trace}"


# 6. AssemblyAI (опционально)
def t_assemblyai():
    if not config.ASSEMBLYAI_API_KEY:
        raise RuntimeError("ASSEMBLYAI_API_KEY не задан — пропущено")
    import struct

    wav_path = config.TMP_DIR / "silence_16k.wav"
    with wave.open(str(wav_path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        w.writeframes(struct.pack("<" + "h" * 16000, *([0] * 16000)))
    from src import stt

    tr = stt.transcribe_assemblyai(wav_path)
    return f"провайдер {tr.provider}, текст «{tr.text[:40]}», язык {tr.language}"


# 7. TTS (опционально)
def t_tts():
    from src import tts

    if not tts.available():
        raise RuntimeError("sag или ключ недоступны — пропущено")
    path = tts.synthesize("Проверка синтеза речи.", out=config.TMP_DIR / "smoke_tts.mp3")
    size = Path(path).stat().st_size
    assert size > 1000, size
    return f"{Path(path).name} ({size // 1024} KB)"


def main() -> int:
    print("=== Voice Market Agent · smoke test ===\n")
    check("Рыночные данные (Binance)", t_market)
    check("Сводка по BTC/ETH/SOL", t_snapshot)
    check("Индекс страха и жадности", t_fear_greed)
    check("Генерация графика", t_chart)
    check("Диспетчер инструментов", t_tools)
    check("Цикл агента (LLM-заглушка)", t_agent_loop)
    check("AssemblyAI STT", t_assemblyai)
    check("TTS (sag/ElevenLabs)", t_tts)

    passed = sum(1 for _, ok, _ in results if ok)
    print(f"\nитог: {passed}/{len(results)} проверок пройдено")
    return 0 if passed >= 6 else 1


if __name__ == "__main__":
    raise SystemExit(main())
