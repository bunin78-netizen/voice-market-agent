"""Оркестратор: вопрос пользователя → инструменты → финальный ответ.

Ответ задуман «под озвучку»: короткие фразы, без markdown-таблиц и без ссылок.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from . import config, tools
from .llm import chat

SYSTEM_PROMPT = """Ты — Voice Market Agent, голосовой рыночный ассистент в Telegram.

Правила:
1. Отвечай на языке пользователя (русский → русский, английский → английский).
2. Структура ответа всегда такая: сначала 2–3 коротких предложения УСТНОЙ ЧАСТИ — их озвучат голосом, без цифр-простыней, без markdown и ссылок; затем строка `---` в отдельной строке; затем подробности текстом для чтения (уровни, числа, детали) — их в голос не читают. В подробностях НЕ используй markdown (без ** , # и - в начале строки): пункты начинай символом «•».
3. Числа произноси кратко: «сто девятнадцать тысяч двести», цену — с двумя знаками смысла, не больше.
4. Всегда опирайся на инструменты, не выдумывай цены. Если данных нет — скажи прямо.
5. График: если вопрос про состояние, тренд, уровни, «что происходит» или «покажи» — вызови make_chart и добавь одну фразу, что на графике видно. Если спрашивают только цену одним словом — график не нужен.
6. Не давай инвестиционных советов и прогнозов «куда пойдёт цена»: только факты, уровни и состояния индикаторов.
7. Про Solana умеешь: состояние сети, баланс и токены кошелька, историю транзакций, запрос на оплату в Solana Pay (ссылка + QR) и котировку обмена через Jupiter. Ключей у тебя нет и быть не должно: платежи и обмены человек делает из своего кошелька. Если нужен адрес, а его не назвали — возьми кошелёк по умолчанию; если и его нет, попроси адрес одной короткой фразой, не выдумывай.
8. Если вопрос не о рынке — коротко ответь по существу без инструментов.
"""

MAX_STEPS = 5


def split_spoken(text: str) -> tuple[str, str]:
    """Делит ответ на устную часть и подробности: их разделяет строка `---`."""
    if not text:
        return "", ""
    for sep in ("\n---\n", "\n---", "---\n", "---"):
        if sep in text:
            head, _, tail = text.partition(sep)
            return head.strip(), tail.strip()
    return text.strip(), ""



@dataclass
class AgentResult:
    text: str
    charts: list[Path] = field(default_factory=list)
    trace: list[str] = field(default_factory=list)


def answer(question: str, history: list[dict] | None = None,
           allow_tools: bool = True) -> AgentResult:
    tools.ARTIFACTS.clear()
    messages: list[dict] = [{"role": "system", "content": SYSTEM_PROMPT}]
    if history:
        messages.extend(history[-6:])
    messages.append({"role": "user", "content": question})

    trace: list[str] = []
    for _ in range(MAX_STEPS):
        reply = chat(messages, tools=tools.TOOL_SCHEMAS if allow_tools else None)
        if not reply.tool_calls:
            return AgentResult(text=reply.content or "Не смог сформулировать ответ.",
                               charts=list(tools.ARTIFACTS), trace=trace)

        messages.append({
            "role": "assistant",
            "content": reply.content or "",
            "tool_calls": [
                {"id": c["id"], "type": "function",
                 "function": {"name": c["name"], "arguments": __import__("json").dumps(c["args"],
                                                                                      ensure_ascii=False)}}
                for c in reply.tool_calls
            ],
        })
        for call in reply.tool_calls:
            result = tools.execute(call["name"], call["args"])
            trace.append(f"{call['name']}({call['args']})")
            messages.append({"role": "tool", "tool_call_id": call["id"], "content": result})

    return AgentResult(text="Слишком много шагов для одного вопроса — уточни, пожалуйста.",
                       charts=list(tools.ARTIFACTS), trace=trace)
