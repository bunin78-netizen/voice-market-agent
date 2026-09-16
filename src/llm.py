"""LLM-клиент с поддержкой tool calling (OpenAI-совместимый протокол)."""
from __future__ import annotations

import json
from dataclasses import dataclass

import requests

from . import config

DEEPSEEK_URL = "https://api.deepseek.com/chat/completions"
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
TIMEOUT = 120


class LLMError(RuntimeError):
    pass


@dataclass
class LLMReply:
    content: str
    tool_calls: list[dict]
    raw: dict


def _endpoint() -> tuple[str, str, dict[str, str]]:
    if config.DEEPSEEK_API_KEY:
        return (DEEPSEEK_URL, config.LLM_MODEL,
                {"Authorization": f"Bearer {config.DEEPSEEK_API_KEY}"})
    if config.OPENROUTER_API_KEY:
        return (OPENROUTER_URL, config.LLM_MODEL,
                {"Authorization": f"Bearer {config.OPENROUTER_API_KEY}"})
    raise LLMError("не задан ни DEEPSEEK_API_KEY, ни OPENROUTER_API_KEY")


def chat(messages: list[dict], tools: list[dict] | None = None,
         temperature: float = 0.2) -> LLMReply:
    url, model, headers = _endpoint()
    payload: dict = {"model": model, "messages": messages, "temperature": temperature}
    if tools:
        payload["tools"] = tools
        payload["tool_choice"] = "auto"

    r = requests.post(url, headers={**headers, "Content-Type": "application/json"},
                      json=payload, timeout=TIMEOUT)
    if r.status_code >= 300:
        raise LLMError(f"{r.status_code}: {r.text[:400]}")

    msg = r.json()["choices"][0]["message"]
    calls = []
    for c in msg.get("tool_calls") or []:
        try:
            args = json.loads(c["function"].get("arguments") or "{}")
        except json.JSONDecodeError:
            args = {}
        calls.append({"id": c.get("id"), "name": c["function"]["name"], "args": args})
    return LLMReply(content=(msg.get("content") or "").strip(), tool_calls=calls, raw=msg)
