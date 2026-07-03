(function () {
  'use strict';
  const STATE_URL = '/api/state';
  const CONFIG_URL = '/api/config';
  let D = {};
  let pollTimer = null;
  let synced = false;
  let started = false;
  let lastPrice = null;
  let priceDir = 'flat';
  let lastPosKey = '';
  const POLL_MS = 800;

  function setText(id, text) {
    if (!id) return;
    id.textContent = text ?? '';
  }
  function addClass(id, className) {
    if (!id) return;
    id.className = className;
  }
  function f(n) {
    if (n == null) return '0.00';
    return parseFloat(n).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  }
  function f4(n) {
    if (n == null) return '0.0000';
    return parseFloat(n).toFixed(4);
  }
  function indClass(id, cls) {
    const el = document.getElementById(id);
    if (!el) return;
    el.className = 'ind ' + cls;
  }
  function scoreBars(id, n, cls) {
    const el = document.getElementById(id);
    if (!el || !el.children) return;
    const bars = el.children;
    for (let i = 0; i < 4; i++) bars[i].className = 'score-bar' + (i < n ? ' ' + cls : '');
  }
  function dot(id, s) {
    const el = document.getElementById(id);
    if (!el) return;
    el.className = 'dot dot-' + s;
  }
  function toast(msg, kind) {
    const el = document.getElementById('toast');
    el.textContent = msg;
    el.className = 'toast show ' + (kind || '');
    if (toastTimer) clearTimeout(toastTimer);
    toastTimer = setTimeout(() => { el.className = 'toast'; }, 3500);
  }
  function flB(id, t) {
    const b = document.getElementById(id);
    if (!b) return;
    const o = b.textContent;
    b.textContent = t; b.classList.add('done');
    setTimeout(() => { b.textContent = o; b.classList.remove('done'); }, 1500);
  }
  function togC(el, bodyId) {
    el.classList.toggle('open');
    document.getElementById(bodyId).classList.toggle('show');
  }
  function ft(s) {
    if (s < 60) return s + 's';
    if (s < 3600) return Math.floor(s / 60) + 'm ' + (s % 60) + 's';
    return Math.floor(s / 3600) + 'h ' + Math.floor((s % 3600) / 60) + 'm';
  }

  async function fetchS() {
    try {
      const r = await fetch('/api/state', { cache: 'no-store' });
      if (!r.ok) return;
      D = await r.json();
      render();
      if (!synced && D.api_ok) { syncIn(); synced = true; }
      if (!started && D.on !== true) {
        started = true;
        botGo().catch(() => { started = false; });
      }
    } catch (e) {}
  }

  document.addEventListener('DOMContentLoaded', () => {
    pollTimer = setInterval(fetchS, POLL_MS);
    fetchS();
    fetch('/api/keys/status').then(r => r.json()).then(d => {
      const el = document.getElementById('kS');
      if (d.has_key && d.has_secret && d.has_pass) {
        el.textContent = d.ws_prv_connected ? 'WS Connected' : 'Configured';
        el.style.color = d.ws_prv_connected ? 'var(--cyan)' : 'var(--amber)';
      } else {
        el.textContent = 'Not configured';
        el.style.color = 'var(--text-dim)';
      }
    }).catch(() => {});
    document.addEventListener('visibilitychange', () => {
      if (document.hidden) {
        if (pollTimer) { clearInterval(pollTimer); pollTimer = null; }
      } else {
        if (!pollTimer) { fetchS(); pollTimer = setInterval(fetchS, POLL_MS); }
      }
    });
  });

  function render() {
    dot('sN', D.api_ok ? 'live' : 'off');
    dot('sWP', D.connected ? 'live' : 'off');
    dot('sWPr', D.connected ? 'live' : 'off');
    dot('sB', D.on ? 'live' : 'off');

    const srcEl = document.getElementById('sSrc');
    srcEl.textContent = D.connected ? 'WS' : 'REST';
    srcEl.style.color = D.connected ? 'var(--cyan)' : 'var(--amber)';

    const orderEl = document.getElementById('sOrd');
    if (orderEl) orderEl.textContent = 'ORDER:' + (D.order_type || 'market').toUpperCase();
    const indEl = document.getElementById('sInd');
    if (indEl) indEl.textContent = 'ind:ok';

    const tk = D.ticker || {};
    const p = D.price || 0;
    if (lastPrice !== null && p !== lastPrice) priceDir = p > lastPrice ? 'up' : 'down';
    lastPrice = p;
    const tp = document.getElementById('tP');
    tp.textContent = '$' + f(p);
    tp.className = 'tg-val price-lg ' + (priceDir === 'up' ? 'c-up' : priceDir === 'down' ? 'c-down' : 'c-flat');
    document.getElementById('tH').textContent = '$' + f(tk.high24h || tk.high || 0);
    document.getElementById('tL').textContent = '$' + f(tk.low24h || tk.low || 0);
    document.getElementById('tB').textContent = '$' + f(tk.bidPr || tk.bid || 0);
    document.getElementById('tA').textContent = '$' + f(tk.askPr || tk.ask || 0);
    document.getElementById('tS').textContent = '$' + ((tk.askPr && tk.bidPr) ? (tk.askPr - tk.bidPr).toFixed(2) : '0.00');

    document.getElementById('vB').textContent = '$' + f(D.balance || 0);
    document.getElementById('vE').textContent = '$' + f(D.equity || 0);
    const rp = D.pnl || 0;
    const rpEl = document.getElementById('vR');
    rpEl.textContent = (rp >= 0 ? '+' : '') + '$' + f(rp);
    rpEl.className = 'bal-val ' + (rp >= 0 ? 'c-up' : 'c-down');
    document.getElementById('vWL').textContent = 'W:' + (D.w || 0) + ' L:' + (D.l || 0);
    const totalTrades = (D.w || 0) + (D.l || 0);
    const wr = totalTrades > 0 ? Math.round((D.w || 0) / totalTrades * 100) : 0;
    document.getElementById('vWR').textContent = wr + '%';
    document.getElementById('vTT').textContent = totalTrades + ' trades';
    document.getElementById('vBS').textContent = (D.mode === 'demo' ? 'Demo' : 'Real') + ' $' + f(D.mode === 'demo' ? (D.demo_bal || 0) : (D.real_bal || 0));
    document.getElementById('bT').textContent = new Date().toLocaleTimeString();

    renderIndicators();
    renderPosition();
    renderTrades();

    const vlog = document.getElementById('vLog');
    if (vlog) {
      const prev = vlog.textContent || '';
      vlog.textContent = D.log || 'Ready.';
      if (vlog.textContent !== prev) vlog.scrollTop = vlog.scrollHeight;
    }
    const lt = document.getElementById('logTick');
    if (lt) lt.textContent = 'tick: ' + (D.tick || 0);
  }

  function renderIndicators() {
    const bb = D.bb || {};
    const bbm = bb.mid || 0;
    document.getElementById('iBB').textContent = bbm > 0 ? '$' + f(bbm) : '--';
    document.getElementById('iBBSub').textContent = 'P:' + (D.bbP || 20) + ' D:' + (D.bbD || 2);
    const bbs = D.bb_sig || 'NEUTRAL';
    const bbsEl = document.getElementById('iBBS');
    bbsEl.textContent = bbs;
    bbsEl.className = 'ind-val ' + (bbs === 'BULLISH' ? 'c-up' : bbs === 'BEARISH' ? 'c-down' : '');
    indClass('indBBS', bbs === 'BULLISH' ? 'bull' : bbs === 'BEARISH' ? 'bear' : 'neut');
    indClass('indBB', bbs === 'BULLISH' ? 'bull' : bbs === 'BEARISH' ? 'bear' : 'neut');

    const vd = D.vd || 0;
    const vdEl = document.getElementById('iVD');
    vdEl.textContent = (vd >= 0 ? '+' : '') + f4(vd);
    vdEl.className = 'ind-val ' + (vd > 0 ? 'c-up' : vd < 0 ? 'c-down' : '');
    document.getElementById('iVDSub').textContent = 'vd: ' + f4(vd);
    indClass('indVD', vd > 0 ? 'bull' : vd < 0 ? 'bear' : 'neut');

    const macd = D.macd || {};
    const hm = macd.hist || 0;
    document.getElementById('iMACD').textContent = hm !== 0 ? f4(hm) : '--';
    document.getElementById('iMACDSub').textContent = 'F:' + (D.macd_fast || 12) + ' S:' + (D.macd_slow || 26) + ' Sig:' + (D.macd_sig || 9);
    const mSig = hm > 0 ? 'BULLISH' : hm < 0 ? 'BEARISH' : 'NEUTRAL';
    const mI = document.getElementById('mI');
    if (mI) mI.textContent = mSig;
    const mCls = mSig === 'BULLISH' ? 'ind bull' : mSig === 'BEARISH' ? 'ind bear' : 'ind neut';
    indClass('indMACD', mSig === 'BULLISH' ? 'bull' : mSig === 'BEARISH' ? 'bear' : 'neut');

    const cvd = D.cvd || 0;
    document.getElementById('iCVD').textContent = (cvd >= 0 ? '+' : '') + f4(cvd);
    document.getElementById('iCVDSub').textContent = 'period: ' + (D.cvdP || 20) + ' candles';
    indClass('indCVD', cvd > 0 ? 'bull' : cvd < 0 ? 'bear' : 'neut');

    const dom = D.dom || 'NEUTRAL';
    document.getElementById('iDOM').textContent = dom;
    document.getElementById('iDOMSub').textContent = 'cvd:' + f4(D.dom_cvd || 0) + ' n:' + (D.dom_count || 0);
    indClass('indDOM', dom === 'SUPPORT' ? 'bull' : dom === 'RESISTANCE' ? 'bear' : 'neut');

    document.getElementById('iCDOM').textContent = (D.dom_cvd >= 0 ? '+' : '') + f4(D.dom_cvd);
    document.getElementById('iCDOMSub').textContent = 'count:' + (D.dom_count || 0);
    indClass('indCDOM', D.dom_cvd > 0 ? 'bull' : D.dom_cvd < 0 ? 'bear' : 'neut');

    document.getElementById('vBS2').textContent = D.buy_score || 0;
    document.getElementById('vSS').textContent = D.sell_score || 0;
    scoreBars('bBar', D.buy_score || 0, 'filled-buy');
    scoreBars('sBar', D.sell_score || 0, 'filled-sell');

    renderDataPanels();
    renderSuperDom();
    drawCharts();

    const macdSub1 = document.getElementById('macdSub1');
    if (macdSub1 && D.macd_hist && D.macd_hist.length) macdSub1.textContent = 'F:' + (D.macd_fast || 12) + ' S:' + (D.macd_slow || 26) + ' Sig:' + (D.macd_sig || 9);
    const macdSub2 = document.getElementById('macdSub2');
    if (macdSub2 && D.m5_macd_hist && D.m5_macd_hist.length) macdSub2.textContent = 'F:' + (D.macd_fast || 12) + ' S:' + (D.macd_slow || 26) + ' Sig:' + (D.macd_sig || 9);
  }

  function renderDataPanels() {
    const vdEl = document.getElementById('dVd'); if (vdEl) vdEl.textContent = (D.vd >= 0 ? '+' : '') + f4(D.vd);
    const cvdEl = document.getElementById('dCvd'); if (cvdEl) cvdEl.textContent = (D.cvd >= 0 ? '+' : '') + f4(D.cvd);
    const vd5El = document.getElementById('dVd5'); if (vd5El) vd5El.textContent = (D.vd5 >= 0 ? '+' : '') + f4(D.vd5);
    const cvd5El = document.getElementById('dCvd5'); if (cvd5El) cvd5El.textContent = (D.cvd5 >= 0 ? '+' : '') + f4(D.cvd5);

    const domSig = document.getElementById('dDomSig'); if (domSig) domSig.textContent = D.dom || 'NEUTRAL';
    const cdomEl = document.getElementById('dCdom'); if (cdomEl) cdomEl.textContent = (D.dom_cvd >= 0 ? '+' : '') + f4(D.dom_cvd);
    const nEl = document.getElementById('dDomN'); if (nEl) nEl.textContent = D.dom_count || 0;

    const bids = D.bids_detail || [];
    const asks = D.asks_detail || [];
    const totalBid = bids.reduce((a, b) => a + (b.cum || b.s || 0), 0);
    const totalAsk = asks.reduce((a, b) => a + (b.cum || b.s || 0), 0);
    const imb = (totalBid + totalAsk) > 0 ? (totalBid / (totalBid + totalAsk)) : 0;
    const imbEl = document.getElementById('dDomImb'); if (imbEl) imbEl.textContent = (imb * 100).toFixed(1);

    const vdSub1 = document.getElementById('vdSub1'); if (vdSub1) vdSub1.textContent = D.tf || 'M1';
    const cvdSub1 = document.getElementById('cvdSub1'); if (cvdSub1) cvdSub1.textContent = 'cvdP: ' + (D.cvdP || 20);
    const domSub1 = document.getElementById('domSub1'); if (domSub1) domSub1.textContent = (D.dom || 'NEUTRAL') + ' | imb: ' + (imb * 100).toFixed(1);
    const domSub2 = document.getElementById('domSub2'); if (domSub2) domSub2.textContent = 'count: ' + (D.dom_count || 0);
    const domMeta = document.getElementById('domMeta'); if (domMeta) domMeta.textContent = D.ob ? 'Bids: ' + ((D.ob.bids || []).length) + ' | Asks: ' + ((D.ob.asks || []).length) : 'orderbook levels';
    const domLevels = document.getElementById('domLevels'); if (domLevels) domLevels.textContent = D.ob ? 'B:' + ((D.ob.bids || []).length) + ' A:' + ((D.ob.asks || []).length) : '--';
  }

  function renderSuperDom() {
    const bids = (D.bids_detail || []).slice(0, 25);
    const asks = (D.asks_detail || []).slice(0, 25);
    const bidVol = bids.reduce((a, b) => a + (b.cum || b.s || 0), 0);
    const askVol = asks.reduce((a, b) => a + (b.cum || b.s || 0), 0);
    const ratio = askVol > 0 ? bidVol / askVol : (bids.length ? 1 : 0);
    const mx = Math.max(1, ...bids.map(b => b.cum || b.s || 0), ...asks.map(a => a.cum || a.s || 0));
    let h = '';
    const rows = Math.max(bids.length, asks.length, 5);
    for (let i = 0; i < rows; i++) {
      const bi = bids[i], ai = asks[i];
      const bw = bi ? Math.max(10, Math.round((bi.cum || bi.s || 0) / mx * 60)) : 0;
      const aw = ai ? Math.max(10, Math.round((ai.cum || ai.s || 0) / mx * 60)) : 0;
      h += '<div class="dom-row">';
      h += '<div style="color:var(--cyan)">';
      if (bi) h += '<span style="display:inline-block;background:var(--cyan);width:' + bw + 'px;margin-right:6px"></span>' + (bi.cum || bi.s || 0).toFixed(4);
      h += '</div>';
      h += '<div style="color:var(--text-dim)">' + (bi ? f(bi.p) : (ai ? f(ai.p) : '--')) + '</div>';
      h += '<div style="color:var(--red)">';
      if (ai) h += (ai.cum || ai.s || 0).toFixed(4) + '<span style="display:inline-block;background:var(--red);width:' + aw + 'px;margin-left:6px"></span>';
      h += '</div></div>';
    }
    h += '<div class="dom-ratio" style="margin-top:6px;color:var(--text-dim)">Ratio:' + ratio.toFixed(2) + ' | B:' + f(bidVol) + ' A:' + f(askVol) + '</div>';
    const out = document.getElementById('domD');
    if (out) out.innerHTML = h;
  }

  function renderPosition() {
    const pos = D.pos;
    const w = document.getElementById('pW');
    const b = document.getElementById('pB');
    const d = document.getElementById('pD');
    const s = document.getElementById('pS');
    const m = document.getElementById('pMeta');

    if (!pos || !pos.side) {
      w.className = 'pos-wrap';
      b.className = 'pos-banner idle-bg';
      s.textContent = 'No Position';
      m.textContent = '';
      d.innerHTML = '<div style="text-align:center;color:var(--text-dim);padding:24px 0;font-size:11px">Waiting for signal...</div>';
      return;
    }

    const isBuy = pos.side === 'BUY';
    const pnl = D.unrealized_pnl || 0;
    w.className = 'pos-wrap ' + (isBuy ? 'has-buy' : 'has-sell');
    b.className = 'pos-banner ' + (isBuy ? 'buy-bg' : 'sell-bg');
    s.textContent = pos.side + ' ' + (pos.qty || '');
    const dur = pos.t ? ft(Math.max(0, Math.floor((Date.now() / 1000) - pos.t))) : '0s';
    m.textContent = '@ ' + f(pos.ep) + ' | ' + dur;

    let trail = '';
    if (D.trail_on) {
      const w2 = D.trail_hi > 0 ? Math.min(100, (D.trail_lock / D.trail_hi) * 100) : 0;
      trail = '<div style="margin-top:8px">'
        + '<div style="display:flex;justify-content:space-between;font-size:9px;color:var(--text-dim);font-family:JetBrains Mono,monospace"><span>Lock: $' + (D.trail_lock || 0).toFixed(2) + '</span><span>Peak: $' + (D.trail_hi || 0).toFixed(2) + '</span></div>'
        + '<div class="trail-track"><div class="trail-fill" style="width:' + w2 + '%"></div></div></div>';
    }

    d.innerHTML =
      '<div class="pos-pnl ' + (pnl >= 0 ? 'c-up' : 'c-down') + '">' + (pnl >= 0 ? '+' : '') + '$' + f(pnl) + '</div>'
      + '<div class="pos-row"><span class="pos-lbl">Entry</span><span class="pos-val">' + f(pos.ep) + '</span></div>'
      + '<div class="pos-row"><span class="pos-lbl">Size</span><span class="pos-val">' + (pos.qty || '-') + '</span></div>'
      + trail
      + '<div class="pos-sl-tp">'
      + '<div><div class="stl">Stop Loss</div><div class="stv c-down">' + f(D.sl || 0) + '</div><div class="sts">@ ' + f(pos.sl || 0) + '</div></div>'
      + '<div><div class="stl">Take Profit</div><div class="stv c-up">' + f(D.tp || 0) + '</div><div class="sts">@ ' + f(pos.tp || 0) + '</div></div>'
      + '</div>';
  }

  function renderTrades() {
    const t = D.trades || [];
    const el = document.getElementById('tList');
    if (!el) return;
    if (!t.length) {
      el.innerHTML = '<div style="text-align:center;color:var(--text-dim);padding:12px;font-size:11px">No trades yet</div>';
      return;
    }
    el.innerHTML = t.map(x => {
      const p = x.pnl;
      const c = p != null ? (p >= 0 ? 'c-up' : 'c-down') : '';
      const tx = p != null ? (p >= 0 ? '+' : '') + p.toFixed(2) : 'open';
      return '<div class="trade-row">'
        + '<span class="trade-side ' + (x.side === 'BUY' ? 'buy' : 'sell') + '">' + x.side + '</span>'
        + '<span style="flex:1;color:var(--text-secondary);text-align:center;font-size:10px">' + f(x.price) + ' x' + x.qty + '</span>'
        + '<span style="font-weight:700;width:65px;text-align:right" class="' + c + '">$' + tx + '</span>'
        + '</div>';
    }).join('');
  }

  function drawCharts() {
    ['cMacd', 'cMacd5', 'cVd', 'cCvd', 'cOb'].forEach(id => {
      const c = document.getElementById(id); if (c) { const x = c.getContext('2d'); x.clearRect(0, 0, c.width, c.height); }
    });
    drawMacd('cMacd', (D.macd_hist || []).slice(-80));
    drawMacd('cMacd5', (D.m5_macd_hist || []).slice(-80));
    drawLine('cVd', (D.vd_hist || []).slice(-80), '#0ff');
    drawLine('cCvd', (D.cvd_hist || []).slice(-80), '#f0f');
    drawOb('cOb', D.ob);
  }

  function cumSum(arr) {
    const out = []; let s = 0; for (let i = 0; i < arr.length; i++) { s += arr[i]; out.push(s); } return out;
  }
  function drawGrid(ctx, W, H, minV, maxV, pad, plotH) {
    ctx.strokeStyle = 'rgba(255,255,255,0.08)'; ctx.lineWidth = 1;
    for (let i = 0; i <= 4; i++) {
      const y = pad + (plotH / 4) * i;
      ctx.beginPath(); ctx.moveTo(20, y); ctx.lineTo(W - 20, y); ctx.stroke();
      const v = maxV - (maxV - minV) * (i / 4);
      ctx.fillStyle = '#666'; ctx.font = '9px JetBrains Mono,monospace';
      ctx.fillText(v.toFixed(2), 2, y + 3);
    }
  }
  function drawMacd(id, hist) {
    const canvas = document.getElementById(id); if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const W = canvas.width = canvas.clientWidth || 320; const H = canvas.height = canvas.clientHeight || 180;
    ctx.clearRect(0, 0, W, H);
    if (!hist || hist.length < 2) return;
    const vals = hist.map(h => h.hist);
    const sigVals = hist.map(h => h.signal);
    const macdVals = hist.map(h => h.macd);
    const merged = [...vals, ...sigVals, ...macdVals];
    const minV = Math.min(...merged); const maxV = Math.max(...merged);
    const pad = H * 0.18; const plotH = H - pad * 2;
    const xs = (i) => (i / (Math.max(1, vals.length - 1))) * (W - 40) + 20;
    const ys = (v) => H - pad - ((v - minV) / (maxV - minV || 1)) * plotH;
    const yZero = ys(0);
    ctx.strokeStyle = 'rgba(255,255,255,0.25)'; ctx.lineWidth = 1;
    ctx.beginPath(); ctx.moveTo(20, yZero); ctx.lineTo(W - 20, yZero); ctx.stroke();
    drawGrid(ctx, W, H, minV, maxV, pad, plotH);
    const barW = Math.max(2, (W - 40) / vals.length * 0.7);
    for (let i = 0; i < vals.length; i++) {
      const x = xs(i) - barW / 2;
      const yVal = ys(vals[i]);
      const h = Math.abs(yVal - yZero);
      ctx.fillStyle = vals[i] >= 0 ? 'rgba(38,166,154,0.85)' : 'rgba(239,83,80,0.85)';
      ctx.fillRect(x, Math.min(yVal, yZero), barW, h);
    }
    ctx.strokeStyle = '#FF6D00'; ctx.lineWidth = 1; ctx.beginPath();
    for (let i = 0; i < sigVals.length; i++) { const x = xs(i), y = ys(sigVals[i]); i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y); }
    ctx.stroke();
    ctx.strokeStyle = '#2196F3'; ctx.lineWidth = 1; ctx.beginPath();
    for (let i = 0; i < macdVals.length; i++) { const x = xs(i), y = ys(macdVals[i]); i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y); }
    ctx.stroke();
    ctx.fillStyle = '#888'; ctx.font = '9px JetBrains Mono,monospace';
    if (vals.length) {
      ctx.fillText('hist:' + vals[vals.length - 1].toFixed(2), 4, 12);
      ctx.fillStyle = '#FF6D00'; ctx.fillText('sig:' + sigVals[sigVals.length - 1].toFixed(2), 4, 24);
      ctx.fillStyle = '#2196F3'; ctx.fillText('macd:' + macdVals[macdVals.length - 1].toFixed(2), 4, 36);
    }
  }
  function drawLine(id, series, color) {
    const canvas = document.getElementById(id); if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const W = canvas.width = canvas.clientWidth || 320; const H = canvas.height = canvas.clientHeight || 180;
    ctx.clearRect(0, 0, W, H);
    if (!series || series.length < 2) return;
    const nums = series.map(x => typeof x === 'number' ? x : (x.val != null ? x.val : 0));
    const minV = Math.min(0, ...nums); const maxV = Math.max(0, ...nums);
    const pad = H * 0.18; const plotH = H - pad * 2;
    const xs = (i) => (i / (Math.max(1, nums.length - 1))) * (W - 40) + 20;
    const ys = (v) => H - pad - ((v - minV) / (maxV - minV || 1)) * plotH;
    const yZero = ys(0);
    ctx.strokeStyle = 'rgba(255,255,255,0.25)'; ctx.lineWidth = 1;
    ctx.beginPath(); ctx.moveTo(20, yZero); ctx.lineTo(W - 20, yZero); ctx.stroke();
    drawGrid(ctx, W, H, minV, maxV, pad, plotH);
    ctx.strokeStyle = color; ctx.lineWidth = 1; ctx.beginPath();
    for (let i = 0; i < nums.length; i++) { const x = xs(i), y = ys(nums[i]); i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y); }
    ctx.stroke();
    ctx.fillStyle = '#888'; ctx.font = '9px JetBrains Mono,monospace';
    ctx.fillText('last:' + nums[nums.length - 1].toFixed(2), 4, 12);
  }
  function drawOb(id, ob) {
    const canvas = document.getElementById(id); if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const W = canvas.width = canvas.clientWidth || 320; const H = canvas.height = canvas.clientHeight || 180;
    ctx.clearRect(0, 0, W, H);
    const bids = (ob && ob.bids) || []; const asks = (ob && ob.asks) || [];
    if (!bids.length && !asks.length) return;
    const all = [...bids.map(x => +x.p), ...asks.map(x => +x.p)];
    const mn = Math.min(...all); const mx = Math.max(...all); const range = mx - mn || 1;
    const maxVol = Math.max(1, ...bids.map(x => +x.s), ...asks.map(x => +x.s));
    const pad = 24; const plotW = W - pad * 2;
    const xp = (p) => ((p - mn) / range) * (W - 2 * pad) + pad;
    ctx.strokeStyle = 'rgba(255,255,255,0.06)'; ctx.lineWidth = 1;
    for (let i = 1; i <= 4; i++) {
      const x = pad + (plotW / 4) * i;
      ctx.beginPath(); ctx.moveTo(x, pad); ctx.lineTo(x, H - pad); ctx.stroke();
    }
    ctx.fillStyle = 'rgba(0,240,255,0.7)';
    for (const b of bids.slice(0, 40)) {
      const x = xp(+b.p); const w = Math.max(2, (+b.s) / maxVol * plotW);
      ctx.fillRect(x - w, H - pad - 12, w, 12);
    }
    ctx.fillStyle = 'rgba(255,59,92,0.7)';
    for (const a of asks.slice(0, 40)) {
      const x = xp(+a.p); const w = Math.max(2, (+a.s) / maxVol * plotW);
      ctx.fillRect(x, pad, w, 12);
    }
  }

  function syncIn() {
    if (D.sym) document.getElementById('iSy').value = D.sym;
    if (D.tf) document.getElementById('iTF').value = D.tf;
    if (D.lev) document.getElementById('iLv').value = D.lev;
    if (D.sz) document.getElementById('iSz').value = D.sz;
    if (D.sl != null) document.getElementById('iSL').value = D.sl;
    if (D.tp != null) document.getElementById('iTP').value = D.tp;
    if (D.bbP) document.getElementById('iBP').value = D.bbP;
    if (D.bbD != null) document.getElementById('iBD').value = D.bbD;
    if (D.cvdP) document.getElementById('iCP').value = D.cvdP;
    if (D.domP) document.getElementById('iDP').value = D.domP;
    showClampHints();
  }
  function showClampHints() {
    [['iLv', 'wLv', 1, 125], ['iSz', 'wSz', 1, 100000], ['iBP', 'wBP', 5, 500], ['iCP', 'wCP', 5, 500], ['iDP', 'wDP', 5, 500]].forEach(([iid, wid, lo, hi]) => {
      const v = parseFloat(document.getElementById(iid).value);
      document.getElementById(wid).className = 'clamp-warn' + (isFinite(v) && (v < lo || v > hi) ? ' show' : '');
    });
  }

  async function saveK() {
    const k = document.getElementById('iAK').value.trim();
    const s = document.getElementById('iAS').value.trim();
    const p = document.getElementById('iAP').value.trim();
    if (!k && !s && !p) { toast('Enter at least one value', 'warn'); return; }
    try {
      const r = await fetch('/api/setkeys', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ key: k, secret: s, passphrase: p }) });
      const d = await r.json();
      if (d.ok && d.changed.length) { flB('bK', 'SAVED'); toast('Keys: ' + d.changed.join(', '), 'ok'); }
    } catch (e) { toast('Error: ' + e.message, 'err'); }
  }
  async function saveT() {
    try {
      const r = await fetch('/api/config', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({
        symbol: document.getElementById('iSy').value, tf: document.getElementById('iTF').value,
        lev: +document.getElementById('iLv').value, sz: +document.getElementById('iSz').value,
        sl: +document.getElementById('iSL').value, tp: +document.getElementById('iTP').value
      }) });
      const d = await r.json();
      if (d.ok) { flB('bT2', 'SAVED'); toast('Trading params saved', 'ok'); synced = false; }
    } catch (e) { toast('Error: ' + e.message, 'err'); }
  }
  async function saveI() {
    try {
      const r = await fetch('/api/config', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({
        bbP: +document.getElementById('iBP').value, bbD: +document.getElementById('iBD').value,
        cvdP: +document.getElementById('iCP').value, domP: +document.getElementById('iDP').value
      }) });
      const d = await r.json();
      if (d.ok) { flB('bI', 'SAVED'); toast('Indicator params saved', 'ok'); synced = false; }
    } catch (e) { toast('Error: ' + e.message, 'err'); }
  }
  async function setMode(m) {
    if (D.mode === m) return;
    if (!confirm('Switch to ' + m.toUpperCase() + ' mode?')) return;
    try {
      const r = await fetch('/api/mode', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ mode: m }) });
      const d = await r.json();
      if (d.ok) { toast('Mode: ' + m.toUpperCase(), 'ok'); synced = false; }
    } catch (e) { toast('Error: ' + e.message, 'err'); }
  }
  async function botGo() {
    try {
      const r = await fetch('/api/start', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({
        symbol: document.getElementById('iSy').value, tf: document.getElementById('iTF').value,
        bbP: +document.getElementById('iBP').value, bbD: +document.getElementById('iBD').value,
        cvdP: +document.getElementById('iCP').value, domP: +document.getElementById('iDP').value,
        lev: +document.getElementById('iLv').value, sz: +document.getElementById('iSz').value,
        sl: +document.getElementById('iSL').value, tp: +document.getElementById('iTP').value
      }) });
      const d = await r.json();
      if (!d.ok) { toast('Start failed: ' + (d.error || 'unknown'), 'err'); return; }
      toast('Bot started', 'ok');
    } catch (e) { toast('Start failed: ' + e.message, 'err'); }
  }
  async function botStop() {
    if (!confirm('Stop the bot?')) return;
    try { await fetch('/api/stop', { method: 'POST' }); toast('Bot stopped', 'warn'); } catch (e) { toast('Error: ' + e.message, 'err'); }
  }
  async function execGo() {
    try {
      const r = await fetch('/api/exec/start', { method: 'POST' });
      const d = await r.json();
      if (d.ok) { toast('Execution started', 'ok'); synced = false; } else { toast('Execute failed: ' + (d.error || 'unknown'), 'err'); }
    } catch (e) { toast('Error: ' + e.message, 'err'); }
  }
  async function execStop() {
    try {
      const r = await fetch('/api/exec/stop', { method: 'POST' });
      const d = await r.json();
      if (d.ok) { toast('Execution stopped', 'warn'); synced = false; } else { toast('Stop execute failed: ' + (d.error || 'unknown'), 'err'); }
    } catch (e) { toast('Error: ' + e.message, 'err'); }
  }
  async function botClose() {
    if (!confirm('Close current position?')) return;
    try { await fetch('/api/close', { method: 'POST' }); toast('Close sent', 'warn'); } catch (e) { toast('Error: ' + e.message, 'err'); }
  }
})();
