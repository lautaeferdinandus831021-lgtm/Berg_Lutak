import os,json,time,math,hashlib,hmac,base64,threading,ssl,traceback
from datetime import datetime
from flask import Flask,send_from_directory,request,jsonify
import requests as req_lib
import websocket
import urllib3
urllib3.disable_warnings()

from dotenv import load_dotenv
load_dotenv()

app=Flask(__name__,static_folder=os.path.join(os.path.dirname(os.path.abspath(__file__)),'public'))

def _load_bitget_creds():
    # 1) .env first
    key=os.environ.get('BITGET_API_KEY','')
    secret=os.environ.get('BITGET_API_SECRET','')
    pas=os.environ.get('BITGET_PASSPHRASE','')
    # 2) fallback secret file
    if not key or not secret or not pas:
        p=os.path.expanduser('~/.hermes/secrets/bitget_keys.json')
        try:
            with open(p,'r',encoding='utf-8') as f:
                d=json.load(f)
            if not key: key=d.get('api_key') or d.get('API_KEY','')
            if not secret: secret=d.get('secret_key') or d.get('API_SECRET','')
            if not pas: pas=d.get('passphrase') or d.get('PASSPHRASE','')
        except Exception:
            pass
    return key or 'DEMO', secret or 'DEMO', pas or 'DEMO'

API_KEY, API_SECRET, PASSPHRASE = _load_bitget_creds()
MODE=os.environ.get('MODE','demo')
PORT=int(os.environ.get('PORT','5000'))
REST='https://api.bitget.com'
WS_URL='wss://ws.bitget.com/v2/ws/public'

REAL_EXEC_MIN_BALANCE=10.0
ORDER_TYPE_DEFAULT='limit'
MAX_OLHC_SPREAD_SATOSHI=1200.0
ORDER_TYPE_LIMIT='limit'
ORDER_TYPE_MARKET='market'
SL_MIN_PCT=0.1
SL_MAX_PCT=50.0
TP_MIN_PCT=0.1
TP_MAX_PCT=200.0
DEFAULT_LEV=20
DEFAULT_SZ=0.1
DEFAULT_SL=3.0
DEFAULT_TP=20.0
DEFAULT_BB_PERIOD=20
DEFAULT_BB_DEV=1.8
DEFAULT_CVD_PERIOD=20
DEFAULT_DOM_PERIOD=20
DEFAULT_COOLDOWN_MS=5000
MIN_INDICATOR_SCORE=3
DEFAULT_USE_MACD=True
MACD_FAST=12
MACD_SLOW=26
MACD_SIG=9
MAX_OPEN_ERROR_RATIO=0.05
MAX_OPEN_ERROR_MS=30000
MIN_MANAGE_INTERVAL_MS=100
MIN_REFRESH_CANDLE_MS=1000
MIN_REFRESH_TICKER_MS=1000
MIN_REFRESH_OB_MS=1000
MIN_REFRESH_BALANCE_MS=1000
MAX_LOG_LINES=2000
EMAIL_SMTP_HOST=os.environ.get('EMAIL_SMTP_HOST','smtp.gmail.com')
EMAIL_SMTP_PORT=int(os.environ.get('EMAIL_SMTP_PORT','587'))
EMAIL_USER=os.environ.get('EMAIL_USER','')
EMAIL_TO=os.environ.get('EMAIL_TO','')
EMAIL_PASSWORD_FILE=os.environ.get('EMAIL_PASSWORD_FILE','') or os.path.expanduser('~/.hermes/secrets/smtp_app_password')

try:
    with open(EMAIL_PASSWORD_FILE,'r',encoding='utf-8') as f: _smtp_app_password=f.read().strip()
except Exception as _e_smtp:
    _smtp_app_password=''

# Auto-detect working proxy
PROXIES={}

def detect_proxy():
    global PROXIES
    # Try direct connection
    try:
        r=req_lib.get('https://api.bitget.com/api/v2/mix/market/time',timeout=10,verify=False)
        d=r.json()
        if d.get('code')=='00000':
            PROXIES={}
            print('  Proxy    : DIRECT (connected)')
            return
    except Exception as e:
        print('  Direct   : '+str(e)[:60])

    # Try env vars
    hp=os.environ.get('HTTP_PROXY','')
    hs=os.environ.get('HTTPS_PROXY','')
    if hs: PROXIES={'https':hs,'http':hp or hs}
    elif hp: PROXIES={'http':hp}
    if PROXIES:
        print('  Proxy    : ENV '+str(PROXIES))
        return

    print('  Proxy    : NONE - will try direct anyway')

detect_proxy()

HTTP=req_lib.Session();HTTP.verify=False;HTTP.timeout=30
if PROXIES: HTTP.proxies=PROXIES
WS_SSL={"cert_reqs":ssl.CERT_NONE}

def make_state():
    return {
        'sym':'BTCUSDT','tf':'1m','tf5':'5m',
        'bbP':DEFAULT_BB_PERIOD,'bbD':DEFAULT_BB_DEV,'cvdP':DEFAULT_CVD_PERIOD,'domP':DEFAULT_DOM_PERIOD,
        'lev':DEFAULT_LEV,'sz':DEFAULT_SZ,'sl':DEFAULT_SL,'tp':DEFAULT_TP,'order_type':ORDER_TYPE_DEFAULT,'min_profit_target_usdt':1.0,
        'on':False,'candles':[],'ticker':{},'m5_candles':[],
        'ob':{'asks':[],'bids':[]},

        'bb':{'upper':0.0,'mid':0.0,'lower':0.0},
        'vd':0.0,'cvd':0.0,'pos':None,
        'trades':[],'pnl':0.0,'wins':0,'losses':0,
        'lastT':0,'cd':5000,
        'mode':'demo','log':'Ready.','debug':[],
        'demo_bal':1000.0,'real_bal':0.0,
        'trail_on':False,'trail_hi':0.0,'trail_lock':0.0,
        'bb_sig':'NEUTRAL','last_price':0.0,
        'ws_ok':False,'ws':None,'tick':0,
        'api_ok':False,'data_source':'none',
        'reversed':False,'buy_ready':False,'sell_ready':False,
        'buy_score':0,'sell_score':0,'dom':'NEUTRAL',
        'dom_hist':[],'dom_cvd':0.0,
        'err_count':0,'loop_ok':True,'ws_backoff':0,
        'asks_detail':[],'bids_detail':[],
        'm5_sig':'NEUTRAL',
        'pnl_per_sec':0.0,'balance_lock':0.0,'pnl_locks_total':0.0,
        '_pnl_ts':0.0,'_pnl_prev':0.0,
        '_fee_rate':0.0005,
        'daily_start_balance':1000.0,
        'daily_drawdown_limit_pct':5.0,
        'daily_drawdown_breached':False,
        'daily_drawdown_date':datetime.now().strftime('%Y-%m-%d'),
        'use_macd':DEFAULT_USE_MACD,
        'macd_fast':MACD_FAST,
        'macd_slow':MACD_SLOW,
        'macd_sig':MACD_SIG,
        'macd':{'macd':0.0,'signal':0.0,'hist':0.0},
        'm5_macd':{'macd':0.0,'signal':0.0,'hist':0.0},
    }

