/* Polls /api/live/<slugs> every 30s and updates the live strip in place (no reload, the video keeps playing). */
(function () {
  var box = document.getElementById('live'); if (!box) return;
  var slugs = box.dataset.slugs, seen = {}, first = true, busy = false, status = document.getElementById('lvstatus');
  function esc(s) { return String(s == null ? '' : s).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); }
  function game(p, L) { return { who: p.gamertag, outcome: L.outcome || '', map: L.map || '', mode: L.mode || '', k: L.k, d: L.d, a: L.a }; }
  var calm = window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches;
  /* new-game banner: slides down from the top in the result's colour */
  function banner(g) {
    var o = (g.outcome || '').toLowerCase(), el = document.createElement('div');
    el.className = 'gamebanner ' + o; el.setAttribute('role', 'status');
    el.innerHTML = '<b class="gb-res">' + (o === 'win' ? 'W' : o === 'loss' ? 'L' : '–') + '</b><span class="gb-txt"><b>' + esc(g.who) + ' · ' + esc(g.outcome || 'Game') + '</b><small>' + esc(g.map) + (g.mode ? ' · ' + esc(g.mode) : '') + ' · ' + g.k + '/' + g.d + '/' + g.a + '</small></span>';
    document.body.appendChild(el); requestAnimationFrame(function () { el.classList.add('on'); });
    setTimeout(function () { el.classList.remove('on'); setTimeout(function () { el.remove(); }, 500); }, 5200);
    lastRes = { cls: o === 'win' ? 'won' : o === 'loss' ? 'lost' : '', t: Date.now() }; glow();
  }
  var lastRes = null;
  function glow() { var oa = document.getElementById('onair') || document.getElementById('playnow'); if (!oa || calm || !lastRes || !lastRes.cls || Date.now() - lastRes.t > 8000) return;
    oa.classList.remove('won', 'lost'); void oa.offsetWidth; oa.classList.add(lastRes.cls); }
  /* heartbeat on the live panel: "checked 12s ago" + a ring that fills until the next check */
  var lastCheck = 0;
  function beat() { lastCheck = Date.now(); var b = document.querySelector('.oa-beat'); if (!b) return; b.classList.remove('go'); void b.offsetWidth; b.classList.add('go'); ago(); }
  function ago() { var t = document.querySelector('[data-beat]'); if (!t || !lastCheck) return; var s = Math.round((Date.now() - lastCheck) / 1000); t.textContent = s < 5 ? 'checked just now' : 'checked ' + s + 's ago'; }
  setInterval(ago, 5000);
  function set(card, k, html) { var el = card.querySelector('[data-k="' + k + '"]'); if (el && el.innerHTML !== html) { el.innerHTML = html; el.classList.add('flash'); setTimeout(function () { el.classList.remove('flash'); }, 1200); } }
  function tick() {
    if (busy || document.hidden) return; busy = true;
    var controller=new AbortController(),timeout=setTimeout(function(){controller.abort()},12000);
    fetch('/api/live/' + slugs, { cache: 'no-store', signal:controller.signal }).then(function (r) { if (!r.ok) throw new Error('Stats unavailable'); return r.json(); }).then(function (j) {
      var any = false, fresh = [];
      j.players.forEach(function (p) {
        var l = p.live, card = box.querySelector('.lvcard[data-slug="' + p.slug + '"]');
        if (!l) { if (first) seen[p.slug] = ''; return; }                 /* remember "no game yet" so the first game tonight counts as new */
        if (!card) { if (!first && seen[p.slug] !== l.last.match_id) fresh.push(game(p, l.last)); seen[p.slug] = l.last.match_id; return; }
        if (l.active) any = true;
        set(card, 'record', esc(l.record)); set(card, 'games', esc(l.games)); set(card, 'kda', esc(l.kda)); set(card, 'kd', esc(l.kd));
        set(card, 'rating', esc(l.rating || '—'));
        var d = card.querySelector('[data-k="delta"]'); if (d) { d.textContent = l.delta == null ? '' : (l.delta > 0 ? '+' : '') + l.delta; d.className = l.delta > 0 ? 'pos' : l.delta < 0 ? 'neg' : ''; }
        set(card, 'pips', l.pips.map(function (o) { return '<i class="pip sm ' + esc(o) + '"></i>'; }).join(''));
        set(card, 'games_list', (l.games_list || []).map(function (g) { return '<a href="/match/' + encodeURIComponent(g.match_id) + '?player=' + encodeURIComponent(p.slug) + '" class="' + esc((g.outcome || '').toLowerCase()) + '">' + esc(g.map || '?') + ' · <b>' + g.k + '/' + g.d + '/' + g.a + '</b></a>'; }).join(''));
        var L = l.last;
        set(card, 'last', 'Last: <b class="res ' + esc((L.outcome || '').toLowerCase()) + '">' + esc(L.outcome) + '</b> · ' + esc(L.map || '') + ' ' + esc(L.mode || '') +
          ' · ' + L.k + '/' + L.d + '/' + L.a + ' · ' + Math.floor(l.ended_ago / 60) + 'm ago');
        if (!first && seen[p.slug] != null && seen[p.slug] !== L.match_id) fresh.push(game(p, L));
        seen[p.slug] = L.match_id;
      });
      if (any && box.hidden) { box.hidden = false; box.classList.add('on'); }
      if (fresh.length) { fresh.forEach(function (g, i) { setTimeout(function () { banner(g); }, i * 2600); }); refresh(fresh);
        /* the rest of a game lands after its first row: squadmates' copies (often 2-3 min later), then the film read
           (advanced stats, clips) — none of which shows up as a new game, so check again a few times (2026-10-11) */
        clearTimeout(follow.a); clearTimeout(follow.b); clearTimeout(follow.c);
        follow.a = setTimeout(function () { refresh(fresh); }, 45000); follow.b = setTimeout(function () { refresh(fresh); }, 120000); follow.c = setTimeout(function () { refresh(fresh); }, 240000); }
      beat();
      first = false;
      if (status) status.textContent = j.players.some(function (p) { return p.syncing; }) ? 'Updating match history…' : 'Checked just now · new results may take a few minutes.';
    }).catch(function () { if (status) status.textContent = 'Could not check for new results. Retrying automatically; your stats are still here.'; }).finally(function () { clearTimeout(timeout);busy = false; });
  }
  /* New game: re-fetch this page and swap the stat sections in place; the video (and its position) is never touched. */
  var follow = {};
  var SWAP = ['#onair', '#playnow', '#sqtable', '#statsboard', '#livevs', '.hubkpis', '.advhelp', '.gamelog', '#raw', '.brk', '#periods', '.hub-sessions', '.clipsec', '.twclips', '#teamwork', '#vodvs', '#watchguide'];
  /* what changed gets animated: numbers roll from the old value to the new one and glow, new game rows slide in */
  var NUM = /^([^\d\-+−]{0,3})([+\-−]?)(\d[\d,]*(?:\.\d+)?)(%|s|m)?$/;
  function leaves(root) { return [].slice.call(root.querySelectorAll('b,td,span,small,strong,div')).filter(function (e) { return !e.children.length && NUM.test(e.textContent.trim()); }); }
  var INJ = /\b(swipehint|colnav|mobile-sort|mobile-totals|mobile-expand|chatx)\b/;   /* elements the page scripts add or tag after load; skipped when matching */
  function rowKey(tr) { var a = tr.querySelector('a[href^="/match/"]'); return tr.getAttribute('data-match') || tr.getAttribute('data-gwatch') || (a && a.getAttribute('href')) || ''; }
  function roll(el, from, to) {
    var m = NUM.exec(to), f = NUM.exec(from); if (!m || !f) return;
    var sign = function (x) { return x[2] === '-' || x[2] === '−' ? -1 : 1; };
    var a = sign(f) * parseFloat(f[3].replace(/,/g, '')), b = sign(m) * parseFloat(m[3].replace(/,/g, '')), dec = (m[3].split('.')[1] || '').length, comma = m[3].indexOf(',') >= 0;
    el.classList.add(b > a ? 'tick-up' : b < a ? 'tick-down' : 'tick'); setTimeout(function () { el.classList.remove('tick-up', 'tick-down', 'tick'); }, 1600);
    if (calm || a === b || !isFinite(a) || !isFinite(b)) return;
    var t0 = performance.now(), dur = 900;
    (function step(now) { var k = Math.min(1, (now - t0) / dur), e = 1 - Math.pow(1 - k, 3), v = a + (b - a) * e;
      var txt = Math.abs(v).toFixed(dec); if (comma) txt = Number(txt).toLocaleString('en-US', { minimumFractionDigits: dec, maximumFractionDigits: dec });
      el.textContent = m[1] + (v < 0 ? (m[2] === '−' ? '−' : '-') : (m[2] === '+' ? '+' : '')) + txt + (m[4] || '');
      if (k < 1) requestAnimationFrame(step); else el.textContent = to; })(t0);
  }
  function diff(old, neu) {
    var keys = {}; [].forEach.call(old.querySelectorAll('tbody tr'), function (tr) { var k = rowKey(tr); if (k) keys[k] = 1; });
    var fresh = 0; [].forEach.call(neu.querySelectorAll('tbody tr'), function (tr) { var k = rowKey(tr); if (k && !keys[k] && Object.keys(keys).length) { tr.classList.add('row-new'); fresh++; } });
    /* match numbers by where they sit (a table row's game + column, else the path of child positions), so an added
       game row doesn't throw the rest out of line */
    function where(el, root) { var path = []; for (var e = el; e && e !== root; e = e.parentElement) {
        if (e.tagName === 'TR' && rowKey(e)) { path.unshift(rowKey(e)); continue; }
        /* a named stat (data-k): matched by name within its player card, wherever pinning moved it (customize.js) */
        if (e.dataset && e.dataset.k) { var card = e.closest('.oa-card'), cards = card && card.parentElement ? [].indexOf.call(card.parentElement.children, card) : 0;
          return 'card' + cards + '>k:' + e.dataset.k + (path.length ? '>' + path.join('>') : ''); }
        var sib = e.parentElement ? [].filter.call(e.parentElement.children, function (c) { return c.tagName === e.tagName && !INJ.test(c.className); }) : [];
        path.unshift(e.tagName + sib.indexOf(e)); }
      return path.join('>'); }
    var before = {}; leaves(old).forEach(function (el) { before[where(el, old)] = el.textContent.trim(); });
    var rolled = 0; leaves(neu).forEach(function (el) { if (el.closest('tr.row-new')) return; var o = before[where(el, neu)], n = el.textContent.trim();
      if (o != null && o !== n) { roll(el, o, n); rolled++; } });
    if (!fresh && !rolled && old.innerHTML !== neu.innerHTML) { neu.classList.add('sec-new'); setTimeout(function () { neu.classList.remove('sec-new'); }, 1600); }
  }
  /* where a new section goes: next to a neighbour (in the fetched page) that this page has too, found by id or SWAP selector */
  function same(el) { if (el.id) return document.getElementById(el.id);
    for (var i = 0; i < SWAP.length; i++) if (SWAP[i][0] === '.' && el.matches(SWAP[i])) { var all = document.querySelectorAll(SWAP[i]); return all.length === 1 ? all[0] : null; }
    var c = el.classList && el.classList[0]; if (!c || !window.CSS) return null;                  /* else: a class only one element has */
    var hit = document.querySelectorAll('.' + CSS.escape(c)); return hit.length === 1 && el.ownerDocument.querySelectorAll('.' + CSS.escape(c)).length === 1 ? hit[0] : null; }
  function anchor(nw, doc) {
    for (var s = nw.previousElementSibling; s; s = s.previousElementSibling) { var m = same(s); if (m) return { el: m, after: true }; }
    for (s = nw.nextElementSibling; s; s = s.nextElementSibling) { m = same(s); if (m) return { el: m, after: false }; }
    var par = nw.parentElement && same(nw.parentElement); if (!par) return null;
    return par.firstElementChild ? { el: par.firstElementChild, after: false } : { el: par, inside: true }; }
  function appear(n) { if (calm) return; n.animate([{ opacity: 0, transform: 'translateY(12px)' }, { opacity: 1, transform: 'none' }], { duration: 420, easing: 'cubic-bezier(.2,.8,.2,1)' }); }
  function vanish(o) { if (calm) { o.remove(); return; } o.animate([{ opacity: 1 }, { opacity: 0, transform: 'scale(.98)' }], { duration: 260, easing: 'ease-in' }).finished.then(function () { o.remove(); }, function () { o.remove(); }); }
  function refresh(quiet) {   /* quiet: the periodic pass — only the live box (stream info), never sections someone may have opened */
    var lu = new URL(location.href); if (document.querySelector('#raw:not([data-lazy])')) lu.searchParams.set('raw', '1');   /* keep a loaded raw table */
    lastFull = Date.now();
    fetch(lu, { cache: 'no-store', credentials: 'same-origin' }).then(function (r) { return r.ok ? r.text() : Promise.reject(); }).then(function (html) {
      var doc = new DOMParser().parseFromString(html, 'text/html');
      (quiet === true ? ['#onair', '#playnow'] : SWAP).forEach(function (sel) {
        var olds = document.querySelectorAll(sel), news = doc.querySelectorAll(sel);
        if (olds.length && olds.length === news.length) olds.forEach(function (o, i) { var n = document.importNode(news[i], true);
          if (o.hasAttribute('data-hold')) { o.__next = n; return; }   /* a clip is playing in the live box (livedetail.js): applied when it closes */
          o.replaceWith(n); try { diff(o, n); } catch (e) {} });
        /* 2026-10-11: a section that only exists from the first game on (game log, tiles, vs table…) is added where the
           page puts it — after the nearest earlier sibling that is already here — and one that's gone is removed */
        else if (!olds.length && news.length) [].forEach.call(news, function (nw) { var spot = anchor(nw, doc); if (!spot) return;
          var n = document.importNode(nw, true); if (spot.inside) spot.el.appendChild(n); else spot.el[spot.after ? 'after' : 'before'](n); appear(n); });
        else if (olds.length && !news.length) [].forEach.call(olds, function (o) { if (!o.hasAttribute('data-hold')) vanish(o); });
      });
      if (window.ctHeat) window.ctHeat(); if (window.ctPage) window.ctPage();
      beat(); glow();
    }).catch(function () { document.getElementById('lvreload').hidden = false; });
  }
  window.ctLiveRefresh = refresh; window.ctLiveBanner = banner;
  /* while someone is live, refresh quietly every 2 minutes too — stream title, viewers, the game they're on, and
     anything that settled after a game (film reads, clips) — not only when a new game lands (2026-10-11) */
  var lastFull = Date.now();
  setInterval(function () { if (document.hidden || busy || !(document.getElementById('onair') || document.getElementById('playnow'))) return;
    if (Date.now() - lastFull >= 115000) refresh(true); }, 15000);   /* also used by the browser test to replay an update */
  document.getElementById('lvreload').onclick = function () { this.hidden = true; refresh(); };
  /* keep the live uptime ticking */
  setInterval(function () { var oa = document.getElementById('onair'), b = oa && oa.querySelector('[data-uptime]'); if (!b || !oa.dataset.started) return;
    var up = Math.max(0, Math.floor(Date.now() / 1000 - +oa.dataset.started)); b.textContent = (up >= 3600 ? Math.floor(up / 3600) + 'h ' : '') + Math.floor(up % 3600 / 60) + 'm'; }, 30000);
  /* every 15s while live or playing now (the server re-syncs a streaming player every 20s, a playing one every 30s), 30-40s otherwise */
  tick(); setInterval(tick, document.getElementById('onair') || document.getElementById('playnow') ? 15000 : 30000 + Math.random()*10000);
})();
