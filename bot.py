import os
import httpx
import logging
import google.generativeai as genai
from flask import Flask
from telegram import Update, constants
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters
from threading import Thread

# --- CONFIGURACIÓN ---
logging.basicConfig(level=logging.INFO)
app = Flask(__name__)

@app.route('/')
def health(): return "Bot MC Losibe Online 🚀", 200

# IA y Preferencias
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model = genai.GenerativeModel('gemini-1.5-flash')
MY_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID") # Para señales automáticas

# --- LÓGICA DE TRADING IA ---
async def analizar_con_ia(datos, es_señal=False):
    prompt = f"Analiza estos datos de Solana: {datos}. "
    prompt += "Dime: ACCIÓN, ENTRADA y SALIDA." if es_señal else "Resumen técnico rápido."
    try:
        res = model.generate_content(prompt)
        return res.text
    except: return "⚠️ IA ocupada, intenta luego."

# --- TAREA AUTOMÁTICA (Cada 4 Horas) ---
async def tarea_automatica(context: ContextTypes.DEFAULT_TYPE):
    if not MY_CHAT_ID: return
    # Aquí el bot busca el mercado solo y te escribe
    await context.bot.send_message(chat_id=MY_CHAT_ID, text="📈 **Estudio de mercado en curso...**")

# --- COMANDOS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ Sistema Activo. Usa /sniper o háblame directamente.")

async def sniper(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🎯 Escaneando gemas en Solana...")

async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # El bot sabe quién eres por el contexto que le damos
    ctx = "Eres el asistente de MC Losibe (Psicólogo y Rapero). Sé breve y profesional."
    res = model.generate_content(f"{ctx}\nUsuario: {update.message.text}")
    await update.message.reply_text(res.text)

# --- LANZAMIENTO ---
if __name__ == "__main__":
    # Iniciar Web Server para Render
    Thread(target=lambda: app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000))), daemon=True).start()

    token = os.getenv("TELEGRAM_TOKEN")
    if token:
        app_tg = ApplicationBuilder().token(token).build()
        
        # Programar cada 4 horas
        if app_tg.job_queue:
            app_tg.job_queue.run_repeating(tarea_automatica, interval=14400, first=10)

        app_tg.add_handler(CommandHandler("start", start))
        app_tg.add_handler(CommandHandler("sniper", sniper))
        app_tg.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), chat))
        
        app_tg.run_polling(drop_pending_updates=True)
