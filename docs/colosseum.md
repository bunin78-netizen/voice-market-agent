# Colosseum — Crypto World's Fair: текст заявки

Дедлайн: **12 октября 2026** (по данным сайта — отсчёт 25 дней от 17.09).
Регистрация: https://www.colosseum.org → аккаунт через GitHub или Google.
Победители попадают в акселератор Colosseum с $250 000 финансирования.

---

## Project name

Voice Market Agent

## One-liner (до 100 символов)

A voice-first copilot for market data and Solana — ask by voice, get an answer out loud.

## Description (для основного поля)

Voice Market Agent is a Telegram bot that answers market and Solana questions **out loud**.
You send a voice message; AssemblyAI transcribes it; an LLM with tool calling decides which
data it needs; the answer comes back as a voice note, with the numbers in writing and a chart
rendered on demand.

**The problem.** Market data and on-chain data are built for eyes and hands. A trader
glancing at a terminal, a Solana user checking a wallet — both need a screen, an app and a
free pair of hands. Telegram already sits on more than a billion devices, and a voice message
is a familiar gesture there. We use that instead of asking people to adopt a new tool.

**What it does today.** Two families of questions, answered from live sources:
* market — price, SMA20, RSI(14), Bollinger Bands, volume, the Fear & Greed index, and
  candlestick charts;
* Solana — network state (slot, epoch, throughput, slot time), wallet balance and recent
  transaction history.

Nothing is pre-scripted: the model chooses the tools from the wording of the question. The
answer is split in two layers — a short spoken summary for listening, and the numbers as text
for re-reading, because listening and reading are different jobs.

## Solana integration

The agent talks to Solana directly over a **public JSON-RPC endpoint** — no API keys and no
custodial accounts:

* network state: `getVersion`, `getSlot`, `getEpochInfo`, `getRecentPerformanceSamples`;
* wallets: `getBalance`, `getSignaturesForAddress` (including failed transactions).

Engineering notes:

* endpoint failover — `api.mainnet-beta.solana.com` first, a public fallback node second;
* addresses validated locally (base58, 32–44 characters) before any request, so a misheard
  address produces a clear answer instead of a failed call;
* an optional default wallet for "my wallet" questions: dictating a 44-character address by
  voice is unrealistic, so the address is configured once;
* three tools exposed to the model — `get_solana_network`, `get_sol_balance`,
  `get_my_sol_balance` — alongside the market tools.

Live example: "how is the Solana network doing" returns the current slot, epoch progress and
live throughput from mainnet; "how much SOL is on my wallet" returns the balance of the
configured address.

## Links

* Live product: https://t.me/VoiceMarketAgentBot (send a voice message, Russian or English)
* Demo video: https://youtu.be/ksVNBLllp-w (2 minutes, English subtitles)
* Code (MIT): https://github.com/bunin78-netizen/voice-market-agent

## Track

AI / Consumer — a voice interface to market and on-chain data. (Выбрать ближайший из списка
треков на сайте: если есть «AI» или «Consumer», брать его.)

## Team

Viacheslav — solo founder and developer. Backend and bots in Python, trading systems,
Telegram services; the whole product — speech pipeline, tool calling, voice synthesis and
the demo pipeline — built and shipped by one person.

## Roadmap

* streaming recognition for lower latency;
* portfolio-aware answers: the agent knows the user's positions, not just the market;
* on-chain actions through a connected wallet — swap, transfer, stake — confirmed by voice;
* more venues and instruments beyond the current Binance + Solana pair.

## Deployment

Runs 24/7 on a small always-on Ubuntu host; a cron watchdog restarts the bot within five
minutes if it dies. External services: AssemblyAI (speech-to-text), an LLM with function
calling, ElevenLabs (text-to-speech), the public Binance API and the public Solana RPC.
No user keys are collected or stored — the bot only reads public data.
