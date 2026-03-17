import json
import logging
import requests
from datetime import datetime
import pytz

logger = logging.getLogger(__name__)


def send_message(token, chat_id, text):
    url = "https://api.telegram.org/bot" + token + "/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML"
    }
    logger.info("[Telegram] Sending, length: " + str(len(text)))
    try:
        r = requests.post(url, json=payload, timeout=10)
        result = r.json()
        if result.get("ok"):
            logger.info("[Telegram] OK")
            return True
        else:
            logger.error("[Telegram] FAIL: " + result.get("description", "unknown"))
            return False
    except Exception as e:
        logger.error("[Telegram] ERROR: " + str(e))
        return False


def format_test_message():
    now = datetime.now(pytz.timezone("America/New_York"))
    ts = now.strftime("%Y-%m-%d %H:%M:%S")
    msg = "<b>MyOptionScanner Test</b>\n\n"
    msg += "Telegram OK\n"
    msg += "Time: " + ts + " ET\n\n"
    msg += "System ready"
    return msg


def format_scan_report(results, scan_date):
    qualified = [r for r in results if r.get("qualified")]
    waiting   = [r for r in results if not r.get("qualified")]
    lines = []
    lines.append("<b>Option Scanner " + scan_date + "</b>")
    lines.append("")
    if qualified:
        lines.append("OK - Act now:")
        for r in qualified:
            s = "CC" if r["strategy"] == "covered_call" else "CSP"
            line = "  " + r["symbol"]
            line += " IV:" + str(round(r["iv_rank"]))
            line += " " + s
            line += " $" + str(round(r["current_price"], 2))
            lines.append(line)
    else:
        lines.append("OK - Act now: none this week")
    lines.append("")
    if waiting:
        lines.append("WAIT - Watching:")
        for r in waiting:
            if r.get("error"):
                lines.append("  " + r["symbol"] + " ERROR: " + r["error"])
            else:
                line = "  " + r["symbol"]
                line += " IV:" + str(round(r["iv_rank"]))
                line += " (need:" + str(r["min_iv_rank"]) + ")"
                lines.append(line)
    lines.append("")
    lines.append("Scan: " + scan_date)
    lines.append("Next: Next Monday")
    lines.append("")
    lines.append("<i>Not investment advice</i>")
    return "\n".join(lines)


def format_error_report(error_msg):
    now = datetime.now(pytz.timezone("America/New_York"))
    ts = now.strftime("%Y-%m-%d %H:%M")
    msg = "<b>MyOptionScanner Error</b>\n\n"
    msg += ts + "\n"
    msg += "<code>" + error_msg + "</code>"
    return msg


def test_connection(config_path):
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s"
    )
    print("=" * 40)
    print("  Telegram Connection Test")
    print("=" * 40)
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
        print("OK - config loaded")
    except FileNotFoundError:
        print("FAIL - config.json not found")
        print("Path: " + config_path)
        return False
    except Exception as e:
        print("FAIL - " + str(e))
        return False

    token   = config.get("telegram", {}).get("token", "")
    chat_id = config.get("telegram", {}).get("chat_id", "")

    if not token or token == "YOUR_BOT_TOKEN_HERE":
        print("FAIL - token not set in config.json")
        return False
    if not chat_id or chat_id == "YOUR_CHAT_ID_HERE":
        print("FAIL - chat_id not set in config.json")
        return False

    print("OK - token: ..." + token[-6:])
    print("OK - chat_id: " + chat_id)

    success = send_message(token, chat_id, format_test_message())
    print("=" * 40)
    if success:
        print("  SUCCESS - Check your Telegram")
    else:
        print("  FAIL - Check token and chat_id")
    print("=" * 40)
    return success