daily_start_balance_default=1000.0
daily_drawdown_limit_default=5.0

def reset_daily_drawdown(force=False):
    today=datetime.now().strftime('%Y-%m-%d')
    if S.get('daily_drawdown_date') != today or force:
        S['daily_drawdown_date']=today
        S['daily_start_balance']=round(bal(),2)
        S['daily_drawdown_breached']=False

def check_daily_drawdown():
    reset_daily_drawdown()
    if S.get('daily_drawdown_breached'):
        return
    limit=S.get('daily_drawdown_limit_pct', daily_drawdown_limit_default)
    start=S.get('daily_start_balance', daily_start_balance_default)
    if start <= 0:
        return
    current=bal()
    dd_pct=(start - current) / start * 100
    S['daily_drawdown_pct']=round(dd_pct,2)
    if dd_pct >= limit:
        S['daily_drawdown_breached']=True
        S['on']=False
        log('DAILY DRAWDOWN LIMIT BREACHED: '+str(round(dd_pct,2))+'% >= '+str(round(limit,2))+'','err')


S=make_state()

def now_str(): return datetime.now().strftime('%H:%M:%S')
def log(m,t='info'):
    line='['+now_str()+'] '+m;print(line,flush=True)
    S['log']=line;S['debug'].insert(0,{'t':now_str(),'m':m,'y':t})
    if len(S['debug'])>50: S['debug'].pop()
def pt(): return 'SUSDT-FUTURES' if S['mode']=='demo' else 'USDT-FUTURES'
def bal(): return S['demo_bal'] if S['mode']=='demo' else S['real_bal']
def can_exec():
    if S['mode']=='demo':
        return True
    if S.get('real_bal',0) <= REAL_EXEC_MIN_BALANCE:
        return False
    return True

# HTTP
def bg_hdr(method,path,body=''):
    ts=str(int(time.time()*1000))
    sig=base64.b64encode(hmac.new(API_SECRET.encode(),(ts+method.upper()+path+body).encode(),hashlib.sha256).digest()).decode()
    return {'ACCESS-KEY':API_KEY,'ACCESS-SIGN':sig,'ACCESS-TIMESTAMP':ts,'ACCESS-PASSPHRASE':PASSPHRASE,'Content-Type':'application/json'}

def api_get(path,label=''):
    for att in range(3):
        try:
            r=HTTP.get(REST+path,timeout=30)
            txt=r.text
            if txt and txt.strip():
                parsed=json.loads(txt)
                if att>0: log('API '+label+' recovered after '+str(att)+' retries','ok')
                return parsed
            else:
                if att==0: log('API '+label+' empty response','warn')
        except Exception as e:
            if att==0: log('API '+label+' err: '+str(e)[:60],'warn')
        time.sleep(1)
    log('API '+label+' FAILED after 3 retries','err')
    return None

def api_get_signed(path,label=''):
    for att in range(3):
        try:
            h=bg_hdr('GET',path,'')
            r=HTTP.get(REST+path,headers=h,timeout=30)
            txt=r.text
            if txt and txt.strip():
                parsed=json.loads(txt)
                if att>0: log('API signed '+label+' recovered after '+str(att)+' retries','ok')
                return parsed
            else:
                if att==0: log('API signed '+label+' empty response','warn')
        except Exception as e:
            if att==0: log('API signed '+label+' err: '+str(e)[:60],'warn')
        time.sleep(1)
    log('API signed '+label+' FAILED after 3 retries','err')
    return None

# FETCH
def fetch_candles():
    log('Fetching candles '+S['sym']+' '+S['tf']+'...')
    d=api_get('/api/v2/mix/market/candles?symbol='+S['sym']+'&granularity='+S['tf']+'&productType='+pt()+'&limit=100')
    if not d or d.get('code')!='00000' or not d.get('data'):
        log('Candles FAILED: '+str(d.get('msg','') if d else 'no response'),'err');return False
    raw=d['data']
    if isinstance(raw,dict): raw=raw.get('candles',raw.get('data',[]))
    if not isinstance(raw,list) or len(raw)==0:
        log('Candles: empty data','err');return False
    cs=[]
    for c in raw:
        cs.append({'ts':int(c[0]),'o':float(c[1]),'h':float(c[2]),'l':float(c[3]),'c':float(c[4]),'v':float(c[5])})
    cs.sort(key=lambda x:x['ts'])
    S['candles']=cs;S['api_ok']=True
    log('CANDLES OK: '+str(len(cs))+' last='+str(cs[-1]['c']),'ok')
    return True

def fetch_m5_candles():
    if not S.get('tf5') or S['tf5']==S['tf']: return
    log('Fetching M5 candles '+S['sym']+' '+S['tf5']+'...')
    d=api_get('/api/v2/mix/market/candles?symbol='+S['sym']+'&granularity='+S['tf5']+'&productType='+pt()+'&limit=100')
    if not d or d.get('code')!='00000' or not d.get('data'):
        log('Candles M5 FAILED: '+str(d.get('msg','') if d else 'no response'),'err');return
    raw=d['data']
    if isinstance(raw,dict): raw=raw.get('candles',raw.get('data',[]))
    if not isinstance(raw,list) or len(raw)==0:
        log('Candles M5: empty data','err');return
    cs=[]
    for c in raw:
        cs.append({'ts':int(c[0]),'o':float(c[1]),'h':float(c[2]),'l':float(c[3]),'c':float(c[4]),'v':float(c[5])})
    cs.sort(key=lambda x:x['ts'])
    S['m5_candles']=cs
    log('CANDLES M5 OK: '+str(len(cs))+' last='+str(cs[-1]['c']),'ok')

