import os
from flask import Flask
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
import ccxt

# 1. Configuración del Servidor Web (para mantener Render vivo)
app = Flask(__name__)

@app.route('/')
def home():
    return "Solana Sniper Activo y Vigilando 🚀"

# 2. Lógica del Bot
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 ¡Hola! Tu asistente profesional está en línea.\n\n"
        "📊 **Mercado (22 Abr, 2026):** Miedo Extremo (9/100).\n"
        "Recuerda: Acepto el cambio y opero con equilibrio."
    )

def run_bot():
    token = os.getenv("TELEGRAM_TOKEN")
    if not token:
        print("Error: No se encontró el TELEGRAM_TOKEN")
        return

    # Creamos la aplicación (Forma moderna v20+)
    application = ApplicationBuilder().token(token).build()
    
    # Añadimos el comando de inicio
    application.add_handler(CommandHandler("start", start))
    
    # Encendemos el bot de forma estable
    print("🤖 Bot de Telegram iniciando...")
    application.run_polling()

if __name__ == "__main__":
    from threading import Thread
    
    # Lanzar Flask en un hilo aparte
    port = int(os.environ.get("PORT", 10000))
    Thread(target=lambda: app.run(host="0.0.0.0", port=port)).start()
    
    # Lanzar el bot de Telegram directamente
    run_bot()
