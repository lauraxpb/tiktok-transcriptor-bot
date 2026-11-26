# Bot de Telegram para transcribir TikToks

Pegas el enlace de un TikTok en el chat y el bot te devuelve la transcripción del audio (usa Whisper en local, sin APIs de pago).

## Requisitos
- Python 3.10+
- ffmpeg (`sudo apt install ffmpeg`)
- Un bot propio: crea uno con [@BotFather](https://t.me/BotFather) y copia el token

## Instalación
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Uso
```bash
export TELEGRAM_BOT_TOKEN="tu_token"
python bot_tiktok_transcriptor.py
```
Luego pega un enlace de TikTok en el chat con tu bot.

> No subas nunca tu token a GitHub.
