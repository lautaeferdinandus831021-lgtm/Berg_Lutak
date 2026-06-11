import math, requests, sys
from datetime import datetime

REST = 'https://api.bitget.com'
SYM = 'BTCUSDT'
TF = '1m'
TF5 = '5m'
PRODUCT = 'USDT-FUTURES'
LIMIT = 1000

SESSION = requests.Session()
SESSION.verify = False

PRESETS = {
    'A': {'sl': 5.0, 'tp': 10.0, 'bbD': 2.5, 'lev': 5, 'min_score': 4},
    'B': {'sl': 5.0, 'tp': 15.0, 'bbD': 2.2, 'lev': 10, 'min_score': 4},
    'C': {'sl': 3.0, 'tp': 20.0, 'bbD': 1.8, 'lev': 20, 'min_score': 3},
}


def api_get(path):
    try:
        r = SESSION.get(REST + path, timeout=20)
        d = r.json()
        if d.get('code') == '00000':
            return d.get('data', [])
    except Exception:
        pass
    return []


def to_candles(raw):
    out = []
    for c in raw:
        out.append({'ts': int(c[0]), 'o': float(c[1]), 'h': float(c[2]), 'l': float(c[3]), 'c': float(c[4]), 'v': float(c[5])})
    out.sort(key=lambda x: x['ts'])
    return out


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
    m5_bb_cache = {}

    for i in range(len(c1)):
        if i < 20:
            continue
        window = c1[max(0, i-100): i+1]
        bb = calc_bb(window, preset['bbP'] if 'bbP' in preset else 20, preset['bbD'])
        if not bb:
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
        if m5_idx is not None and m5_idx >= 20:
            m5_bb_cache.setdefault(m5_idx, calc_bb(c5[max(0, m5_idx-19): m5_idx+1], 20, 2.2))
            m5_bb = m5_bb_cache[m5_idx]
            if m5_bb:
                if c5[m5_idx]['c'] > m5_bb['mid']:
                    m5_sig = 'BULLISH'
                elif c5[m5_idx]['c'] < m5_bb['mid']:
                    m5_sig = 'BEARISH'

        dom = 'NEUTRAL'
        if bb:
            if close > bb['mid']:
                dom = 'SUPPORT'
            elif close < bb['mid']:
                dom = 'RESISTANCE'

        bs = 0
        ss = 0
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

        buy_ok = bs >= preset['min_score']
        sell_ok = ss >= preset['min_score']

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
            elif bb and ((pos['side'] == 'BUY' and close < bb['mid']) or (pos['side'] == 'SELL' and close > bb['mid'])):
                trades.append({'pnl': usdt, 'side': pos['side'], 'reason': 'BB_REVERSAL'})
                pos = None
            else:
                if usdt >= pos.get('lock', 0) + 1.0:
                    pos['lock'] = usdt
            continue

        if i - last_entry_idx < cooldown:
            continue
        if not buy_ok and not sell_ok:
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
