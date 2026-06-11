(function () {
  'use strict';
  const STATE_URL = '/api/state';
  const CONFIG_URL = '/api/config';
  const el = {
    tP: document.getElementById('tP'),
    tCh: document.getElementById('tCh'),
    tS: document.getElementById('tS'),
    tH: document.getElementById('tH'),
    tL: document.getElementById('tL'),
    tB: document.getElementById('tB'),
    tA: document.getElementById('tA'),
    vB: document.getElementById('vB'),
    vE: document.getElementById('vE'),
    vR: document.getElementById('vR'),
    vWL: document.getElementById('vWL'),
    vWR: document.getElementById('vWR'),
    vTT: document.getElementById('vTT'),
    vBS: document.getElementById('vBS'),
    bT: document.getElementById('bT'),
    pW: document.getElementById('pW'),
    pB: document.getElementById('pB'),
    pS: document.getElementById('pS'),
    pMeta: document.getElementById('pMeta'),
    pD: document.getElementById('pD'),
    iBB: document.getElementById('iBB'),
    iBBSub: document.getElementById('iBBSub'),
    iBBS: document.getElementById('iBBS'),
    indBB: document.getElementById('indBB'),
    indBBS: document.getElementById('indBBS'),
    iMACD: document.getElementById('iMACD'),
    iMACDSub: document.getElementById('iMACDSub'),
    indMACD: document.getElementById('indMACD'),
    mI: document.getElementById('mI'),
    iVD: document.getElementById('iVD'),
    iVDSub: document.getElementById('iVDSub'),
    indVD: document.getElementById('indVD'),
    iCVD: document.getElementById('iCVD'),
    iCVDSub: document.getElementById('iCVDSub'),
    indCVD: document.getElementById('indCVD'),
    iDOM: document.getElementById('iDOM'),
    iDOMSub: document.getElementById('iDOMSub'),
    indDOM: document.getElementById('indDOM'),
    iCDOM: document.getElementById('iCDOM'),
    iCDOMSub: document.getElementById('iCDOMSub'),
    indCDOM: document.getElementById('indCDOM'),
    vBS2: document.getElementById('vBS2'),
    vSS: document.getElementById('vSS'),
    bBar: document.getElementById('bBar'),
    sBar: document.getElementById('sBar'),
    cda: document.getElementById('cda'),
    domD: document.getElementById('domD'),
    mB: document.getElementById('mB'),
    mD: document.getElementById('mD'),
    mR: document.getElementById('mR'),
    kS: document.getElementById('kS'),
    iSy: document.getElementById('iSy'),
    iTF: document.getElementById('iTF'),
    iLv: document.getElementById('iLv'),
    wLv: document.getElementById('wLv'),
    iSz: document.getElementById('iSz'),
    wSz: document.getElementById('wSz'),
    iSL: document.getElementById('iSL'),
    iTP: document.getElementById('iTP'),
    bT2: document.getElementById('bT2'),
    iBP: document.getElementById('iBP'),
    wBP: document.getElementById('wBP'),
    iBD: document.getElementById('iBD'),
    iCP: document.getElementById('iCP'),
    wCP: document.getElementById('wCP'),
    iDP: document.getElementById('iDP'),
    wDP: document.getElementById('wDP'),
    bI: document.getElementById('bI'),
    vLog: document.getElementById('vLog'),
    logTick: document.getElementById('logTick'),
    tList: document.getElementById('tList'),
    toast: document.getElementById('toast'),
    sN: document.getElementById('sN'),
    sWP: document.getElementById('sWP'),
    sWPr: document.getElementById('sWPr'),
    sB: document.getElementById('sB'),
    sSrc: document.getElementById('sSrc'),
    sAge: document.getElementById('sAge'),
    sInd: document.getElementById('sInd'),
  };

  function setText(id, text) {
    if (!id) return;
    id.textContent = text ?? '';
  }

  function addClass(id, className) {
    if (!id) return;
    id.className = className;
  }

  function formatNumber(n) {
    if (n == null) return '0.00';
    return parseFloat(n).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  }

  async function poll() {
    try {
      const r = await fetch(STATE_URL, { headers: { Accept: 'application/json' } });
      if (!r.ok) return;
      const d = await r.json();
      render(d);
    } catch (e) {
      // silent
    }
  }

  function render(d) {
    // Status dots
    addClass('sN', d.api_ok ? 'dot dot-live' : 'dot dot-off');
    addClass('sWP', d.ws_ok ? 'dot dot-live' : 'dot dot-off');
    addClass('sWPr', d.ws_ok ? 'dot dot-live' : 'dot dot-off');
    addClass('sB', d.on ? 'dot dot-live' : 'dot dot-off');

    // Source
    setText('sSrc', d.connected ? 'WS' : 'REST');

    // Order type
    setText('sOrd', 'ORDER:' + (d.order_type || 'market').toUpperCase());

    // Age
    const tick = d.ticker || {};
    setText('tP', '$' + formatNumber(d.price || 0));
    setText('tH', '$' + formatNumber(tick.high || 0));
    setText('tL', '$' + formatNumber(tick.low || 0));
    setText('tB', '$' + formatNumber(tick.bid || 0));
    setText('tA', '$' + formatNumber(tick.ask || 0));
    const spread = (tick.ask && tick.bid) ? (tick.ask - tick.bid).toFixed(2) : '0.00';
    setText('tS', '$' + spread);

    // Mode
    const mode = d.mode || 'demo';
    setText('mB', mode.toUpperCase());
    addClass('mD', mode === 'demo' ? 'ms-btn active-demo' : 'ms-btn inactive');
    addClass('mR', mode === 'real' ? 'ms-btn active-real' : 'ms-btn inactive');

    // Balance
    setText('vB', '$' + formatNumber(d.balance || 0));
    setText('vE', '$' + formatNumber(d.equity || 0));
    const realized = d.pnl || 0;
    setText('vR', (realized >= 0 ? '+' : '') + '$' + formatNumber(realized));
    setText('vWL', 'W:' + (d.wins || 0) + ' L:' + (d.losses || 0));
    const total = (d.wins || 0) + (d.losses || 0);
    const wr = total > 0 ? Math.round((d.wins || 0) / total * 100) : 0;
    setText('vWR', wr + '%');
    setText('vTT', total + ' trades');
    setText('vBS', (mode === 'demo' ? 'Demo' : 'Real') + ' $' + formatNumber(mode === 'demo' ? (d.demo_bal || 0) : (d.real_bal || 0)));
    setText('bT', new Date().toLocaleTimeString());

    // Indicators
    const macd = (d.macd || {});
    const useMacd = !!d.use_macd;
    setText('iMACD', (macd.macd != null ? formatNumber(macd.macd) : '--'));
    setText('iMACDSub', 'F:' + (d.macd_fast || 12) + ' S:' + (d.macd_slow || 26) + ' Sig:' + (d.macd_sig || 9));
    const mSig = useMacd ? (macd.hist > 0 ? 'BULLISH' : macd.hist < 0 ? 'BEARISH' : 'NEUTRAL') : 'OFF';
    setText('mI', mSig);
    const mCls = mSig === 'BULLISH' ? 'ind bull' : mSig === 'BEARISH' ? 'ind bear' : 'ind neut';
    addClass('indMACD', mCls);

    // Existing BB stays for reference
    const bb = d.bb || {};
    setText('iBB', bb.mid ? '$' + formatNumber(bb.mid) : '--');
    setText('iBBSub', useMacd ? 'MACD Active' : 'P:' + (d.bbP || 20) + ' D:' + (d.bbD || 2));
    const bbs = useMacd ? 'MACD' : (d.bb_sig || 'NEUTRAL');
    setText('iBBS', bbs);
    const bCls = useMacd ? 'ind neut' : bbs === 'BULLISH' ? 'ind bull' : bbs === 'BEARISH' ? 'ind bear' : 'ind neut';
    addClass('indBB', bCls); addClass('indBBS', bCls);

    // Volume Delta placeholders
    setText('iVD', '0');
    setText('iVDSub', 'B:0 / S:0');
    addClass('indVD', 'ind neut');

    // CVD
    setText('iCVD', (d.cvd >= 0 ? '+' : '') + formatNumber(d.cvd));
    setText('iCVDSub', 'period: ' + (d.cvdP || 20) + ' candles');
    addClass('indCVD', d.cvd > 0 ? 'ind bull' : d.cvd < 0 ? 'ind bear' : 'ind neut');

    // DOM
    setText('iDOM', d.dom || 'NEUTRAL');
    setText('iDOMSub', 'B:' + formatNumber(0) + ' / A:' + formatNumber(0));
    addClass('indDOM', d.dom === 'SUPPORT' ? 'ind bull' : d.dom === 'RESISTANCE' ? 'ind bear' : 'ind neut');

    // Cumul DOM
    setText('iCDOM', (d.dom_cvd >= 0 ? '+' : '') + formatNumber(d.dom_cvd));
    setText('iCDOMSub', 'imb:0 n:' + (d.dom_count || 0));
    addClass('indCDOM', d.dom_cvd > 0 ? 'ind bull' : d.dom_cvd < 0 ? 'ind bear' : 'ind neut');

    // Scores
    setText('vBS2', d.buy_score || 0);
    setText('vSS', d.sell_score || 0);
    fillBars('bBar', d.buy_score || 0);
    fillBars('sBar', d.sell_score || 0);

    // Super DOM from asks_detail/bids_detail
    renderSuperDom(d.asks_detail || [], d.bids_detail || []);

    // Position
    renderPosition(d);

    // Log
    setText('vLog', d.log || 'Ready.');
    setText('logTick', 'tick: ' + (d.tick || 0));
    renderTrades(d.trades || []);
  }

  function fillBars(id, n) {
    const bars = document.getElementById(id);
    if (!bars) return;
    for (let i = 0; i < 4; i++) {
      bars.children[i].className = 'score-bar' + (i < n ? ' filled-buy' : '');
    }
  }

  function renderSuperDom(asks, bids) {
    const out = document.getElementById('domD');
    if (!out) return;
    const all = [...asks.map(a => ({ p: a.p, s: Math.abs(a.s), side: 'ask' })), ...bids.map(b => ({ p: b.p, s: Math.abs(b.s), side: 'bid' }))].sort((a, b) => a.p - b.p);
    const mx = Math.max(1, ...all.map(x => x.s));
    let h = '';
    const rows = Math.max(all.length, 5);
    for (let i = 0; i < rows; i++) {
      const row = all[i] || { p: '--', s: 0, side: 'bid' };
      const color = row.side === 'bid' ? 'var(--cyan)' : 'var(--red)';
      const w = Math.max(20, Math.round(row.s / mx * 60));
      h += '<div class="dom-row"><div class="dom-price-col">' + row.p + '</div>';
      h += '<div class="' + (row.side === 'bid' ? 'dom-bid-side' : 'dom-ask-side') + '" style="color:' + color + '">';
      h += '<span class="dom-bar-vis" style="background:' + color + ';width:' + w + 'px;margin-' + (row.side === 'bid' ? 'right' : 'left') + ':6px"></span>';
      h += row.s.toFixed(4) + '</div></div>';
    }
    out.innerHTML = h;
  }

  function renderPosition(d) {
    const pos = d.pos;
    const w = document.getElementById('pW');
    const b = document.getElementById('pB');
    const body = document.getElementById('pD');
    const side = document.getElementById('pS');
    const meta = document.getElementById('pMeta');

    if (!pos) {
      if (w) w.className = 'pos-wrap';
      if (b) b.className = 'pos-banner idle-bg';
      setText('pS', 'No Position');
      setText('pMeta', '');
      if (body) body.innerHTML = '<div style="text-align:center;color:var(--text-dim);padding:24px 0;font-size:11px">Waiting for signal...</div>';
      return;
    }

    const isBuy = pos.side === 'BUY';
    if (w) w.className = 'pos-wrap ' + (isBuy ? 'has-buy' : 'has-sell');
    if (b) b.className = 'pos-banner ' + (isBuy ? 'buy-bg' : 'sell-bg');
    setText('pS', pos.side + ' ' + (pos.qty || ''));
    setText('pMeta', '@ ' + formatNumber(pos.ep || 0));
    if (body) {
      const pnl = d.unrealized_pnl || 0;
      body.innerHTML =
        '<div class="pos-pnl ' + (pnl >= 0 ? 'c-up' : 'c-down') + '">' + (pnl >= 0 ? '+' : '') + '$' + formatNumber(pnl) + '</div>' +
        '<div class="pos-row"><span class="pos-lbl">Entry</span><span class="pos-val">' + formatNumber(pos.ep || 0) + '</span></div>' +
        '<div class="pos-row"><span class="pos-lbl">Size</span><span class="pos-val">' + (pos.qty || '-') + '</span></div>';
    }
  }

  function renderTrades(trades) {
    const out = document.getElementById('tList');
    if (!out) return;
    if (!trades.length) {
      out.innerHTML = '<div style="text-align:center;color:var(--text-dim);padding:12px;font-size:11px">No trades yet</div>';
      return;
    }
    out.innerHTML = trades.map(x => {
      const p = x.pnl;
      const color = p != null ? (p >= 0 ? 'c-up' : 'c-down') : '';
      const txt = p != null ? (p >= 0 ? '+' : '') + formatNumber(p) : 'open';
      return '<div class="trade-row">' +
        '<span class="trade-side ' + (x.side === 'BUY' ? 'buy' : 'sell') + '">' + x.side + '</span>' +
        '<span style="flex:1;color:var(--text-secondary);text-align:center;font-size:10px">' + formatNumber(x.price) + ' x' + x.qty + '</span>' +
        '<span style="font-weight:700;width:65px;text-align:right" class="' + color + '">$' + txt + '</span>' +
        '</div>';
    }).join('');
  }

  document.addEventListener('DOMContentLoaded', () => {
    setInterval(poll, 1000);
    poll();
  });
})();
