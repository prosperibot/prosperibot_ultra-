import os
import requests
from flask import Flask
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from threading import Thread

app = Flask(__name__)
@app.route('/')
def home(): return "Solana Sniper & Radar Activo 🚀"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

# --- NUEVA FUNCIÓN: SCANNER DE SOLANA ---
async def sniper_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔎 Escaneando la red de Solana... Dame un momento.")
    
    try:
        # Llamada a DexScreener para ver tokens tendencia en Solana
        url = "https://api.dexscreener.com/latest/dex/search?q=solana"
        response = requests.get(url).json()
        pairs = response.get('pairs', [])[:5] # Tomamos los 5 principales

        if not pairs:
            await update.message.reply_text("No encontré movimientos claros ahora. El mercado está muy quieto.")
            return

        reporte = "🚀 **TOP 5 TRENDING SOLANA (Sniper Mode)**\n\n"
        for p in pairs:
            nombre = p.get('baseToken', {}).get('name', 'N/A')
            simbolo = p.get('baseToken', {}).get('symbol', 'N/A')
            precio = p.get('priceUsd', '0')
            volumen = p.get('volume', {}).get('h24', 0)
            liqiudez = p.get('liquidity', {}).get('usd', 0)
            
            reporte += f"🔹 **{nombre} ({simbolo})**\n"
            reporte += f"💵 Precio: `${precio}`\n"
            reporte += f"📊 Vol 24h: `${volumen:,.0f}`\n"
            reporte += f"💧 Liq: `${liqiudez:,.0f}`\n"
            reporte += "--- \n"

        reporte += "\n⚠️ *Recordatorio:* Con Miedo Extremo (9/100), verifica siempre la liquidez antes de entrar. No operes por ansiedad."
        await update.message.reply_text(reporte, parse_mode='Markdown')

    except Exception as e:
        await update.message.reply_text(f"❌ Error al escanear: {str(e)}")

# --- HANDLER INICIAL ---
async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "💪 ¡Radar Listo, MC Losibe!\n\n"
        "Usa `/sniper` para ver qué se está moviendo en Solana ahora mismo.\n"
        "Recuerda que estamos en zona de pánico (9/100). Mantén el equilibrio profesional."
    )

if __name__ == "__main__":
    Thread(target=run_flask, daemon=True).start()

    token = os.getenv("TELEGRAM_TOKEN")
    if token:
        application = ApplicationBuilder().token(token).build()
        application.add_handler(CommandHandler("start", start_handler))
        application.add_handler(CommandHandler("sniper", sniper_handler)) # Activamos el sniper
        
        print("🤖 Sniper configurado y listo...")
        application.run_polling(drop_pending_updates=True)
