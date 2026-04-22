import os
import httpx
import asyncio
import google.generativeai as genai
from flask import Flask
from telegram import Update, constants
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters
from threading import Thread

# --- CONFIGURACIÓN DE IA ---
# Asegúrate de que en Render/Railway se llame: GEMINI_API_KEY
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model = genai.GenerativeModel('gemini-1.5-flash')
chat_sessions = {}

# --- MEMORIA Y PREFERENCIAS ---
user_prefs = {
    "min_liquidity": 25000,
    "style": "Analítico y creativo (MC Losibe Style)",
    "last_instruction": "Filtros de seguridad activos"
}
# Tu ID de Telegram para alertas automáticas
MY_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

app = Flask(__name__)
@app.route('/')
def home(): return "Mente Maestra MC Losibe: ONLINE 🧠🚀"

# --- MÓDULO DE ANÁLISIS TÉCNICO ---
async def analizar_grafico_ia(pair_data, modo_señal=False):
    try:
        nombre = pair_data.get('baseToken', {}).get('name', 'Token')
        m5 = pair_data.get('priceChange', {}).get('m5', 0)
        h1 = pair_data.get('priceChange', {}).get('h1', 0)
        liq = float(pair_data.get('liquidity', {}).get('usd', 0))
        vol = float(pair_data.get('volume', {}).get('h24', 0))

        prompt = (
            f"Analiza {nombre}. Variación: 5m: {m5}% | 1h: {h1}%.\n"
            f"Liquidez: ${liq:,.0f} | Vol: ${vol:,.0f}.\n"
        )

        if modo_señal:
            prompt += "Genera señal: ACCIÓN (Compra/Espera), ENTRADA, TAKE PROFIT, STOP LOSS y RAZÓN breve."
        else:
            prompt += "Dime si la tendencia es sana o es un pump artificial en 2 líneas."

        response = model.generate_content(prompt)
        return response.text
    except:
        return "⚠️ Análisis no disponible."

# --- TAREA AUTOMÁTICA: ESTUDIO CADA 4 HORAS ---
async def tarea_monitoreo(context: ContextTypes.DEFAULT_TYPE):
    if not MY_CHAT_ID: return
    try:
        async with httpx.AsyncClient() as client:
            r = await client.get("https://api.dexscreener.com/latest/dex/search?q=solana", timeout=15)
            pairs = r.json().get('pairs', [])
        
        # Buscar la mejor gema
        gema = next((p for p in pairs if float(p.get('liquidity', {}).get('usd', 0)) > user_prefs["min_liquidity"]), None)
        
        if gema:
            señal = await analizar_grafico_ia(gema, modo_señal=True)
            await context.bot.send_message(
                chat_id=MY_CHAT_ID, 
                text=f"⚡ **ESTUDIO DE MERCADO AUTOMÁTICO** ⚡\n\n{señal}\n\n🔗 [Ver Gráfico]({gema['url']})",
                parse_mode=constants.ParseMode.MARKDOWN
            )
    except: pass

# --- COMANDOS ---
async def mercado_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("🌐 Consultando mercado...")
    try:
        async with httpx.AsyncClient() as client:
            r = await client.get("https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&ids=bitcoin,ethereum,solana", timeout=10)
            data = r.json()
        rep = "🌍 **GLOBAL**\n"
        for c in data:
            rep += f"• {c['name']}: `${c['current_price']:,.2f}`\n"
        await msg.edit_text(rep, parse_mode=constants.ParseMode.MARKDOWN)
    except: await msg.edit_text("❌ Error de conexión.")

async def sniper_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("🎯 Radar Solana + IA...")
    try:
        async with httpx.AsyncClient() as client:
            r = await client.get("https://api.dexscreener.com/latest/dex/search?q=solana", timeout=10)
            pairs = r.json().get('pairs', [])
        
        filtro = user_prefs["min_liquidity"]
        top = [p for p in pairs if float(p.get('liquidity', {}).get('usd', 0)) > filtro][:3]
        
        rep = "🚀 **RADAR SOLANA**\n\n"
        for p in top:
            analisis = await analizar_grafico_ia(p)
            rep += f"🔹 **{p['baseToken']['symbol']}**: {analisis}\n\n"
        await msg.edit_text(rep, parse_mode=constants.ParseMode.MARKDOWN, disable_web_page_preview=True)
    except: await msg.edit_text("❌ Error en el radar.")

async def aprender_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = " ".join(context.args)
    if txt:
        if "liquidez" in txt.lower():
            n = [int(s) for s in txt.split() if s.isdigit()]
            if n: user_prefs["min_liquidity"] = n[0]
        user_prefs["last_instruction"] = txt
        await update.message.reply_text(f"🧠 Aprendido: {txt}")

async def chat_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if uid not in chat_sessions: chat_sessions[uid] = model.start_chat(history=[])
    
    contexto = f"Asistente de MC Losibe (Psicólogo/Rapero/Trader). Nota: {user_prefs['last_instruction']}. Sé breve."
    try:
        res = chat_sessions[uid].send_message(f"{contexto}\n\nPregunta: {update.message.text}")
        await update.message.reply_text(res.text, parse_mode=constants.ParseMode.MARKDOWN)
    except: await update.message.reply_text("🤯 Error de IA, intenta de nuevo.")

# --- INICIO ---
if __name__ == "__main__":
    def run(): app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
    Thread(target=run, daemon=True).start()

    token = os.getenv("TELEGRAM_TOKEN")
    if token:
        # Aquí se inicializa con soporte para JobQueue
        application = ApplicationBuilder().token(token).build()
        
        # PROGRAMACIÓN: Cada 4 horas
        if application.job_queue:
            application.job_queue.run_repeating(tarea_monitoreo, interval=14400, first=10)

        application.add_handler(CommandHandler("start", mercado_handler))
        application.add_handler(CommandHandler("mercado", mercado_handler))
        application.add_handler(CommandHandler("sniper", sniper_handler))
        application.add_handler(CommandHandler("aprender", aprender_handler))
        application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), chat_handler))
        
        print("🤖 Bot MASTER iniciado...")
        application.run_polling(drop_pending_updates=True)
