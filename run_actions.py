import os, json, logging, requests as req, pandas as pd, numpy as np, yfinance as yf
from datetime import datetime
from scipy.stats import norm
import pytz

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger('scanner')

TELEGRAM_TOKEN   = os.environ.get('TELEGRAM_TOKEN', '')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID', '')
WATCHLIST_PATH   = 'MyOptionScanner/input/watchlist.csv'
OUTPUT_DIR       = 'MyOptionScanner/output'
os.makedirs(OUTPUT_DIR, exist_ok=True)

VIX_HIGH            = 25.0
VIX_LOW             = 15.0
VIX_HIGH_MULTIPLIER = 0.85
VIX_LOW_MULTIPLIER  = 1.15
GAMMA_WARN          = 0.05
GAMMA_LIMIT         = 0.10
RISK_FREE_RATE      = 0.05

def get_vix():
    try:
        hist = yf.Ticker('^VIX').history(period='5d')
        if hist.empty:
            return 20.0
        v = round(float(hist['Close'].iloc[-1]), 2)
        logger.info('VIX: ' + str(v))
        return v
    except Exception as e:
        logger.error('VIX error: ' + str(e))
        return 20.0

def get_vix_regime(vix):
    if vix > VIX_HIGH:
        return 'HIGH', VIX_HIGH_MULTIPLIER
    elif vix < VIX_LOW:
        return 'LOW', VIX_LOW_MULTIPLIER
    else:
        return 'NORMAL', 1.0

def adjust_threshold(base, multiplier):
    return round(base * multiplier, 1)

def bs_greeks(S, K, T, r, sigma, option_type):
    if T <= 0 or sigma <= 0:
        return None, None
    d1    = (np.log(S/K) + (r + 0.5*sigma**2)*T) / (sigma*np.sqrt(T))
    d2    = d1 - sigma*np.sqrt(T)
    delta = norm.cdf(d1) if option_type == 'call' else norm.cdf(d1) - 1
    gamma = norm.pdf(d1) / (S * sigma * np.sqrt(T))
    return round(abs(delta), 4), round(gamma, 6)

def send_message(text):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        logger.error('Telegram credentials missing')
        return False
    url     = 'https://api.telegram.org/bot' + TELEGRAM_TOKEN + '/sendMessage'
    payload = {'chat_id': TELEGRAM_CHAT_ID, 'text': text, 'parse_mode': 'HTML'}
    try:
        r      = req.post(url, json=payload, timeout=10)
        result = r.json()
        if result.get('ok'):
            logger.info('Telegram OK')
            return True
        else:
            logger.error('Telegram FAIL: ' + result.get('description','unknown'))
            return False
    except Exception as e:
        logger.error('Telegram ERROR: ' + str(e))
        return False

def calculate_iv_percentile(symbol):
    try:
        hist = yf.Ticker(symbol).history(period='1y')
        if hist.empty or len(hist) < 22:
            return None, 'Not enough data'
        closes  = hist['Close'].values
        returns = np.diff(np.log(closes))
        vols    = [np.std(returns[i-20:i]) * np.sqrt(252) * 100 for i in range(20, len(returns))]
        if len(vols) < 2:
            return None, 'Not enough vol data'
        current = vols[-1]
        iv_pct  = round(sum(1 for v in vols[:-1] if v < current) / len(vols[:-1]) * 100, 1)
        logger.info(symbol + ' IVP=' + str(iv_pct) + '%')
        return iv_pct, None
    except Exception as e:
        return None, str(e)

def get_best_option(symbol, strategy, target_delta, delta_range):
    logger.info(symbol + ' scanning option chain...')
    try:
        ticker     = yf.Ticker(symbol)
        price      = float(ticker.history(period='5d')['Close'].iloc[-1])
        today      = datetime.now(pytz.timezone('America/New_York')).date()
        opt_type   = 'call' if strategy == 'covered_call' else 'put'
        d_min      = target_delta - delta_range
        d_max      = target_delta + delta_range
        candidates = []
        for exp in ticker.options:
            exp_date = datetime.strptime(exp, '%Y-%m-%d').date()
            dte      = (exp_date - today).days
            if not (40 <= dte <= 70):
                continue
            try:
                chain = ticker.option_chain(exp)
                df    = chain.calls if opt_type == 'call' else chain.puts
                T     = dte / 365
                for _, row in df.iterrows():
                    strike = float(row['strike'])
                    iv     = float(row['impliedVolatility'])
                    delta, gamma = bs_greeks(price, strike, T, RISK_FREE_RATE, iv, opt_type)
                    if delta is None:
                        continue
                    if not (d_min <= delta <= d_max):
                        continue
                    if gamma > GAMMA_LIMIT:
                        continue
                    premium    = float(row['bid']) if float(row['bid']) > 0 else float(row['lastPrice'])
                    if premium <= 0:
                        continue
                    annual     = round((premium / strike) * (365 / dte) * 100, 1)
                    gamma_flag = 'WARN' if gamma > GAMMA_WARN else 'OK'
                    candidates.append({
                        'strike':      round(strike, 2),
                        'exp_date':    exp,
                        'exp_label':   exp_date.strftime('%b %d'),
                        'dte':         dte,
                        'delta':       delta,
                        'gamma':       gamma,
                        'gamma_flag':  gamma_flag,
                        'premium':     round(premium, 2),
                        'annual_pct':  annual,
                        'price':       round(price, 2),
                    })
            except Exception:
                continue
        if not candidates:
            return None, 'No candidates in delta/dte range'
        best = sorted(candidates, key=lambda x: x['annual_pct'], reverse=True)[0]
        logger.info(symbol + ' best strike=' + str(best['strike']) + ' annual=' + str(best['annual_pct']) + '%')
        return best, None
    except Exception as e:
        return None, str(e)

