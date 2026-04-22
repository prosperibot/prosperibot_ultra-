import os
import httpx
import asyncio
import google.generativeai as genai
from flask import Flask
from telegram import Update, constants
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters
from threading import Thread

# --- 1. CONFIGURACIÓN DE INTELIGENCIA (GEMINI) ---
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model = genai.GenerativeModel('gemini-1.5-flash')
chat_sessions = {}

# --- 2. CONFIGURACIÓN DE USUARIO Y FILTROS ---
# Estos valores se guardan en memoria y se ajustan con /aprender
user_prefs = {
    "min_liquidity": 30000,
    "style": "Analítico, profesional y creativo",
    "last_instruction": "Filtros de seguridad activos y análisis de tendencia orgánica"
}
# Agrega tu ID de Telegram en las variables de entorno para las alertas automáticas
MY_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

app = Flask(__name__)
@app.route('/')
def home(): return "Sistema Global MC Losibe: Operativo 🧠📈"

# --- 3. MÓDULO ANALISTA (OPCIÓN 1: DATOS TÉCNICOS) ---
async def analizar_grafico_ia(pair_data, modo_señal=False):
    """
    Procesa la acción del precio (5m, 1h, 24h) y genera un veredicto o una señal.
    """
    nombre = pair_data.get('baseToken', {}).get('name', 'Token')
    precio = pair_data.get('priceUsd', '0')
    m5 = pair_data.get('priceChange', {}).get('m5', 0)
    h1 = pair_data.get('priceChange', {}).get('h1', 0)
    h24 = pair_data.get('priceChange', {}).get('h24', 0)
    liq = float(pair_data.get('liquidity', {}).get('usd', 0))
    vol = float(pair_data.get('volume', {}).get('h24', 0))

    prompt = (
        f"Analiza el activo {nombre} (${precio}) en Solana.\n"
        f"Variación: 5m: {m5}% | 1h: {h1}% | 24h: {h24}%\n"
        f"Liquidez: ${liq:,.0f} | Volumen: ${vol:,.0f}\n\n"
    )

    if modo_señal:
        prompt += (
            "Genera una señal de inversión con este formato:\n"
            "🎯 ACCIÓN: (Compra/Espera)\n"
            "📥 ENTRADA: (Precio sugerido)\n"
            "💰 TAKE PROFIT: (Objetivo de ganancia)\n"
            "🛑 STOP LOSS: (Nivel de salida en pérdida)\n"
            "📝 RAZÓN: (Breve análisis técnico)"
        )
    else:
        prompt += "Dime brevemente si la tendencia es sana o es un pump artificial."

    try:
        response = model.generate_content(prompt)
        return response.text
    except:
        return "⚠️ Análisis no disponible."

# --- 4. TAREA AUTOMÁTICA: ESTUDIO CONSTANTE ---
async def tarea_monitoreo_mercado(context: ContextTypes.DEFAULT_TYPE):
    """Escanea el mercado solo cada 4 horas y envía recomendaciones."""
    try:
        url = "https://api.dexscreener.com/latest/dex/search?q=solana"
        async with httpx.AsyncClient() as client:
            r = await client.get(url, timeout=15)
            pairs = r.json().get('pairs', [])

        # Buscamos la mejor oportunidad que pase nuestros filtros
        oportunidad = next((p for p in pairs if float(p.get('liquidity', {}).get('usd', 0)) > user_prefs["min_liquidity"]), None)

        if oportunidad and MY_CHAT_ID:
            señal = await analizar_grafico_ia(oportunidad, modo_señal=True)
            mensaje = f"⚡ **RECOMENDACIÓN DE INVERSIÓN (Auto-Scan)** ⚡\n\n{señal}\n\n🔗 [Ver en DexScreener]({oportunidad['url']})"
            await context.bot.send_message(chat_id=MY_CHAT_ID, text=mensaje, parse_mode=constants.ParseMode.MARKDOWN)
    except Exception as e:
        print(f"Error en escaneo automático: {e}")

# --- 5. COMANDOS ---
async def mercado_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Pulso global: BTC, ETH, SOL"""
    msg = await update.message.reply_text("🌐 Consultando mercado global...")
    try:
        url = "https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&ids=bitcoin,ethereum,solana&order=market_cap_desc"
        async with httpx.AsyncClient() as client:
            r = await client.get(url, timeout=10)
            data = r.json()
        
        rep = "🌍 **ESTADO GLOBAL**\n\n"
        for c in data:
            rep += f"• **{c['name']}**: `${c['current_price']:,.2f}` ({c['price_change_percentage_24h']:.1f}%)\n"
        await msg.edit_text(rep, parse_mode=constants.ParseMode.MARKDOWN)
    except:
        await msg.edit_text("❌ Error de conexión con el mercado.")

async def sniper_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Radar de Solana con análisis técnico detallado"""
    msg = await update.message.reply_text("🎯 Ejecutando Sniper + Análisis IA...")
    try:
        url = "https://api.dexscreener.com/latest/dex/search?q=solana"
        async with httpx.AsyncClient() as client:
            r = await client.get(url, timeout=10)
            pairs = r.json().get('pairs', [])

        top = [p for p in pairs if float(p.get('liquidity', {}).get('usd', 0)) > user_prefs["min_liquidity"]][:3]
        
        reporte = "🚀 **SOLANA SMART RADAR**\n\n"
        for p in top:
            analisis = await analizar_grafico_ia(p, modo_señal=False)
            reporte += f"🔹 **{p['baseToken']['name']}**\n🧠 {analisis}\n🔗 [Gráfico]({p['url']})\n\n"
        
        await msg.edit_text(reporte, parse_mode=constants.ParseMode.MARKDOWN, disable_web_page_preview=True)
    except:
        await msg.edit_text("❌ Error en el radar.")

async def aprender_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Entrenamiento de preferencias"""
    txt = " ".join(context.args)
    if txt:
        if "liquidez" in txt.lower():
            n = [int(s) for s in txt.split() if s.isdigit()]
            if n: user_prefs["min_liquidity"] = n[0]
        user_prefs["last_instruction"] = txt
        await update.message.reply_text(f"🧠 Memoria actualizada: '{txt}'")

async def chat_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Conversación fluida personalizada"""
    user_id = update.effective_user.id
    if user_id not in chat_sessions: chat_sessions[user_id] = model.start_chat(history=[])
    
    contexto = (
        f"Eres el asistente de MC Losibe (Psicólogo/Rapero/Trader). Estilo: {user_prefs['style']}. "
        f"Nota trading: {user_prefs['last_instruction']}. Ayúdalo con inversiones y rimas."
    )
    try:
        res = chat_sessions[user_id].send_message(f"{contexto}\n\nPregunta: {update.message.text}")
        await update.message.reply_text(res.text, parse_mode=constants.ParseMode.MARKDOWN)
    except:
        await update.message.reply_text("🤯 Mi cerebro está saturado, reintenta.")

# --- 6. DESPLIEGUE ---
if __name__ == "__main__":
    def run(): app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
    Thread(target=run, daemon=True).start()

    token = os.getenv("TELEGRAM_TOKEN")
    if token:
        application = ApplicationBuilder().token(token).build()
        
        # MONITOR AUTOMÁTICO: Cada 4 horas (14400 segundos)
        job_queue = application.job_queue
        job_queue.run_repeating(tarea_monitoreo_mercado,
