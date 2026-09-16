"""Telegram-бот: голос или текст → ответ голосом и текстом, плюс график."""
from __future__ import annotations

import logging

from telegram import Update
from telegram.constants import ChatAction
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


async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(HELP)


async def _handle_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE, question: str,
                       reply_as_voice: bool) -> None:
    chat_id = update.effective_chat.id
    await ctx.bot.send_chat_action(chat_id, ChatAction.TYPING)

    try:
        result = answer(question, history=HISTORY.get(chat_id))
    except Exception as e:  # noqa: BLE001
        log.exception("agent failed")
        await update.message.reply_text(f"Ошибка агента: {e}"[:400])
        return

    HISTORY.setdefault(chat_id, []).extend(
        [{"role": "user", "content": question}, {"role": "assistant", "content": result.text}])
    HISTORY[chat_id] = HISTORY[chat_id][-8:]

    await update.message.reply_text(result.text)

    for chart in result.charts:
        try:
            with open(chart, "rb") as fh:
                await update.message.reply_photo(fh)
        except Exception:  # noqa: BLE001
            log.warning("не удалось отправить график %s", chart)

    if reply_as_voice and config.TTS_ENABLED:
        await ctx.bot.send_chat_action(chat_id, ChatAction.RECORD_VOICE)
        try:
            voice_file = tts.synthesize(result.text, as_voice=True)
            with open(voice_file, "rb") as fh:
                await update.message.reply_voice(fh)
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

    await ctx.bot.send_chat_action(chat_id, ChatAction.TYPING)
    tg_file = await ctx.bot.get_file(voice.file_id)
    ogg = config.TMP_DIR / f"{chat_id}_{voice.file_unique_id}.ogg"
    await tg_file.download_to_drive(custom_path=str(ogg))

    try:
        wav = audio.to_wav16k(ogg)
        transcript = stt.transcribe(wav)
    except Exception as e:  # noqa: BLE001
        log.exception("STT failed")
        await update.message.reply_text(f"Не смог распознать голос: {e}"[:300])
        return

    text = transcript.text.strip()
    if not text:
        await update.message.reply_text("В записи не разобрал ни слова — попробуй ещё раз.")
        return

    await update.message.reply_text(f"🎧 «{text}»")
    await _handle_text(update, ctx, text, reply_as_voice=True)


def main() -> None:
    if not config.TELEGRAM_BOT_TOKEN:
        raise SystemExit("TELEGRAM_BOT_TOKEN не задан")
    app = Application.builder().token(config.TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_start))
    app.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, on_voice))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))
    log.info("Voice Market Agent запущен (STT: %s, TTS: %s)", config.STT_MODE,
             "on" if tts.available() else "off")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
