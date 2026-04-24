import os
import httpx
import logging
import asyncio
import pandas as pd
import numpy as np
import google.generativeai as genai
from flask import Flask
from telegram import Update, constants
from telegram.ext import (
    ApplicationBuilder, CommandHandler, ContextTypes,
    MessageHandler, filters
)
from threading import Thread
from datetime import datetime, timezone

# ─────────────────────────────────────────
#  CONFIGURACIÓN
# ─────────────────────────────────────────
logging.basicConfig(level=logging.INFO)
app = Flask(__name__)

@app.route('/')
def health():
    return "Cerebro Racional MC Losibe: Operativo 🧠", 200

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model = genai.GenerativeModel('gemini-1.5-flash')
chat_sessions = {}

COINGECKO_BASE = "https://api.coingecko.com/api/v3"

# ─────────────────────────────────────────
#  CAPA DE DATOS: COINGECKO
# ─────────────────────────────────────────

async def get_price(coin_id: str) -> dict:
    """Precio actual, volumen y variación 24h."""
    url = f"{COINGECKO_BASE}/simple/price"
    params = {
        "ids": coin_id,
        "vs_currencies": "usd",
        "include_24hr_vol": "true",
        "include_24hr_change": "true",
        "include_market_cap": "true",
    }
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(url, params=params)
        r.raise_for_status()
        data = r.json()
        return data.get(coin_id, {})


async def get_ohlc(coin_id: str, days: int = 14) -> list:
    """OHLC en USD (velas diarias)."""
    url = f"{COINGECKO_BASE}/coins/{coin_id}/ohlc"
    params = {"vs_currency": "usd", "days": days}
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.get(url, params=params)
        r.raise_for_status()
        return r.json()  # [[timestamp, open, high, low, close], ...]


async def resolve_coin_id(symbol: str) -> str:
    """Convierte símbolo (BTC, ETH…) en coin_id de CoinGecko."""
    MAPPING = {
        "btc": "bitcoin", "eth": "ethereum", "bnb": "binancecoin",
        "sol": "solana", "xrp": "ripple", "ada": "cardano",
        "doge": "dogecoin", "avax": "avalanche-2", "dot": "polkadot",
        "matic": "matic-network", "link": "chainlink", "ltc": "litecoin",
        "uni": "uniswap", "atom": "cosmos", "near": "near",
        "trx": "tron", "ton": "the-open-network",
    }
    return MAPPING.get(symbol.lower(), symbol.lower())


# ─────────────────────────────────────────
#  CAPA DE ANÁLISIS TÉCNICO
# ─────────────────────────────────────────

def calcular_rsi(closes: list, period: int = 14) -> float:
    """RSI clásico de Wilder."""
    if len(closes) < period + 1:
        return None
    deltas = np.diff(closes)
    gains = np.where(deltas > 0, deltas, 0.0)
    losses = np.where(deltas < 0, -deltas, 0.0)
    avg_gain = np.mean(gains[:period])
    avg_loss = np.mean(losses[:period])
    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return round(100 - (100 / (1 + rs)), 2)


def calcular_ema(closes: list, period: int) -> list:
    """EMA estándar."""
    if len(closes) < period:
        return []
    k = 2 / (period + 1)
    ema = [sum(closes[:period]) / period]
    for price in closes[period:]:
        ema.append(price * k + ema[-1] * (1 - k))
    return ema


def calcular_macd(closes: list) -> dict:
    """MACD (12,26,9)."""
    ema12 = calcular_ema(closes, 12)
    ema26 = calcular_ema(closes, 26)
    if not ema12 or not ema26:
        return {}
    # Alinear por el largo menor
    diff = len(ema12) - len(ema26)
    macd_line = [e12 - e26 for e12, e26 in zip(ema12[diff:], ema26)]
    signal = calcular_ema(macd_line, 9)
    if not signal:
        return {}
    histogram = [m - s for m, s in zip(macd_line[-len(signal):], signal)]
    return {
        "macd": round(macd_line[-1], 6),
        "signal": round(signal[-1], 6),
        "histogram": round(histogram[-1], 6),
    }


