import os
import httpx
import asyncio
import google.generativeai as genai
from flask import Flask
from telegram import Update, constants
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters
from threading import Thread

# --- CONFIGURACIÓN DE IA (GEMINI) ---
# Recuerda que en tu panel debe llamarse exactamente: GEMINI_API_KEY
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model = genai.GenerativeModel('gemini-1.5-flash')
chat_sessions = {}

# --- MEMORIA LOCAL Y CONFIGURACIÓN ---
user_prefs = {
    "min_liquidity": 20000,
    "style": "Analítico, empático y creativo",
    "last_instruction": "Ninguna"
}

app = Flask(__name__)
@app.route('/')
def home(): return "Mente Maestra MC Losibe Online 🧠🚀"

# --- UTILIDADES DE MERCADO ---
async def fetch_global_market():
    """Obtiene el top de criptos globales desde CoinGecko"""
    url = "https://api.coingecko.com/api/v3/coins/markets"
    params = {
        "vs_currency": "usd",
        "ids": "bitcoin,ethereum,solana,binancecoin,ripple,cardano",
        "order": "market_cap_desc"
    }
    async with httpx.AsyncClient() as client:
        r = await client.get(url, params=params, timeout=10)
        return r.json()

async def fetch_solana_trends():
    """Busca tokens tendencia en Solana vía DexScreener"""
    url = "https://api.dexscreener.com/latest/dex/search?q=solana"
    async with httpx.AsyncClient() as client:
        r = await client.get(url, timeout=10)
        return r.json().get('pairs', [])

# --- COMANDO: MERCADO GLOBAL ---
async def mercado_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("🌐 Consultando el pulso del mercado global...")
    try:
        data = await fetch_global_market()
        reporte = "🌍 **ESTADO DEL MERCADO CRYPTO**\n"
        reporte += "----------------------------------\n"
        
        for coin in data:
            change = coin['price_change_percentage_24h']
            emoji = "📈" if change > 0 else "📉"
            reporte += f"{emoji} **{coin['name']}**: `${coin['current_price']:,.2f}` ({change:.2f}%)\n"
        
        reporte += "\n💡 _El mercado es una frecuencia, aprende a sintonizarla._"
        await msg.edit_text(reporte, parse_mode=constants.ParseMode.MARKDOWN)
    except Exception as e:
        await msg.edit_text(f"❌ Error al conectar con el mercado global: {e}")

# --- COMANDO: SNIPER SOLANA ---
async def sniper_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("🎯 Ejecutando Radar de Solana (Filtros Activos)...")
    try:
        pairs = await fetch_solana_trends()
        min_liq = user_prefs["min_liquidity"]
        
        # Filtrado inteligente
        filtered = [
            p for p in pairs 
            if float(p.get('liquidity', {}).get('usd', 0)) > min_liq 
            and p.get('baseToken', {}).get('symbol') != 'SOL'
        ][:5]

        if not filtered:
            await msg.edit_text(f"⚠️ No hay oportunidades que superen los ${min_liq:,.0f} de liquidez ahora.")
            return

        reporte = f"🚀 **SOLANA SNIPER RADAR**\n"
        reporte += f"⚙️ Filtro: `>${min_liq:,.0f} Liq`\n\n"

        for p in filtered:
            name = p['baseToken']['name']
            liq = float(p['liquidity']['usd'])
            vol = float(p['volume']['h24'])
            # Ratio de salud: Volumen no debería ser 100 veces la liquidez (posible scam)
            ratio = vol / liq if liq > 0 else 0
            alerta = "⚠️" if ratio > 10 else "✅"

            reporte += f"🔹 **{name}** {alerta}\n"
            reporte += f"💧 Liq: `${liq:,.0f}` | 📊 Vol: `${vol:,.0f}`\n"
            reporte += f"🔗 [Gráfico en DexScreener]({p['url']})\n\n"

        await msg.edit_text(reporte, parse_mode=constants.ParseMode.MARKDOWN, disable_web_page_preview=True)
    except Exception as e:
        await msg.edit_text(f"❌ Error en el radar: {e}")

# --- COMANDO: APRENDER ---
async def aprender_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto = " ".join(context.args)
    if not texto:
        await update.message.reply_text("💡 Dime qué quieres que ajuste. Ej: `/aprender solo busca liquidez mayor a 50k`.")
        return
    
    if "liquidez" in texto.lower():
        nums = [int(s) for s in texto.split() if s.isdigit()]
        if nums: user_prefs["min_liquidity"] = nums[0]
    
    user_prefs["last_instruction"] = texto
    await update.message.reply_text(f"🧠 Ajuste guardado: '{texto}'. He calibrado mis sensores.")

# --- CHAT FLUIDO CON GEMINI ---
async def chat_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_text = update.message.text

    if user_id not in chat_sessions:
        chat_sessions[user_id] = model.start_chat(history=[])

    # El "Cerebro" de MC Losibe
    system_instruction = (
        f"Eres el asistente inteligente de MC Losibe, quien es Psicólogo, Rapero y Driver en Chile. "
        f"Tu tono es {user_prefs['style']}. "
        f"Contexto actual de trading: {user_prefs['last_instruction']}. "
        f"Si te pide rimas, usa el estilo 'música medicina'. Si te pide consejos de psicología, sé empático pero profesional. "
        f"Mantén tus respuestas breves y directas para Telegram."
    )

    try:
        response = chat_sessions[user_id].send_message(f"{system_instruction}\n\nUsuario: {user_text}")
        await update.message.reply_text(response.text, parse_mode=constants.ParseMode.MARKDOWN)
    except Exception as e:
        await update.message.reply_text("🤯 Estoy procesando demasiada información. Dame un respiro e inténtalo de nuevo.")

# --- INICIO DE APLICACIÓN ---
async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 **¡Radar Adaptativo MC Losibe v3.0!**\n\n"
        "He optimizado mis algoritmos para detectar scams y entender tu estilo de vida.\n\n"
        "📌 **/mercado** - Pulso de las grandes (BTC, ETH, SOL).\n"
        "🎯 **/sniper** - Escaneo de gemas en Solana con filtros de seguridad.\n"
        "🧠 **/aprender** - Dame instrucciones de cómo quieres que trabaje.\n\n"
        "Cualquier otra cosa, **solo escríbeme** y charlamos."
    )

if __name__ == "__main__":
    def run_flask():
        app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
    
    Thread(target=run_flask, daemon=True).start()

    token = os.getenv("TELEGRAM_TOKEN")
    if token:
        application = ApplicationBuilder().token(token).build()
        application.add_handler(CommandHandler("start", start_handler))
        application.add_handler(CommandHandler("mercado", mercado_handler))
        application.add_handler(CommandHandler("sniper", sniper_handler))
        application.add_handler(CommandHandler("aprender", aprender_handler))
        application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), chat_handler))
        
        print("🤖 Bot Híbrido Optimizado desplegando...")
        application.run_polling(drop_pending_updates=True)