def fetch_ticker():
    d=api_get('/api/v2/mix/market/ticker?symbol='+S['sym']+'&productType='+pt())
    if not d or d.get('code')!='00000' or not d.get('data'): return False
    raw=d['data']
    t=None
    if isinstance(raw,list) and len(raw)>0: t=raw[0]
    elif isinstance(raw,dict): t=raw
    if not t: return False
    try:
        last=float(t.get('lastPr',0) or t.get('last',0) or 0)
        if last>0:
            S['last_price']=last
            S['ticker']={'last':last,'high':float(t.get('high24h',0) or 0),'low':float(t.get('low24h',0) or 0),'vol':float(t.get('baseVolume',0) or 0),'bid':float(t.get('bidPr',0) or 0),'ask':float(t.get('askPr',0) or 0)}
            if S['candles']:
                S['candles'][-1]['c']=last
                S['candles'][-1]['h']=max(S['candles'][-1]['h'],last)
                S['candles'][-1]['l']=min(S['candles'][-1]['l'],last)
        return True
    except: return False

def fetch_orderbook():
    d=api_get('/api/v2/mix/market/orderbook?symbol='+S['sym']+'&productType='+pt()+'&limit=20')
    if not d or d.get('code')!='00000' or not d.get('data'): return False
    try:
        raw=d['data']
        if isinstance(raw,list) and len(raw)>0: raw=raw[0]
        asks=raw.get('asks',[]);bids=raw.get('bids',[])
        S['ob']={'asks':[{'p':float(a[0]),'s':float(a[1])} for a in asks],'bids':[{'p':float(b[0]),'s':float(b[1])} for b in bids]}
        return True
    except: return False

def fetch_real_balance():
    if API_KEY=='DEMO' or S['mode']=='demo': return
    try:
        path='/api/v2/mix/account/accounts?productType='+pt()
        d=api_get_signed(path,'real_bal')
        if d and d.get('code')=='00000' and d.get('data'):
            S['real_bal']=float(d['data'][0].get('available',0))
    except: pass

# WEBSOCKET

def _ws_opts():
    opts={'sslopt':WS_SSL,'ping_interval':15,'ping_timeout':8}
    if PROXIES:
        pu=PROXIES.get('https',PROXIES.get('http',''))
        if pu:
            from urllib.parse import urlparse;p=urlparse(pu)
            opts['http_proxy_host']=p.hostname;opts['http_proxy_port']=p.port
            if pu.startswith('socks5://') or pu.startswith('socks5h://'):
                opts['proxy_type']='socks5'
            elif pu.startswith('socks4://') or pu.startswith('socks4a://'):
                opts['proxy_type']='socks4'
            else:
                opts['proxy_type']='http'
    return opts

def _ws_sub(ws):
    try:
        for ch in ['ticker','books5','candle'+S['tf']]:
            ws.send(json.dumps({"op":"subscribe","args":[{"instType":pt(),"channel":ch,"instId":S['sym']}]}))
            log('WS SUB: '+ch)
        if S.get('tf5') and S['tf5'] != S['tf']:
            ch = 'candle'+S['tf5']
            ws.send(json.dumps({"op":"subscribe","args":[{"instType":pt(),"channel":ch,"instId":S['sym']}]}))
            log('WS SUB: '+ch)
    except Exception as e: log('WS SUB ERR: '+str(e),'err')

def ws_start():
    log('WS disabled: using REST polling','warn')
    return

def ws_restart():
    if S.get('ws'):
        try: S['ws'].close()
        except: pass
    S['ws_ok']=False


# =============================================
# INDICATOR FORMULAS
# =============================================

def calc_bb():
    """
    BOLLINGER BANDS - Standard Formula
    ===================================
    Period N = N most recent close prices

    Middle Band = SMA(Close, N)
              = (C1 + C2 + ... + CN) / N

    Standard Deviation (population):
        sigma = sqrt( (sum of (Ci - SMA)^2) / N )

    Upper Band = SMA + (Deviations * sigma)
    Lower Band = SMA - (Deviations * sigma)

    Signal:
        Close > Upper  -> OVERBOUGHT
        Close > Middle -> BULLISH
        Close < Middle -> BEARISH
        Close < Lower  -> OVERSOLD
    """
    try:
        c = S['candles']
        n = S['bbP']
        dev = S['bbD']

        if len(c) < n:
            return

        # Take last N closing prices (including current)
        closes = [x['c'] for x in c[-n:]]
        count = len(closes)

        if count < n:
            return

        # SMA (Simple Moving Average)
        sma = sum(closes) / count

        # Population Standard Deviation
        variance = sum((v - sma) ** 2 for v in closes) / count
        std = math.sqrt(variance)

        # Bands
        S['bb'] = {
            'upper': sma + dev * std,
            'mid': sma,
            'lower': sma - dev * std
        }

    except Exception as e:
        log('BB ERR: ' + str(e), 'err')


def bb_check():
    """
    BB Signal based on Close vs Middle Band
    Close > Mid -> BULLISH
    Close < Mid -> BEARISH
    """
    try:
        bb_mid = S['bb'].get('mid', 0)
        if bb_mid <= 0 or not S['candles']:
            return 'NEUTRAL'
        cl = S['candles'][-1]['c']
        if cl > bb_mid:
            return 'BULLISH'
        elif cl < bb_mid:
            return 'BEARISH'
        return 'NEUTRAL'
    except:
        return 'NEUTRAL'


def calc_macd():
    """
    MACD (Moving Average Convergence Divergence)
    - fast EMA, slow EMA, signal EMA(hist)
    - hist = macd - signal
    """
    try:
        c = S['candles']
        n = S.get('macd_slow', 26)
        if len(c) < n:
            return
        closes = [x['c'] for x in c]
        fast = S.get('macd_fast', 12)
        slow = S.get('macd_slow', 26)
        sig = S.get('macd_sig', 9)

        def ema(vals, period):
            k = 2 / (period + 1)
            out = [sum(vals[:period]) / period]
            for v in vals[period:]:
                out.append(v * k + out[-1] * (1 - k))
            return out

        if len(closes) < slow + sig:
            return
        ema_fast = ema(closes, fast)
        ema_slow = ema(closes, slow)
        offset = slow - fast
        macd_line = ema_fast[-1] - ema_slow[-1]
        # Build signal from recent macd values approx
        diff = [ema_fast[i] - ema_slow[i] for i in range(len(ema_slow))]
        sig_line = ema(diff, sig)[-1]
        hist = macd_line - sig_line
        S['macd'] = {'macd': macd_line, 'signal': sig_line, 'hist': hist}
    except Exception as e:
        log('MACD ERR: ' + str(e), 'err')


def macd_check():
    """
    MACD signal:
      hist > 0           -> BULLISH
      hist < 0           -> BEARISH
      crossing up/down   -> STRONGER
    """
    try:
        m = S.get('macd', {})
        hist = m.get('hist', 0)
        if hist > 0:
            return 'BULLISH'
        elif hist < 0:
            return 'BEARISH'
        return 'NEUTRAL'
    except:
        return 'NEUTRAL'