def analizar_indicadores(ohlc_data: list) -> dict:
    """Calcula RSI, EMA20, EMA50, MACD sobre los datos OHLC."""
    if not ohlc_data or len(ohlc_data) < 15:
        return {"error": "Datos insuficientes para análisis técnico"}

    closes = [candle[4] for candle in ohlc_data]  # índice 4 = close

    rsi = calcular_rsi(closes)
    ema20 = calcular_ema(closes, 20)
    ema50 = calcular_ema(closes, 50)
    macd = calcular_macd(closes)

    precio_actual = closes[-1]
    tendencia = "neutral"
    if ema20 and ema50:
        if ema20[-1] > ema50[-1]:
            tendencia = "alcista 📈"
        elif ema20[-1] < ema50[-1]:
            tendencia = "bajista 📉"

    return {
        "precio_actual": precio_actual,
        "rsi": rsi,
        "ema20": round(ema20[-1], 4) if ema20 else None,
        "ema50": round(ema50[-1], 4) if ema50 else None,
        "macd": macd,
        "tendencia_ema": tendencia,
        "velas_analizadas": len(ohlc_data),
    }


# ─────────────────────────────────────────
#  GESTIÓN DE RIESGO
# ─────────────────────────────────────────

def calcular_riesgo(precio: float, capital: float, riesgo_pct: float = 1.0, stop_pct: float = 3.0) -> dict:
    """
    Calcula tamaño de posición con gestión de riesgo.
    - capital: capital total en USD
    - riesgo_pct: % del capital a arriesgar (default 1%)
    - stop_pct: % de stop loss desde entrada (default 3%)
    """
    monto_riesgo = capital * (riesgo_pct / 100)
    stop_loss = precio * (1 - stop_pct / 100)
    take_profit_1 = precio * (1 + stop_pct * 1.5 / 100)  # R:R 1.5
    take_profit_2 = precio * (1 + stop_pct * 2.5 / 100)  # R:R 2.5

    perdida_por_unidad = precio - stop_loss
    if perdida_por_unidad <= 0:
        return {}

    unidades = monto_riesgo / perdida_por_unidad
    tamaño_posicion = unidades * precio

    return {
        "entrada_sugerida": round(precio, 4),
        "stop_loss": round(stop_loss, 4),
        "take_profit_1": round(take_profit_1, 4),
        "take_profit_2": round(take_profit_2, 4),
        "tamaño_posicion_usd": round(tamaño_posicion, 2),
        "unidades": round(unidades, 6),
        "capital_en_riesgo_usd": round(monto_riesgo, 2),
        "riesgo_pct": riesgo_pct,
        "ratio_riesgo_recompensa_tp1": "1:1.5",
        "ratio_riesgo_recompensa_tp2": "1:2.5",
    }


# ─────────────────────────────────────────
#  MOTOR DE IA (PROMPT MEJORADO)
# ─────────────────────────────────────────

def prompt_analista(mensaje_usuario: str, contexto_mercado: str = "") -> str:
    mercado_str = f"\n\n📊 DATOS DE MERCADO EN TIEMPO REAL:\n{contexto_mercado}" if contexto_mercado else ""
    return (
        "Eres el Socio Estratégico de MC Losibe: analista cripto experto con mente de trader cuantitativo. "
        "Combinas análisis técnico, gestión de riesgo y psicología de trading.\n\n"
        "ESTRUCTURA DE RESPUESTA OBLIGATORIA:\n"
        "1. 🔍 OBSERVACIÓN: Qué está pidiendo/planteando realmente el usuario.\n"
        "2. 📊 ANÁLISIS: Datos técnicos, niveles clave, momentum, contexto macro.\n"
        "3. ⚠️ RIESGOS: Qué puede salir mal. Sé honesto, no vendas ilusiones.\n"
        "4. ✅ DECISIÓN RACIONAL: Acción concreta con lógica clara.\n\n"
        "REGLAS:\n"
        "- Nunca des señales de compra/venta sin justificación técnica.\n"
        "- Siempre menciona el stop loss y gestión de riesgo.\n"
        "- Si el RSI > 70: zona de sobrecompra. Si RSI < 30: sobreventa.\n"
        "- Responde en español, de forma directa y accionable.\n"
        f"- Máximo 400 palabras."
        f"{mercado_str}\n\n"
        f"Usuario: {mensaje_usuario}\n"
        "Responde con tu análisis racional:"
    )