def format_report(qualified, waiting, scan_date, vix, vix_regime, multiplier):
    lines = []
    lines.append('<b>Option Scanner ' + scan_date + '</b>')
    lines.append('')
    regime_label = {'HIGH': 'HIGH - threshold DOWN', 'LOW': 'LOW - threshold UP', 'NORMAL': 'NORMAL'}
    lines.append('VIX: ' + str(vix) + '  ' + regime_label.get(vix_regime, ''))
    lines.append('Multiplier: x' + str(multiplier))
    lines.append('')
    if qualified:
        lines.append('OK - Act now (' + str(len(qualified)) + '):')
        lines.append('---')
        for r in qualified:
            opt = r['option']
            s   = 'Covered Call' if r['strategy'] == 'covered_call' else 'Cash Secured Put'
            lines.append('<b>' + r['symbol'] + '</b> - ' + s)
            lines.append('  Strike:  $' + str(opt['strike']))
            lines.append('  Expiry:  ' + opt['exp_label'] + ' (' + str(opt['dte']) + 'd)')
            lines.append('  Delta:   ' + str(opt['delta']) + '  Gamma: ' + str(opt['gamma']) + ' [' + opt['gamma_flag'] + ']')
            lines.append('  Premium: $' + str(opt['premium']) + '  Annual: ' + str(opt['annual_pct']) + '%')
            lines.append('  IVP:     ' + str(r['iv_percentile']) + '%  Price: $' + str(opt['price']))
            lines.append('')
    else:
        lines.append('OK - Act now: none today')
        lines.append('')
    if waiting:
        lines.append('WAIT - Watching (' + str(len(waiting)) + '):')
        for r in waiting:
            if r.get('error'):
                lines.append('  ' + r['symbol'] + ' - ' + r['error'])
            else:
                lines.append('  ' + r['symbol'] + ' IVP:' + str(r['iv_percentile']) + '% (need:' + str(r['adjusted_threshold']) + '%)')
    lines.append('')
    lines.append('Scan: ' + scan_date)
    lines.append('<i>Not investment advice</i>')
    return chr(10).join(lines)

def main():
    now_et = datetime.now(pytz.timezone('America/New_York'))
    today  = now_et.strftime('%Y-%m-%d')
    logger.info('=' * 40)
    logger.info('MyOptionScanner - ' + today)
    logger.info('=' * 40)

    vix = get_vix()
    vix_regime, multiplier = get_vix_regime(vix)
    logger.info('VIX regime: ' + vix_regime + ' x' + str(multiplier))

    try:
        df = pd.read_csv(WATCHLIST_PATH)
        logger.info('Loaded ' + str(len(df)) + ' symbols')
    except Exception as e:
        logger.error('Watchlist FAIL: ' + str(e))
        send_message('MyOptionScanner ERROR: ' + str(e))
        return

    qualified = []
    waiting   = []

    for _, row in df.iterrows():
        symbol         = str(row['symbol'])
        base_threshold = int(row['min_iv_rank']) if pd.notna(row['min_iv_rank']) else 50
        adj_threshold  = adjust_threshold(base_threshold, multiplier)
        target_delta   = float(row['target_delta']) if 'target_delta' in row and pd.notna(row['target_delta']) else 0.15
        delta_range    = float(row['delta_range'])  if 'delta_range'  in row and pd.notna(row['delta_range'])  else 0.05
        iv_pct, err    = calculate_iv_percentile(symbol)
        iv_pct         = iv_pct if iv_pct is not None else 0.0

        if iv_pct >= adj_threshold:
            opt, opt_err = get_best_option(symbol, str(row['strategy']), target_delta, delta_range)
            if opt:
                qualified.append({
                    'symbol':             symbol,
                    'strategy':           str(row['strategy']),
                    'iv_percentile':      iv_pct,
                    'adjusted_threshold': adj_threshold,
                    'option':             opt,
                })
            else:
                waiting.append({
                    'symbol':             symbol,
                    'iv_percentile':      iv_pct,
                    'adjusted_threshold': adj_threshold,
                    'error':              'IVP OK but: ' + str(opt_err),
                })
        else:
            waiting.append({
                'symbol':             symbol,
                'iv_percentile':      iv_pct,
                'adjusted_threshold': adj_threshold,
                'error':              '',
            })

    output_path = OUTPUT_DIR + '/' + today + '.json'
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump({'date': today, 'vix': vix, 'vix_regime': vix_regime,
                      'qualified': qualified, 'waiting': waiting}, f, indent=2)
        logger.info('Output saved: ' + output_path)
    except Exception as e:
        logger.error('Output FAIL: ' + str(e))

    if qualified:
        logger.info(str(len(qualified)) + ' qualified - sending Telegram')
        send_message(format_report(qualified, waiting, today, vix, vix_regime, multiplier))
    else:
        logger.info('0 qualified - skipping Telegram, log only')
    logger.info('Done - ' + today)

if __name__ == '__main__':
    main()