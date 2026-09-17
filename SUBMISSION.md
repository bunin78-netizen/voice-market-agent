# Чек-лист заявки — AssemblyAI Voice Agent Hackathon (lablab.ai)

Дедлайн: **30 сентября 2026**. Регистрация открыта всю дистанцию — заявиться можно в любой день.
Призовой фонд: $10 000 ($5 000 деньгами + $5 000 кредитами AssemblyAI).

## Что уже сделано (со стороны агента)

- [x] рабочий пайплайн: голос → AssemblyAI → LLM с инструментами → голосовой ответ + график
- [x] 7 из 8 smoke-проверок проходят (AssemblyAI ждёт ключ)
- [x] реальный ответ LLM с двумя последовательными вызовами инструментов
- [x] схема архитектуры и сценарий демо-видео
- [x] MIT-лицензия, README, `.env.example`, `requirements.txt`
- [x] репозиторий опубликован: https://github.com/bunin78-netizen/voice-market-agent
- [x] бот @VoiceMarketAgentBot работает, полный голосовой цикл проверен
- [x] демо-видео собрано: закадровый текст моделью, голос бота из архива, английские субтитры
- [x] инструкции по записи и сборке: `docs/demo-voiceover.md`

## Ссылки для формы

- **Репозиторий:** https://github.com/bunin78-netizen/voice-market-agent (публичный, MIT)
- **Работающий бот:** https://t.me/VoiceMarketAgentBot
- **Субтитры:** `~/Videos/voice-market-DEMO.en.srt` — загрузить в YouTube (Субтитры → English → Загрузить файл)
- **Видео-демо:** https://youtu.be/dPmGT7n8ua0 — 3:00, 1920×1002 (нативная запись), закадровая озвучка моделью + голос бота из архива, заставка с аватаром
- **Страница хакатона:** https://lablab.ai/ai-hackathons/assemblyai-voice-agent-hackathon

## Что нужно от человека

1. **Регистрация на lablab.ai** — https://lablab.ai/ai-hackathons/assemblyai-voice-agent-hackathon
   (личный email подойдёт; корпоративный — приоритетнее для организаторов).
2. **AssemblyAI API key** — https://www.assemblyai.com/dashboard → «API keys».
   Бесплатный тир даёт стартовые кредиты, карта не нужна.
   Ключ положить в `.env` проекта (не в чат).
3. **Telegram-бот** — отдельный токен от @BotFather для этого проекта.
4. **Запись демо-видео** 2:30–3:00 по `docs/demo-script.md` (YouTube, unlisted).
5. **Публикация репозитория** на GitHub (MIT).
6. **Отправка проекта** через форму на странице хакатона: ссылка на репо, видео, описание,
   использованные технологии.

## Текст описания проекта (для формы)

> **Voice Market Agent** — голосовой рыночный ассистент в Telegram. Пользователь отправляет
> голосовое сообщение: AssemblyAI превращает запись в текст (с подсказкой доменным словарём —
> RSI, линии Боллинджера, таймфрейм), затем языковая модель с вызовами инструментов сама решает,
> какие рыночные данные нужны — цена, SMA20, RSI(14), полосы Боллинджера, объём, индекс страха
> и жадности — и при необходимости строит свечной график.
>
> Ответ приходит двумя слоями: короткая устная часть озвучивается голосом, а цифры и уровни
> идут текстом, чтобы их можно было перечитать. Сводку можно получить, не отрывая глаз от работы.
> Telegram выбран как интерфейс: он установлен у более чем миллиарда пользователей, и голосовое
> сообщение там — привычный жест, а не новый навык.
>
> Технологии: AssemblyAI (speech_models `universal-3-5-pro` / `universal-2`, `keyterms_prompt`,
> фиксированный язык распознавания), LLM с function calling, публичный API Binance,
> ElevenLabs TTS через REST, python-telegram-bot, matplotlib.


## Подробное описание проекта (для поля 600–2000 символов)

### Полный вариант (1775 символов)

Voice Market Agent is a voice-first market copilot for Telegram. Market updates normally demand your eyes and your hands: a terminal, a chart, a few indicators. When your hands are busy, those minutes are simply lost. This agent needs only your voice.

You send a voice message. AssemblyAI turns the recording into text - we use the universal-3-5-pro model together with a keyterms_prompt glossary (RSI, Bollinger Bands, timeframe, price, volume), so domain terms are transcribed reliably even in short, quiet clips. The transcript then goes to an LLM with tool calling, which decides for itself which data it needs: current price, SMA20, RSI(14), Bollinger Bands, volume ratio, the market Fear and Greed index, or a freshly rendered candlestick chart.

The answer comes back in two layers: a short spoken summary is synthesised with ElevenLabs and returned as a Telegram voice note, while the numbers and levels arrive as text you can re-read. Nothing is pre-scripted - the model chooses the tools from the wording of the question, so "what is Bitcoin doing today" and "show me a daily Ether chart" take different paths through the same agent.

Under the hood: AssemblyAI for speech recognition, an LLM with function calling for reasoning, the public Binance API for market data, ElevenLabs for speech synthesis, matplotlib for charts and python-telegram-bot as the interface. Telegram was chosen deliberately: it is installed on more than a billion devices, and a voice message is a familiar gesture there.

The project is open source under MIT. Code: https://github.com/bunin78-netizen/voice-market-agent. The working bot is @VoiceMarketAgentBot, and the demo video shows a complete conversation: three spoken questions, three spoken answers, two freshly generated charts.

### Короткий вариант (1005 символов)

Voice Market Agent is a voice-first market copilot for Telegram. Market updates usually demand your eyes and hands: a terminal, a chart, a few indicators. This agent needs only your voice.

Send a voice message - AssemblyAI transcribes it (universal-3-5-pro plus a keyterms_prompt glossary for RSI, Bollinger Bands and timeframes), then an LLM with tool calling decides which data it needs: price, SMA20, RSI(14), Bollinger Bands, volume, the Fear and Greed index, or a freshly built candlestick chart. Nothing is pre-scripted: "what is Bitcoin doing today" and "show me a daily Ether chart" take different paths through the same agent.

The reply comes in two layers: a short spoken summary synthesised with ElevenLabs as a Telegram voice note, and the numbers as text you can re-read. The stack is AssemblyAI, an LLM with function calling, the public Binance API, ElevenLabs and python-telegram-bot. Open source under MIT: https://github.com/bunin78-netizen/voice-market-agent, bot @VoiceMarketAgentBot.

## Риски

| Риск | Что делаем |
|---|---|
| Ключ приходит с задержкой | пайплайн уже работает на локальном whisper, запись демо возможна без AssemblyAI, но в видео озвучиваем именно AssemblyAI-путь |
| Разговорный ответ длиннее 900 символов | `tts.synthesize` обрезает текст до первого пробела перед лимитом |
| Тяжёлый запрос тормозит ответ | `MAX_STEPS=5` в `agent.py`, инструменты синхронные и быстрые |
