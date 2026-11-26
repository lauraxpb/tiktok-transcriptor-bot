import os
import re
import tempfile
import logging

import yt_dlp
import whisper
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, ContextTypes, filters

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "PON_TU_TOKEN_AQUI")

WHISPER_MODEL = whisper.load_model("small")

TIKTOK_REGEX = re.compile(r"(https?://\S*tiktok\.com\S*)")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text or ""
    match = TIKTOK_REGEX.search(text)

    if not match:
        await update.message.reply_text(
            "Mándame un link de TikTok (algo como https://www.tiktok.com/@usuario/video/...)."
        )
        return

    url = match.group(1)
    status_msg = await update.message.reply_text("Descargando audio... 🎧")

    with tempfile.TemporaryDirectory() as tmpdir:
        audio_path = os.path.join(tmpdir, "audio.mp3")

        ydl_opts = {
            "format": "best",
            "outtmpl": os.path.join(tmpdir, "audio.%(ext)s"),
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }],
            "quiet": True,
            "noplaylist": True,
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
        except Exception as e:
            logger.exception("Error descargando el TikTok")
            await status_msg.edit_text(f"No pude descargar ese TikTok 😕\n({e})")
            return

        if not os.path.exists(audio_path):
            await status_msg.edit_text("No encontré el audio descargado, intenta con otro link.")
            return

        await status_msg.edit_text("Transcribiendo... 📝 (puede tardar un poco)")

        try:
            result = WHISPER_MODEL.transcribe(audio_path, language="es")
            transcript = result["text"].strip()
        except Exception as e:
            logger.exception("Error transcribiendo")
            await status_msg.edit_text(f"Error al transcribir 😕\n({e})")
            return

    if not transcript:
        await status_msg.edit_text("No detecté texto hablado en ese video.")
        return

    await status_msg.edit_text("Listo ✅ Aquí está la transcripción:")
    for i in range(0, len(transcript), 4000):
        await update.message.reply_text(transcript[i:i + 4000])


def main():
    if BOT_TOKEN == "PON_TU_TOKEN_AQUI":
        raise SystemExit("Configura tu token en la variable TELEGRAM_BOT_TOKEN.")

    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("Bot iniciado. Esperando mensajes...")
    app.run_polling()


if __name__ == "__main__":
    main()