def calc_vd():
    """
    VOLUME DELTA + CVD (Periode 14)
    ===============================
    - CurVD = Volume Delta candle berlangsung (approximation buy/sell)
    - VD    = CurVD (detail per candle yang sedang berlangsung)
    - CVD   = Cumulative Volume Delta 14 candle terakhir
    """
    try:
        c = S['candles']
        n = S['cvdP']

        if len(c) < 1:
            S['vd'] = 0
            S['cvd'] = 0
            return

        # current candle delta approximation
        x = c[-1]
        rng = x['h'] - x['l']
        if rng > 0:
            buy_ratio = (x['c'] - x['l']) / rng
            sell_ratio = (x['h'] - x['c']) / rng
            S['vd'] = x['v'] * buy_ratio - x['v'] * sell_ratio
        else:
            S['vd'] = 0

        window = c[-n:] if len(c) >= n else c
        cvd_sum = 0
        for w in window:
            r = w['h'] - w['l']
            if r > 0:
                buy_r = (w['c'] - w['l']) / r
                sell_r = (w['h'] - w['c']) / r
                cvd_sum += w['v'] * buy_r - w['v'] * sell_r
        S['cvd'] = cvd_sum
    except Exception as e:
        log('VD ERR: ' + str(e), 'err')


def calc_dom():
    """
    DOM + SUPER DOM (Periode 14)
    =============================
    - DOM                     : sinyal SUPPORT / RESISTANCE / NEUTRAL
    - DOM detail per level    : volume di tiap harga (asks + bids)
    - Super DOM cumulative    : akumulasi volume dom per level harga
    """
    try:
        asks = S['ob'].get('asks', [])
        bids = S['ob'].get('bids', [])

        if not asks or not bids:
            return S['dom']

        a = [x for x in asks if x['s'] > 0]
        b = [x for x in bids if x['s'] > 0]
        if not a or not b:
            return S['dom']

        def build_detail(levels, reverse=False):
            items = [{'p': float(x['p']), 's': float(x['s'])} for x in levels]
            items.sort(key=lambda x: x['p'], reverse=reverse)
            out, cum = [], 0.0
            for it in items:
                cum += it['s']
                out.append({'p': it['p'], 's': it['s'], 'cum': cum})
            return out

        S['asks_detail'] = build_detail(a, reverse=True)
        S['bids_detail'] = build_detail(b, reverse=False)

        total_bid = sum(x['s'] for x in b)
        total_ask = sum(x['s'] for x in a)
        total = total_bid + total_ask
        if total <= 0:
            return S['dom']

        current_imb = total_bid - total_ask
        S['dom_hist'].append(current_imb)
        n = S['domP']
        if len(S['dom_hist']) >= n:
            S['dom_hist'] = S['dom_hist'][-n:]
        S['dom_cvd'] = sum(S['dom_hist'])

        if len(S['dom_hist']) < 3:
            return S['dom']

        avg_imb = sum(abs(x) for x in S['dom_hist']) / len(S['dom_hist'])
        if avg_imb > 0:
            ratio = S['dom_cvd'] / avg_imb
            if ratio > 0.5:
                return 'SUPPORT'
            elif ratio < -0.5:
                return 'RESISTANCE'
        return 'NEUTRAL'
    except:
        return S['dom']


def calc_m5_sig():
    """M5 trend signal using MACD primary"""
    try:
        c=S['m5_candles']
        if len(c)<max(26,9)+9: return 'NEUTRAL'
        closes=[x['c'] for x in c]
        fast = S.get('macd_fast', 12)
        slow = S.get('macd_slow', 26)
        sign = S.get('macd_sig', 9)

        def ema(vals, period):
            k = 2 / (period + 1)
            out = [sum(vals[:period]) / period]
            for v in vals[period:]:
                out.append(v * k + out[-1] * (1 - k))
            return out

        if len(closes) < slow + sign:
            return 'NEUTRAL'
        ema_fast = ema(closes, fast)
        ema_slow = ema(closes, slow)
        diff = [ema_fast[i] - ema_slow[i] for i in range(len(ema_slow))]
        sig_line = ema(diff, sign)[-1]
        hist = ema_fast[-1] - ema_slow[-1] - sig_line
        S['m5_macd']={'macd': ema_fast[-1] - ema_slow[-1],'signal': sig_line,'hist': hist}
        if hist > 0:
            return 'BULLISH'
        elif hist < 0:
            return 'BEARISH'
        return 'NEUTRAL'
    except Exception as e:
        log('M5 SIG ERR: '+str(e),'err')
        return 'NEUTRAL'


def trailing(pr):
    p=S['pos']
    if not p: return
    if p['side']=='BUY': pnl=(pr-p['ep'])/p['ep']*100*S['lev']
    else: pnl=(p['ep']-pr)/p['ep']*100*S['lev']
    usdt=pnl*S['sz']/100
    fee=abs(p['ep']*S['sz'])*S.get('_fee_rate',0.0005)+abs(pr*S['sz'])*S.get('_fee_rate',0.0005)
    net=usdt-fee
    if net<=0:
        S['trail_on']=False; S['trail_hi']=0.0; S['trail_lock']=0.0
        return
    if not S['trail_on']:
        S['trail_on']=True; S['trail_hi']=0.0; S['trail_lock']=0.0
    if net>S['trail_hi']:
        S['trail_hi']=net
        mp=S.get('min_profit_target_usdt',0.1)
        step=max(1.0, mp)
        new_lock=step*int((net/mp)+1e-9)
        if new_lock>S.get('trail_lock',0.0):
            S['trail_lock']=new_lock
            S['balance_lock']=round(bal()+S['trail_lock'],2)
            S['pnl_locks_total']=round(S.get('pnl_locks_total',0.0)+1.0,2)
    if S.get('trail_lock',0.0)>0 and net<S['trail_lock']:
        do_close(pr,'TRAIL_LOCK')
def rule_snapshot():
    return {
        'sym':S['sym'],'tf':S['tf'],'bbP':S['bbP'],'bbD':S['bbD'],
        'cvdP':S['cvdP'],'domP':S['domP'],'lev':S['lev'],'sz':S['sz'],
        'sl':S['sl'],'tp':S['tp']
    }

def _shutdown_server():
    try:
        shutdown = getattr(Flask, 'shutdown')
    except AttributeError:
        import os
        os._exit(0)
    shutdown()

def glue_route(name, fn):
    target = getattr(app, name)
    def wrapped(*args, **kwargs):
        try:
            resp, code = fn()
            return resp, code
        except TypeError:
            return fn()
        except Exception as e:
            return jsonify({'ok': False, 'error': str(e)}), 500
    setattr(app, name, wrapped)
    app.add_url_rule(rule=getattr(target, 'rule', '/api/'+name), endpoint=target.__name__+'_wrapped', view_func=getattr(app, name), methods=getattr(target, 'methods', ['POST']))

