"""Telegram-бот: голос или текст → ответ голосом и текстом, плюс график."""
from __future__ import annotations

import asyncio
import logging
import sys

from telegram import Update
from telegram.constants import ChatAction
from telegram.error import NetworkError, RetryAfter, TimedOut
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from . import audio, config, stt, tts
from .agent import answer

logging.basicConfig(format="%(asctime)s %(levelname)s %(name)s: %(message)s", level=logging.INFO)
# httpx/PTB логируют полные URL запросов, а в них — токен бота. Гасим, чтобы токен не попадал в лог.
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("telegram.ext").setLevel(logging.WARNING)
logging.getLogger("apscheduler").setLevel(logging.WARNING)
log = logging.getLogger("voice-market-agent")

HELP = (
    "Voice Market Agent — спроси рынок голосом.\n\n"
    "• Отправь голосовое: «что с биткоином на четырёхчасовом?»\n"
    "• Или текстом: «покажи график эфира за день»\n\n"
    "Умею: цена, RSI, SMA20, полосы Боллинджера, объём, индекс страха и жадности, графики."
)

HISTORY: dict[int, list[dict]] = {}


async def with_retry(fn, *args, attempts: int = 3, **kwargs):
    """Отправка в Telegram может отвалиться по таймауту — повторяем с паузой."""
    delay = 1.5
    for attempt in range(1, attempts + 1):
        try:
            return await fn(*args, **kwargs)
        except RetryAfter as e:
            await asyncio.sleep(float(e.retry_after) + 0.5)
        except (TimedOut, NetworkError) as e:
            if attempt == attempts:
                raise
            log.warning("отправка не прошла (%s), попытка %d/%d",
                        e.__class__.__name__, attempt, attempts)
            await asyncio.sleep(delay)
            delay *= 2


async def safe_action(ctx: ContextTypes.DEFAULT_TYPE, chat_id: int, action: str) -> None:
    try:
        await ctx.bot.send_chat_action(chat_id, action)
    except Exception:  # noqa: BLE001 — индикатор набора не критичен
        pass


async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await with_retry(update.message.reply_text, HELP)


async def _handle_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE, question: str,
                       reply_as_voice: bool) -> None:
    chat_id = update.effective_chat.id
    await safe_action(ctx, chat_id, ChatAction.TYPING)

    try:
        result = answer(question, history=HISTORY.get(chat_id))
    except Exception as e:  # noqa: BLE001
        log.exception("agent failed")
        await with_retry(update.message.reply_text, f"Ошибка агента: {e}"[:400])
        return

    log.info("инструменты: %s | графиков: %d", result.trace or "нет", len(result.charts))

    HISTORY.setdefault(chat_id, []).extend(
        [{"role": "user", "content": question}, {"role": "assistant", "content": result.text}])
    HISTORY[chat_id] = HISTORY[chat_id][-8:]

    await with_retry(update.message.reply_text, result.text)

    for chart in result.charts:
        try:
            with open(chart, "rb") as fh:
                await with_retry(update.message.reply_photo, fh)
        except Exception as e:  # noqa: BLE001
            log.warning("не удалось отправить график %s: %s", chart, e)

    if reply_as_voice and config.TTS_ENABLED:
        await safe_action(ctx, chat_id, ChatAction.RECORD_VOICE)
        try:
            voice_file = tts.synthesize(result.text, as_voice=True)
            with open(voice_file, "rb") as fh:
                await with_retry(update.message.reply_voice, fh)
        except tts.TTSError as e:
            log.info("TTS пропущен: %s", e)
        except Exception as e:  # noqa: BLE001
            log.warning("отправка голоса не удалась: %s", e)


async def on_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await _handle_text(update, ctx, update.message.text or "", reply_as_voice=False)


async def on_voice(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    voice = update.message.voice or update.message.audio
    if voice is None:
        return

    await safe_action(ctx, chat_id, ChatAction.TYPING)
    tg_file = await ctx.bot.get_file(voice.file_id)
    ogg = config.TMP_DIR / f"{chat_id}_{voice.file_unique_id}.ogg"
    await tg_file.download_to_drive(custom_path=str(ogg))

    try:
        wav = audio.to_wav16k(ogg)
        transcript = stt.transcribe(wav)
    except Exception as e:  # noqa: BLE001
        log.exception("STT failed")
        await with_retry(update.message.reply_text, f"Не смог распознать голос: {e}"[:300])
        return

    text = transcript.text.strip()
    if not text:
        await with_retry(update.message.reply_text,
                         "В записи не разобрал ни слова — попробуй ещё раз.")
        return

    await with_retry(update.message.reply_text, f"🎧 «{text}»")
    await _handle_text(update, ctx, text, reply_as_voice=True)


async def on_error(update: object, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    log.error("обработка апдейта упала: %s", ctx.error)
    if isinstance(update, Update) and update.effective_message:
        try:
            await update.effective_message.reply_text(
                "Сорвалась связь с Telegram — повтори сообщение, пожалуйста.")
        except Exception:  # noqa: BLE001
            pass


def main() -> None:
    if not config.TELEGRAM_BOT_TOKEN:
        sys.exit("TELEGRAM_BOT_TOKEN не задан")
    app = (Application.builder()
           .token(config.TELEGRAM_BOT_TOKEN)
           .connect_timeout(20)
           .read_timeout(30)
           .write_timeout(60)
           .pool_timeout(10)
           .build())
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_start))
    app.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, on_voice))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))
    app.add_error_handler(on_error)
    log.info("Voice Market Agent запущен (STT: %s, TTS: %s)", config.STT_MODE,
             "on" if tts.available() else "off")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
