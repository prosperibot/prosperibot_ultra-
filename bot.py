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
def health(): return "Cerebro Racional MC Losibe: Operativo 🧠", 200

# IA y Gestión de Sesiones
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model = genai.GenerativeModel('gemini-1.5-flash')
chat_sessions = {}

# --- EL MOTOR DE RACIONALIZACIÓN ---
def prompt_racional(mensaje_usuario):
    return (
        f"Actúa como un Socio Estratégico y Analista Crítico de MC Losibe. "
        "Tu objetivo es RACIONALIZAR cada respuesta. No des respuestas simples.\n\n"
        "Sigue siempre esta estructura mental:\n"
        "1. OBSERVACIÓN: Qué es lo que el usuario está pidiendo o planteando realmente.\n"
        "2. ANÁLISIS: Cuáles son los riesgos, beneficios o implicancias (en trading, música o psicología).\n"
        "3. CONCLUSIÓN/ACUERDO: Qué sugieres hacer y por qué.\n\n"
        f"Usuario dice: {mensaje_usuario}\n"
        "Responde de forma fluida pero estructurada."
    )

# --- MANEJO DE DIÁLOGO ---
async def chat_racional(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    texto = update.message.text

    # Memoria de Sesión para Diálogo Fluido
    if uid not in chat_sessions:
        chat_sessions[uid] = model.start_chat(history=[])

    try:
        # Pedimos a Gemini que racionalice antes de responder
        response = chat_sessions[uid].send_message(prompt_racional(texto))
        
        # Enviar la respuesta racionalizada
        await update.message.reply_text(response.text, parse_mode='Markdown')
        
    except Exception as e:
        logging.error(f"Error en racionalización: {e}")
        await update.message.reply_text("🤯 Mi proceso de razonamiento se bloqueó. Intentemos simplificar la idea.")

# --- COMANDOS DE ACCIÓN ---
async def sniper(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🎯 Analizando el mercado con lógica de riesgo/beneficio...")
    # Aquí llamaríamos a la función de análisis técnico que racionalice la entrada

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🧠 **Socio Racional Activado.**\nEstoy listo para debatir ideas, analizar trades y llegar a acuerdos lógicos contigo.")

# --- ARRANQUE ---
if __name__ == "__main__":
    Thread(target=lambda: app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000))), daemon=True).start()

    token = os.getenv("TELEGRAM_TOKEN")
    if token:
        app_tg = ApplicationBuilder().token(token).build()
        
        app_tg.add_handler(CommandHandler("start", start))
        app_tg.add_handler(CommandHandler("sniper", sniper))
        app_tg.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), chat_racional))
        
        app_tg.run_polling(drop_pending_updates=True)
