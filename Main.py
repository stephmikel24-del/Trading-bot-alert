n
import requests
import time
from datetime import datetime

# ═══════════════════════════════════════════
# YOUR PRIVATE DETAILS — FILL THESE IN
# ═══════════════════════════════════════════
TELEGRAM_TOKEN = "8426730533:AAF1YFHvkORgjdWkdbchMFktY8Ga4uQ5JWE"  # Paste your new BotFather token here
CHAT_ID        =  "6879729980"        # We'll get this in a moment

TIMEFRAMES = ["15", "240"]  # 15m and 4H
CHECK_INTERVAL = 60  # checks every 60 seconds

# ═══════════════════════════════════════════
# GET ALL BYBIT CRYPTO PAIRS
# ═══════════════════════════════════════════
def get_all_pairs():
    url = "https://api.bybit.com/v5/market/instruments-info?category=linear&limit=1000"
    try:
        res = requests.get(url, timeout=10).json()
        pairs = [
            item["symbol"]
            for item in res["result"]["list"]
            if item["symbol"].endswith("USDT") and item["status"] == "Trading"
        ]
        return pairs
    except:
        return ["BTCUSDT", "ETHUSDT", "SOLUSDT"]  # fallback

# ═══════════════════════════════════════════
# GET CANDLE DATA FROM BYBIT
# ═══════════════════════════════════════════
def get_candles(symbol, interval, limit=100):
    url = f"https://api.bybit.com/v5/market/kline?category=linear&symbol={symbol}&interval={interval}&limit={limit}"
    try:
        res = requests.get(url, timeout=10).json()
        candles = res["result"]["list"]
        # Each candle: [timestamp, open, high, low, close, volume, turnover]
        data = []
        for c in reversed(candles):
            data.append({
                "time":  int(c[0]),
                "open":  float(c[1]),
                "high":  float(c[2]),
                "low":   float(c[3]),
                "close": float(c[4]),
            })
        return data
    except:
        return []

# ═══════════════════════════════════════════
# FIND FIRST PEAK (HIGHEST HIGH IN LOOKBACK)
# ═══════════════════════════════════════════
def find_first_peak(candles, lookback=50):
    if len(candles) < lookback + 2:
        return None, None

    # Look at candles excluding the last one (current candle)
    search_candles = candles[-(lookback+1):-1]
    peak_high = max(c["high"] for c in search_candles)
    peak_wick = peak_high  # wick high = high of candle
    return peak_high, peak_wick

# ═══════════════════════════════════════════
# DETECT LIQUIDITY SWEEP SETUP
# ═══════════════════════════════════════════
def detect_sweep(candles):
    if len(candles) < 10:
        return False, None, None

    first_peak_high, first_peak_wick = find_first_peak(candles)
    if first_peak_high is None:
        return False, None, None

    # Current (last closed) candle
    current = candles[-1]
    c_high  = current["high"]
    c_open  = current["open"]
    c_close = current["close"]
    c_body_top = max(c_open, c_close)

    # ── Your Setup Rules ──────────────────
    wick_swept      = c_high > first_peak_wick          # wick went above first peak
    body_below      = c_body_top < first_peak_wick      # body closed below first peak wick
    bearish_candle  = c_close < c_open                  # bearish close

    if wick_swept and body_below and bearish_candle:
        stop_loss = c_high  # SL above sweep candle wick
        return True, current["close"], stop_loss

    return False, None, None

# ═══════════════════════════════════════════
# SEND TELEGRAM ALERT
# ═══════════════════════════════════════════
def send_alert(symbol, timeframe, entry, stop_loss):
    tf_label = "15m" if timeframe == "15" else "4H"
    risk = round(abs(stop_loss - entry), 6)
    message = (
        f"🚨 *LIQUIDITY SWEEP DETECTED!*\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📊 *Pair:* `{symbol}`\n"
        f"⏰ *Timeframe:* {tf_label}\n"
        f"📉 *Entry:* `{entry}`\n"
        f"🛑 *Stop Loss:* `{stop_loss}`\n"
        f"⚡ *Risk:* `{risk}`\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🕒 {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC"
    )
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(url, json={
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    })

# ═══════════════════════════════════════════
# MAIN LOOP
# ═══════════════════════════════════════════
def main():
    print("🤖 Bot started! Scanning all Bybit crypto pairs...")
    alerted = set()  # prevent duplicate alerts

    while True:
        pairs = get_all_pairs()
        print(f"📡 Scanning {len(pairs)} pairs... {datetime.utcnow().strftime('%H:%M:%S')}")

        for symbol in pairs:
            for tf in TIMEFRAMES:
                try:
                    candles = get_candles(symbol, tf)
                    detected, entry, sl = detect_sweep(candles)

                    if detected:
                        alert_key = f"{symbol}_{tf}_{candles[-1]['time']}"
                        if alert_key not in alerted:
                            print(f"🚨 SWEEP FOUND: {symbol} {tf}")
                            send_alert(symbol, tf, entry, sl)
                            alerted.add(alert_key)

                except Exception as e:
                    print(f"Error on {symbol} {tf}: {e}")
                    continue

                time.sleep(0.1)  # avoid hitting API rate limits

        # Clear old alerts every 24 hours
        if len(alerted) > 10000:
            alerted.clear()

        print(f"✅ Scan complete. Waiting {CHECK_INTERVAL}s...\n")
        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    main()
