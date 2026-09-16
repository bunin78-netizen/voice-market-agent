"""Инструменты, доступные LLM: рыночные данные и построение графика."""
from __future__ import annotations

import json
from pathlib import Path

from . import market
from .chart import make_chart

TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "get_price",
            "description": "Текущая цена актива в USDT (BTC, ETH, SOL и другие пары).",
            "parameters": {
                "type": "object",
                "properties": {"symbol": {"type": "string", "description": "Тикер, например BTC"}},
                "required": ["symbol"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_indicators",
            "description": "Технические индикаторы по активу: цена, изменение, SMA20, RSI14, полосы Боллинджера, объём.",
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {"type": "string"},
                    "interval": {"type": "string", "enum": ["15m", "1h", "4h", "1d"]},
                },
                "required": ["symbol", "interval"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_market_snapshot",
            "description": "Быстрая сводка по BTC, ETH и SOL одним вызовом.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_fear_greed",
            "description": "Индекс страха и жадности крипторынка (0-100) и его качественная оценка.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "make_chart",
            "description": "Построить свечной график с SMA20, полосами Боллинджера и RSI. Используй, когда пользователь просит график или визуальную картину.",
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {"type": "string"},
                    "interval": {"type": "string", "enum": ["15m", "1h", "4h", "1d"]},
                },
                "required": ["symbol", "interval"],
            },
        },
    },
]

# какие файлы-артефакты вернул вызов (графики)
ARTIFACTS: list[Path] = []


def execute(name: str, args: dict) -> str:
    """Выполняет инструмент, возвращает строку JSON для LLM."""
    try:
        if name == "get_price":
            symbol = market.normalize_symbol(args.get("symbol", ""))
            return json.dumps({"symbol": symbol, "price": market.price(symbol)}, ensure_ascii=False)

        if name == "get_indicators":
            ind = market.indicators(args.get("symbol", ""), args.get("interval", "1h"))
            return json.dumps(ind.as_text(), ensure_ascii=False)

        if name == "get_market_snapshot":
            return json.dumps(market.snapshot(), ensure_ascii=False)

        if name == "get_fear_greed":
            return json.dumps(market.fear_greed(), ensure_ascii=False)

        if name == "make_chart":
            ind = market.indicators(args.get("symbol", ""), args.get("interval", "1h"))
            path = make_chart(ind)
            ARTIFACTS.append(path)
            return json.dumps({"chart": str(path), "summary": ind.as_text()}, ensure_ascii=False)

        return json.dumps({"error": f"неизвестный инструмент {name}"}, ensure_ascii=False)
    except Exception as e:  # noqa: BLE001 — ошибку возвращаем модели, она объяснит пользователю
        return json.dumps({"error": str(e)[:300]}, ensure_ascii=False)
