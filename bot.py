import os
import asyncio
from flask import Flask
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler
import ccxt

# Servidor para que Render mantenga el bot activo
app = Flask(__name__)
@app.route('/')
def home(): return "Solana Sniper Activo 🚀"

async def start(update: Update, context):
    await update.message.reply_text(
        "💪 ¡Hola! Tu asistente de inversiones está en línea.\n\n"
        "Analizando BTC, ETH y la red de Solana.\n"
        "Recuerda: Operamos con el equilibrio de un profesional."
    )

async def run_bot():
    token = os.getenv("TELEGRAM_TOKEN")
    if not token:
        print("Error: No se encontró el TELEGRAM_TOKEN")
        return
    
    app_bot = ApplicationBuilder().token(token).build()
    app_bot.add_handler(CommandHandler("start", start))
    
    await app_bot.initialize()
    await app_bot.start_polling()
    print("Bot activo y rastreando...")

if __name__ == "__main__":
    from threading import Thread
    # Inicia el servidor web en un hilo aparte
    port = int(os.environ.get("PORT", 5000))
    Thread(target=lambda: app.run(host="0.0.0.0", port=port)).start()
    # Inicia el bot de Telegram
    asyncio.run(run_bot())
