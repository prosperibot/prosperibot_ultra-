import os
import httpx
import logging
import google.generativeai as genai
from flask import Flask
from telegram import Update, constants
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters
from threading import Thread

# --- CONFIGURACIÓN INICIAL ---
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# Flask para Render (Evita el "Timed out")
app = Flask(__name__)
@app.route('/')
def health(): return "Sistema MC Losibe: Activo 🚀", 200

# Configuración de IA (Gemini)
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model = genai.GenerativeModel('gemini-1.5-flash')

# Memoria de Preferencias
user_prefs = {
    "min_liq": 25000,
    "style": "Analítico, empático y centrado en el bienestar",
    "chat_id": os.getenv("TELEGRAM_CHAT_ID") # Tu ID para reportes automáticos
}

# --- FUNCIONES DE CEREBRO (IA) ---
async def ia_analisis_tecnico(datos, modo_señal=False):
    """Le pasa los datos de precio a Gemini para un veredicto profesional."""
    prompt = (
        f"Actúa como analista senior de trading. Datos: {datos}\n"
        "Si modo_señal es True, dame: ACCIÓN, ENTRADA, TP, SL y RAZÓN.\n"
        "Si no, dame un resumen técnico de 2 líneas sobre la salud del gráfico."
    )
    try:
        response = model.generate_content(f"Contexto: {modo_señal}. {prompt}")
        return response.text
    except Exception as e:
        return f"⚠️ Error IA: {str(e)}"

# --- FUNCIONES DE MERCADO ---
async def buscar_oportunidades():
    """Busca en DexScreener tokens con liquidez real."""
    url = "https://api.dexscreener.com/latest/dex/search?q=solana"
    async with httpx.AsyncClient(timeout=15.0) as client:
        r = await client.get(url)
        pairs = r.json().get('pairs', [])
        return [p for p in pairs if float(p.get('liquidity', {}).get('usd', 0)) > user_prefs["min_liq"]][:3]

# --- TAREAS AUTOMÁTICAS (Cada 4 Horas) ---
async def reporte_automatico(context: ContextTypes.DEFAULT_TYPE):
    if not user_prefs["chat_id"]: return
    oportunidades = await buscar_oportunidades()
    if oportunidades:
        top = oportunidades[0]
        analisis = await ia_analisis_tecnico(top, modo_señal=True)
        mensaje = f"⚡ **ESTUDIO DE MERCADO MC LOSIBE** ⚡\n\n{analisis}\n\n🔗 [Gráfico]({top['url']})"
        await context.bot.send_message(chat_id=user_prefs["chat_id"], text=mensaje, parse_mode='Markdown')

# --- HANDLERS DE TELEGRAM ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 **Radar MC Losibe v5.0**\n\n"
        "Cerebro híbrido listo para el trading y la creatividad.\n"
        "• `/sniper` - Escaneo rápido con análisis IA.\n"
        "• `/mercado` - Pulso de BTC, ETH y SOL.\n"
        "• `/aprender` - Ajusta mis parámetros.\n\n"
        "Háblame para analizar trades o escribir rimas."
    )

async def sniper(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("🎯 Escaneando Solana...")
    ops = await buscar_oportunidades()
    rep = "🚀 **TOP OPORTUNIDADES**\n\n"
    for p in ops:
        resumen = await ia_analisis_tecnico(p, modo_señal=False)
        rep += f"🔹 **{p['baseToken']['symbol']}**: {resumen}\n\n"
    await msg.edit_text(rep, parse_mode='Markdown', disable_web_page_preview=True)

async def chat_personalizado(update: Update, context: ContextTypes.DEFAULT_TYPE):
    identidad = f"Eres el asistente de MC Losibe: Psicólogo, Rapero Medicina y Driver. Estilo: {user_prefs['style']}."
    try:
        chat = model.start_chat(history=[])
        res = chat.send_message(f"{identidad}\n\nUsuario dice: {update.message.text}")
        await update.message.reply_text(res.text, parse_mode='Markdown')
    except:
        await update.message.reply_text("🤯 Mi cerebro está saturado.")

# --- ARRANQUE ---
if __name__ == "__main__":
    # 1. Servidor Web
    def run_web(): app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
    Thread(target=run_web, daemon=True).start()

    # 2. Bot de Telegram
    token = os.getenv("TELEGRAM_TOKEN")
    if token:
        builder = ApplicationBuilder().token(token).build()
        
        # Programación (JobQueue) - 4 horas
        if builder.job_queue:
            builder.job_queue.run_repeating(reporte_automatico, interval=14400, first=10)

        builder.add_handler(CommandHandler("start", start))
        builder.add_handler(CommandHandler("sniper", sniper))
        builder.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), chat_personalizado))
        
        print("🤖 Sistema en línea...")
        builder.run_polling(drop_pending_updates=True)