def _qty(price):
    return S['sz']

def _limit_price_for_side(side, c):
    """Return limit price = close +/- 1200 satoshi, clamped inside candle."""
    try:
        sp=float(MAX_OLHC_SPREAD_SATOSHI)
    except Exception:
        sp=1200.0
    px=float(c.get('c') or 0)
    if px<=0:
        return px
    if side=='BUY':
        # bid side: upper bound = close + spread (lower fill price)
        # We intentionally buy BELOW close by max spread from close as upper band boundary: use MIN(close, close+spread?) actually BUY limit = lower band = close - spread satoshi
        # Requirement: spread batas bawah untuk buy -> c - sp
        p=px - sp
        if c.get('l') is not None:
            p=max(p, float(c.get('l')))
        return p
    else:
        # spread batas atas untuk sell -> c + sp
        p=px + sp
        if c.get('h') is not None:
            p=min(p, float(c.get('h')))
        return p

def place(side,price):
    S['buy_ready']=False;S['sell_ready']=False
    b=bal()
    c=S['candles'][-1] if S['candles'] else None

    if S.get('order_type','market')=='limit' and c:
        price=_limit_price_for_side(side, c)
    qty=_qty(price)
    if side=='BUY': sl=price-S['sl'];tp=price+S['tp']
    else: sl=price+S['sl'];tp=price-S['tp']
    score=S.get('buy_score' if side=='BUY' else 'sell_score',0)
    if S['mode']=='real' and b<=REAL_EXEC_MIN_BALANCE:
        log('[ANALYZE-ONLY] '+side+' bal='+str(round(b,2))+' score='+str(score)+'/4 SL='+str(round(sl,2))+' TP='+str(round(tp,2))+' total_pnl='+str(round(S['pnl'],2))+' wins='+str(S['wins'])+' losses='+str(S['losses']));return
    log(side+' '+str(qty)+' @ '+str(round(price,2))+' SL:'+str(round(sl,2))+' TP:'+str(round(tp,2))+' type='+S.get('order_type','market'),'ok')
    if S['mode']=='real' and API_KEY!='DEMO':
        try:
            body={'symbol':S['sym'],'productType':pt(),'marginMode':'isolated','marginCoin':'USDT','size':str(qty),'side':'buy' if side=='BUY' else 'sell','orderType':'limit' if S.get('order_type','market')=='limit' else 'market','leverage':str(S['lev'])}
            if S.get('order_type','market')!='market':
                body['price']=str(round(price,2))
            bs=json.dumps(body);h=bg_hdr('POST','/api/v2/mix/order/place-order',bs)
            r=HTTP.post(REST+'/api/v2/mix/order/place-order',json=body,headers=h,timeout=30)
            d=r.json()
            if d.get('code')!='00000': log('Order fail: '+str(d),'err');return
        except Exception as e: log('Order err: '+str(e),'err');return
    if not (S['mode']=='real' and b<=REAL_EXEC_MIN_BALANCE):
        S['pos']={'side':side,'ep':price,'sl':sl,'tp':tp,'qty':str(qty),'t':time.time()}
        S['trail_on']=False;S['trail_hi']=0;S['trail_lock']=0
        S['err_count']=0
    S['trades'].insert(0,{'t':datetime.now().isoformat(),'side':side,'price':price,'qty':str(qty),'pnl':None,'bal':b})
    if len(S['trades'])>50: S['trades'].pop()

def do_close(price,reason):
    p=S['pos']
    if not p: return
    if p['side']=='BUY': pnl=(price-p['ep'])/p['ep']*100*S['lev']
    else: pnl=(p['ep']-price)/p['ep']*100*S['lev']
    gross=pnl*S['sz']/100
    fee=round(abs(p['ep']*S['sz'])*S.get('_fee_rate',0.0005)+abs(price*S['sz'])*S.get('_fee_rate',0.0005),2)
    fee=min(fee, abs(gross)) if gross>=0 else fee
    usdt=gross-fee
    before=S['trades'][0]['bal'] if S['trades'] else bal()
    S['pnl']+=usdt
    if S['mode']=='demo': S['demo_bal']+=usdt
    else: S['real_bal']+=usdt
    if usdt>0: S['wins']+=1
    else: S['losses']+=1
    if S['trades']:
        if S['trades'][0]['pnl'] is None: S['trades'][0]['pnl']=round(usdt,2)
        S['trades'][0]['gross_pnl']=round(gross,2)
        S['trades'][0]['fee']=round(fee,2)
        S['trades'][0]['bal_after']=round(bal(),2)
        S['trades'][0]['reason']=reason
    log('CLOSE '+p['side']+' '+reason+' @ '+str(round(price,2))+' fee='+str(round(fee,2))+' net='+( '+' if usdt>=0 else '' )+str(round(usdt,2))+' bal='+str(round(bal(),2)),'ok' if usdt>=0 else 'err')
    S['pos']=None;S['trail_on']=False;S['trail_hi']=0;S['trail_lock']=0

def chk_exit():
    p=S['pos'];c=S['candles']
    if not p or not c: return
    pr=c[-1]['c']
    if p['side']=='BUY' and pr<=p['sl']: do_close(pr,'SL');S['reversed']=True;return
    if p['side']=='SELL' and pr>=p['sl']: do_close(pr,'SL');S['reversed']=True;return
    mid=S['bb'].get('mid',0)
    if not mid: return
    if p['side']=='BUY' and pr<mid: do_close(pr,'BB_REVERSAL');S['reversed']=True
    elif p['side']=='SELL' and pr>mid: do_close(pr,'BB_REVERSAL');S['reversed']=True
    else: trailing(pr)

def _baseline_ok(side, price):
    """Baseline PnL guard: prevent immediate re-entry after a loss."""
    try:
        if not S['trades']:
            return True
        last = S['trades'][0]
        pnl = last.get('pnl')
        if pnl is None:
            return True
        # Skip next entry if last trade was a loss (anti-revenge)
        if pnl < 0:
            log('Baseline guard: skip entry after loss pnl='+str(round(pnl,2)),'warn')
            return False
        # Allow only if last trade met target-ish
        return True
    except Exception:
        return True

