/* Polls /api/live/<slugs> every 30s and updates the live strip in place (no reload, the video keeps playing). */
(function () {
  var box = document.getElementById('live'); if (!box) return;
  var slugs = box.dataset.slugs, seen = {}, first = true, busy = false, status = document.getElementById('lvstatus');
  function esc(s) { return String(s == null ? '' : s).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); }
  function set(card, k, html) { var el = card.querySelector('[data-k="' + k + '"]'); if (el && el.innerHTML !== html) { el.innerHTML = html; el.classList.add('flash'); setTimeout(function () { el.classList.remove('flash'); }, 1200); } }
  function tick() {
    if (busy || document.hidden) return; busy = true;
    var controller=new AbortController(),timeout=setTimeout(function(){controller.abort()},12000);
    fetch('/api/live/' + slugs, { cache: 'no-store', signal:controller.signal }).then(function (r) { if (!r.ok) throw new Error('Stats unavailable'); return r.json(); }).then(function (j) {
      var any = false, fresh = [];
      j.players.forEach(function (p) {
        var l = p.live, card = box.querySelector('.lvcard[data-slug="' + p.slug + '"]');
        if (!l) { if (first) seen[p.slug] = ''; return; }                 /* remember "no game yet" so the first game tonight counts as new */
        if (!card) { if (!first && seen[p.slug] !== l.last.match_id) fresh.push(p.gamertag + ': ' + l.last.outcome + ' on ' + (l.last.map || '?')); seen[p.slug] = l.last.match_id; return; }
        if (l.active) any = true;
        set(card, 'record', esc(l.record)); set(card, 'games', esc(l.games)); set(card, 'kda', esc(l.kda)); set(card, 'kd', esc(l.kd));
        set(card, 'rating', esc(l.rating || '—'));
        var d = card.querySelector('[data-k="delta"]'); if (d) { d.textContent = l.delta == null ? '' : (l.delta > 0 ? '+' : '') + l.delta; d.className = l.delta > 0 ? 'pos' : l.delta < 0 ? 'neg' : ''; }
        set(card, 'pips', l.pips.map(function (o) { return '<i class="pip sm ' + esc(o) + '"></i>'; }).join(''));
        set(card, 'games_list', (l.games_list || []).map(function (g) { return '<a href="/match/' + encodeURIComponent(g.match_id) + '?player=' + encodeURIComponent(p.slug) + '" class="' + esc((g.outcome || '').toLowerCase()) + '">' + esc(g.map || '?') + ' · <b>' + g.k + '/' + g.d + '/' + g.a + '</b></a>'; }).join(''));
        var L = l.last;
        set(card, 'last', 'Last: <b class="res ' + esc((L.outcome || '').toLowerCase()) + '">' + esc(L.outcome) + '</b> · ' + esc(L.map || '') + ' ' + esc(L.mode || '') +
          ' · ' + L.k + '/' + L.d + '/' + L.a + ' · ' + Math.floor(l.ended_ago / 60) + 'm ago');
        if (!first && seen[p.slug] != null && seen[p.slug] !== L.match_id) fresh.push(p.gamertag + ': ' + L.outcome + ' on ' + (L.map || '?') + ' · ' + L.k + '/' + L.d + '/' + L.a);
        seen[p.slug] = L.match_id;
      });
      if (any && box.hidden) { box.hidden = false; box.classList.add('on'); }
      if (fresh.length) { if (window.toast) toast('New game in — ' + fresh[0]); refresh(); }
      first = false;
      if (status) status.textContent = j.players.some(function (p) { return p.syncing; }) ? 'Updating match history…' : 'Checked just now · new results may take a few minutes.';
    }).catch(function () { if (status) status.textContent = 'Could not check for new results. Retrying automatically; your stats are still here.'; }).finally(function () { clearTimeout(timeout);busy = false; });
  }
  /* New game: re-fetch this page and swap the stat sections in place; the video (and its position) is never touched. */
  var SWAP = ['#onair', '.hubkpis', '.advhelp', '.gamelog', '#periods', '.hub-sessions'];
  function refresh() {
    fetch(location.href, { cache: 'no-store', credentials: 'same-origin' }).then(function (r) { return r.ok ? r.text() : Promise.reject(); }).then(function (html) {
      var doc = new DOMParser().parseFromString(html, 'text/html');
      SWAP.forEach(function (sel) {
        var olds = document.querySelectorAll(sel), news = doc.querySelectorAll(sel);
        if (olds.length && olds.length === news.length) olds.forEach(function (o, i) { o.replaceWith(document.importNode(news[i], true)); });
      });
      if (window.ctHeat) window.ctHeat(); if (window.ctPage) window.ctPage();
      var oa = document.getElementById('onair'); if (oa) { oa.classList.add('flash'); setTimeout(function () { oa.classList.remove('flash'); }, 1500); }
    }).catch(function () { document.getElementById('lvreload').hidden = false; });
  }
  document.getElementById('lvreload').onclick = function () { this.hidden = true; refresh(); };
  /* keep the live uptime ticking */
  setInterval(function () { var oa = document.getElementById('onair'), b = oa && oa.querySelector('[data-uptime]'); if (!b || !oa.dataset.started) return;
    var up = Math.max(0, Math.floor(Date.now() / 1000 - +oa.dataset.started)); b.textContent = (up >= 3600 ? Math.floor(up / 3600) + 'h ' : '') + Math.floor(up % 3600 / 60) + 'm'; }, 30000);
  tick(); setInterval(tick, 30000 + Math.random()*10000);
})();
