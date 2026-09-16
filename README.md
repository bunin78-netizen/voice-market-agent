# Voice Market Agent — голосовой копайлот рынка для Telegram

> Заявка на **AssemblyAI - Voice Agent Hackathon** (lablab.ai, 1–30 сентября 2026, $10 000 призовой фонд)

Агент принимает **голосовое сообщение** в Telegram, распознаёт его через AssemblyAI,
сам решает, какие рыночные данные ему нужны (цена, RSI, полосы Боллинджера, индекс страха и жадности),
строит график и **отвечает голосом** — на языке собеседника.

Проблема, которую решаем: трейдер/аналитик получает рыночную сводку только глазами — терминал, графики,
таблицы. Руки заняты, глаза заняты. Voice Market Agent даёт тот же ответ там, где человек уже находится:
в мессенджере, голосом, без интерфейса.

## Как это работает

```
Telegram voice note (OGG/Opus)
        │
        ▼
ffmpeg → WAV 16 kHz mono
        │
        ▼
AssemblyAI  /v2/upload → /v2/transcript   ← распознавание речи (ru/en, авто-детект языка)
        │
        ▼
LLM (DeepSeek / OpenRouter) + tool calling
        │   ├── get_price(symbol)
        │   ├── get_indicators(symbol, interval)   RSI(14), SMA(20), BB(20,2)
        │   ├── get_market_snapshot()               BTC / ETH / SOL
        │   ├── get_fear_greed()
        │   └── make_chart(symbol, interval)        PNG-график
        ▼
Ответ: текст + голос (ElevenLabs) + график
```

Подробнее — [`docs/architecture.md`](docs/architecture.md).

## Что нужно для запуска

1. Telegram-бот (уже есть у проекта — `CONTENT_BOT_TOKEN` или отдельный)
2. **AssemblyAI API key** — бесплатный тир, [assemblyai.com/dashboard](https://www.assemblyai.com/dashboard)
3. LLM key — DeepSeek или OpenRouter
4. `ffmpeg` в PATH (для конвертации голосовых)
5. Опционально: `ELEVENLABS_API_KEY` — для голосового ответа (REST напрямую; CLI `sag` используется как резерв)

```bash
cp .env.example .env        # заполнить ключи
pip install -r requirements.txt
python -m src.bot           # запустить бота
```

## Проверка без внешних ключей

```bash
python scripts/smoke_test.py        # прогон всего пайплайна на заглушках STT/TTS
```

## Структура

| Файл | Назначение |
|---|---|
| `src/audio.py` | конвертация OGG/Opus → WAV 16 kHz mono через ffmpeg |
| `src/stt.py` | AssemblyAI (upload + polling), локальный whisper как dev-fallback |
| `src/llm.py` | вызов LLM с tool calling (DeepSeek / OpenRouter, OpenAI-совместимый) |
| `src/market.py` | публичные данные Binance + индикаторы (RSI, SMA, BB) + Fear & Greed |
| `src/chart.py` | свечной график с SMA/BB и панелью RSI (matplotlib) |
| `src/tools.py` | схемы инструментов и их исполнение |
| `src/agent.py` | цикл «вопрос → инструменты → ответ» |
| `src/bot.py` | Telegram-бот: голос/текст → ответ голосом/текстом |
| `scripts/smoke_test.py` | оффлайн-проверка пайплайна |

## Лицензия

MIT — см. `LICENSE`.