def rt_pnl():
    p=S['pos'];c=S['candles']
    if not p or not c: 
        if '_pnl_ts' in S: S['pnl_per_sec']=0.0
        return 0.0
    pr=c[-1]['c']
    if p['side']=='BUY': pnl=(pr-p['ep'])/p['ep']*100*S['lev']
    else: pnl=(p['ep']-pr)/p['ep']*100*S['lev']
    usdt=pnl*S['sz']/100
    try:
        now=time.time(); prev_ts=getattr(S,'_pnl_ts',None); prev_usdt=getattr(S,'_pnl_prev',None)
        if prev_ts is not None and prev_usdt is not None and now>prev_ts:
            dt=now-prev_ts
            if dt>0:
                S['pnl_per_sec']=round((usdt-prev_usdt)/dt,4)
        S['_pnl_ts']=now; S['_pnl_prev']=usdt
    except Exception:
        pass
    return usdt

# STRATEGY
def strategy():
    try:
        c=S['candles']
        if len(c)<max(S.get('macd_slow',26),5): return

        calc_bb()
        calc_macd()
        calc_vd()
        S['dom']=calc_dom()
        S['m5_sig']=calc_m5_sig()

        macd_sig = S.get('macd', {}).get('hist', 0)
        cvdB=S['cvd']>0;cvdS=S['cvd']<0
        vdB=S['vd']>0;vdS=S['vd']<0
        d=S['dom'];cl=c[-1]['c'];now=time.time()*1000

        bs=0;ss=0
        if S.get('use_macd', True):
            if macd_sig > 0: bs += 1
            elif macd_sig < 0: ss += 1
        else:
            S['bb_sig']=bb_check()
            if S['bb_sig']=='BULLISH': bs+=1
            elif S['bb_sig']=='BEARISH': ss+=1
        if cvdB: bs+=1
        if cvdS: ss+=1
        if vdB: bs+=1
        if vdS: ss+=1
        if d=='SUPPORT': bs+=1
        elif d=='RESISTANCE': ss+=1

        S['buy_score']=bs;S['sell_score']=ss
        buy_ok=bs>=MIN_INDICATOR_SCORE;sell_ok=ss>=MIN_INDICATOR_SCORE
        S['buy_ready']=buy_ok;S['sell_ready']=sell_ok

        if S['tick']%100==0:
            bbm=S['bb'].get('mid',0)
            log('SCORE BUY='+str(bs)+'/4 SELL='+str(ss)+'/4 BB_mid='+str(round(bbm,2))+' VD='+str(round(S['vd'],1))+' CVD='+str(round(S['cvd'],1))+' DOM='+d)

        chk_exit()

        if S['reversed'] and not S['pos']:
            S['reversed']=False
            if S['m5_sig']=='BEARISH' and sell_ok and now-S['lastT']>100:
                S['lastT']=now;place('SELL',cl);log('REVERSE->SELL '+str(ss)+'/4','ok')
            elif S['m5_sig']=='BULLISH' and buy_ok and now-S['lastT']>100:
                S['lastT']=now;place('BUY',cl);log('REVERSE->BUY '+str(bs)+'/4','ok')
            return

        if not S['pos']:
            if S['m5_sig']=='BEARISH' and sell_ok and now-S['lastT']>=S['cd']:
                if _baseline_ok('SELL', cl):
                    S['lastT']=now;place('SELL',cl);log('SELL score='+str(ss)+'/4 M5 aligned','ok')
            elif S['m5_sig']=='BULLISH' and buy_ok and now-S['lastT']>=S['cd']:
                if _baseline_ok('BUY', cl):
                    S['lastT']=now;place('BUY',cl);log('BUY score='+str(bs)+'/4 M5 aligned','ok')

        S['err_count']=0;S['loop_ok']=True
    except Exception as e:
        S['err_count']+=1
        if S['err_count']<=3: log('STRATEGY ERR: '+str(e),'err')
        S['loop_ok']=False

# LOOP
def analysis_loop():
    log('LOOP START 0.1s','ok')
    consecutive_err=0
    while S['on']:
        try:
            time.sleep(0.1);S['tick']+=1
            if S['candles']: strategy()
            ti=30 if S['ws_ok'] else 10
            if S['tick']%ti==0:
                try: fetch_ticker()
                except: pass
            oi=50 if S['ws_ok'] else 20
            if S['tick']%oi==0:
                try: fetch_orderbook()
                except: pass
            if S['tick']%300==0:
                try: fetch_candles()
                except: pass
            if S['tick']%600==0 and S['mode']=='real' and API_KEY!='DEMO':
                try: fetch_real_balance()
                except: pass
            if S['tick']>=36000: S['tick']=0
            if S['tick']%200==0:
                check_daily_drawdown()
            consecutive_err=0
        except Exception as e:
            consecutive_err+=1
            if consecutive_err<=3: log('LOOP ERR: '+str(e),'err')
            time.sleep(0.5)
            if consecutive_err>20: time.sleep(2);consecutive_err=0
    log('LOOP STOPPED','warn')

def build():
    c=S['candles'][-1] if S['candles'] else None
    upnl=rt_pnl();b=bal();eq=b+upnl if S['pos'] else b
    return {
        'sym':S['sym'],'tf':S['tf'],'price':S['last_price'] or (c['c'] if c else 0),
        'c':c,'bb':S['bb'],'ob':S['ob'],'vd':S['vd'],'cvd':S['cvd'],
        'pos':S['pos'],'trades':S['trades'],
        'pnl':round(S['pnl'],2),'w':S['wins'],'l':S['losses'],
        'on':S['on'],'mode':S['mode'],'dom':S['dom'],
        'bbP':S['bbP'],'bbD':S['bbD'],'cvdP':S['cvdP'],'domP':S['domP'],
        'lev':S['lev'],'sz':S['sz'],'sl':S['sl'],'tp':S['tp'],'order_type':S.get('order_type','market'),'min_profit_target_usdt':round(S.get('min_profit_target_usdt',0.1),2),
        'bb_sig':S['bb_sig'],
        'demo_bal':1000.0,'real_bal':round(S['real_bal'],2),'balance':round(b,2),'equity':round(eq,2),
        'unrealized_pnl':round(upnl,2),'can_execute':can_exec(),
        'pnl_per_trade':round(S['pnl'],2),
        'pnl_detail':{
            'last_price':S['last_price'],
            'price_move_per_unit':(S['last_price']-S['pos']['ep']) if S['pos'] else 0,
            'fee_rate':round(S.get('_fee_rate',0.0005),6),
        },
        'trail_on':S['trail_on'],'trail_hi':round(S['trail_hi'],2),'trail_lock':round(S['trail_lock'],2),
        'log':S['log'],'connected':S['ws_ok'],'ticker':S['ticker'],
        'debug':S['debug'][:10],'tick':S['tick'],'candle_count':len(S['candles']),
        'api_ok':S['api_ok'],'data_source':S['data_source'],
        'proxy':'Yes' if PROXIES else 'No',
        'reversed':S['reversed'],'buy_ready':S['buy_ready'],'sell_ready':S['sell_ready'],
        'buy_score':S['buy_score'],'sell_score':S['sell_score'],'dom':S['dom'],
        'asks_detail':S['asks_detail'],'bids_detail':S['bids_detail'],
        'dom_cvd':S['dom_cvd'],'dom_count':len(S['dom_hist']),'m5_sig':S['m5_sig'],
        'err_count':S['err_count'],'loop_ok':S['loop_ok'],
        'pnl_per_sec':round(S['pnl_per_sec'],4),'fee_rate':round(S.get('_fee_rate',0.0005),6),'balance_lock':round(S['balance_lock'],2),'pnl_locks_total':round(S['pnl_locks_total'],2),
    }

