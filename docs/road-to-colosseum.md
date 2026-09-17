# Road to Colosseum — submission text

## Project Name & Tagline

**Voice Market Agent** — a voice-first market and Solana copilot for Telegram.

## Problem & Product

Market data is built for eyes and hands: a terminal, a chart, a list of indicators.
When your hands are busy — driving, working, cooking — those minutes are lost, and
checking a wallet or the state of a network means opening yet another app.

Voice Market Agent removes the screen from the loop. You send a voice message to a
Telegram bot; AssemblyAI transcribes it; an LLM with tool calling decides what data it
needs; the answer comes back **out loud** and in writing, with a chart when it helps.

Two things it answers today:

* market questions — price, SMA20, RSI(14), Bollinger Bands, volume, the Fear & Greed index,
  and a freshly rendered candlestick chart;
* Solana questions — network state (slot, epoch, throughput, slot time) and wallet data
  (SOL balance, recent transactions).

Nothing is pre-scripted: the model picks the tools from the wording of the question, so
"What is Bitcoin doing today" and "how is the Solana network doing" take different paths
through the same agent.

## Solana Integration

The agent talks to Solana directly over a **public JSON-RPC endpoint** — no API keys,
no custodial accounts:

* `getVersion`, `getSlot`, `getEpochInfo`, `getRecentPerformanceSamples` — network status
  (node version, current slot, epoch progress, average TPS and slot time);
* `getBalance` — SOL balance of any address;
* `getSignaturesForAddress` — recent transaction history, including failures.

Implementation notes:

* `src/solana.py` wraps the RPC with an endpoint failover —
  `api.mainnet-beta.solana.com` first, `solana-rpc.publicnode.com` as a fallback;
* addresses are validated locally (base58, 32–44 characters) before any request, so a
  misheard address produces a clear answer instead of a failed call;
* the agent can use a configured default wallet for "my wallet" questions — dictating a
  44-character address by voice is unrealistic;
* three tools are exposed to the model: `get_solana_network`, `get_sol_balance`,
  `get_my_sol_balance`, alongside the market tools.

Example, verified in the demo: "how is the Solana network doing" returns the current slot,
epoch progress and ~4,500 TPS read live from mainnet; "how much SOL is on my wallet"
returns the balance of the configured address.

## Live MVP / Test Link

https://t.me/VoiceMarketAgentBot — send a voice message (Russian or English).

## Demo Video

https://youtu.be/ksVNBLllp-w — 2 minutes, English subtitles in the player

## Public GitHub Repository

https://github.com/bunin78-netizen/voice-market-agent (MIT)

## Deployment Details

* Runs 24/7 on a small always-on Ubuntu host; the bot process is supervised by a cron
  watchdog that restarts it within five minutes if it dies.
* External services: AssemblyAI (speech-to-text), an LLM with function calling for
  reasoning, ElevenLabs (text-to-speech), public Binance API (market data) and the public
  Solana RPC. No user keys are collected or stored.
* The demo video was produced with the same repository: silent screen capture, generated
  narration, the bot's own voice replies and subtitles with timings taken from the
  finished file.
