"""Инструменты, доступные LLM: рыночные данные и построение графика."""
from __future__ import annotations

import json
from pathlib import Path

from . import config, market, solana
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
    {
        "type": "function",
        "function": {
            "name": "get_solana_network",
            "description": "Состояние сети Solana: версия узла, текущий слот и эпоха, пропускная способность, среднее время слота.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_sol_balance",
            "description": "Баланс кошелька Solana в SOL по его адресу (base58).",
            "parameters": {
                "type": "object",
                "properties": {"address": {"type": "string", "description": "Адрес кошелька Solana"}},
                "required": ["address"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_my_sol_balance",
            "description": "Баланс SOL на кошельке пользователя по умолчанию. Вызывай, когда спрашивают «мой кошелёк» без адреса.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_solana_activity",
            "description": "Последние транзакции кошелька Solana: сколько успешных и неудачных, слот самой свежей.",
            "parameters": {
                "type": "object",
                "properties": {
                    "address": {"type": "string"},
                    "limit": {"type": "integer", "description": "Сколько транзакций проверить, 1–20"},
                },
                "required": ["address"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_token_balances",
            "description": "Токены на кошельке Solana: SOL и ненулевые балансы SPL-токенов (USDC, USDT, JUP и другие).",
            "parameters": {
                "type": "object",
                "properties": {"address": {"type": "string", "description": "Адрес кошелька; можно не указывать — тогда возьмётся кошелёк пользователя по умолчанию"}},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_payment_request",
            "description": "Создать запрос на оплату в Solana Pay: ссылка и QR-код, по которому платят из своего кошелька. Ключи не используются.",
            "parameters": {
                "type": "object",
                "properties": {
                    "amount": {"type": "number", "description": "Сумма"},
                    "token": {"type": "string", "description": "USDC, USDT или не указывать для SOL"},
                    "recipient": {"type": "string", "description": "Адрес получателя; по умолчанию кошелёк пользователя"},
                    "message": {"type": "string", "description": "Короткая пометка к платежу"},
                },
                "required": ["amount"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_swap_quote",
            "description": "Котировка обмена токенов на Solana через Jupiter: сколько получится и какой курс. Исполнение — в кошельке пользователя.",
            "parameters": {
                "type": "object",
                "properties": {
                    "from_token": {"type": "string", "description": "SOL, USDC, USDT, JUP, BONK"},
                    "to_token": {"type": "string"},
                    "amount": {"type": "number"},
                },
                "required": ["from_token", "to_token", "amount"],
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

        if name == "get_solana_network":
            return json.dumps(solana.network_status().as_text(), ensure_ascii=False)

        if name == "get_my_sol_balance":
            from .config import SOLANA_WALLET as _w
            if not _w:
                return json.dumps({"error": "адрес кошелька по умолчанию не задан — попроси пользователя назвать адрес"},
                                  ensure_ascii=False)
            return json.dumps(solana.balance(_w).as_text(), ensure_ascii=False)

        if name == "get_sol_balance":
            info = solana.balance(args.get("address", ""))
            return json.dumps(info.as_text(), ensure_ascii=False)

        if name == "get_solana_activity":
            return json.dumps(
                solana.activity_text(args.get("address", ""), args.get("limit", 5)),
                ensure_ascii=False)

        if name == "get_token_balances":
            addr = (args.get("address") or config.SOLANA_WALLET or "").strip()
            if not addr:
                return json.dumps({"error": "адрес не указан и кошелёк по умолчанию не задан"},
                                  ensure_ascii=False)
            return json.dumps(solana.tokens_text(addr), ensure_ascii=False)

        if name == "create_payment_request":
            recipient = (args.get("recipient") or config.SOLANA_WALLET or "").strip()
            token = (args.get("token") or "").strip().upper()
            mint = solana.SWAP_MINTS.get(token) if token else None
            if token and not mint:
                return json.dumps({"error": f"неизвестный токен {token}"}, ensure_ascii=False)
            url = solana.pay_url(recipient, float(args.get("amount", 0)), mint=mint,
                                 message=(args.get("message") or "")[:120])
            path = solana.qr_png(url, config.TMP_DIR / "pay_qr.png")
            ARTIFACTS.append(Path(path))
            payload = {"url": url, "qr": path, "recipient": recipient,
                       "amount": args.get("amount"), "token": token or "SOL"}
            return json.dumps(payload, ensure_ascii=False)

        if name == "get_swap_quote":
            return json.dumps(
                solana.swap_text(args.get("from_token", "SOL"), args.get("to_token", "USDC"),
                                 float(args.get("amount", 0))),
                ensure_ascii=False)

        return json.dumps({"error": f"неизвестный инструмент {name}"}, ensure_ascii=False)
    except Exception as e:  # noqa: BLE001 — ошибку возвращаем модели, она объяснит пользователю
        return json.dumps({"error": str(e)[:300]}, ensure_ascii=False)
