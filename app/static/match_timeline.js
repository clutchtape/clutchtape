/* Match timeline (match page v2, 2026-10-08): kill race + one lane per player from the Theater film.
   Data: /api/match/<mid>/events -> e = [kind, t_ms, a, b]  (k: killer, victim · d: -, victim · m: player, medal · o: player, -)
   window.CT_MATCH = {mid, dur (s), team (your team id), roster: [{n, t (team id), mine, you, tr, k, d, a}]}.
   Pure SVG, re-rendered on resize. Hover/tap shows a crosshair + what happened; click jumps the event list (#recap-time). */
(function () {
  'use strict';
  var M = window.CT_MATCH, root = document.getElementById('mtl');
  if (!M || !root) return;
  var NS = 'http://www.w3.org/2000/svg';
  var MULTI = ['Double Kill', 'Triple Kill', 'Overkill', 'Killtacular', 'Killtrocity', 'Killamanjaro', 'Killtastrophe', 'Killpocalypse', 'Killionaire'];
  var SPREE = ['Killing Spree', 'Killing Frenzy', 'Running Riot', 'Rampage', 'Nightmare', 'Boogeyman', 'Grim Reaper', 'Demon'];
  var RARE = ['Extermination', 'Perfection', 'Ninja', 'Hail Mary', '360', 'Quigley', 'Off the Rack', 'Sneak King', 'Bank Shot', 'Mind the Gap',
              'Cluster Luck', 'Interlinked', 'Fastball', 'Last Shot', 'Clock Stop', 'Goal Line Stand', 'Stopped Short'];
  function big(medal) { var i = MULTI.indexOf(medal), j = SPREE.indexOf(medal); return i >= 1 ? 10 + i : j >= 1 ? 5 + j : RARE.indexOf(medal) >= 0 ? 8 : 0; }
  var teamOf = {}, info = {};
  M.roster.forEach(function (p) { if (!(p.n in teamOf)) { teamOf[p.n] = p.t; info[p.n] = p; } });
  var lanes = M.roster.filter(function (p, i, a) { return a.findIndex(function (q) { return q.n === p.n; }) === i; });
  var my = M.team, events = [], durMs = Math.max(1, (M.dur || 0) * 1000);

  function el(tag, attrs, parent) { var e = document.createElementNS(NS, tag); for (var k in attrs) e.setAttribute(k, attrs[k]); if (parent) parent.appendChild(e); return e; }
  function clock(ms) { var s = Math.max(0, Math.round(ms / 1000)); return Math.floor(s / 60) + ':' + ('0' + s % 60).slice(-2); }
  function tcls(t) { return t === 0 ? 'tA' : t === 1 ? 'tB' : 'tX'; }
  function esc(v) { return String(v == null ? '' : v).replace(/[&<>"']/g, function (c) { return '&#' + c.charCodeAt(0) + ';'; }); }

  function render() {
    root.innerHTML = '';
    if (!events.length) { root.innerHTML = '<p class="muted">No film events for this game (Halo did not supply a Theater film).</p>'; return; }
    var W = root.clientWidth, phone = W < 640, L = phone ? 96 : 168, R = 14, CW = Math.max(120, W - L - R);
    var RACE = phone ? 96 : 130, FLAGS = 46, LANE = phone ? 22 : 26, AX = 26;
    var top0 = 8, raceY = top0, flagY = raceY + RACE + 10, laneY = flagY + FLAGS, H = laneY + lanes.length * LANE + AX;
    var x = function (ms) { return L + CW * Math.min(1, Math.max(0, ms / durMs)); };
    var svg = el('svg', { viewBox: '0 0 ' + W + ' ' + H, width: W, height: H, class: 'mtl-svg', role: 'img', 'aria-label': 'Match timeline' }, root);
    var defs = el('defs', {}, svg);
    [['gA', 'var(--tA)'], ['gB', 'var(--tB)']].forEach(function (g) {
      var lg = el('linearGradient', { id: g[0], x1: 0, y1: 0, x2: 0, y2: 1 }, defs);
      el('stop', { offset: '0%', 'stop-color': g[1], 'stop-opacity': .34 }, lg); el('stop', { offset: '100%', 'stop-color': g[1], 'stop-opacity': 0 }, lg);
    });
    var glow = el('filter', { id: 'glow', x: '-50%', y: '-50%', width: '200%', height: '200%' }, defs);
    el('feGaussianBlur', { stdDeviation: 2.2, result: 'b' }, glow); var mg = el('feMerge', {}, glow); el('feMergeNode', { in: 'b' }, mg); el('feMergeNode', { in: 'SourceGraphic' }, mg);

    // minute grid
    var g = el('g', { class: 'grid' }, svg), step = durMs > 20 * 60000 ? 5 : durMs > 8 * 60000 ? 2 : 1;
    for (var mn = 0; mn * 60000 <= durMs; mn += step) {
      el('line', { x1: x(mn * 60000), x2: x(mn * 60000), y1: raceY, y2: H - AX + 4 }, g);
      var tl = el('text', { x: x(mn * 60000), y: H - 8, class: 'tick' }, g); tl.textContent = mn + ':00';
    }

    // ---- kill race: cumulative kills per team (two smooth step areas)
    var teams = {}, ktimes = { 0: [], 1: [] };
    events.forEach(function (e) { if (e[0] === 'k' && e[2] in teamOf) { var t = teamOf[e[2]]; if (t === 0 || t === 1) ktimes[t].push(e[1]); } });
    var maxK = Math.max(1, ktimes[0].length, ktimes[1].length), yR = function (n) { return raceY + RACE - (RACE - 14) * n / maxK; };
    var rg = el('g', { class: 'race' }, svg);
    el('rect', { x: L, y: raceY, width: CW, height: RACE, class: 'race-bg', rx: 8 }, rg);
    [0, 1].forEach(function (t) {
      var pts = [[x(0), yR(0)]]; ktimes[t].forEach(function (ms, i) { pts.push([x(ms), yR(i)]); pts.push([x(ms), yR(i + 1)]); }); pts.push([x(durMs), yR(ktimes[t].length)]);
      var d = 'M' + pts.map(function (p) { return p[0].toFixed(1) + ',' + p[1].toFixed(1); }).join('L');
      el('path', { d: d + 'L' + x(durMs) + ',' + (raceY + RACE) + 'L' + x(0) + ',' + (raceY + RACE) + 'Z', fill: 'url(#g' + (t ? 'B' : 'A') + ')' }, rg);
      el('path', { d: d, class: 'race-line ' + tcls(t), filter: 'url(#glow)' }, rg);
      var end = el('text', { x: x(durMs) - 4, y: yR(ktimes[t].length) - 5, class: 'race-end ' + tcls(t) }, rg); end.textContent = ktimes[t].length;
    });
    var rl = el('text', { x: L - 10, y: raceY + 16, class: 'lane-title' }, svg); rl.textContent = 'Kill race';
    var rs = el('text', { x: L - 10, y: raceY + 32, class: 'lane-sub' }, svg); rs.textContent = (my === 1 ? ktimes[1].length + '–' + ktimes[0].length : ktimes[0].length + '–' + ktimes[1].length) + ' kills';
    // biggest lead marker
    var lead = 0, leadAt = 0, a0 = 0, b0 = 0;
    events.forEach(function (e) { if (e[0] === 'k' && e[2] in teamOf) { if (teamOf[e[2]] === 0) a0++; else if (teamOf[e[2]] === 1) b0++; var dlt = (my === 1 ? b0 - a0 : a0 - b0); if (Math.abs(dlt) > Math.abs(lead)) { lead = dlt; leadAt = e[1]; } } });
    if (lead) { var lx = x(leadAt); el('line', { x1: lx, x2: lx, y1: raceY + 4, y2: raceY + RACE - 2, class: 'lead-line' }, rg);
      var lt = el('text', { x: lx + 6 + 150 > L + CW ? lx - 6 : lx + 6, y: raceY + RACE - 8, class: 'lead-txt' + (lx + 156 > L + CW ? ' rt' : '') }, rg); lt.textContent = 'Biggest ' + (lead > 0 ? 'lead' : 'deficit') + ' ' + (lead > 0 ? '+' : '') + lead + ' · ' + clock(leadAt); }

    // ---- lanes
    var lg2 = el('g', { class: 'lanes' }, svg), laneOf = {};
    lanes.forEach(function (p, i) {
      var y = laneY + i * LANE; laneOf[p.n] = y + LANE / 2;
      el('rect', { x: 0, y: y, width: W, height: LANE, class: 'lane ' + (i % 2 ? 'odd' : '') + (p.you ? ' you' : '') }, lg2);
      el('rect', { x: 2, y: y + 3, width: 4, height: LANE - 6, rx: 2, class: 'tbar ' + tcls(p.t) }, lg2);
      var nm = el('text', { x: 12, y: y + LANE / 2 + 4, class: 'lane-name' + (p.tr ? ' tr' : '') }, lg2);
      var max = phone ? 11 : 15, name = p.n.length > max ? p.n.slice(0, max - 1) + '…' : p.n; nm.textContent = name; nm.setAttribute('data-gamertag',p.n);
      if (!phone) { var kd = el('text', { x: L - 10, y: y + LANE / 2 + 4, class: 'lane-kd' }, lg2); kd.textContent = p.k + '/' + p.d + '/' + p.a; }
    });
    // multikill chains: kills by one player within 4.5 s of each other
    var lastK = {}, chains = el('g', { class: 'chains' }, svg);
    events.forEach(function (e) {
      if (e[0] !== 'k' || !(e[2] in laneOf)) return; var pk = lastK[e[2]];
      if (pk != null && e[1] - pk <= 4500) el('line', { x1: x(pk), x2: x(e[1]), y1: laneOf[e[2]], y2: laneOf[e[2]], class: 'chain ' + tcls(teamOf[e[2]]) }, chains);
      lastK[e[2]] = e[1];
    });
    var dots = el('g', { class: 'dots' }, svg), flags = [];
    events.forEach(function (e) {
      var k = e[0];
      if (k === 'k' && e[2] in laneOf) el('circle', { cx: x(e[1]), cy: laneOf[e[2]], r: phone ? 3 : 3.8, class: 'kill ' + tcls(teamOf[e[2]]) }, dots);
      if ((k === 'k' || k === 'd') && e[3] in laneOf) { var dx = x(e[1]), dy = laneOf[e[3]], s = phone ? 2.4 : 3;
        el('path', { d: 'M' + (dx - s) + ',' + (dy - s) + 'L' + (dx + s) + ',' + (dy + s) + 'M' + (dx + s) + ',' + (dy - s) + 'L' + (dx - s) + ',' + (dy + s), class: 'death' }, dots); }
      if (k === 'm' && e[2] in laneOf) { var bx = x(e[1]), by = laneOf[e[2]] - LANE / 2 + 5, w = big(e[3]) ? 4.5 : 2.8;
        el('path', { d: 'M' + bx + ',' + (by - w) + 'L' + (bx + w) + ',' + by + 'L' + bx + ',' + (by + w) + 'L' + (bx - w) + ',' + by + 'Z', class: 'medal' + (big(e[3]) ? ' big' : '') }, dots);
        if (big(e[3])) flags.push(e); }
      if (k === 'o' && e[2] in laneOf) el('rect', { x: x(e[1]) - 2.5, y: laneOf[e[2]] + LANE / 2 - 8, width: 5, height: 5, rx: 1.2, class: 'obj' }, dots);
    });
    // ---- big-moment flags (best few, staggered so labels don't collide)
    flags.sort(function (a, b) { return big(b[3]) - big(a[3]) || a[1] - b[1]; });
    var fg = el('g', { class: 'flags' }, svg), placed = [];
    flags.slice(0, phone ? 3 : 7).sort(function (a, b) { return a[1] - b[1]; }).forEach(function (e) {
      var fx = x(e[1]), label = e[3] + ' · ' + e[2], wTxt = label.length * 6.1 + 10, row = 0;
      while (placed.some(function (p) { return p.row === row && Math.abs(p.x - fx) < (p.w + wTxt) / 2 + 4; }) && row < 3) row++;
      if (row > 2) return;                                        /* no room: skip rather than overlap */
      placed.push({ x: fx, w: wTxt, row: row });
      var fy = flagY + row * 15;
      el('line', { x1: fx, x2: fx, y1: fy + 6, y2: laneOf[e[2]] - LANE / 2 + 2, class: 'flag-pole' }, fg);
      var bx = Math.max(L, Math.min(L + CW - wTxt, fx - wTxt / 2));
      el('rect', { x: bx, y: fy - 7, width: wTxt, height: 13, rx: 6.5, class: 'flag-pill ' + tcls(teamOf[e[2]]) }, fg);
      var t = el('text', { x: bx + wTxt / 2, y: fy + 3, class: 'flag-txt' }, fg); t.textContent = label;
    });

    // ---- hover crosshair + tooltip; click jumps the event list
    /* ?at=<seconds> (Best plays links): mark that moment */
    var atS = Number(new URLSearchParams(location.search).get('at'));
    if (atS > 0) { var ax = x(atS * 1000); el('rect', { x: ax - 2, y: raceY, width: 26, height: H - AX - raceY, class: 'at-band' }, svg);
      var al = el('text', { x: Math.min(ax + 4, L + CW - 80), y: H - AX - 6, class: 'at-lab' }, svg); al.textContent = '▶ this play · ' + clock(atS * 1000); }
    var cross = el('line', { x1: 0, x2: 0, y1: raceY, y2: H - AX, class: 'cross', visibility: 'hidden' }, svg);
    var tip = document.createElement('div'); tip.className = 'mtl-tip'; tip.hidden = true; root.appendChild(tip);
    var hit = el('rect', { x: L, y: 0, width: CW, height: H - AX, fill: 'transparent', class: 'hit' }, svg);
    function at(evt) { var r = svg.getBoundingClientRect(), px = (evt.touches ? evt.touches[0].clientX : evt.clientX) - r.left; return Math.max(0, Math.min(durMs, (px - L) / CW * durMs)); }
    function show(evt) {
      var ms = at(evt), cx = x(ms); cross.setAttribute('x1', cx); cross.setAttribute('x2', cx); cross.setAttribute('visibility', 'visible');
      var near = events.filter(function (e) { return Math.abs(e[1] - ms) <= 2500; }).slice(0, 7), a = 0, b = 0;
      events.forEach(function (e) { if (e[1] <= ms && e[0] === 'k' && e[2] in teamOf) { if (teamOf[e[2]] === 0) a++; else if (teamOf[e[2]] === 1) b++; } });
      var mine = my === 1 ? [b, a] : [a, b];
      tip.innerHTML = '<b>' + clock(ms) + '</b> <span class="muted">kills ' + mine[0] + '–' + mine[1] + '</span>' + (near.length ? '<ul>' + near.map(function (e) {
        var who = '<span class="' + tcls(teamOf[e[2]]) + '">' + esc(e[2] || '') + '</span>', vic = '<span class="' + tcls(teamOf[e[3]]) + '">' + esc(e[3] || '') + '</span>';
        return '<li><i>' + clock(e[1]) + '</i> ' + (e[0] === 'k' ? who + ' ▸ ' + vic : e[0] === 'd' ? vic + ' died' : e[0] === 'm' ? who + ' · <em>' + esc(e[3]) + '</em>' : who + ' · objective') + '</li>';
      }).join('') + '</ul>' : '<div class="muted">Quiet moment</div>');
      tip.hidden = false; var r = root.getBoundingClientRect(), left = cx + 14; if (left + 260 > r.width) left = cx - 274; tip.style.left = Math.max(4, left) + 'px'; tip.style.top = (laneY - 10) + 'px';
    }
    function hide() { cross.setAttribute('visibility', 'hidden'); tip.hidden = true; }
    hit.addEventListener('mousemove', show); hit.addEventListener('mouseleave', hide); hit.addEventListener('touchstart', show, { passive: true });
    hit.addEventListener('click', function (evt) {
      var fold = document.querySelector('.recap-fold'); if (fold) fold.open = true;
      var t = document.getElementById('recap-time'); if (!t) return; t.value = Math.round(at(evt) / 1000); t.dispatchEvent(new Event('input'));
      var list = document.getElementById('recap-events'); if (list) list.scrollIntoView({ behavior: 'smooth', block: 'center' });
    });
  }

  fetch('/api/match/' + M.mid + '/events').then(function (r) { return r.ok ? r.json() : { e: [] }; }).then(function (d) {
    events = d.e || [];
    var last = events.reduce(function (m, e) { return Math.max(m, e[1]); }, 0); if (last > durMs) durMs = last;
    render();
    var rz; window.addEventListener('resize', function () { clearTimeout(rz); rz = setTimeout(render, 150); });
  }).catch(function () { root.innerHTML = '<p class="muted">Could not load the film timeline. Try again in a minute.</p>'; });
})();
