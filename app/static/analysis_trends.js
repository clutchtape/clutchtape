/* Analysis tab trends (2026-10-09): every player on ONE chart.
   - CSR: one line per player for the chosen ranked playlist (default: the playlist with the most rated games).
   - Trend: any metric (default SC%), rolling 5-game average per player, or each game.
   Data = #analysis-data (analysis_view.board: ranks[{name,playlist,points[{at,value,pre,url,label,outcome}]}],
   series[{name,points[{at,values{},rolling{},url,label,outcome}]}], metrics[{key,label,unit}]).
   Colours = player colours (window.CT_PLAYER_COLORS), else a fixed palette. Pure SVG, no libraries. */
(function () {
  'use strict';
  var payload = document.getElementById('analysis-data'), root = document.getElementById('trends');
  if (!payload || !root) return;
  var data = JSON.parse(payload.textContent), NS = 'http://www.w3.org/2000/svg';
  var PALETTE = ['#ffab70', '#4aa3ff', '#ff6b6b', '#4ade80', '#c084fc', '#facc15', '#2dd4bf', '#f472b6'];
  var custom = {}; Object.values(window.CT_PLAYER_COLORS || {}).forEach(function (c) { custom[(c.name || '').toLowerCase()] = c.color; });
  var names = []; (data.series || []).forEach(function (s) { if (names.indexOf(s.name) < 0) names.push(s.name); });
  (data.ranks || []).forEach(function (r) { if (names.indexOf(r.name) < 0) names.push(r.name); });
  function color(n) { return custom[n.toLowerCase()] || PALETTE[names.indexOf(n) % PALETTE.length]; }
  var hidden = {};
  function el(tag, a, parent) { var e = document.createElementNS(NS, tag); for (var k in a) e.setAttribute(k, a[k]); if (parent) parent.appendChild(e); return e; }
  function esc(v) { return String(v == null ? '' : v).replace(/[&<>"']/g, function (c) { return '&#' + c.charCodeAt(0) + ';'; }); }
  function day(t) { return new Date(t * 1000).toLocaleDateString(undefined, { month: 'short', day: 'numeric' }); }
  function fmt(v, unit) { return v == null ? '—' : (Math.abs(v) >= 100 ? Math.round(v).toLocaleString() : Math.round(v * 10) / 10) + (unit || ''); }

  /* one chart: lines = [{name, pts:[{t, v, url, label}]}] */
  function draw(host, lines, opt) {
    host.innerHTML = '';
    var shown = lines.filter(function (l) { return l.pts.length && !hidden[l.name]; });
    var all = []; shown.forEach(function (l) { l.pts.forEach(function (p) { all.push(p); }); });
    if (!all.length) { host.innerHTML = '<p class="muted tr-empty">' + esc(opt.empty) + '</p>'; return; }
    var W = Math.max(320, host.clientWidth), H = opt.h || 260, L = 46, R = 112, T = 12, B = 26;
    if (W < 520) R = 14;
    /* x = game order, evenly spaced (real time squashes a night of games into a spike); sessions split by a divider */
    var times = all.map(function (p) { return p.t; }).sort(function (a, b) { return a - b; }).filter(function (t, i, a) { return !i || t - a[i - 1] > 60; });
    function idx(t) { var lo = 0, hi = times.length - 1; while (lo < hi) { var mid = (lo + hi) >> 1; if (times[mid] < t - 60) lo = mid + 1; else hi = mid; } return lo; }
    var t0 = 0, t1 = Math.max(1, times.length - 1);
    var v0 = Math.min.apply(null, all.map(function (p) { return p.v; })), v1 = Math.max.apply(null, all.map(function (p) { return p.v; }));
    if (v0 === v1) { v0 -= 1; v1 += 1; } var pad = (v1 - v0) * 0.08; v0 -= pad; v1 += pad;
    if (t0 === t1) { t0 -= 3600; t1 += 3600; }
    var x = function (t) { return L + (W - L - R) * idx(t) / t1; }, y = function (v) { return T + (H - T - B) * (1 - (v - v0) / (v1 - v0)); };
    var svg = el('svg', { viewBox: '0 0 ' + W + ' ' + H, width: W, height: H, class: 'tr-svg', role: 'img', 'aria-label': opt.title }, host);
    for (var i = 0; i <= 4; i++) { var v = v0 + (v1 - v0) * i / 4; el('line', { x1: L, x2: W - R, y1: y(v), y2: y(v), class: 'tr-grid' }, svg); var tx = el('text', { x: L - 6, y: y(v) + 4, class: 'tr-ax', 'text-anchor': 'end' }, svg); tx.textContent = fmt(v, opt.unit); }
    var lastLab = -99;
    times.forEach(function (t, i) { if (i && t - times[i - 1] < 3 * 3600) return;             /* new session */
      var px = L + (W - L - R) * i / t1; if (i) el('line', { x1: px - 3, x2: px - 3, y1: T, y2: H - B, class: 'tr-sess' }, svg);
      if (px - lastLab > 46) { var tx = el('text', { x: px, y: H - 6, class: 'tr-ax', 'text-anchor': 'start' }, svg); tx.textContent = day(t); lastLab = px; } });
    var ends = [];
    shown.forEach(function (l) {
      var c = color(l.name), d = l.pts.map(function (p, i) { return (i ? 'L' : 'M') + x(p.t).toFixed(1) + ',' + y(p.v).toFixed(1); }).join('');
      el('path', { d: d, class: 'tr-line', stroke: c }, svg);
      if (l.pts.length <= 60) l.pts.forEach(function (p) { el('circle', { cx: x(p.t), cy: y(p.v), r: 2.6, fill: c, class: 'tr-dot' }, svg); });
      var last = l.pts[l.pts.length - 1]; ends.push({ name: l.name, c: c, x: x(last.t), y: y(last.v), v: last.v });
    });
    if (R > 20) {                       /* end labels, nudged apart */
      ends.sort(function (a, b) { return a.y - b.y; });
      for (var k = 1; k < ends.length; k++) if (ends[k].y - ends[k - 1].y < 14) ends[k].y = ends[k - 1].y + 14;
      ends.forEach(function (e) { var tx = el('text', { x: W - R + 6, y: e.y + 4, class: 'tr-end', fill: e.c }, svg); tx.textContent = fmt(e.v, opt.unit) + ' ' + (e.name.length > 11 ? e.name.slice(0, 10) + '…' : e.name); });
    }
    /* hover: nearest game per player at that time */
    var cross = el('line', { y1: T, y2: H - B, class: 'tr-cross', visibility: 'hidden' }, svg), tip = document.createElement('div'); tip.className = 'tr-tip'; tip.hidden = true; host.appendChild(tip);
    function move(ev) {
      var r = svg.getBoundingClientRect(), px = ((ev.touches ? ev.touches[0].clientX : ev.clientX) - r.left) * W / r.width, t = times[Math.max(0, Math.min(times.length - 1, Math.round((px - L) / (W - L - R) * t1)))];
      cross.setAttribute('x1', px); cross.setAttribute('x2', px); cross.setAttribute('visibility', 'visible');
      var rows = shown.map(function (l) { var best = null; l.pts.forEach(function (p) { if (!best || Math.abs(p.t - t) < Math.abs(best.t - t)) best = p; }); return best ? { n: l.name, p: best } : null; }).filter(Boolean)
        .sort(function (a, b) { return b.p.v - a.p.v; });
      tip.innerHTML = '<b>' + day(t) + '</b>' + rows.map(function (r) { return '<div><i style="background:' + color(r.n) + '"></i>' + esc(r.n) + ' <b>' + fmt(r.p.v, opt.unit) + '</b> <span class="muted">' + esc(r.p.label || '') + '</span></div>'; }).join('');
      tip.hidden = false; var left = px / W * host.clientWidth + 14; if (left + 240 > host.clientWidth) left -= 268; tip.style.left = Math.max(0, left) + 'px';
    }
    svg.addEventListener('mousemove', move); svg.addEventListener('touchstart', move, { passive: true });
    svg.addEventListener('mouseleave', function () { tip.hidden = true; cross.setAttribute('visibility', 'hidden'); });
  }

  function legend(host, rerender, have) {
    host.innerHTML = names.map(function (n) { var ok = have(n);
      return '<button type="button" class="tr-chip' + (hidden[n] ? ' off' : '') + (ok ? '' : ' none') + '" data-n="' + esc(n) + '"' + (ok ? '' : ' disabled title="No games in this selection"') + '><i style="background:' + color(n) + '"></i>' + esc(n) + (ok ? '' : ' · no games') + '</button>'; }).join('');
    host.onclick = function (e) { var b = e.target.closest('[data-n]'); if (!b || b.disabled) return; hidden[b.dataset.n] = !hidden[b.dataset.n]; rerender(); };
  }

  /* CSR */
  var csrHost = root.querySelector('[data-tr="csr"]'), plSel = root.querySelector('#tr-playlist');
  var playlists = {}; (data.ranks || []).forEach(function (r) { playlists[r.playlist] = (playlists[r.playlist] || 0) + r.points.length; });
  var plNames = Object.keys(playlists).sort(function (a, b) { return playlists[b] - playlists[a]; });
  plSel.innerHTML = plNames.map(function (p) { return '<option>' + esc(p) + '</option>'; }).join('') || '<option>No ranked games</option>';
  function renderCsr() {
    var pl = plSel.value, lines = names.map(function (n) { var r = (data.ranks || []).find(function (x) { return x.name === n && x.playlist === pl; });
      return { name: n, pts: r ? r.points.map(function (p) { return { t: p.at, v: p.value, label: (p.label || '') + ' · ' + (p.outcome || '') + ' · ' + (p.value - p.pre >= 0 ? '+' : '') + (p.value - p.pre) }; }) : [] }; });
    legend(root.querySelector('[data-legend="csr"]'), renderCsr, function (n) { return lines.some(function (l) { return l.name === n && l.pts.length; }); });
    draw(csrHost, lines, { title: 'CSR over time, one line per player', empty: 'No ranked games in this selection. Try a longer period in Filters.', unit: '' });
  }
  plSel.onchange = renderCsr;

  /* Trend */
  var trHost = root.querySelector('[data-tr="trend"]'), mSel = root.querySelector('#tr-metric'), mode = root.querySelector('#tr-mode');
  var metrics = (data.metrics || []).filter(function (m) { return (data.series || []).some(function (s) { return s.points.some(function (p) { return p.values && p.values[m.key] != null; }); }); });
  var PREF = ['sc_pct', 'kda', 'dmg_pm', 'dmg_ka', 'dmg_diff', 'kd', 'acc', 'team_damage_share'];
  metrics.sort(function (a, b) { var i = PREF.indexOf(a.key), j = PREF.indexOf(b.key); return (i < 0 ? 99 : i) - (j < 0 ? 99 : j); });
  mSel.innerHTML = metrics.map(function (m) { return '<option value="' + esc(m.key) + '">' + esc(m.label) + '</option>'; }).join('');
  function renderTrend() {
    var key = mSel.value, m = metrics.find(function (x) { return x.key === key; }) || {}, src = mode.value === 'game' ? 'values' : 'rolling';
    var lines = names.map(function (n) { var s = (data.series || []).find(function (x) { return x.name === n; });
      return { name: n, pts: s ? s.points.filter(function (p) { return p[src] && p[src][key] != null; }).map(function (p) { return { t: p.at, v: p[src][key], label: p.label + ' · ' + (p.outcome || '') }; }) : [] }; });
    legend(root.querySelector('[data-legend="trend"]'), renderTrend, function (n) { return lines.some(function (l) { return l.name === n && l.pts.length; }); });
    draw(trHost, lines, { title: (m.label || key) + ' over time, one line per player', empty: 'No games with this stat in this selection.', unit: m.unit || '' });
  }
  mSel.onchange = renderTrend; mode.onchange = renderTrend;
  renderCsr(); renderTrend();
  var rz; window.addEventListener('resize', function () { clearTimeout(rz); rz = setTimeout(function () { renderCsr(); renderTrend(); }, 150); });
})();
