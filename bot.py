import os
import httpx
import asyncio
import logging
import google.generativeai as genai
from flask import Flask
from telegram import Update, constants
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters
from threading import Thread

# 1. LOGGING Y SERVIDOR WEB (Anti-Timeout)
logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)
app = Flask(__name__)

@app.route('/')
def health_check():
    return "Mente Maestra MC Losibe: Operativa 🧠", 200

def start_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

# 2. CONFIGURACIÓN DE IA Y MEMORIA
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model = genai.GenerativeModel('gemini-1.5-flash')
chat_sessions = {}

user_prefs = {
    "min_liquidity": 30000,
    "style": "Analítico, profesional y empático",
    "last_instruction": "Filtros de seguridad activos y análisis de tendencia orgánica"
}
MY_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# 3. ANALISTA TÉCNICO IA (Opción 1: Datos OHLC)
async def analizar_grafico_ia(pair_data, modo_señal=False):
    try:
        nombre = pair_data.get('baseToken', {}).get('name', 'Token')
        precio = pair_data.get('priceUsd', '0')
        m5 = pair_data.get('priceChange', {}).get('m5', 0)
        h1 = pair_data.get('priceChange', {}).get('h1', 0)
        h24 = pair_data.get('priceChange', {}).get('h24', 0)
        liq = float(pair_data.get('liquidity', {}).get('usd', 0))
        vol = float(pair_data.get('volume', {}).get('h24', 0))

        prompt = (
            f"Analiza {nombre} (${precio}) en Solana.\n"
            f"Cambios: 5m: {m5}% | 1h: {h1}% | 24h: {h24}%\n"
            f"Liquidez: ${liq:,.0f} | Vol 24h: ${vol:,.0f}\n\n"
        )

        if modo_señal:
            prompt += (
                "Genera una señal de inversión profesional:\n"
                "🎯 ACCIÓN: (Compra/Espera)\n"
                "📥 ENTRADA: (Precio sugerido)\n"
                "💰 TAKE PROFIT: (Objetivo)\n"
                "🛑 STOP LOSS: (Protección)\n"
                "📝 RAZÓN: (Análisis de estructura de mercado)"
            )
        else:
            prompt += "Como trader experto, dime si la tendencia es orgánica o manipulación en 2 líneas."

        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        logging.error(f"Error IA: {e}")
        return "⚠️ Análisis no disponible."

# 4. MONITOREO AUTOMÁTICO (Cada 4 horas)
async def tarea_monitoreo_mercado(context: ContextTypes.DEFAULT_TYPE):
    if not MY_CHAT_ID: return
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            r = await client.get("https://api.dexscreener.com/latest/dex/search?q=solana")
            pairs = r.json().get('pairs', [])

        oportunidad = next((p for p in pairs if float(p.get('liquidity', {}).get('usd', 0)) > user_prefs["min_liquidity"]), None)

        if oportunidad:
            señal = await analizar_grafico_ia(oportunidad, modo_señal=True)
            mensaje = f"⚡ **ESTUDIO PROACTIVO DE MERCADO** ⚡\n\n{señal}\n\n🔗 [DexScreener]({oportunidad['url']})"
            await context.bot.send_message(chat_id=MY_CHAT_ID, text=mensaje, parse_mode=constants.ParseMode.MARKDOWN)
    except Exception as e:
        logging.error(f"Error Monitoreo: {e}")

# 5. HANDLERS DE COMANDOS
async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 **¡Radar MC Losibe Online!**\n"
        "Integración total de Psicología, Rap y Trading.\n\n"
        "📌 `/mercado` - Global (BTC/ETH/SOL)\n"
        "🎯 `/sniper` - Escaneo Solana con IA\n"
        "🧠 `/aprender` - Ajustar mis parámetros"
    )

async def mercado_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("🌐 Consultando pulso global...")
    try:
        url = "https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&ids=bitcoin,ethereum,solana&order=market_cap_desc"
        async with httpx.AsyncClient() as client:
            r = await client.get(url, timeout=10)
            data = r.json()
        rep = "🌍 **ESTADO GLOBAL**\n\n"
        for c in data:
            rep += f"• **{c['name']}**: `${c['current_price']:,.2f}` ({c['price_change_percentage_24h']:.1f}%)\n"
        await msg.edit_text(rep, parse_mode=constants.ParseMode.MARKDOWN)
    except: await msg.edit_text("❌ Error de mercado.")

async def sniper_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("🎯 Analizando Solana con ojos de IA...")
    try:
        async with httpx.AsyncClient() as client:
            r = await client.get("https://api.dexscreener.com/latest/dex/search?q=solana")
            pairs = r.json().get('pairs', [])
        
        filtro = user_prefs["min_liquidity"]
        top = [p for p in pairs if float(p.get('liquidity', {}).get('usd', 0)) > filtro][:3]
        
        rep = "🚀 **RADAR SOLANA (Analista IA)**\n\n"
        for p in top:
            analisis = await analizar_grafico_ia(p, modo_señal=False)
            rep += f"🔹 **{p['baseToken']['symbol']}**\n🧠 {analisis}\n\n"
        await msg.edit_text(rep, parse_mode=constants.ParseMode.MARKDOWN, disable_web_page_preview=True)
    except: await msg.edit_text("❌ Error en radar.")

async def aprender_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = " ".join(context.args)
    if txt:
        if "liquidez" in txt.lower():
            n = [int(s) for s in txt.split() if s.isdigit()]
            if n: user_prefs["min_liquidity"] = n[0]
        user_prefs["last_instruction"] = txt
        await update.message.reply_text(f"🧠 Ajuste guardado: {txt}")

async def chat_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if uid not in chat_sessions: chat_sessions[uid] = model.start_chat(history=[])
    
    ctx = (f"Eres el asistente de MC Losibe. Psicólogo, Rapero Medicina y Driver. "
           f"Filtro: {user_prefs['min_liquidity']} USD. Contexto: {user_prefs['last_instruction']}.")
    try:
        res = chat_sessions[uid].send_message(f"{ctx}\n\nPregunta: {update.message.text}")
        await update.message.reply_text(res.text, parse_mode=constants.ParseMode.MARKDOWN)
    except Exception as e:
        logging.error(f"Error Chat: {e}")
        await update.message.reply_text("🤯 Mi cerebro está saturado, reintenta.")

# 6. ARRANQUE MAESTRO
if __name__ == "__main__":
    Thread(target=start_flask, daemon=True).start()
    token = os.getenv("TELEGRAM_TOKEN")
    if token:
        application = ApplicationBuilder().token(token).build()
        if application.job_queue:
            application.job_queue.run_repeating(tarea_monitoreo_mercado, interval=14400, first=15)
        
        application.add_handler(CommandHandler("start", start_handler))
        application.add_handler(CommandHandler("mercado", mercado_handler))
        application.add_handler(CommandHandler("sniper", sniper_handler))
        application.add_handler(CommandHandler("aprender", aprender_handler))
        application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), chat_handler))
        
        logging.info("🚀 Sistema MC Losibe Iniciado.")
        application.run_polling(drop_pending_updates=True)
