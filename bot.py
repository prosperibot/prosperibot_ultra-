import os
import httpx
import asyncio
import google.generativeai as genai
from flask import Flask
from telegram import Update, constants
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters
from threading import Thread

# --- CONFIGURACIÓN DE IA (GEMINI) ---
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model = genai.GenerativeModel('gemini-1.5-flash')
chat_sessions = {}

# --- MEMORIA Y PREFERENCIAS ---
user_prefs = {
    "min_liquidity": 25000,
    "style": "Analítico y profesional",
    "last_note": "Ninguna"
}

app = Flask(__name__)
@app.route('/')
def home(): return "Mente Maestra MC Losibe: Online 🧠"

# --- BLOQUE 1: ANALISTA TÉCNICO IA (LA MEJORA) ---
async def analizar_grafico_ia(pair_data):
    """Procesa los datos de acción de precio y da un veredicto"""
    nombre = pair_data.get('baseToken', {}).get('name', 'Token')
    
    # Datos de cambio de precio en distintas temporalidades
    m5 = pair_data.get('priceChange', {}).get('m5', 0)
    h1 = pair_data.get('priceChange', {}).get('h1', 0)
    h6 = pair_data.get('priceChange', {}).get('h6', 0)
    h24 = pair_data.get('priceChange', {}).get('h24', 0)
    
    liq = float(pair_data.get('liquidity', {}).get('usd', 0))
    vol = float(pair_data.get('volume', {}).get('h24', 0))
    
    prompt = (
        f"Analiza la estructura técnica de {nombre} en Solana.\n"
        f"Variación: 5m: {m5}% | 1h: {h1}% | 6h: {h6}% | 24h: {h24}%\n"
        f"Liquidez: ${liq:,.0f} | Volumen: ${vol:,.0f}\n\n"
        "Como trader experto, dime: ¿Es una tendencia sana, un pump artificial o está en zona de acumulación? "
        "Sé muy breve (máximo 3 líneas)."
    )

    try:
        response = model.generate_content(prompt)
        return response.text
    except:
        return "⚠️ Análisis técnico no disponible en este momento."

# --- BLOQUE 2: COMANDOS DE RADAR ---
async def mercado_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("🌐 Escaneando el ecosistema global...")
    try:
        url = "https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&ids=bitcoin,ethereum,solana&order=market_cap_desc"
        async with httpx.AsyncClient() as client:
            r = await client.get(url)
            data = r.json()
        
        rep = "🌍 **PULSO GLOBAL CRYPTO**\n"
        for c in data:
            rep += f"• **{c['name']}**: `${c['current_price']:,.2f}` ({c['price_change_percentage_24h']:.1f}%)\n"
        await msg.edit_text(rep, parse_mode=constants.ParseMode.MARKDOWN)
    except:
        await msg.edit_text("❌ Error al conectar con CoinGecko.")

async def sniper_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("🎯 Iniciando Sniper con Análisis IA...")
    try:
        url = "https://api.dexscreener.com/latest/dex/search?q=solana"
        async with httpx.AsyncClient() as client:
            r = await client.get(url)
            pairs = r.json().get('pairs', [])

        # Filtro de liquidez según tu entrenamiento
        min_liq = user_prefs["min_liquidity"]
        top_pairs = [p for p in pairs if float(p.get('liquidity', {}).get('usd', 0)) > min_liq][:3]

        if not top_pairs:
            await msg.edit_text(f"⚠️ No hay tokens con liquidez > ${min_liq:,.0f}.")
            return

        reporte = f"🚀 **RADAR SOLANA (Analista IA)**\n"
        reporte += f"⚙️ Filtro: `>${min_liq:,.0f} Liq`\n\n"

        for p in top_pairs:
            nombre = p['baseToken']['name']
            simbolo = p['baseToken']['symbol']
            
            # Llamamos a la IA para analizar el gráfico
            veredicto = await analizar_grafico_ia(p)
            
            reporte += f"🔹 **{nombre} ({simbolo})**\n"
            reporte += f"🧠 **IA:** _{veredicto}_\n"
            reporte += f"🔗 [Gráfico]({p['url']})\n\n"

        await msg.edit_text(reporte, parse_mode=constants.ParseMode.MARKDOWN, disable_web_page_preview=True)
    except Exception as e:
        await msg.edit_text(f"❌ Error en radar: {str(e)}")

# --- BLOQUE 3: APRENDIZAJE Y CHAT ---
async def aprender_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto = " ".join(context.args)
    if texto:
        if "liquidez" in texto.lower():
            nums = [int(s) for s in texto.split() if s.isdigit()]
            if nums: user_prefs["min_liquidity"] = nums[0]
        user_prefs["last_note"] = texto
        await update.message.reply_text(f"✅ Memoria actualizada: {texto}")

async def chat_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in chat_sessions:
        chat_sessions[user_id] = model.start_chat(history=[])
    
    instr = f"Eres el asistente de MC Losibe (Psicólogo y Rapero). Tu filtro: {user_prefs['min_liquidity']} USD. Nota: {user_prefs['last_note']}"
    try:
        res = chat_sessions[user_id].send_message(f"{instr}\n\nPregunta: {update.message.text}")
        await update.message.reply_text(res.text, parse_mode=constants.ParseMode.MARKDOWN)
    except:
        await update.message.reply_text("🤯 Estoy procesando mucha info. Intenta de nuevo.")

# --- INICIO ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ **Radar MC Losibe Online.**\n\n`/mercado` - Global\n`/sniper` - Solana IA\n`/aprender` - Ajustes")

if __name__ == "__main__":
    def run_f(): app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
    Thread(target=run_f, daemon=True).start()

    token = os.getenv("TELEGRAM_TOKEN")
    if token:
        app_tg = ApplicationBuilder().token(token).build()
        app_tg.add_handler(CommandHandler("start", start))
        app_tg.add_handler(CommandHandler("mercado", mercado_handler))
        app_tg.add_handler(CommandHandler("sniper", sniper_handler))
        app_tg.add_handler(CommandHandler("aprender", aprender_handler))
        app_tg.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), chat_handler))
        app_tg.run_polling()
