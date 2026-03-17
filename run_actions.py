import os, json, logging, requests as req, pandas as pd, numpy as np, yfinance as yf
from datetime import datetime
import pytz

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger('scanner')

TELEGRAM_TOKEN   = os.environ.get('TELEGRAM_TOKEN', '')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID', '')
WATCHLIST_PATH   = 'MyOptionScanner/input/watchlist.csv'
OUTPUT_DIR       = 'MyOptionScanner/output'
os.makedirs(OUTPUT_DIR, exist_ok=True)

def send_message(text):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        logger.error('Telegram credentials missing')
        return False
    url = 'https://api.telegram.org/bot' + TELEGRAM_TOKEN + '/sendMessage'
    payload = {'chat_id': TELEGRAM_CHAT_ID, 'text': text, 'parse_mode': 'HTML'}
    try:
        r = req.post(url, json=payload, timeout=10)
        result = r.json()
        if result.get('ok'):
            logger.info('Telegram OK')
            return True
        else:
            logger.error('Telegram FAIL: ' + result.get('description', 'unknown'))
            return False
    except Exception as e:
        logger.error('Telegram ERROR: ' + str(e))
        return False

def calculate_iv_percentile(symbol):
    logger.info('Fetching: ' + symbol)
    try:
        ticker = yf.Ticker(symbol)
        hist   = ticker.history(period='1y')
        if hist.empty:
            return None, 'No price data'
        closes = hist['Close'].values
        if len(closes) < 22:
            return None, 'Not enough data'
        returns = np.diff(np.log(closes))
        window  = 20
        vols    = []
        for i in range(window, len(returns)):
            v = np.std(returns[i-window:i]) * np.sqrt(252) * 100
            vols.append(v)
        if len(vols) < 2:
            return None, 'Not enough vol data'
        current_vol = vols[-1]
        count_below = sum(1 for v in vols[:-1] if v < current_vol)
        iv_pct = round(count_below / len(vols[:-1]) * 100, 1)
        logger.info(symbol + ' vol=' + str(round(current_vol,1)) + '% iv_pct=' + str(iv_pct))
        return iv_pct, None
    except Exception as e:
        return None, str(e)

def format_report(results, scan_date):
    qualified = [r for r in results if r.get('qualified') == 1]
    waiting   = [r for r in results if r.get('qualified') != 1]
    lines = []
    lines.append('<b>Option Scanner ' + scan_date + '</b>')
    lines.append('')
    if qualified:
        lines.append('OK - Act now:')
        for r in qualified:
            s = 'CC' if r['strategy'] == 'covered_call' else 'CSP'
            lines.append('  ' + r['symbol'] + ' IVP:' + str(r['iv_percentile']) + '% ' + s + ' $' + str(round(r['current_price'],2)))
    else:
        lines.append('OK - Act now: none today')
    lines.append('')
    if waiting:
        lines.append('WAIT - Watching:')
        for r in waiting:
            if r.get('error'):
                lines.append('  ' + r['symbol'] + ' ERROR: ' + r['error'])
            else:
                lines.append('  ' + r['symbol'] + ' IVP:' + str(r['iv_percentile']) + '% (need:' + str(r['min_iv_rank']) + '%)')
    lines.append('')
    lines.append('Scan: ' + scan_date)
    lines.append('')
    lines.append('<i>Not investment advice</i>')
    return chr(10).join(lines)

def main():
    now_et = datetime.now(pytz.timezone('America/New_York'))
    today  = now_et.strftime('%Y-%m-%d')
    logger.info('=' * 40)
    logger.info('MyOptionScanner - ' + today)
    logger.info('=' * 40)
    try:
        df = pd.read_csv(WATCHLIST_PATH)
        logger.info('Loaded ' + str(len(df)) + ' symbols')
    except Exception as e:
        logger.error('Watchlist FAIL: ' + str(e))
        send_message('MyOptionScanner ERROR: ' + str(e))
        return
    results = []
    for _, row in df.iterrows():
        symbol    = row['symbol']
        threshold = int(row['min_iv_rank']) if pd.notna(row['min_iv_rank']) else 50
        iv_pct, error = calculate_iv_percentile(symbol)
        ticker = yf.Ticker(symbol)
        hist   = ticker.history(period='5d')
        price  = float(hist['Close'].iloc[-1]) if not hist.empty else 0.0
        results.append({
            'symbol':        str(symbol),
            'name':          str(row['name']),
            'strategy':      str(row['strategy']),
            'iv_percentile': float(iv_pct) if iv_pct is not None else 0.0,
            'min_iv_rank':   int(threshold),
            'current_price': float(round(price, 2)),
            'qualified':     int(1 if (iv_pct is not None and iv_pct >= threshold) else 0),
            'error':         str(error) if error else ''
        })
    output_path = OUTPUT_DIR + '/' + today + '.json'
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump({'date': today, 'results': results}, f, indent=2)
        logger.info('Output saved: ' + output_path)
    except Exception as e:
        logger.error('Output FAIL: ' + str(e))
    qualified_list = [r for r in results if r.get('qualified') == 1]
    if qualified_list:
        logger.info(str(len(qualified_list)) + ' qualified - sending Telegram')
        send_message(format_report(results, today))
    else:
        logger.info('0 qualified - skipping Telegram, log only')
    logger.info('Done - ' + today)

if __name__ == '__main__':
    main()