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
  var R = { t: 0, speed: 20, run: false, started: false }, phX = null, phLine = null;   /* replay (2026-10-11, below) */

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
    phX = x; phLine = el('line', { x1: 0, x2: 0, y1: raceY, y2: H - AX, class: 'playhead', visibility: R.started ? 'visible' : 'hidden' }, svg); if (R.started) head();
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
      if (R.started) seek(at(evt));          /* replaying: jump the replay there too */
      var t = document.getElementById('recap-time'); if (!t) return; t.value = Math.round(at(evt) / 1000); t.dispatchEvent(new Event('input'));
      var list = document.getElementById('recap-events'); if (list) list.scrollIntoView({ behavior: 'smooth', block: 'center' });
    });
  }

  /* ---- Replay (2026-10-11): ▶ plays the game back fast. The header score counts up (kills — for Slayer-style games
     that IS the score; other modes show a running kill count under the final score) and each big play pops up beside
     it: left for your team, right for theirs. Click the timeline to jump; scrolled away, the score docks at the top. */
  var hsc = document.querySelector('.mhero .mh-score'), nums = hsc ? hsc.querySelectorAll('.sc b') : [], orig = [].map.call(nums, function (b) { return b.dataset.v != null ? b.dataset.v : b.textContent; });   /* data-v: the real final (the count-up animation may be mid-way) */
  var ctl, bug, kA = 0, kB = 0, done = 0, raf = 0, last = 0, docked = false, slayer = false, lastObj = {};
  function mineKill(e) { return teamOf[e[2]] === my; }
  function scoreTo(ms) { kA = 0; kB = 0; done = 0;
    events.forEach(function (e, i) { if (e[1] <= ms) { done = i + 1; if (e[0] === 'k' && e[2] in teamOf && (teamOf[e[2]] === 0 || teamOf[e[2]] === 1)) { if (mineKill(e)) kA++; else kB++; } } }); }
  function paint(bump) {
    var txt = [String(kA), String(kB)];
    if (slayer) [].forEach.call(nums, function (b, i) { if (b.textContent !== txt[i]) { b.textContent = txt[i]; if (bump) b.animate([{ transform: 'scale(1.35)' }, { transform: 'none' }], { duration: 320, easing: 'cubic-bezier(.2,.9,.3,1.4)' }); } });
    var run = hsc && hsc.querySelector('.mh-run'); if (run) run.textContent = clock(R.t) + (slayer ? '' : ' · kills ' + kA + '–' + kB);
    if (bug) { bug.querySelector('.sb-a').textContent = kA; bug.querySelector('.sb-b').textContent = kB; bug.querySelector('.sb-t').textContent = clock(R.t) + (slayer ? '' : ' · kills'); }
  }
  function head() { if (!phLine || !phX) return; var px = phX(R.t); phLine.setAttribute('x1', px); phLine.setAttribute('x2', px); phLine.setAttribute('visibility', 'visible'); }
  function pop(e) {
    var mine = mineKill(e), host = docked && bug ? bug : hsc; if (!host) return;
    var box = host.querySelector('.mh-pops.' + (mine ? 'l' : 'r')); if (!box) return;
    var d = document.createElement('div'); d.className = 'mh-pop ' + tcls(teamOf[e[2]]) + (big(e[3] || '') >= 10 ? ' huge' : '');
    d.innerHTML = '<b>' + esc(e[0] === 'o' ? 'Objective' : e[3]) + '</b><span>' + esc(e[2] || '') + '</span>';
    box.prepend(d); while (box.children.length > 3) box.lastChild.remove();
    setTimeout(function () { d.classList.add('out'); setTimeout(function () { d.remove(); }, 400); }, 2600);
  }
  function step(ts) {
    if (!R.run) return; var dt = Math.min(250, ts - (last || ts)); last = ts; var to = Math.min(durMs, R.t + dt * R.speed), bump = false;
    while (done < events.length && events[done][1] <= to) { var e = events[done++];
      if (e[0] === 'k' && e[2] in teamOf && (teamOf[e[2]] === 0 || teamOf[e[2]] === 1)) { if (mineKill(e)) kA++; else kB++; bump = true; }
      if (e[0] === 'm' && big(e[3])) pop(e);
      else if (e[0] === 'o' && e[2] in teamOf && !(e[1] - (lastObj[e[2]] || -1e9) < 15000)) { lastObj[e[2]] = e[1]; pop(e); }   /* Oddball/KOTH log objective plays constantly: one per player per 15 s */
      else if (e[0] === 'o') lastObj[e[2]] = e[1]; }
    R.t = to; paint(bump); head();
    if (R.t >= durMs) { finish(); return; } raf = requestAnimationFrame(step); }
  function play() { if (R.t >= durMs) { R.t = 0; scoreTo(0); } R.run = true; R.started = true; last = 0; hsc && hsc.classList.add('replaying'); if (bug) bug.hidden = !docked; setCtl(); paint(false); head(); raf = requestAnimationFrame(step); }
  function pause() { R.run = false; cancelAnimationFrame(raf); setCtl(); }
  function seek(ms) { R.t = ms; scoreTo(ms); lastObj = {}; paint(false); head(); }
  function finish() { R.run = false; [].forEach.call(nums, function (b, i) { b.textContent = orig[i]; b.animate([{ transform: 'scale(1.4)' }, { transform: 'none' }], { duration: 420, easing: 'cubic-bezier(.2,.9,.3,1.4)' }); });
    var run = hsc && hsc.querySelector('.mh-run'); if (run) run.textContent = 'Final';
    if (bug && slayer) { bug.querySelector('.sb-a').textContent = orig[0]; bug.querySelector('.sb-b').textContent = orig[1]; bug.querySelector('.sb-t').textContent = 'Final'; } setCtl(); }
  function stop() { pause(); R.started = false; R.t = 0; [].forEach.call(nums, function (b, i) { b.textContent = orig[i]; });
    if (hsc) { hsc.classList.remove('replaying'); [].forEach.call(hsc.querySelectorAll('.mh-pop'), function (n) { n.remove(); }); }
    if (phLine) phLine.setAttribute('visibility', 'hidden'); if (bug) bug.hidden = true; setCtl(); }
  function setCtl() { if (!ctl) return; var b = ctl.querySelector('.rp-go'); b.textContent = R.run ? '❚❚ Pause' : R.started && R.t < durMs ? '▶ Resume' : R.started ? '↺ Replay again' : '▶ Replay the game';
    ctl.querySelector('.rp-stop').hidden = !R.started; }
  function setup() {
    if (!hsc || !nums.length || !events.length) return;
    var fa = parseInt(orig[0], 10), fb = parseInt(orig[1], 10), ka = 0, kb = 0;
    events.forEach(function (e) { if (e[0] === 'k' && e[2] in teamOf && (teamOf[e[2]] === 0 || teamOf[e[2]] === 1)) { if (mineKill(e)) ka++; else kb++; } });
    var eb = document.querySelector('.mhero .eyebrow');
    /* the score is (about) the kill count: count it up in the header; betrayals/suicides can shift the official score a
       little, so the real final always lands at the end */
    slayer = (fa === ka && fb === kb) || (!!eb && /Slayer/i.test(eb.textContent) && Math.abs(fa - ka) <= 6 && Math.abs(fb - kb) <= 6);
    ['l', 'r'].forEach(function (s) { var d = document.createElement('div'); d.className = 'mh-pops ' + s; d.setAttribute('aria-live', 'polite'); hsc.appendChild(d); });
    var run = document.createElement('small'); run.className = 'mh-run'; hsc.appendChild(run);
    ctl = document.createElement('div'); ctl.className = 'mtl-replay';
    ctl.innerHTML = '<button type="button" class="rp-go"></button><label>Speed <select class="rp-speed"><option value="10">×10</option><option value="20" selected>×20</option><option value="40">×40</option></select></label><button type="button" class="rp-stop">✕ Stop</button>';
    var ph = document.querySelector('#timeline .ph'); if (ph) ph.appendChild(ctl);
    ctl.querySelector('.rp-go').onclick = function () { if (R.run) pause(); else play(); };
    ctl.querySelector('.rp-stop').onclick = stop;
    ctl.querySelector('.rp-speed').onchange = function () { R.speed = +this.value; };
    bug = document.createElement('div'); bug.className = 'mh-bug'; bug.hidden = true;
    bug.innerHTML = '<div class="mh-pops l"></div><b class="sb-a ' + tcls(my) + '"></b><span class="sb-t"></span><b class="sb-b ' + tcls(my === 1 ? 0 : 1) + '"></b><div class="mh-pops r"></div>';
    document.body.appendChild(bug);
    if (window.IntersectionObserver) new IntersectionObserver(function (es) { docked = !es[0].isIntersecting; bug.hidden = !(docked && R.started); }, { rootMargin: '-60px 0px 0px 0px' }).observe(hsc);
    setCtl();
  }

  fetch('/api/match/' + M.mid + '/events').then(function (r) { return r.ok ? r.json() : { e: [] }; }).then(function (d) {
    events = d.e || [];
    var last = events.reduce(function (m, e) { return Math.max(m, e[1]); }, 0); if (last > durMs) durMs = last;
    render(); setup();
    var rz; window.addEventListener('resize', function () { clearTimeout(rz); rz = setTimeout(render, 150); });
  }).catch(function () { root.innerHTML = '<p class="muted">Could not load the film timeline. Try again in a minute.</p>'; });
})();