# ROUTES
@app.route('/')
def index(): return send_from_directory('public','index.html')

@app.route('/api/state')
def get_state(): return jsonify(build())

@app.route('/api/start',methods=['POST'])
def start_bot():
    d=request.json or {}

    # ---- minimal config validation (reject bad config before starting) ----
    bad=[]
    if d.get('symbol'):
        sym=str(d.get('symbol')).upper()
        if not ('USDT' in sym and 'FUTURES' not in sym):
            bad.append('symbol harus pair perpetual, contoh BTCUSDT')
    if 'sl' in d:
        slv=float(d.get('sl'))
        if slv <= 0 or slv > 100:
            bad.append('SL % harus 0.1..100')
    if 'tp' in d:
        tpv=float(d.get('tp'))
        if tpv <= 0 or tpv > 500:
            bad.append('TP % harus 0.1..500')
    if 'lev' in d:
        lv=int(d.get('lev'))
        if lv <= 0 or lv > 125:
            bad.append('Lev harus 1..125')
    if 'sz' in d:
        sv=float(d.get('sz'))
        if sv <= 0 or sv > 10:
            bad.append('Size harus >0 dan <=10')
    if 'bbP' in d:
        bp=int(d.get('bbP'))
        if bp < 2 or bp > 200:
            bad.append('BB period harus 2..200')
    if 'bbD' in d:
        bd=float(d.get('bbD'))
        if bd <= 0 or bd > 10:
            bad.append('BB deviasi harus >0..10')
    if 'cvdP' in d:
        cp=int(d.get('cvdP'))
        if cp < 2 or cp > 200:
            bad.append('CVD period harus 2..200')
    if 'domP' in d:
        dp=int(d.get('domP'))
        if dp < 2 or dp > 200:
            bad.append('DOM period harus 2..200')
    if bad:
        return jsonify({'ok': False, 'error': '; '.join(bad), 'invalid': bad}), 400
    # ------------------------------------------------------------------------

    S['sym']=(d.get('symbol','') or S['sym']).upper();S['tf']=str(d.get('tf',S['tf'])).lower();S['tf5']=str(d.get('tf5',S['tf5'])).lower()
    S['bbP']=int(d.get('bbP',S['bbP']));S['bbD']=float(d.get('bbD',S['bbD']))
    S['cvdP']=int(d.get('cvdP',S['cvdP']));S['domP']=int(d.get('domP',S['domP']))
    S['lev']=int(d.get('lev',S['lev']));S['sz']=float(d.get('sz',S['sz']))
    S['sl']=float(d.get('sl',S['sl']));S['tp']=float(d.get('tp',S['tp']))
    S['on']=True;S['cvd']=0;S['tick']=0;S['reversed']=False;S['dom_hist']=[];S['dom_cvd']=0;S['err_count']=0
    reset_daily_drawdown(force=True)
    log('START '+S['sym']+' '+S['tf']+' BB('+str(S['bbP'])+','+str(S['bbD'])+') CVD_P:'+str(S['cvdP'])+' DOM_P:'+str(S['domP'])+' Lev:'+str(S['lev'])+'x'+((' TF5='+S['tf5']) if S.get('tf5') and S['tf5']!=S['tf'] else ''))
    ok=fetch_candles()
    if not ok: S['on']=False;return jsonify({'ok':False,'error':'Cannot fetch candles'})
    fetch_ticker();fetch_orderbook();fetch_m5_candles()
    try:
        calc_bb();calc_vd();S['bb_sig']=bb_check();S['dom']=calc_dom();S['m5_sig']=calc_m5_sig()
        log('INIT BB_mid='+str(round(S['bb']['mid'],2))+' sig='+S['bb_sig']+' VD='+str(round(S['vd'],1))+' CVD='+str(round(S['cvd'],1))+' DOM='+S['dom']+' M5='+S['m5_sig'],'ok')
    except Exception as e: log('INIT CALC ERR: '+str(e),'err')
    threading.Thread(target=ws_start,daemon=True).start()
    threading.Thread(target=analysis_loop,daemon=True).start()
    if S['mode']=='real' and API_KEY!='DEMO': fetch_real_balance()
    return jsonify({'ok':True,'balance':bal()})

@app.route('/api/stop',methods=['POST'])
def stop_bot():
    S['on']=False
    if S['ws']:
        try: S['ws'].close()
        except: pass
    log('Bot stopped','warn')
    threading.Thread(target=_shutdown_server, daemon=True).start()
    return jsonify({'ok':True})

@app.route('/api/close',methods=['POST'])
def close_api():
    if S['pos'] and S['candles']: do_close(S['candles'][-1]['c'],'MANUAL')
    return jsonify({'ok':True})

@app.route('/api/stats')
def stats():
    total=S.get('wins',0)+S.get('losses',0)
    wr=(S.get('wins',0)/total*100) if total>0 else None
    return jsonify({
        'ok':True,
        'wins':S.get('wins',0),
        'losses':S.get('losses',0),
        'total':total,
        'winrate_pct':round(wr,2) if wr is not None else None,
        'pnl':round(S.get('pnl',0.0),2),
        'balance':round(bal(),2),
        'sl_pct':round(S.get('sl',0.0),2),
        'tp_pct':round(S.get('tp',0.0),2),
        'fee_rate':round(S.get('_fee_rate',0.0005),6),
        'order_type':S.get('order_type','market'),
        'mode':S.get('mode','demo'),
        'trades':S.get('trades',[])[:20],
        'can_execute':can_exec()
    })

@app.route('/api/export/trades')
def export_trades():
    trades=[]
    for t in S.get('trades',[]):
        out=dict(t)
        out.setdefault('fee_rate', round(S.get('_fee_rate',0.0005),6))
        trades.append(out)
    return jsonify({'ok':True,'trades':trades})