# ─────────────────────────────────────────
#  HANDLERS TELEGRAM
# ─────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "🧠 *Cerebro Racional MC Losibe — Activado*\n\n"
        "Comandos disponibles:\n"
        "• `/precio BTC` — Precio + variación 24h\n"
        "• `/analisis BTC` — Indicadores técnicos completos\n"
        "• `/sniper BTC` — Señal de entrada con gestión de riesgo\n"
        "• `/riesgo BTC 1000 1 3` — Calc. riesgo (capital, %riesgo, %stop)\n\n"
        "O simplemente escríbeme y debatimos cualquier trade 💬"
    )
    await update.message.reply_text(msg, parse_mode='Markdown')


async def cmd_precio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler para /precio BTC"""
    args = context.args
    if not args:
        await update.message.reply_text("Uso: `/precio BTC`", parse_mode='Markdown')
        return

    coin_sym = args[0].upper()
    coin_id = await resolve_coin_id(args[0])

    await update.message.reply_text(f"🔍 Consultando precio de *{coin_sym}*...", parse_mode='Markdown')

    try:
        data = await get_price(coin_id)
        if not data:
            await update.message.reply_text(f"❌ No encontré datos para `{coin_sym}`. Verifica el símbolo.")
            return

        precio = data.get("usd", 0)
        cambio = data.get("usd_24h_change", 0)
        volumen = data.get("usd_24h_vol", 0)
        mcap = data.get("usd_market_cap", 0)
        emoji = "🟢" if cambio >= 0 else "🔴"

        msg = (
            f"💰 *{coin_sym}* — Precio en tiempo real\n\n"
            f"Precio: `${precio:,.4f}`\n"
            f"Cambio 24h: {emoji} `{cambio:+.2f}%`\n"
            f"Volumen 24h: `${volumen:,.0f}`\n"
            f"Market Cap: `${mcap:,.0f}`\n\n"
            f"🕐 `{datetime.now(timezone.utc).strftime('%H:%M UTC')}`"
        )
        await update.message.reply_text(msg, parse_mode='Markdown')

    except Exception as e:
        logging.error(f"Error precio: {e}")
        await update.message.reply_text("❌ Error al obtener datos. CoinGecko puede estar en rate-limit.")


async def cmd_analisis(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler para /analisis BTC — Indicadores técnicos completos."""
    args = context.args
    if not args:
        await update.message.reply_text("Uso: `/analisis BTC`", parse_mode='Markdown')
        return

    coin_sym = args[0].upper()
    coin_id = await resolve_coin_id(args[0])

    await update.message.reply_text(f"⚙️ Calculando indicadores para *{coin_sym}*...", parse_mode='Markdown')

    try:
        ohlc = await get_ohlc(coin_id, days=60)
        indicadores = analizar_indicadores(ohlc)

        if "error" in indicadores:
            await update.message.reply_text(f"⚠️ {indicadores['error']}")
            return

        rsi = indicadores["rsi"]
        rsi_emoji = "🔴 Sobrecompra" if rsi and rsi > 70 else ("🟢 Sobreventa" if rsi and rsi < 30 else "🟡 Neutral")

        macd = indicadores["macd"]
        macd_str = "N/A"
        if macd:
            hist = macd.get("histogram", 0)
            macd_emoji = "📈" if hist > 0 else "📉"
            macd_str = f"`{macd.get('macd', 0):.6f}` {macd_emoji} Histograma: `{hist:.6f}`"

        msg = (
            f"📊 *Análisis Técnico — {coin_sym}* (últimas 60 velas diarias)\n\n"
            f"💵 Precio actual: `${indicadores['precio_actual']:,.4f}`\n"
            f"📈 Tendencia EMA: *{indicadores['tendencia_ema']}*\n\n"
            f"*Indicadores:*\n"
            f"• RSI(14): `{rsi}` — {rsi_emoji}\n"
            f"• EMA20: `${indicadores['ema20']:,.4f}`\n"
            f"• EMA50: `${indicadores['ema50']:,.4f}`\n"
            f"• MACD(12,26,9): {macd_str}\n\n"
            f"🕐 `{datetime.now(timezone.utc).strftime('%H:%M UTC')}`"
        )
        await update.message.reply_text(msg, parse_mode='Markdown')

    except Exception as e:
        logging.error(f"Error análisis: {e}")
        await update.message.reply_text("❌ Error al calcular indicadores.")


