#!/usr/bin/env python3
import json, smtplib, urllib.request
from email.mime.text import MIMEText
from datetime import datetime

STATE_URL = 'http://127.0.0.1:5000/api/state'
FROM = 'lautaeferdinandus@gmail.com'
TO = 'botbitgetrade@gmail.com'
SMTP_USER = FROM
SMTP_PASS_PATH = '/data/data/com.termux/files/home/.hermes/secrets/smtp_app_password'
SMTP_HOST = 'smtp.gmail.com'
SMTP_PORT = 587

def load_state():
    with urllib.request.urlopen(STATE_URL, timeout=10) as r:
        return json.loads(r.read())

def load_pass():
    with open(SMTP_PASS_PATH, 'r') as f:
        return f.read().strip()

def fmt_num(x, n=2):
    if x is None:
        return '0'
    return f"{float(x):.{int(n)}f}"

def build_body(d):
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    p = d.get('pos')
    trades = d.get('trades') or []
    lines = [
        f"Berglutak Hourly Report - {now}",
        f"Pair : {d.get('sym')} | TF: {d.get('tf')} | Mode: {d.get('mode')} | Running: {d.get('on')}",
        f"Price: {d.get('price')} | BB: {d.get('bb_sig')} | M5: {d.get('m5_sig')} | DOM: {d.get('dom')} | VD: {fmt_num(d.get('vd'),1)} | CVD: {fmt_num(d.get('cvd'),1)}",
    ]
    if p:
        lines += [
            "OPEN POSITION:",
            f"  Side   : {p.get('side')}",
            f"  Entry  : {p.get('ep')}",
            f"  Qty    : {p.get('qty')}",
            f"  SL     : {fmt_num(p.get('sl'))} | TP : {fmt_num(p.get('tp'))}",
            f"  Unreal : {fmt_num(d.get('unrealized_pnl'))} USDT",
        ]
    else:
        lines += ["Open Position: None"]

    lines += [
        f"Realized PnL: {fmt_num(d.get('pnl'))} USDT",
        f"Balance     : {fmt_num(d.get('balance'))} USDT",
        f"Equity      : {fmt_num(d.get('equity'))} USDT",
        f"BalanceLock : {fmt_num(d.get('balance_lock'))} USDT",
        f"PnLLocksTot : {fmt_num(d.get('pnl_locks_total'))} USDT",
        f"Win/Loss    : {d.get('w')} / {d.get('l')}",
    ]
    if trades:
        lines.append("Last Trades:")
        for t in trades[:5]:
            lines.append(
                f"  {t.get('t')} | {t.get('side')} | entry {t.get('price')} | pnl {t.get('pnl')} | bal_after {t.get('bal_after')} | {t.get('reason')}"
            )
    return '\n'.join(lines)

def send():
    d = load_state()
    body = build_body(d)
    msg = MIMEText(body)
    msg['Subject'] = f"Berglutak Hourly Report - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    msg['From'] = FROM
    msg['To'] = TO
    pw = load_pass()
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as s:
        s.starttls()
        s.login(SMTP_USER, pw)
        s.sendmail(FROM, [TO], msg.as_string())

if __name__ == '__main__':
    send()
