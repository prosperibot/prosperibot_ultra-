import os
import httpx # Más rápido y asíncrono que requests
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from threading import Thread

app = Flask(__name__)
@app.route('/')
def home(): return "Solana Radar MC Losibe Activo 🚀"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

# --- UTILIDADES ---
async def get_market_sentiment():
    try:
        async with httpx.AsyncClient() as client:
            r = await client.get("https://api.alternative.me/fng/")
            data = r.json()
            return f"{data['data'][0]['value']}/100 ({data['data'][0]['value_classification']})"
    except:
        return "No disponible"

# --- SCANNER MEJORADO ---
async def sniper_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("🔎 Analizando contratos en Solana... filtrando basura...")
    
    try:
        sentiment = await get_market_sentiment()
        # Buscamos tokens recientes con volumen
        url = "https://api.dexscreener.com/latest/dex/search?q=solana"
        
        async with httpx.AsyncClient() as client:
            response = await client.get(url)
            data = response.json()
        
        pairs = data.get('pairs', [])
        # FILTRO CRÍTICO: Solo tokens con liquidez > $10,000 y que no sean el SOL real
        filtered_pairs = [
            p for p in pairs 
            if float(p.get('liquidity', {}).get('usd', 0)) > 10000 
            and p.get('baseToken', {}).get('symbol') != 'SOL'
        ][:5]

        if not filtered_pairs:
            await msg.edit_text("⚠️ No encontré tokens que superen los filtros de seguridad ahora.")
            return

        reporte = f"🚀 **SOLANA RADAR (Sniper Mode)**\n"
        reporte += f"📊 Sentimiento: `{sentiment}`\n"
        reporte += "----------------------------------\n\n"

        for p in filtered_pairs:
            nombre = p.get('baseToken', {}).get('name', 'N/A')
            simbolo = p.get('baseToken', {}).get('symbol', 'N/A')
            precio = p.get('priceUsd', '0')
            liq = float(p.get('liquidity', {}).get('usd', 0))
            vol = float(p.get('volume', {}).get('h24', 0))
            url_dex = p.get('url')

            reporte += f"🔹 **{nombre} ({simbolo})**\n"
            reporte += f"💵 `$ {precio}`\n"
            reporte += f"💧 Liq: `${liq:,.0f}` | 📈 Vol: `${vol:,.0f}`\n"
            reporte += f"🔗 [Ver en DexScreener]({url_dex})\n\n"

        reporte += "⚠️ *Consejo:* Si la liquidez es menor al volumen, procede con cautela extrema."
        
        await msg.edit_text(reporte, parse_mode='Markdown', disable_web_page_preview=True)

    except Exception as e:
        await msg.edit_text(f"❌ Error en el escaneo: {str(e)}")

# --- START PERSONALIZADO ---
async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_name = update.effective_user.first_name
    await update.message.reply_text(
        f"💪 ¡Radar Listo, MC Losibe!\n\n"
        "He integrado filtros de seguridad para evitar los honeypots de 'falso SOL'.\n\n"
        "📌 `/sniper` - Escaneo rápido de gemas.\n"
        "Mantén el equilibrio mental, el mercado es solo una danza."
    )

if __name__ == "__main__":
    # Necesitas instalar httpx: pip install httpx
    Thread(target=run_flask, daemon=True).start()

    token = os.getenv("TELEGRAM_TOKEN")
    if token:
        application = ApplicationBuilder().token(token).build()
        application.add_handler(CommandHandler("start", start_handler))
        application.add_handler(CommandHandler("sniper", sniper_handler))
        
        print("🤖 Bot Profesional configurado...")
        application.run_polling(drop_pending_updates=True)
