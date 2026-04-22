import os
import httpx
import asyncio
import google.generativeai as genai
from flask import Flask
from telegram import Update, constants
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters
from threading import Thread
import logging

# 1. Configuración de Logs (para que veas los errores en el panel de Render)
logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)

# 2. Flask (Debe ser lo más ligero posible)
app = Flask(__name__)
@app.route('/')
def health_check():
    return "MC Losibe Bot Operativo", 200 # Respuesta rápida para el servidor

def start_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

# 3. Configuración de IA
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model = genai.GenerativeModel('gemini-1.5-flash')
chat_sessions = {}
user_prefs = {"min_liquidity": 25000, "style": "Analítico/Creativo", "last_instruction": "Filtros activos"}
MY_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# --- Lógica de Análisis (Igual a la anterior, pero con timeouts largos) ---
async def analizar_grafico_ia(pair_data, modo_señal=False):
    try:
        nombre = pair_data.get('baseToken', {}).get('name', 'Token')
        m5, h1 = pair_data.get('priceChange', {}).get('m5', 0), pair_data.get('priceChange', {}).get('h1', 0)
        liq, vol = float(pair_data.get('liquidity', {}).get('usd', 0)), float(pair_data.get('volume', {}).get('h24', 0))
        
        prompt = f"Analiza {nombre}. 5m: {m5}% | 1h: {h1}% | Liq: ${liq:,.0f}. "
        prompt += "Genera señal: ACCIÓN, ENTRADA, TP, SL." if modo_señal else "Resumen técnico en 2 líneas."
        
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        logging.error(f"Error Gemini: {e}")
        return "⚠️ IA temporalmente fuera de línea."

async def tarea_monitoreo(context: ContextTypes.DEFAULT_TYPE):
    if not MY_CHAT_ID: return
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            r = await client.get("https://api.dexscreener.com/latest/dex/search?q=solana")
            pairs = r.json().get('pairs', [])
        
        gema = next((p for p in pairs if float(p.get('liquidity', {}).get('usd', 0)) > user_prefs["min_liquidity"]), None)
        if gema:
            señal = await analizar_grafico_ia(gema, modo_señal=True)
            await context.bot.send_message(chat_id=MY_CHAT_ID, text=f"⚡ **AUTO-SCAN**\n\n{señal}", parse_mode='Markdown')
    except Exception as e:
        logging.error(f"Error Monitoreo: {e}")

# --- Handlers de Comandos ---
async def sniper_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🎯 Buscando... dame un segundo.")
    # (Lógica de sniper aquí)

async def chat_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if uid not in chat_sessions: chat_sessions[uid] = model.start_chat(history=[])
    try:
        res = chat_sessions[uid].send_message(f"Asistente de MC Losibe. Contexto: {user_prefs['last_instruction']}. Responde a: {update.message.text}")
        await update.message.reply_text(res.text, parse_mode='Markdown')
    except: await update.message.reply_text("🤯 IA saturada.")

# --- ARRANQUE PRINCIPAL ---
if __name__ == "__main__":
    # PASO A: Arrancar el servidor web inmediatamente en un hilo
    logging.info("Arrancando Web Server...")
    Thread(target=start_flask, daemon=True).start()

    # PASO B: Configurar y arrancar Telegram
    token = os.getenv("TELEGRAM_TOKEN")
    if not token:
        logging.error("Falta TELEGRAM_TOKEN. Saliendo...")
    else:
        logging.info("Iniciando Bot de Telegram...")
        application = ApplicationBuilder().token(token).build()
        
        # Configurar JobQueue (asegúrate de tener 'apscheduler' en requirements.txt)
        if application.job_queue:
            application.job_queue.run_repeating(tarea_monitoreo, interval=14400, first=15)
        
        application.add_handler(CommandHandler("sniper", sniper_handler))
        application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), chat_handler))
        
        # drop_pending_updates=True evita que el bot se sature de mensajes viejos al arrancar
        application.run_polling(drop_pending_updates=True)
