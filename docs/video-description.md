# Описание для YouTube (демо Solana)

## Название

Voice Market Agent — voice-first market & Solana copilot (demo)

## Описание (копировать целиком)

Ask the market — by voice.

Voice Market Agent is a Telegram bot that answers market and Solana questions out
loud. You send a voice message; AssemblyAI transcribes it; an LLM with tool calling
decides which data it needs; the answer comes back as a voice note, with the numbers
in writing and a chart on demand.

In this demo:

0:00 intro
0:15 "What is Bitcoin doing today?" — price, SMA20, RSI(14), Bollinger Bands, and a chart rendered on the spot
0:54 "How is the Solana network doing?" — network state read live from Solana: slot, epoch, throughput
1:34 "How much SOL is on my wallet?" — wallet balance read straight from the chain

Solana integration:
- talks to Solana over a public JSON-RPC endpoint, no API keys required
- methods used: getVersion, getSlot, getEpochInfo, getRecentPerformanceSamples, getBalance, getSignaturesForAddress
- endpoint failover between api.mainnet-beta.solana.com and a public fallback node
- addresses are validated locally before any request, so a misheard address gets a clear answer instead of a failed call
- optional default wallet for "my wallet" questions

Under the hood: AssemblyAI (speech recognition), an LLM with function calling,
ElevenLabs (speech synthesis), the public Binance API (market data), public Solana RPC,
python-telegram-bot and matplotlib.

Bot: https://t.me/VoiceMarketAgentBot
Code (MIT): https://github.com/bunin78-netizen/voice-market-agent

Narration is in Russian; English subtitles are available in the player.
