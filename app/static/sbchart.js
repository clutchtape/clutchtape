/* Session chart on the live Stats board (2026-10-11, _statsboard.html .sb-chartbox): one line per player across this
   session's games, oldest → newest. Views: All (small multiples — CSR, KDA, Dmg/min, Score %, each on its own scale,
   one shared crosshair; never two scales on one axis), CSR (the rating after each ranked game), CSR ± (running
   change from 0), KDA, Dmg/min, Score %. Under each plot a W/L strip (status colours; the letter on the big chart).
   Colours: the player's own colour (player-colors.js, this browser) else the validated default order by squad
   position (never by rank, so a line keeps its colour). Legend + names at the line ends (≤4 players, wide view),
   hover/tap a game for everyone's numbers, click it to open that game's row below.
   live.js swaps #statsboard after every game: the MutationObserver draws the new one. View remembered per device. */
(function () {
  'use strict';
  var NS = 'http://www.w3.org/2000/svg', KEY = 'ct-sbmetric';
  var DEF = ['#3987e5', '#d95926', '#199e70', '#c98500'];   /* dark slots 1-4, validated on #151210 (adjacent pairs) */
  var FMT = { rating: function (v) { return String(Math.round(v)); }, csr: function (v) { return (v > 0 ? '+' : '') + Math.round(v); },
              kda: function (v) { return (v > 0 ? '+' : '') + (+v).toFixed(1); }, dmg_pm: function (v) { return String(Math.round(v)); },
              sc_pct: function (v) { return (+v).toFixed(1) + '%'; } };
  var NAME = { rating: 'CSR', csr: 'CSR ±', kda: 'KDA', dmg_pm: 'Dmg/min', sc_pct: 'Score %' };
  var ALL = ['rating', 'kda', 'dmg_pm', 'sc_pct'];
  function el(tag, a, parent) { var e = document.createElementNS(NS, tag); for (var k in a) e.setAttribute(k, a[k]); if (parent) parent.appendChild(e); return e; }
  function esc(s) { return String(s == null ? '' : s).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); }
  function own() { try { var o = JSON.parse(localStorage.getItem('clutchtape.colors.v1') || '{}'); return o && typeof o === 'object' ? o : {}; } catch (e) { return {}; } }
  function view() { try { return localStorage.getItem(KEY) || 'all'; } catch (e) { return 'all'; } }
  function nice(lo, hi, n) {
    var span = hi - lo || 1, raw = span / n, mag = Math.pow(10, Math.floor(Math.log10(raw))), f = raw / mag;
    var step = (f <= 1 ? 1 : f <= 2 ? 2 : f <= 5 ? 5 : 10) * mag, a = Math.floor(lo / step) * step, b = Math.ceil(hi / step) * step, t = [];
    for (var v = a; v <= b + step / 2; v += step) t.push(+v.toFixed(6));
    return t;
  }
  function tickTxt(m, v) { return m === 'sc_pct' ? v + '%' : m === 'csr' && v > 0 ? '+' + v : String(v); }

  /* one plot: returns {x(i), cross(i|null), at(evt), ...} so the All view can sync crosshairs */
  function plot(host, m, ctx, mini) {
    var games = ctx.games, series = ctx.series, has = ctx.has, cols = ctx.cols, names = ctx.names;
    host.innerHTML = '';
    var W = host.clientWidth || 600, phone = W < 520, labels = !mini && ctx.many && !phone && ctx.shown <= 4;
    var L = mini ? 40 : 44, R = labels ? 92 : mini ? 10 : 14, T = mini ? 8 : 12, PH = mini ? (phone ? 92 : 104) : (phone ? 150 : 190), STRIP = mini ? 8 : 22, H = T + PH + 6 + STRIP + 2;
    var vals = []; series.forEach(function (s, si) { if (has[si]) (s.v[m] || []).forEach(function (v) { if (v != null) vals.push(v); }); });
    if (!vals.length) { host.innerHTML = '<p class="muted sb-chnone">No ' + NAME[m] + ' numbers for these games' + (m === 'rating' ? ' (CSR comes from ranked games)' : '') + '.</p>'; return null; }
    var lo = Math.min.apply(null, vals), hi = Math.max.apply(null, vals);
    if (m === 'csr') { lo = Math.min(lo, 0); hi = Math.max(hi, 0); }                 /* CSR ± reads from the zero line */
    if (lo === hi) { lo -= m === 'rating' ? 10 : 1; hi += m === 'rating' ? 10 : 1; }
    var ticks = nice(lo, hi, mini || phone ? 3 : 4); lo = ticks[0]; hi = ticks[ticks.length - 1];
    var n = games.length, CW = W - L - R, x = function (i) { return n === 1 ? L + CW / 2 : L + 10 + (CW - 20) * i / (n - 1); }, y = function (v) { return T + PH - (v - lo) / (hi - lo) * PH; };
    var svg = el('svg', { viewBox: '0 0 ' + W + ' ' + H, width: W, height: H, class: 'sb-svg' + (mini ? ' mini' : '') }, host);
    var g = el('g', { class: 'sb-grid' }, svg);
    ticks.forEach(function (v) { el('line', { x1: L, x2: W - R, y1: y(v), y2: y(v), class: v === 0 && m === 'csr' ? 'zero' : '' }, g);
      var tx = el('text', { x: L - 8, y: y(v) + 4, class: 'sb-tick' }, g); tx.textContent = tickTxt(m, v); });
    var lines = el('g', {}, svg);
    series.forEach(function (s, si) {
      if (!has[si]) return;
      var pts = (s.v[m] || []).map(function (v, i) { return v == null ? null : [x(i), y(v)]; }), d = '', pen = false;
      pts.forEach(function (p) { if (!p) { pen = false; return; } d += (pen ? 'L' : 'M') + p[0].toFixed(1) + ',' + p[1].toFixed(1); pen = true; });
      if (d) el('path', { d: d, class: 'sb-line', stroke: cols[si] }, lines);
      pts.forEach(function (p) { if (p) el('circle', { cx: p[0], cy: p[1], r: mini ? 3 : 4, fill: cols[si], class: 'sb-dot' }, lines); });
      s._ly = null; for (var i = pts.length - 1; i >= 0; i--) if (pts[i]) { s._ly = pts[i][1]; s._lx = pts[i][0]; break; }
    });
    if (labels) {   /* names at the line ends, nudged apart so they never overlap */
      var ord = series.map(function (s, i) { return { i: i, y: has[i] ? s._ly : null }; }).filter(function (o) { return o.y != null; }).sort(function (a, b) { return a.y - b.y; });
      for (var k = 1; k < ord.length; k++) if (ord[k].y - ord[k - 1].y < 13) ord[k].y = ord[k - 1].y + 13;
      ord.forEach(function (o) { var s = series[o.i], t = el('text', { x: s._lx + 9, y: o.y + 4, class: 'sb-dlab' }, svg);
        t.textContent = names[o.i].length > 12 ? names[o.i].slice(0, 11) + '…' : names[o.i]; });
    }
    /* W/L strip: status colour (+ the letter on the big chart) */
    var sy = T + PH + 6, sw = Math.max(8, Math.min(30, (CW - 20) / n - 4));
    games.forEach(function (gm, i) { var o = (gm.o || '').toLowerCase(), cls = o === 'win' ? 'win' : o === 'loss' ? 'loss' : 'tie';
      el('rect', { x: x(i) - sw / 2, y: sy, width: sw, height: STRIP - 2, rx: mini ? 2 : 4, class: 'sb-wl ' + cls }, svg);
      if (!mini && sw >= 14) { var t = el('text', { x: x(i), y: sy + STRIP / 2 + 2, class: 'sb-wlt' }, svg); t.textContent = o === 'win' ? 'W' : o === 'loss' ? 'L' : '–'; } });
    if (!mini) { var sl = el('text', { x: L - 8, y: sy + STRIP / 2 + 2, class: 'sb-tick' }, svg); sl.textContent = 'game'; }
    var cross = el('line', { x1: 0, x2: 0, y1: T, y2: T + PH, class: 'sb-cross', visibility: 'hidden' }, svg);
    var hit = el('rect', { x: L, y: 0, width: CW, height: H, fill: 'transparent', class: 'sb-hit' }, svg);
    return { svg: svg, hit: hit, W: W, x: x, n: n,
      cross: function (i) { if (i == null) { cross.setAttribute('visibility', 'hidden'); return; } cross.setAttribute('x1', x(i)); cross.setAttribute('x2', x(i)); cross.setAttribute('visibility', 'visible'); },
      at: function (evt) { var r = svg.getBoundingClientRect(), px = ((evt.touches ? evt.touches[0].clientX : evt.clientX) - r.left) * (W / r.width), best = 0;
        for (var i = 1; i < n; i++) if (Math.abs(x(i) - px) < Math.abs(x(best) - px)) best = i; return best; } };
  }

  function draw(box) {
    var data; try { data = JSON.parse(box.dataset.chart); } catch (e) { return; }
    var games = data.games || [], series = data.series || [], v = view(), mine = own();
    if (!games.length || !series.length) { box.hidden = true; return; }
    if (v !== 'all' && !NAME[v]) v = 'all';
    [].forEach.call(box.querySelectorAll('[data-metric]'), function (b) { b.setAttribute('aria-pressed', String(b.dataset.metric === v)); });
    var cols = series.map(function (s, i) { var c = s.slug && mine[s.slug]; c = c && (c.color || c); return /^#[0-9a-f]{6}$/i.test(c || '') ? c : DEF[i % DEF.length]; });
    var names = series.map(function (s) { return s.who || box.dataset.solo || 'You'; });
    /* a squadmate with no games this session has no line: no legend entry or tooltip row either (colours were already
       given by squad position above, so nobody's colour moves) */
    var has = series.map(function (s) { return Object.keys(s.v).some(function (k) { return (s.v[k] || []).some(function (x) { return x != null; }); }); });
    var shown = has.filter(Boolean).length, ctx = { games: games, series: series, has: has, cols: cols, names: names, shown: shown, many: shown > 1 };
    var lg = box.querySelector('.sb-legend'); lg.innerHTML = ctx.many ? series.map(function (s, i) { return has[i] ? '<span><i style="background:' + cols[i] + '"></i>' + esc(names[i]) + '</span>' : ''; }).join('') : '';
    var host = box.querySelector('.sb-chart'); host.innerHTML = '';
    var plots = [];
    if (v === 'all') {
      var grid = document.createElement('div'); grid.className = 'sb-multi'; host.appendChild(grid);
      ALL.forEach(function (m) { var c = document.createElement('div'); c.className = 'sb-cell'; c.innerHTML = '<span class="sb-ctitle">' + NAME[m] + '</span><div class="sb-cplot"></div>'; grid.appendChild(c);
        var p = plot(c.querySelector('.sb-cplot'), m, ctx, true); if (p) plots.push(p); });
    } else { var p0 = plot(host, v, ctx, false); if (p0) plots.push(p0); }
    /* hover / tap: crosshair on every plot + everyone's numbers for that game; click opens its row */
    var tip = document.createElement('div'); tip.className = 'sb-tip'; tip.hidden = true; host.appendChild(tip);
    var metrics = v === 'all' ? ALL : [v];
    function show(p, evt) { var i = p.at(evt), gm = games[i]; plots.forEach(function (q) { q.cross(i); });
      var when = new Date(gm.t * 1000).toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' });
      var head = '<b>Game ' + (i + 1) + ' · ' + esc(gm.o || '—') + '</b><small>' + esc(gm.map || '') + (gm.mode ? ' · ' + esc(gm.mode) : '') + ' · ' + when + '</small>';
      var hdr = metrics.length > 1 ? '<div class="sb-tiph"><span></span>' + metrics.map(function (m) { return '<em>' + NAME[m] + '</em>'; }).join('') + '</div>' : '';
      var rows = series.map(function (s, si) { if (!has[si]) return '';
        return '<div><i style="background:' + cols[si] + '"></i><span>' + esc(names[si]) + '</span>' + metrics.map(function (m) { var val = (s.v[m] || [])[i];
          return '<b>' + (val == null ? '—' : FMT[m](val)) + '</b>'; }).join('') + '</div>'; }).join('');
      tip.innerHTML = head + hdr + rows; tip.classList.toggle('wide', metrics.length > 1); tip.hidden = false;
      var hr = host.getBoundingClientRect(), sr = p.svg.getBoundingClientRect(), cx = sr.left - hr.left + p.x(i) * (sr.width / p.W);
      var tw = tip.offsetWidth, left = cx + 14; if (left + tw > host.clientWidth) left = cx - tw - 14;
      tip.style.left = Math.max(0, left) + 'px'; tip.style.top = Math.max(0, sr.top - hr.top + 4) + 'px'; }
    function hide() { plots.forEach(function (q) { q.cross(null); }); tip.hidden = true; }
    plots.forEach(function (p) {
      p.hit.addEventListener('mousemove', function (e) { show(p, e); }); p.hit.addEventListener('mouseleave', hide);
      p.hit.addEventListener('touchstart', function (e) { show(p, e); }, { passive: true });
      p.hit.addEventListener('click', function (evt) { var gm = games[p.at(evt)], row = gm && document.querySelector('.sb-row[data-g="' + gm.id + '"]');
        if (row) { row.open = true; row.scrollIntoView({ block: 'nearest', behavior: 'smooth' }); row.classList.add('sb-flash'); setTimeout(function () { row.classList.remove('sb-flash'); }, 1200); } });
    });
  }
  function all() { [].forEach.call(document.querySelectorAll('.sb-chartbox'), draw); }
  document.addEventListener('click', function (e) { var b = e.target.closest('.sb-metrics [data-metric]'); if (!b) return;
    try { localStorage.setItem(KEY, b.dataset.metric); } catch (x) {} all(); });
  var rz; addEventListener('resize', function () { clearTimeout(rz); rz = setTimeout(all, 150); });
  addEventListener('storage', function (e) { if (e.key === 'clutchtape.colors.v1') all(); });
  new MutationObserver(function (ms) { for (var i = 0; i < ms.length; i++) for (var j = 0; j < ms[i].addedNodes.length; j++) { var nd = ms[i].addedNodes[j];
    if (nd.nodeType === 1 && (nd.id === 'statsboard' || (nd.querySelector && nd.querySelector('.sb-chartbox')))) { requestAnimationFrame(all); return; } } })
    .observe(document.body, { childList: true, subtree: true });
  /* hidden (not in Stats only) has no width: draw when Stats only turns on */
  var so = document.documentElement.classList.contains('statsonly');
  new MutationObserver(function () { var now = document.documentElement.classList.contains('statsonly'); if (now !== so) { so = now; requestAnimationFrame(all); } })
    .observe(document.documentElement, { attributes: true, attributeFilter: ['class'] });
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', all); else all();
})();
