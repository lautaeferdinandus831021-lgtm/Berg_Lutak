import math, os, requests, sys
from datetime import datetime

REST = 'https://api.bitget.com'
SYM = 'BTCUSDT'
TF = '1m'
TF5 = '5m'
PRODUCT = 'USDT-FUTURES'
LIMIT = 1000

SESSION = requests.Session()
SESSION.verify = False

# Proxy aware session (same logic as server.py)
PROXIES = {}
for _var in ('HTTPS_PROXY', 'HTTP_PROXY', 'https_proxy', 'http_proxy'):
    _val = os.environ.get(_var, '')
    if _val:
        PROXIES['https'] = _val
        PROXIES['http'] = _val
        break
if not PROXIES:
    _tor = os.environ.get('TOR_SOCKS', '')
    if _tor:
        PROXIES = {'http': _tor, 'https': _tor}
if PROXIES:
    SESSION.proxies = PROXIES

# Preset MACD untuk target winrate 65-70%
PRESETS = {
    'M1': {'sl': 1.0, 'tp': 2.0, 'macd_fast': 12, 'macd_slow': 26, 'macd_sig': 9, 'lev': 10, 'min_score': 3},
    'M2': {'sl': 1.5, 'tp': 3.0, 'macd_fast': 10, 'macd_slow': 21, 'macd_sig': 7, 'lev': 10, 'min_score': 3},
    'M3': {'sl': 2.0, 'tp': 4.0, 'macd_fast': 8, 'macd_slow': 17, 'macd_sig': 9, 'lev': 10, 'min_score': 3},
}


def api_get(path):
    try:
        r = SESSION.get(REST + path, timeout=20)
        d = r.json()
        if not isinstance(d, dict):
            return []
        if d.get('code') == '00000':
            return d.get('data', [])
        print('api_get non-ok', d.get('code'), d.get('msg'), path)
        return []
    except Exception as e:
        print('api_get exception', e, path)
        return []


def to_candles(raw):
    out = []
    for c in raw:
        out.append({'ts': int(c[0]), 'o': float(c[1]), 'h': float(c[2]), 'l': float(c[3]), 'c': float(c[4]), 'v': float(c[5])})
    out.sort(key=lambda x: x['ts'])
    return out


def ema(vals, period):
    k = 2 / (period + 1)
    out = [sum(vals[:period]) / period]
    for v in vals[period:]:
        out.append(v * k + out[-1] * (1 - k))
    return out


def calc_macd(candles, fast, slow, sig):
    closes = [x['c'] for x in candles]
    if len(closes) < slow + sig:
        return None
    ema_fast = ema(closes, fast)
    ema_slow = ema(closes, slow)
    diff = [ema_fast[i] - ema_slow[i] for i in range(len(ema_slow))]
    sig_line = ema(diff, sig)[-1]
    hist = ema_fast[-1] - ema_slow[-1] - sig_line
    return {'macd': ema_fast[-1] - ema_slow[-1], 'signal': sig_line, 'hist': hist}


def calc_bb(candles, n, dev):
    if len(candles) < n:
        return None
    closes = [x['c'] for x in candles[-n:]]
    sma = sum(closes) / len(closes)
    variance = sum((v - sma) ** 2 for v in closes) / len(closes)
    std = math.sqrt(variance)
    return {'upper': sma + dev * std, 'mid': sma, 'lower': sma - dev * std}