async def cmd_sniper(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler para /sniper BTC — Señal de entrada + gestión de riesgo + IA."""
    args = context.args
    if not args:
        await update.message.reply_text("Uso: `/sniper BTC`", parse_mode='Markdown')
        return

    coin_sym = args[0].upper()
    coin_id = await resolve_coin_id(args[0])

    await update.message.reply_text(f"🎯 Analizando entrada sniper para *{coin_sym}*...", parse_mode='Markdown')

    try:
        precio_data, ohlc = await asyncio.gather(
            get_price(coin_id),
            get_ohlc(coin_id, days=60)
        )

        indicadores = analizar_indicadores(ohlc)
        precio_actual = precio_data.get("usd", indicadores.get("precio_actual", 0))
        cambio_24h = precio_data.get("usd_24h_change", 0)

        riesgo = calcular_riesgo(precio_actual, capital=1000, riesgo_pct=1.0, stop_pct=3.0)

        # Construir contexto para Gemini
        rsi = indicadores.get("rsi", "N/A")
        macd = indicadores.get("macd", {})
        tendencia = indicadores.get("tendencia_ema", "neutral")

        contexto = (
            f"Moneda: {coin_sym}\n"
            f"Precio: ${precio_actual:,.4f}\n"
            f"Cambio 24h: {cambio_24h:+.2f}%\n"
            f"RSI(14): {rsi}\n"
            f"Tendencia EMA20/50: {tendencia}\n"
            f"MACD histograma: {macd.get('histogram', 'N/A')}\n"
            f"Stop Loss sugerido: ${riesgo.get('stop_loss', 'N/A')}\n"
            f"TP1 (R:R 1.5): ${riesgo.get('take_profit_1', 'N/A')}\n"
            f"TP2 (R:R 2.5): ${riesgo.get('take_profit_2', 'N/A')}"
        )

        uid = update.effective_user.id
        if uid not in chat_sessions:
            chat_sessions[uid] = model.start_chat(history=[])

        prompt = prompt_analista(
            f"Dame una señal sniper detallada para {coin_sym}. ¿Es buen momento para entrar?",
            contexto_mercado=contexto
        )
        response = chat_sessions[uid].send_message(prompt)

        # Mensaje con datos duros
        header = (
            f"🎯 *SNIPER — {coin_sym}*\n\n"
            f"💵 Precio: `${precio_actual:,.4f}` ({cambio_24h:+.2f}%)\n"
            f"🛑 Stop Loss: `${riesgo.get('stop_loss', 'N/A')}`\n"
            f"🎯 TP1: `${riesgo.get('take_profit_1', 'N/A')}` (R:R 1.5)\n"
            f"🎯 TP2: `${riesgo.get('take_profit_2', 'N/A')}` (R:R 2.5)\n"
            f"💼 Posición (capital $1000): `${riesgo.get('tamaño_posicion_usd', 'N/A')}`\n\n"
            f"🧠 *Análisis IA:*\n"
        )
        await update.message.reply_text(header + response.text, parse_mode='Markdown')

    except Exception as e:
        logging.error(f"Error sniper: {e}")
        await update.message.reply_text("❌ Error al calcular señal sniper.")


async def cmd_riesgo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler para /riesgo BTC 1000 1 3 — Calculadora de riesgo personalizada."""
    args = context.args
    if len(args) < 4:
        await update.message.reply_text(
            "Uso: `/riesgo BTC 1000 1 3`\n"
            "_(moneda) (capital USD) (%riesgo) (%stop)_",
            parse_mode='Markdown'
        )
        return

    try:
        coin_sym = args[0].upper()
        coin_id = await resolve_coin_id(args[0])
        capital = float(args[1])
        riesgo_pct = float(args[2])
        stop_pct = float(args[3])

        precio_data = await get_price(coin_id)
        precio = precio_data.get("usd", 0)
        if not precio:
            await update.message.reply_text("❌ No se pudo obtener el precio.")
            return

        r = calcular_riesgo(precio, capital, riesgo_pct, stop_pct)

        msg = (
            f"📐 *Gestión de Riesgo — {coin_sym}*\n\n"
            f"Capital total: `${capital:,.2f}`\n"
            f"% en riesgo: `{riesgo_pct}%` → `${r['capital_en_riesgo_usd']}`\n\n"
            f"📍 Entrada: `${r['entrada_sugerida']:,.4f}`\n"
            f"🛑 Stop Loss ({stop_pct}%): `${r['stop_loss']:,.4f}`\n"
            f"🎯 TP1 (R:R 1.5): `${r['take_profit_1']:,.4f}`\n"
            f"🎯 TP2 (R:R 2.5): `${r['take_profit_2']:,.4f}`\n\n"
            f"💼 Tamaño posición: `${r['tamaño_posicion_usd']:,.2f}`\n"
            f"📦 Unidades: `{r['unidades']} {coin_sym}`"
        )
        await update.message.reply_text(msg, parse_mode='Markdown')

    except ValueError:
        await update.message.reply_text("❌ Verifica los parámetros numéricos.")
    except Exception as e:
        logging.error(f"Error riesgo: {e}")
        await update.message.reply_text("❌ Error al calcular gestión de riesgo.")


async def chat_racional(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Conversación libre con contexto de mercado si se menciona una moneda conocida."""
    uid = update.effective_user.id
    texto = update.message.text

    if uid not in chat_sessions:
        chat_sessions[uid] = model.start_chat(history=[])

    # Intentar detectar moneda en el mensaje para enriquecer el contexto
    contexto_mercado = ""
    MONEDAS = ["btc", "eth", "sol", "bnb", "xrp", "ada", "doge", "avax", "bitcoin", "ethereum", "solana"]
    coin_detectada = next((m for m in MONEDAS if m in texto.lower()), None)

    if coin_detectada:
        try:
            coin_id = await resolve_coin_id(coin_detectada)
            precio_data = await get_price(coin_id)
            cambio = precio_data.get("usd_24h_change", 0)
            precio = precio_data.get("usd", 0)
            contexto_mercado = (
                f"{coin_detectada.upper()}: ${precio:,.4f} ({cambio:+.2f}% 24h)"
            )
        except Exception:
            pass

    try:
        response = chat_sessions[uid].send_message(
            prompt_analista(texto, contexto_mercado)
        )
        await update.message.reply_text(response.text, parse_mode='Markdown')
    except Exception as e:
        logging.error(f"Error chat: {e}")
        await update.message.reply_text(
            "🤯 Mi proceso de razonamiento se bloqueó. Simplifica la pregunta o intenta de nuevo."
        )


# ─────────────────────────────────────────
#  ARRANQUE
# ─────────────────────────────────────────

if __name__ == "__main__":
    Thread(
        target=lambda: app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000))),
        daemon=True
    ).start()

    token = os.getenv("TELEGRAM_TOKEN")
    if token:
        app_tg = ApplicationBuilder().token(token).build()

        app_tg.add_handler(CommandHandler("start",    start))
        app_tg.add_handler(CommandHandler("precio",   cmd_precio))
        app_tg.add_handler(CommandHandler("analisis", cmd_analisis))
        app_tg.add_handler(CommandHandler("sniper",   cmd_sniper))
        app_tg.add_handler(CommandHandler("riesgo",   cmd_riesgo))
        app_tg.add_handler(MessageHandler(
            filters.TEXT & (~filters.COMMAND), chat_racional
        ))

        logging.info("🧠 Bot iniciado correctamente")
        app_tg.run_polling(drop_pending_updates=True)
    else:
        logging.error("❌ TELEGRAM_TOKEN no configurado")
