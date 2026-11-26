"""
Bot de Telegram: transcribe TikToks pegando solo el enlace.
Muestra botones para elegir el idioma antes de transcribir.

Uso: export TELEGRAM_BOT_TOKEN="..."  &&  python bot_tiktok_transcriptor.py
"""

import os
import re
import asyncio
import logging
import tempfile

import yt_dlp
import whisper
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CallbackQueryHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
WHISPER_MODEL = whisper.load_model("small")  # tiny / base / small / medium
TIKTOK_REGEX = re.compile(r"(https?://\S*tiktok\.com\S*)")

LANGS = {
    "auto": "🌐 Auto-detectar",
    "es": "🇪🇸 Español",
    "en": "🇬🇧 English",
    "fr": "🇫🇷 Français",
    "de": "🇩🇪 Deutsch",
    "it": "🇮🇹 Italiano",
    "pt": "🇵🇹 Português",
    "ja": "🇯🇵 日本語",
}


def build_keyboard(selected: str) -> InlineKeyboardMarkup:
    buttons = [
        InlineKeyboardButton(
            ("✅ " if code == selected else "") + label,
            callback_data=f"lang|{code}",
        )
        for code, label in LANGS.items()
    ]
    rows = [buttons[i:i + 2] for i in range(0, len(buttons), 2)]
    rows.append([InlineKeyboardButton("📝 Comenzar a transcribir", callback_data="go")])
    rows.append([InlineKeyboardButton("❌ Cancelar", callback_data="cancel")])
    return InlineKeyboardMarkup(rows)


def settings_text(lang: str) -> str:
    return (
        "Enlace recibido ✅\n\n"
        f"Idioma del video: {LANGS[lang]}\n\n"
        "Elige el idioma en el que se habla en el TikTok y pulsa "
        "«Comenzar a transcribir». Si no lo sabes, deja Auto-detectar."
    )


def download_audio(url: str, tmpdir: str) -> str:
    """Descarga el video completo (con la voz) y extrae el audio a mp3."""
    opts = {
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
    with yt_dlp.YoutubeDL(opts) as ydl:
        ydl.download([url])
    path = os.path.join(tmpdir, "audio.mp3")
    if not os.path.exists(path):
        raise FileNotFoundError("No se generó el audio.")
    return path


def transcribe(path: str, lang: str):
    language = None if lang == "auto" else lang
    result = WHISPER_MODEL.transcribe(path, language=language)
    return result["text"].strip(), result.get("language", lang)


async def on_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    match = TIKTOK_REGEX.search(update.message.text or "")
    if not match:
        await update.message.reply_text(
            "Mándame un link de TikTok (https://www.tiktok.com/@usuario/video/...)."
        )
        return

    msg = await update.message.reply_text(
        settings_text("auto"), reply_markup=build_keyboard("auto")
    )
    pending = context.chat_data.setdefault("pending", {})
    pending[msg.message_id] = {"url": match.group(1), "lang": "auto"}


async def on_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    pending = context.chat_data.setdefault("pending", {})
    msg_id = query.message.message_id
    state = pending.get(msg_id)

    if state is None:
        await query.edit_message_text("Esta solicitud caducó. Mándame el enlace otra vez.")
        return

    action = query.data

    if action.startswith("lang|"):
        state["lang"] = action.split("|", 1)[1]
        await query.edit_message_text(
            settings_text(state["lang"]), reply_markup=build_keyboard(state["lang"])
        )
        return

    if action == "cancel":
        pending.pop(msg_id, None)
        await query.edit_message_text("Cancelado ❌")
        return

    if action == "go":
        pending.pop(msg_id, None)
        url, lang = state["url"], state["lang"]

        await query.edit_message_text("Descargando audio... 🎧")
        with tempfile.TemporaryDirectory() as tmpdir:
            try:
                audio = await asyncio.to_thread(download_audio, url, tmpdir)
            except Exception as e:
                logger.exception("Error descargando")
                await query.edit_message_text(f"No pude descargar ese TikTok 😕\n({e})")
                return

            await query.edit_message_text("Transcribiendo... 📝 (puede tardar un poco)")
            try:
                text, detected = await asyncio.to_thread(transcribe, audio, lang)
            except Exception as e:
                logger.exception("Error transcribiendo")
                await query.edit_message_text(f"Error al transcribir 😕\n({e})")
                return

        if not text:
            await query.edit_message_text("No detecté texto hablado en ese video.")
            return

        header = "Listo ✅"
        if lang == "auto":
            header += f" (idioma detectado: {detected})"
        await query.edit_message_text(header)
        for i in range(0, len(text), 4000):
            await query.message.reply_text(text[i:i + 4000])


def main():
    if not BOT_TOKEN:
        raise SystemExit("Define la variable de entorno TELEGRAM_BOT_TOKEN.")
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_message))
    app.add_handler(CallbackQueryHandler(on_button))
    logger.info("Bot iniciado. Esperando mensajes...")
    app.run_polling()


if __name__ == "__main__":
    main()