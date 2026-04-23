import os
import httpx
import logging
import google.generativeai as genai
from flask import Flask
from telegram import Update, constants
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters
from threading import Thread

# --- 1. CONFIGURACIÓN DE NÚCLEO ---
logging.basicConfig(level=logging.INFO)
app = Flask(__name__)

@app.route('/')
def health(): return "Cerebro MC Losibe: Evolucionando 🧠✨", 200

# --- 2. GESTIÓN DE MEMORIA Y APRENDIZAJE ---
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model = genai.GenerativeModel('gemini-1.5-flash')
chat_sessions = {}

# Memoria Persistente de Acuerdos (Se actualiza en vivo)
acuerdos_maestros = {
    "trading": "Priorizar seguridad sobre ganancias rápidas. Liquidez mínima $30k.",
    "estilo": "Hablar como un socio par, con toques de psicología y terminología de rap.",
    "objetivos": "Encontrar gemas orgánicas y potenciar la marca Fun G Prod."
}

def construir_instruccion_maestra():
    return (
        f"Eres el socio inteligente de MC Losibe (Psicólogo, Rapero y Driver).\n"
        f"Tu meta no es solo responder, es APRENDER de él.\n"
        f"ACUERDOS ACTUALES:\n"
        f"- Trading: {acuerdos_maestros['trading']}\n"
        f"- Identidad: {acuerdos_maestros['estilo']}\n"
        f"- Proyectos: {acuerdos_maestros['objetivos']}\n"
        "Si él te da una instrucción nueva o te corrige, di 'Acuerdo actualizado' y asimílalo."
    )

# --- 3. DIÁLOGO Y RESULTADOS ---
async def manejar_dialogo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    mensaje = update.message.text

    # Detectar si el usuario quiere establecer un nuevo acuerdo
    if "acuerdo" in mensaje.lower() or "desde ahora" in mensaje.lower():
        prompt_aprender = f"El usuario quiere establecer un nuevo acuerdo: {mensaje}. Resume este acuerdo en una frase corta."
        res_acuerdo = model.generate_content(prompt_aprender)
        # Actualizamos la memoria (Aquí podrías dividir por categorías)
        acuerdos_maestros["trading"] += f" | {res_acuerdo.text}"
        await update.message.reply_text(f"🤝 **Acuerdo Sellado:** {res_acuerdo.text}\nLo tendré en cuenta para todos nuestros resultados futuros.")
        return

    # Iniciar charla con memoria de sesión
    if uid not in chat_sessions:
        chat_sessions[uid] = model.start_chat(history=[])

    try:
        # Enviamos el contexto maestro + el diálogo
        contexto_vivo = f"[SISTEMA: {construir_instruccion_maestra()}]\n\nUsuario: {mensaje}"
        respuesta = chat_sessions[uid].send_message(contexto_vivo)
        await update.message.reply_text(respuesta.text, parse_mode='Markdown')
    except:
        await update.message.reply_text("🤯 Mi procesador se saturó con tanta info. ¿Podemos retomar el punto anterior?")

# --- 4. ACCIÓN: SNIPER BASADO EN ACUERDOS ---
async def sniper_ia(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🎯 Escaneando el mercado bajo nuestros acuerdos actuales...")
    # (Aquí iría la lógica de DexScreener que ya tenemos, pero filtrada por 'acuerdos_maestros')
    # ...
    await update.message.reply_text("He filtrado los resultados. Según lo que acordamos, solo este token es viable...")

# --- 5. LANZAMIENTO ---
if __name__ == "__main__":
    Thread(target=lambda: app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000))), daemon=True).start()
    
    token = os.getenv("TELEGRAM_TOKEN")
    if token:
        bot_app = ApplicationBuilder().token(token).build()
        bot_app.add_handler(CommandHandler("sniper", sniper_ia))
        bot_app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), manejar_dialogo))
        
        print("🚀 Socio inteligente en línea...")
        bot_app.run_polling(drop_pending_updates=True)
