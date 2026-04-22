import os
import httpx
import asyncio
import google.generativeai as genai
from flask import Flask
from telegram import Update, constants
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters
from threading import Thread

# --- 1. CONFIGURACIÓN DE IA (GEMINI) ---
# Se extrae de las variables de entorno para máxima seguridad
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model = genai.GenerativeModel('gemini-1.5-flash')
chat_sessions = {}

# --- 2. MEMORIA DE PREFERENCIAS Y FILTROS ---
# Estos valores se ajustan en tiempo real con el comando /aprender
user_prefs = {
    "min_liquidity": 25000,
    "style": "Analítico, empático y profesional",
    "last_instruction": "Enfocado en seguridad y tendencias orgánicas"
}

app = Flask(__name__)
@app.route('/')
def home(): return "Mente Maestra MC Losibe: Sistema Activo 🧠🚀"

# --- 3. MÓDULO DE ANÁLISIS TÉCNICO (OPCIÓN 1: DATOS) ---
async def analizar_grafico_ia(pair_data):
    """
    Gemini actúa como analista técnico procesando los datos de acción de precio.
    """
    nombre = pair_data.get('baseToken', {}).get('name', 'Token')
    m5 = pair_data.get('priceChange', {}).get('m5', 0)
    h1 = pair_data.get('priceChange', {}).get('h1', 0)
    h24 = pair_data.get('priceChange', {}).get('h24', 0)
    
    liq = float(pair_data.get('liquidity', {}).get('usd', 0))
    vol = float(pair_data.get('volume', {}).get('h24', 0))
    
    # Prompt técnico especializado
    prompt = (
        f"Analiza el activo {nombre} en Solana.\n"
        f"Variación de precio: 5m: {m5}% | 1h: {h1}% | 24h: {h24}%\n"
        f"Liquidez: ${liq:,.0f} | Volumen: ${vol:,.0f}\n\n"
        "Como trader experto, evalúa la estructura del gráfico. ¿Es una tendencia sana o manipulación? "
        "Dime si hay riesgo de caída o si es una buena entrada. Sé muy breve."
    )

    try:
        response = model.generate_content(prompt)
        return response.text
    except:
        return "⚠️ Análisis técnico no disponible en este momento."

# --- 4. COMANDOS DE RADAR Y MERCADO ---
async def mercado_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Muestra el estado de las criptos principales (BTC, ETH, SOL)"""
    msg = await update.message.reply_text("📊 Consultando el pulso global...")
    try:
        url = "https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&ids=bitcoin,ethereum,solana&order=market_cap_desc"
        async with httpx.AsyncClient() as client:
            r = await client.get(url, timeout=10)
            data = r.json()
        
        reporte = "🌍 **PULSO GLOBAL CRYPTO**\n\n"
        for c in data:
            change = c['price_change_percentage_24h']
            emoji = "🟢" if change > 0 else "🔴"
            reporte += f"{emoji} **{c['name']}**: `${c['current_price']:,.2f}` ({change:.1f}%)\n"
        
        await msg.edit_text(reporte, parse_mode=constants.ParseMode.MARKDOWN)
    except:
        await msg.edit_text("❌ Error al conectar con el mercado global.")

async def sniper_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Busca gemas en Solana y las analiza con IA"""
    msg = await update.message.reply_text("🎯 Ejecutando Sniper Radar con Análisis IA...")
    try:
        url = "https://api.dexscreener.com/latest/dex/search?q=solana"
        async with httpx.AsyncClient() as client:
            r = await client.get(url, timeout=10)
            pairs = r.json().get('pairs', [])

        min_liq = user_prefs["min_liquidity"]
        # Filtramos y tomamos los 3 mejores para un análisis profundo
        top_pairs = [p for p in pairs if float(p.get('liquidity', {}).get('usd', 0)) > min_liq][:3]

        if not top_pairs:
            await msg.edit_text(f"⚠️ No hay tokens con liquidez superior a ${min_liq:,.0f} ahora.")
            return

        reporte = f"🚀 **RADAR SOLANA IA**\n"
        reporte += f"⚙️ Filtro: `>${min_liq:,.0f} Liq`\n\n"

        for p in top_pairs:
            veredicto = await analizar_grafico_ia(p)
            reporte += f"🔹 **{p['baseToken']['name']}**\n"
            reporte += f"🧠 **IA:** _{veredicto}_\n"
            reporte += f"🔗 [Gráfico]({p['url']})\n\n"

        await msg.edit_text(reporte, parse_mode=constants.ParseMode.MARKDOWN, disable_web_page_preview=True)
    except Exception as e:
        await msg.edit_text(f"❌ Error en el radar: {str(e)}")

# --- 5. APRENDIZAJE Y CHAT FLUIDO ---
async def aprender_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Permite al bot adaptarse a tus instrucciones"""
    instruccion = " ".join(context.args)
    if instruccion:
        if "liquidez" in instruccion.lower():
            nums = [int(s) for s in instruccion.split() if s.isdigit()]
            if nums: user_prefs["min_liquidity"] = nums[0]
        
        user_prefs["last_instruction"] = instruccion
        await update.message.reply_text(f"🧠 Memoria actualizada: '{instruccion}'")
    else:
        await update.message.reply_text("💡 Dime qué quieres que aprenda. Ej: `/aprender sube la liquidez a 50k`")

async def chat_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Conversación fluida recordando quién eres (Psicólogo/Rapero)"""
    user_id = update.effective_user.id
    if user_id not in chat_sessions:
        chat_sessions[user_id] = model.start_chat(history=[])
    
    # Contexto persistente de identidad
    identidad = (
        f"Eres el asistente de MC Losibe. Él es Psicólogo, Rapero y Driver en Chile. "
        f"Tu estilo es {user_prefs['style']}. "
        f"Instrucción de trading: {user_prefs['last_instruction']}. "
        "Sé inteligente, breve y mantén una conversación fluida."
    )
    
    try:
        response = chat_sessions[user_id].send_message(f"{identidad}\n\nUsuario dice: {update.message.text}")
        await update.message.reply_text(response.text, parse_mode=constants.ParseMode.MARKDOWN)
    except:
        await update.message.reply_text("🤯 Estoy procesando mucha info. Dame un segundo.")

# --- 6. INICIO Y DESPLIEGUE ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "💪 **¡Radar MC Losibe Online!**\n\n"
        "Analista técnico de Solana y asistente personal activado.\n\n"
        "📌 **/mercado** - Ver BTC, ETH y SOL.\n"
        "🎯 **/sniper** - Buscar gemas con análisis de IA.\n"
        "🧠 **/aprender** - Ajustar mi comportamiento.\n\n"
        "También puedes hablarme directamente para lo que necesites."
    )

if __name__ == "__main__":
    def run_flask():
        app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
    
    Thread(target=run_flask, daemon=True).start()

    token = os.getenv("TELEGRAM_TOKEN")
    if token:
        application = ApplicationBuilder().token(token).build()
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("mercado", mercado_handler))
        application.add_handler(CommandHandler("sniper", sniper_handler))
        application.add_handler(CommandHandler("aprender", aprender_handler))
        application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), chat_handler))
        
        print("🤖 Bot Híbrido Optimizado Desplegando...")
        application.run_polling(drop_pending_updates=True)
