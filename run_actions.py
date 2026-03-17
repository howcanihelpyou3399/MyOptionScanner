import os
import json
import logging
import requests
import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime
import pytz

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger("scanner")

# Read secrets from environment
TELEGRAM_TOKEN   = os.environ.get("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

# Paths (relative, for GitHub Actions)
WATCHLIST_PATH = "MyOptionScanner/input/watchlist.csv"
OUTPUT_DIR = "MyOptionScanner/output"
os.makedirs(OUTPUT_DIR, exist_ok=True)


def send_message(text):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        logger.error("Telegram credentials missing")
        return False
    url = "https://api.telegram.org/bot" + TELEGRAM_TOKEN + "/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "HTML"}
    try:
        r = requests.post(url, json=payload, timeout=10)
        result = r.json()
        if result.get("ok"):
            logger.info("Telegram OK")
            return True
        else:
            logger.error("Telegram FAIL: " + result.get("description", "unknown"))
            return False
    except Exception as e:
        logger.error("Telegram ERROR: " + str(e))
        return False


def calculate_iv_rank(symbol):
    logger.info("Fetching: " + symbol)
    try:
        ticker = yf.Ticker(symbol)
        hist   = ticker.history(period="1y")
        if hist.empty:
            return None, "No price data"
        closes  = hist["Close"].values
        if len(closes) < 20:
            return None, "Not enough data"
        returns = np.diff(np.log(closes))
        window  = 20
        vols    = []
        for i in range(window, len(returns)):
            v = np.std(returns[i-window:i]) * np.sqrt(252) * 100
            vols.append(v)
        if len(vols) < 2:
            return None, "Not enough vol data"
        current_vol = vols[-1]
        vol_min     = min(vols)
        vol_max     = max(vols)
        if vol_max == vol_min:
            return 50.0, None
        iv_rank = (current_vol - vol_min) / (vol_max - vol_min) * 100
        logger.info(symbol + " vol=" + str(round(current_vol,1)) + "% iv_rank=" + str(round(iv_rank,1)))
        return round(iv_rank, 1), None
    except Exception as e:
        return None, str(e)


def format_report(results, scan_date):
    qualified = [r for r in results if r.get("qualified")]
    waiting   = [r for r in results if not r.get("qualified")]
    lines = []
    lines.append("<b>Option Scanner " + scan_date + "</b>")
    lines.append("")
    if qualified:
        lines.append("OK - Act now:")
        for r in qualified:
            s    = "CC" if r["strategy"] == "covered_call" else "CSP"
            line = "  " + r["symbol"]
            line += " IV:" + str(round(r["iv_rank"]))
            line += " " + s
            line += " $" + str(round(r["current_price"], 2))
            lines.append(line)
    else:
        lines.append("OK - Act now: none today")
    lines.append("")
    if waiting:
        lines.append("WAIT - Watching:")
        for r in waiting:
            if r.get("error"):
                lines.append("  " + r["symbol"] + " ERROR: " + r["error"])
            else:
                line  = "  " + r["symbol"]
                line += " IV:" + str(round(r["iv_rank"]))
                line += " (need:" + str(r["min_iv_rank"]) + ")"
                lines.append(line)
    lines.append("")
    lines.append("Scan: " + scan_date)
    lines.append("")
    lines.append("<i>Not investment advice</i>")
    return "\n".join(lines)


def main():
    now_et  = datetime.now(pytz.timezone("America/New_York"))
    today   = now_et.strftime("%Y-%m-%d")

    logger.info("=" * 40)
    logger.info("MyOptionScanner - " + today)
    logger.info("=" * 40)

    # Load watchlist
    try:
        df = pd.read_csv(WATCHLIST_PATH)
        logger.info("Loaded " + str(len(df)) + " symbols")
    except Exception as e:
        logger.error("Watchlist FAIL: " + str(e))
        send_message("MyOptionScanner ERROR: " + str(e))
        return

    # Scan
    results = []
    for _, row in df.iterrows():
        symbol    = row["symbol"]
        threshold = int(row["min_iv_rank"]) if pd.notna(row["min_iv_rank"]) else 50
        iv_rank, error = calculate_iv_rank(symbol)

        ticker = yf.Ticker(symbol)
        hist   = ticker.history(period="5d")
        price  = float(hist["Close"].iloc[-1]) if not hist.empty else 0.0

        results.append({
            "symbol":       symbol,
            "name":         row["name"],
            "strategy":     row["strategy"],
            "iv_rank":      float(iv_rank) if iv_rank is not None else 0.0,
            "min_iv_rank":  threshold,
            "current_price":round(price, 2),
            "qualified":    iv_rank is not None and iv_rank >= threshold,
            "error":        error
        })

    # Save output
    output_path = OUTPUT_DIR + "/" + today + ".json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump({"date": today, "results": results}, f, indent=2)
    logger.info("Output saved: " + output_path)

    # Telegram - only if qualified
    qualified = [r for r in results if r.get("qualified")]
    if qualified:
        logger.info(str(len(qualified)) + " qualified - sending Telegram")
        send_message(format_report(results, today))
    else:
        logger.info("0 qualified - skipping Telegram, log only")

    logger.info("Done - " + today)


if __name__ == "__main__":
    main()