@app.route('/api/config',methods=['POST'])
def update_config():
    d=request.json or {};changed=[];rw=False
    if 'symbol' in d and d['symbol']!=S['sym']: S['sym']=d['symbol'];changed.append('SYM='+S['sym']);rw=True
    if 'tf' in d and d['tf']!=S['tf']: S['tf']=d['tf'];changed.append('TF='+S['tf']);rw=True
    if 'bbP' in d: S['bbP']=int(d['bbP']);changed.append('BB_P='+str(S['bbP']))
    if 'bbD' in d: S['bbD']=float(d['bbD']);changed.append('BB_D='+str(S['bbD']))
    if 'cvdP' in d: S['cvdP']=int(d['cvdP']);changed.append('CVD_P='+str(S['cvdP']))
    if 'domP' in d: S['domP']=int(d['domP']);changed.append('DOM_P='+str(S['domP']));S['dom_hist']=[];S['dom_cvd']=0
    if 'lev' in d: S['lev']=int(d['lev']);changed.append('LEV='+str(S['lev']))
    if 'sz' in d: S['sz']=float(d['sz']);changed.append('SZ='+str(S['sz']))
    if 'sl' in d: S['sl']=float(d['sl']);changed.append('SL='+str(S['sl']))
    if 'tp' in d: S['tp']=float(d['tp']);changed.append('TP='+str(S['tp']))
    if 'order_type' in d:
        v=str(d['order_type']).lower()
        if v in ('market','limit'):
            if S.get('order_type')!=v: S['order_type']=v;changed.append('ORDER_TYPE='+S['order_type'])
    if 'min_profit_target_usdt' in d:
        try:
            v=float(d['min_profit_target_usdt'])
            if v>=0 and S.get('min_profit_target_usdt')!=v:
                S['min_profit_target_usdt']=v;changed.append('MIN_PROFIT='+str(v))
        except Exception:
            pass
    if 'use_macd' in d:
        v=bool(d['use_macd'])
        if S.get('use_macd')!=v:
            S['use_macd']=v;changed.append('USE_MACD='+str(v))
    if 'macd_fast' in d:
        try:
            v=int(d['macd_fast'])
            if v>0 and S.get('macd_fast')!=v:
                S['macd_fast']=v;changed.append('MACD_FAST='+str(v))
        except Exception:
            pass
    if 'macd_slow' in d:
        try:
            v=int(d['macd_slow'])
            if v>0 and S.get('macd_slow')!=v:
                S['macd_slow']=v;changed.append('MACD_SLOW='+str(v))
        except Exception:
            pass
    if 'macd_sig' in d:
        try:
            v=int(d['macd_sig'])
            if v>0 and S.get('macd_sig')!=v:
                S['macd_sig']=v;changed.append('MACD_SIG='+str(v))
        except Exception:
            pass
    if changed:
        log('CONFIG: '+', '.join(changed))
        if rw and S['on']: ws_restart();fetch_candles()
    return jsonify({'ok':True,'changed':changed})

@app.route('/api/mode',methods=['POST'])
def switch_mode():
    d=request.json or {};new_mode=d.get('mode','demo')
    if new_mode not in ['demo','real']: return jsonify({'ok':False,'error':'Invalid'})
    if new_mode==S['mode']: return jsonify({'ok':True,'mode':S['mode'],'balance':bal()})
    if S['pos'] and S['candles']: do_close(S['candles'][-1]['c'],'MODE_SWITCH')
    if S['ws']:
        try: S['ws'].close()
        except: pass
    S['ws_ok']=False;was_on=S['on'];S['on']=False;time.sleep(0.3)
    S['mode']=new_mode;S['candles']=[];S['ob']={'asks':[],'bids':[]};S['ticker']={};S['last_price']=0;S['cvd']=0;S['vd']=0;S['dom_hist']=[];S['dom_cvd']=0;S['bb']={'upper':0,'mid':0,'lower':0}
    if new_mode=='demo': S['demo_bal']=1000.0;log('MODE: DEMO','ok')
    else:
        S['real_bal']=0.0
        if API_KEY!='DEMO':
            try:
                d2=api_get_signed('/api/v2/mix/account/accounts?productType='+pt(),'mode_switch')
                print('MODE_SWITCH_PRIV', d2)
                if d2 and d2.get('code')=='00000' and d2.get('data'): S['real_bal']=float(d2['data'][0].get('available',0))
            except Exception as e: print('MODE_SWITCH_ERR',e)
        log('MODE: REAL | '+str(round(S['real_bal'],2)),'ok')
    if was_on:
        ok=fetch_candles()
        if not ok: time.sleep(1);ok=fetch_candles()
        if ok:
            S['on']=True;fetch_ticker();fetch_orderbook()
            try:
                calc_bb();calc_vd();S['bb_sig']=bb_check();S['dom']=calc_dom()
                log('RESTARTED '+new_mode.upper()+' BB_mid='+str(round(S['bb']['mid'],2))+' BB_sig='+S['bb_sig']+' DOM='+S['dom'],'ok')
            except Exception as e: log('MODE CALC ERR: '+str(e),'err')
            threading.Thread(target=ws_start,daemon=True).start()
            threading.Thread(target=analysis_loop,daemon=True).start()
        else: S['on']=False;log('Restart FAILED','err')
    return jsonify({'ok':True,'mode':new_mode,'balance':bal(),'on':S['on']})

@app.route('/api/force_entry',methods=['POST'])
def force_entry():
    if S['mode']!='demo':
        return jsonify({'ok':False,'error':'real mode blocked'})
    d=request.json or {}
    side=d.get('side','BUY')
    if side not in ('BUY','SELL'):
        return jsonify({'ok':False,'error':'side must BUY/SELL'})
    pr=float(S.get('last_price') or 0)
    if pr<=0:
        if not S.get('candles'):
            return jsonify({'ok':False,'error':'no price'})
        pr=S['candles'][-1]['c']
    # adaptive wait: if recent order errors, skip entry to avoid spam
    err_count=S.get('err_count',0)
    wait_ms=min(5000 + err_count*500, 30000)
    if err_count>3:
        return jsonify({'ok':False,'error':'too many recent errors, wait '+str(int(wait_ms/1000))+'s','err_count':err_count}), 429
    # reuse place()
    place(side, pr)
    p=S['pos']
    return jsonify({'ok':True,'side':side,'price':pr,'pos':p,'balance':bal(),'err_count':err_count})

if __name__=='__main__':
    S['demo_bal']=1000.0
    print('');print('  =============================================');print('    BITGET FUTURES TRADING BOT v9.0');print('    Mode    : '+MODE.upper());print('    Port    : '+str(PORT));print('    Proxy   : '+( 'Yes' if PROXIES else 'No' ));print('    Speed   : 100ms');print('    Formulas: Standard BB/VD/CVD/DOM');print('  =============================================');print('')
    app.run(host='0.0.0.0',port=PORT,debug=False,threaded=True)