def run_preset(pname, preset, data):
    c1 = data['1m']
    c5 = data['5m']
    trades = []
    pos = None
    last_entry_idx = -9999
    cooldown = 5
    use_macd = True
    m5_cache = {}

    for i in range(len(c1)):
        if i < 20:
            continue
        window = c1[max(0, i-100): i+1]
        macd = calc_macd(window, preset['macd_fast'], preset['macd_slow'], preset['macd_sig'])
        bb = calc_bb(window, 20, preset.get('bbD', 2.0))
        if use_macd and not macd:
            continue
        close = c1[i]['c']

        rng = c1[i]['h'] - c1[i]['l']
        buy_ratio = (c1[i]['c'] - c1[i]['l']) / rng if rng > 0 else 0.5
        vd = buy_ratio * 2 - 1

        deltas = []
        for j in range(max(0, i-19), i+1):
            r = c1[j]['h'] - c1[j]['l']
            if r > 0:
                deltas.append((c1[j]['c'] - c1[j]['l']) / r * 2 - 1)
            else:
                deltas.append(0)
        cvd = sum(deltas)

        m5_ts = c1[i]['ts'] // 300000 * 300000
        m5_idx = next((idx for idx, v in enumerate(c5) if v['ts'] == m5_ts), None)
        m5_sig = 'NEUTRAL'
        if m5_idx is not None and m5_idx >= max(preset['macd_slow'], 20):
            m5_cache.setdefault(m5_idx, calc_macd(c5[max(0, m5_idx-99): m5_idx+1], preset['macd_fast'], preset['macd_slow'], preset['macd_sig']))
            m5 = m5_cache[m5_idx]
            if m5:
                if m5['hist'] > 0:
                    m5_sig = 'BULLISH'
                elif m5['hist'] < 0:
                    m5_sig = 'BEARISH'
        elif m5_idx is not None and m5_idx >= 20 and bb:
            if c5[m5_idx]['c'] > bb.get('mid', 0):
                m5_sig = 'BULLISH'
            elif c5[m5_idx]['c'] < bb.get('mid', 0):
                m5_sig = 'BEARISH'

        dom = 'NEUTRAL'
        if bb:
            if close > bb['mid']:
                dom = 'SUPPORT'
            elif close < bb['mid']:
                dom = 'RESISTANCE'

        bs = 0
        ss = 0
        if use_macd:
            if macd and macd['hist'] > 0:
                bs += 1
            elif macd and macd['hist'] < 0:
                ss += 1
        else:
            if bb and close > bb['mid']:
                bs += 1
            elif bb and close < bb['mid']:
                ss += 1
        if cvd > 0:
            bs += 1
        elif cvd < 0:
            ss += 1
        if vd > 0:
            bs += 1
        elif vd < 0:
            ss += 1
        if dom == 'SUPPORT':
            bs += 1
        elif dom == 'RESISTANCE':
            ss += 1

        # Selektivitas ekstrem: butuh semua 4 komponen cocok + konfirmasi M5
        buy_ok = bs >= preset['min_score'] and m5_sig == 'BULLISH'
        sell_ok = ss >= preset['min_score'] and m5_sig == 'BEARISH'

        if pos:
            ep = pos['ep']
            if pos['side'] == 'BUY':
                pnl_pct = (close - ep) / ep * 100 * preset['lev']
            else:
                pnl_pct = (ep - close) / ep * 100 * preset['lev']
            usdt = pnl_pct * 0.1 / 100
            if pos['side'] == 'BUY' and close <= pos['sl']:
                trades.append({'pnl': usdt, 'side': 'BUY', 'reason': 'SL'})
                pos = None
            elif pos['side'] == 'SELL' and close >= pos['sl']:
                trades.append({'pnl': usdt, 'side': 'SELL', 'reason': 'SL'})
                pos = None
            else:
                if usdt >= pos.get('lock', 0) + 1.0:
                    pos['lock'] = usdt
            continue

        if i - last_entry_idx < cooldown:
            continue
        if m5_sig == 'BULLISH' and buy_ok and i - last_entry_idx >= cooldown:
            price = close
            sl = price * (1 - preset['sl'] / 100)
            tp = price * (1 + preset['tp'] / 100)
            pos = {'side': 'BUY', 'ep': price, 'sl': sl, 'tp': tp, 'lock': 0.0}
            last_entry_idx = i
        elif m5_sig == 'BEARISH' and sell_ok and i - last_entry_idx >= cooldown:
            price = close
            sl = price * (1 + preset['sl'] / 100)
            tp = price * (1 - preset['tp'] / 100)
            pos = {'side': 'SELL', 'ep': price, 'sl': sl, 'tp': tp, 'lock': 0.0}
            last_entry_idx = i

    wins = sum(1 for t in trades if t['pnl'] > 0)
    losses = sum(1 for t in trades if t['pnl'] <= 0)
    total = len(trades)
    wr = (wins / total * 100) if total else 0.0
    pnl = round(sum(t['pnl'] for t in trades), 2)
    return {'preset': pname, 'trades': total, 'wins': wins, 'losses': losses, 'winrate': round(wr, 2), 'pnl': pnl}


def main():
    print('Fetching 1m candles...', flush=True)
    raw = api_get('/api/v2/mix/market/candles?symbol=' + SYM + '&granularity=' + TF + '&productType=' + PRODUCT + '&limit=' + str(LIMIT))
    c1 = to_candles(raw) if raw else []
    print('Fetching 5m candles...', flush=True)
    raw5 = api_get('/api/v2/mix/market/candles?symbol=' + SYM + '&granularity=' + TF5 + '&productType=' + PRODUCT + '&limit=' + str(LIMIT))
    c5 = to_candles(raw5) if raw5 else []
    if not c1 or not c5:
        print('Candle fetch failed')
        return
    print('1m:', len(c1), 'last', c1[-1]['c'], '| 5m:', len(c5), 'last', c5[-1]['c'], flush=True)

    results = []
    for name, p in PRESETS.items():
        r = run_preset(name, p, {'1m': c1, '5m': c5})
        results.append(r)
        print(r, flush=True)

    best = max(results, key=lambda x: x['winrate'])
    print('BEST', best, flush=True)


if __name__ == '__main__':
    main()
