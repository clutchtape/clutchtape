/* Click-to-sort for every table (delegated, so dynamic tables work too) + column heatmaps (same colour scale as the main Halo site): green = best in the column, red = worst.
   Opt-in per column: <th data-heat> (higher is better) or <th data-heat="lo"> (lower is better, e.g. Dmg/KA).
   Applies to every table.heat on load; call window.ctHeat(el) after rendering a table dynamically. */
(function () {
  var KEEP = /^(SC%|SC% \(stack\)|KDA|Dmg\/min|Dmg\/m|DMG\/M|Win ?%)$/i;
  function color(s) {
    s = Math.max(0, Math.min(1, s));
    if (s >= 0.5) { var t = (s - 0.5) * 2; return 'rgba(' + Math.round(65 - 43 * t) + ',' + Math.round(82 + 81 * t) + ',' + Math.round(52 + 22 * t) + ',' + (0.18 + 0.28 * t).toFixed(3) + ')'; }
    var u = (0.5 - s) * 2; return 'rgba(' + Math.round(65 + 62 * u) + ',' + Math.round(82 - 53 * u) + ',' + Math.round(52 - 23 * u) + ',' + (0.18 + 0.30 * u).toFixed(3) + ')';
  }
  function num(cell) {
    var raw = cell.getAttribute('data-val');
    var t = (raw != null ? raw : cell.textContent || '').trim().replace(/[,+%s]/g, '').replace('−', '-');
    if (!t || !/^-?\d*\.?\d+$/.test(t)) return null;
    return parseFloat(t);
  }
  function heat(table) {
    var heads = [].slice.call(table.querySelectorAll('thead th')), rows = [].slice.call(table.querySelectorAll('tbody tr'));
    if (rows.length < 2) return;
    heads.forEach(function (th, i) {
      if (!th.hasAttribute('data-heat')) return;
      /* declutter (2026-10-09): colour only the headline numbers unless the table opts in (.heat-all) */
      if (!table.classList.contains('heat-all') && !table.classList.contains('heat-text') && !KEEP.test(th.textContent.trim())) { rows.forEach(function (r) { var c = r.cells[i]; if (c) { c.style.backgroundColor = ''; c.style.color = ''; } }); return; }
      var lo = th.getAttribute('data-heat') === 'lo', cells = [];
      rows.forEach(function (r) { var c = r.cells[i]; if (!c || c.colSpan > 1) return; c.style.backgroundColor = ''; c.style.color = ''; var v = num(c); if (v != null && isFinite(v)) cells.push([c, v]); });
      if (cells.length < 2) return;
      var vs = cells.map(function (x) { return x[1]; }), min = Math.min.apply(null, vs), max = Math.max.apply(null, vs);
      if (max === min) return;
      cells.forEach(function (x) {
        var s = (x[1] - min) / (max - min); if (lo) s = 1 - s;
        if (table.classList.contains('heat-text')) { var tgt = x[0].querySelector('small b') || x[0]; tgt.style.color = s >= 0.72 ? '#6ee79a' : s <= 0.28 ? '#f87171' : ''; return; }
        x[0].style.backgroundColor = color(s);
        x[0].style.color = s >= 0.72 ? '#b7f7c7' : s <= 0.28 ? '#fecaca' : '';
      });
    });
  }

  /* ---- sorting: click a header; numbers sort high→low first, text A→Z; blanks (—) always last; "#" restores game order */
  function key(cell) {
    if (!cell) return null;
    var raw = cell.getAttribute('data-sort') || cell.getAttribute('data-val');
    var t = (raw != null ? raw : cell.textContent || '').trim();
    if (!t || t === '—' || t === '-') return null;
    var kda = t.match(/^(\d+)\s*\/\s*(\d+)\s*\/\s*(\d+)/); if (kda) return +kda[1];              // K/D/A → kills
    var clock = t.match(/^(\d+):(\d\d)$/); if (clock) return +clock[1] * 60 + +clock[2];           // 8:30 length
    var ampm = t.match(/^(\d+):(\d\d)\s*(AM|PM)$/i);                                               // 9:03 PM
    if (ampm) return ((+ampm[1] % 12) + (/pm/i.test(ampm[3]) ? 12 : 0)) * 60 + +ampm[2];
    var n = t.replace(/[,+%]/g, '').replace('−', '-').replace(/s$/, '').match(/^-?\d*\.?\d+$/);
    return n ? parseFloat(n[0]) : t.toLowerCase();
  }
  document.addEventListener('click', function (e) {
    var th = e.target.closest('thead th'); if (!th || e.target.closest('a,button,input,select')) return;
    var table = th.closest('table'), body = table && table.tBodies[0]; if (!body || table.classList.contains('nosort')) return;
    var i = th.cellIndex, rows = [].slice.call(body.rows);
    var keep = rows.filter(function (r) { return r.cells.length < 2; }), data = rows.filter(function (r) { return r.cells.length >= 2; });
    if (data.length < 2) return;
    rows.forEach(function (r, k) { if (r.dataset.ord == null) r.dataset.ord = k; });
    var numeric = data.some(function (r) { return typeof key(r.cells[i]) === 'number'; });
    var dir = th.dataset.dir === 'desc' ? 'asc' : th.dataset.dir === 'asc' ? 'desc' : (numeric && !/^#$/.test(th.textContent.trim()) && th.getAttribute('data-heat') !== 'lo' ? 'desc' : 'asc')   /* first click = best first */;
    [].forEach.call(table.querySelectorAll('thead th'), function (h) { delete h.dataset.dir; h.removeAttribute('aria-sort'); });
    th.dataset.dir = dir; th.setAttribute('aria-sort', dir === 'asc' ? 'ascending' : 'descending');
    data.sort(function (a, b) {
      var x = key(a.cells[i]), y = key(b.cells[i]);
      if (x === null && y === null) return a.dataset.ord - b.dataset.ord;
      if (x === null) return 1; if (y === null) return -1;
      var c = typeof x === typeof y ? (x < y ? -1 : x > y ? 1 : 0) : (typeof x === 'number' ? -1 : 1);
      return (dir === 'asc' ? c : -c) || a.dataset.ord - b.dataset.ord;
    });
    data.concat(keep).forEach(function (r) { body.appendChild(r); });
  });

  /* ---- column pages instead of a sideways scrollbar: identity columns stay put (first column, or <th data-pin>);
     the rest are split into pages that fit the width, in markup order (most important first), with ‹ 1/3 › at the right */
  function page(table) {
    var wrap = table.parentElement, head = table.tHead && table.tHead.rows[0]; if (!wrap || !head) return;
    [].forEach.call(table.querySelectorAll('.colnav'), function (c) { c.remove(); });
    var rows = [].slice.call(table.rows);
    rows.forEach(function (r) { [].forEach.call(r.cells, function (c) { if (c.dataset.pgHide) { c.style.display = ''; delete c.dataset.pgHide; } }); });
    table.classList.remove('paged');
    var hint = wrap.previousElementSibling && wrap.previousElementSibling.classList.contains('swipehint') ? wrap.previousElementSibling : null;
    if (hint) hint.remove(); wrap.classList.remove('swipe');
    if (table.classList.contains('mobile-cards') && innerWidth <= 700) return;
    if (table.scrollWidth <= wrap.clientWidth + 1) return;
    if (table.classList.contains('rawtable') || table.classList.contains('scrollx')) { swipe(wrap); rawStick(table); return; }   /* raw data: always scroll, frozen name/time */
    if (wrap.clientWidth < 700) { swipe(wrap); return; }      /* phones: swipe sideways (no visible scrollbar) with a › arrow */
    var heads = [].slice.call(head.cells), n = heads.length;
    var widths = heads.map(function (th) { return th.getBoundingClientRect().width; });
    var pin = heads.map(function (th, i) { return i === 0 || th.hasAttribute('data-pin'); });
    var navW = 92, sum = function (f) { return widths.reduce(function (a, w, i) { return a + (f(i) ? w : 0); }, 0); };
    var avail = wrap.clientWidth - sum(function (i) { return pin[i]; }) - navW;
    if (avail < Math.min(260, wrap.clientWidth * 0.45)) { pin = pin.map(function (p, i) { return i === 0; }); avail = wrap.clientWidth - widths[0] - navW; }
    var pages = [], cur = [], w = 0;
    for (var i = 0; i < n; i++) { if (pin[i] || !widths[i]) continue;
      if (cur.length && w + widths[i] > avail) { pages.push(cur); cur = []; w = 0; }
      cur.push(i); w += widths[i]; }
    if (cur.length) pages.push(cur);
    if (pages.length < 2) return;
    var pg = Math.min(+(table.dataset.pg || 0), pages.length - 1), show = {};
    pages[pg].forEach(function (i) { show[i] = 1; });
    rows.forEach(function (r) { if (r.cells.length !== n) return;
      [].forEach.call(r.cells, function (c, i) { if (!pin[i] && !show[i]) { c.style.display = 'none'; c.dataset.pgHide = '1'; } }); });
    table.classList.add('paged');
    var th = document.createElement('th'); th.className = 'colnav'; th.setAttribute('data-pin', '');
    th.innerHTML = '<button type="button" data-pg="-1" aria-label="Previous columns"' + (pg ? '' : ' disabled') + '>‹</button><span>' + (pg + 1) + '/' + pages.length + '</span><button type="button" data-pg="1" aria-label="More columns"' + (pg < pages.length - 1 ? '' : ' disabled') + '>›</button>';
    head.appendChild(th);
    rows.forEach(function (r) { if (r !== head && r.cells.length === n) { var td = document.createElement('td'); td.className = 'colnav'; r.appendChild(td); } });
  }
  var PAGED = '.tablewrap > table, table.heat';
  /* raw data table: freeze the columns whose header has data-stick (all widths) or data-stick="wide" (above 700px),
     left offsets measured from the real column widths */
  function rawStick(table) {
    var heads = [].slice.call(table.tHead.rows[0].cells), left = 0, last = -1, at = {};
    [].forEach.call(table.querySelectorAll('.stk'), function (c) { c.classList.remove('stk', 'stk-last'); c.style.left = ''; });
    heads.forEach(function (th, i) { var v = th.getAttribute('data-stick'); if (v === null || (v === 'wide' && innerWidth <= 700)) return;
      if (i !== last + 1 && last !== -1) return;            /* only a run of columns from the left can freeze */
      at[i] = left; left += th.getBoundingClientRect().width; last = i; });
    [].forEach.call(table.rows, function (r) { [].forEach.call(r.cells, function (c, i) { if (i in at) { c.classList.add('stk'); c.style.left = at[i] + 'px'; if (i === last) c.classList.add('stk-last'); } }); });
  }
  function swipe(wrap) {
    wrap.classList.add('swipe');
    /* a zero-height sticky holder before the table keeps the › arrow at mid-screen while the table is in view */
    var box = document.createElement('div'); box.className = 'swipehint';
    var b = document.createElement('button'); b.type = 'button'; b.setAttribute('aria-label', 'Scroll the table for more columns'); b.textContent = '›';
    box.appendChild(b);
    function place() { box.hidden = wrap.scrollLeft + wrap.clientWidth >= wrap.scrollWidth - 4; }
    b.onclick = function () { wrap.scrollBy({ left: wrap.clientWidth * 0.8, behavior: 'smooth' }); };
    wrap.addEventListener('scroll', place, { passive: true }); wrap.before(box); place();
  }
  window.ctPage = function (root) { [].forEach.call((root || document).querySelectorAll(PAGED), page); };
  /* the Analysis stat grid shows/hides column groups itself: re-fit after its buttons */
  document.addEventListener('click', function (e) { if (e.target.closest('.stat-groups button, [data-stat-group] button, .stat-controls button')) setTimeout(function () { window.ctPage(); }, 50); });
  window.addEventListener('load', function () { window.ctPage(); });
  document.addEventListener('click', function (e) {
    var b = e.target.closest('th.colnav button'); if (!b) return;
    var t = b.closest('table'); t.dataset.pg = Math.max(0, +(t.dataset.pg || 0) + +b.dataset.pg); page(t);
  });
  var rz; window.addEventListener('resize', function () { clearTimeout(rz); rz = setTimeout(function () { window.ctPage(); }, 150); });
  /* "All stats": .statfold sections hide their extra (.xc) columns until pressed; remembered per device */
  /* "All stats": .statfold sections hide their extra (.xc) columns; the state lives on <html> so sections swapped in
     live (live.js) inherit it; remembered per device */
  function foldInit() { var on = false; try { on = localStorage.getItem('ct-allstats') === '1'; } catch (e) {}
    document.documentElement.classList.toggle('allstats', on);
    [].forEach.call(document.querySelectorAll('[data-allstats]'), function (b) { b.setAttribute('aria-pressed', String(on)); }); }
  document.addEventListener('click', function (e) {
    var b = e.target.closest('[data-allstats]'); if (!b) return;
    var on = !document.documentElement.classList.contains('allstats'); try { localStorage.setItem('ct-allstats', on ? '1' : '0'); } catch (x) {}
    foldInit(); window.ctPage();
  });
  window.ctHeat = function (root) { [].forEach.call((root || document).querySelectorAll('table.heat'), function (t) { heat(t); page(t); }); };
  function init() { foldInit(); window.ctHeat(); window.ctPage(); }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init); else init();
})();
/* Summary / Raw data switch on the player page (2026-10-10): <html class="rawview">, remembered per device; the class is
   set early by an inline script in base.html so the page doesn't flash the other view */
(function () {
  function sync() { var raw = document.documentElement.classList.contains('rawview');
    [].forEach.call(document.querySelectorAll('[data-view]'), function (b) { b.setAttribute('aria-pressed', String((b.dataset.view === 'raw') === raw)); }); }
  document.addEventListener('click', function (e) {
    var b = e.target.closest('[data-view]'); if (!b) return;
    var raw = b.dataset.view === 'raw'; document.documentElement.classList.toggle('rawview', raw);
    try { localStorage.setItem('ct-view', raw ? 'raw' : 'summary'); } catch (x) {}
    sync(); if (window.ctPage) window.ctPage();
  });
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', sync); else sync();
})();

/* ⋯ header menu: on desktop it's always open and shown as plain buttons (Save · Share · Color); on phones it's a ⋯
   menu that opens toward the side with room and closes on an outside tap or Escape */
(function () {
  var wide = window.matchMedia('(min-width:701px)');
  function inline() { [].forEach.call(document.querySelectorAll('details.hub-more'), function (d) { d.open = wide.matches; }); }
  if (wide.addEventListener) wide.addEventListener('change', inline);
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', inline); else inline();
  document.addEventListener('toggle', function (e) {
    var d = e.target; if (!d.classList || !d.classList.contains('hub-more') || !d.open) return;
    d.classList.remove('edge-left'); var m = d.querySelector('.hub-menu'); if (m && m.getBoundingClientRect().left < 8) d.classList.add('edge-left');
  }, true);
  document.addEventListener('click', function (e) {
    if (wide.matches) return;
    [].forEach.call(document.querySelectorAll('details.hub-more[open]'), function (d) { if (!d.contains(e.target)) d.open = false; });
  });
  document.addEventListener('keydown', function (e) {
    if (e.key !== 'Escape' || wide.matches) return;
    [].forEach.call(document.querySelectorAll('details.hub-more[open]'), function (d) { d.open = false; d.querySelector('summary').focus(); });
  });
})();

/* "+ Add player" (player and squad headers): opening it puts the cursor in the gamertag box */
document.addEventListener('toggle', function (e) {
  var d = e.target; if (d.classList && d.classList.contains('addmem') && d.open) { var i = d.querySelector('input[name=gamertag]'); if (i) i.focus(); }
}, true);

/* Twitch popover: Cancel / outside tap / Escape close it */
(function () {
  function shut(except) { [].forEach.call(document.querySelectorAll('details.twpop[open]'), function (d) { if (d !== except) d.open = false; }); }
  document.addEventListener('click', function (e) {
    var c = e.target.closest('[data-twclose]'); if (c) { c.closest('details').open = false; return; }
    shut(e.target.closest('details.twpop'));
  });
  document.addEventListener('keydown', function (e) { if (e.key === 'Escape') shut(null); });
  document.addEventListener('toggle', function (e) {
    var d = e.target; if (d.classList && d.classList.contains('twpop') && d.open) { var i = d.querySelector('input[name=twitch]'); if (i && window.matchMedia('(min-width:701px)').matches) i.focus(); }
  }, true);
})();

/* live, two columns: the right column (live stats + chat) is exactly as tall as the left (video + session table), and a
   handle between stats and chat resizes both together — drag it, one grows and the other shrinks; double-click resets.
   The split is remembered per device. Phones/tablets: chat is a drawer / sits under the stats, so none of this runs.
   A right side ≥680px wide puts chat and stats side by side instead (.colside.side2). */
(function () {
  var chat = document.getElementById('twchat'), player = document.getElementById('player'); if (!chat || !player) return;
  var side = chat.parentElement, html = document.documentElement, split = null, KEY = 'ct-livesplit';
  try { var v = parseInt(localStorage.getItem(KEY), 10); if (v > 0) split = v; } catch (e) {}
  var bar = document.createElement('div'); bar.className = 'sidesplit'; bar.setAttribute('role', 'separator'); bar.setAttribute('aria-orientation', 'horizontal');
  bar.title = 'Drag to resize live stats and chat · double-click to reset'; bar.tabIndex = 0; bar.innerHTML = '<i></i>';
  function oa() { return side.querySelector('#onair'); }
  function on() { return window.innerWidth >= 1200 && !html.classList.contains('statsonly') && oa() && player.offsetHeight > 200; }
  function fit() {
    var o = oa();
    if (!on()) { side.classList.remove('side2'); chat.style.removeProperty('--chat-h'); if (o) { o.style.height = ''; o.classList.remove('split'); } bar.hidden = true; return; }
    var vs = document.getElementById('livevs'), total = player.offsetHeight + (vs && vs.offsetHeight ? vs.offsetHeight + 12 : 0);
    /* 2026-10-10: when the right side is wide enough for both (screens are wider than tall, so a height-limited video
       leaves width over), chat and live stats sit side by side, chat on the left, both the full height. No handle. */
    var two = side.clientWidth >= 680;
    side.classList.toggle('side2', two);
    if (two) { bar.hidden = true; o.style.height = total + 'px'; o.classList.add('split'); chat.style.setProperty('--chat-h', total + 'px'); return; }
    if (bar.parentElement !== side || bar.nextElementSibling !== chat) side.insertBefore(bar, chat);
    bar.hidden = false;
    o.style.height = ''; o.classList.remove('split'); var natural = o.scrollHeight, gaps = bar.offsetHeight;   /* measure without the size container */
    var h = Math.max(150, Math.min(split || natural, total - gaps - 220));
    o.style.height = h + 'px'; o.classList.add('split');
    chat.style.setProperty('--chat-h', Math.max(220, total - h - gaps) + 'px');
  }
  var drag = null;
  bar.addEventListener('pointerdown', function (e) { var o = oa(); if (!o) return; drag = { y: e.clientY, h: o.offsetHeight }; bar.setPointerCapture(e.pointerId); html.classList.add('dragging-split'); e.preventDefault(); });
  bar.addEventListener('pointermove', function (e) { if (!drag) return; split = Math.round(drag.h + e.clientY - drag.y); fit(); });
  function end() { if (!drag) return; drag = null; html.classList.remove('dragging-split'); try { localStorage.setItem(KEY, String(split)); } catch (e) {} }
  bar.addEventListener('pointerup', end); bar.addEventListener('pointercancel', end);
  bar.addEventListener('dblclick', function () { split = null; try { localStorage.removeItem(KEY); } catch (e) {} fit(); });
  bar.addEventListener('keydown', function (e) { if (e.key !== 'ArrowUp' && e.key !== 'ArrowDown') return; var o = oa(); if (!o) return; split = o.offsetHeight + (e.key === 'ArrowDown' ? 24 : -24); fit(); try { localStorage.setItem(KEY, String(split)); } catch (x) {} e.preventDefault(); });
  if (window.ResizeObserver) { var ro = new ResizeObserver(function () { requestAnimationFrame(fit); }); ro.observe(player); var vs0 = document.getElementById('livevs'); if (vs0) ro.observe(vs0); }
  new MutationObserver(function () { requestAnimationFrame(fit); }).observe(side, { childList: true });   /* live.js swaps #onair in place */
  if (player.parentElement) new MutationObserver(function () { requestAnimationFrame(fit); }).observe(player.parentElement, { childList: true });   /* ...and #livevs */
  window.addEventListener('resize', fit); fit(); window.ctSideFit = fit;
})();

/* live on a phone: the stats panel goes right under the video instead of at the end of the side column */
(function () {
  var oa = document.querySelector('.colside #onair'), player = document.getElementById('player'); if (!oa || !player) return;
  var home = oa.parentElement, mark = document.createComment('onair');
  home.insertBefore(mark, oa);
  var narrow = window.matchMedia('(max-width:1199px)');   /* the columns stack below 1200px */
  function place() { var cur = document.getElementById('onair'); if (!cur) return;
    if (narrow.matches) { if (cur.previousElementSibling !== player) player.after(cur); }
    else if (cur.parentElement !== home) mark.after(cur); }
  if (narrow.addEventListener) narrow.addEventListener('change', place); place();
  /* live.js swaps #onair in place on new games; keep it where it belongs */
  new MutationObserver(function () { if (narrow.matches) place(); }).observe(player.parentElement, { childList: true });
})();

/* live: the side column holds the live stats + chat, so clips move to a scrollable row under the video */
(function () {
  var player = document.querySelector('#player.is-live'); if (!player) return;
  var secs = document.querySelectorAll('.colside .clipsec, .colside .twclips'); if (!secs.length) return;
  var row = document.createElement('div'); row.className = 'liveclips';
  [].forEach.call(secs, function (s) { row.appendChild(s); });
  (document.getElementById('livevs') || player).after(row);   /* after the session table when there is one */
})();

/* live: the video comes first, so the game-type / Summary-Raw row (it only filters the stats) moves below it */
(function () {
  var ms = document.querySelector('#mediasec.live'), kinds = document.querySelector('nav.kinds'); if (!ms || !kinds) return;
  ms.after(kinds); kinds.classList.add('after-live');
})();

/* phones: live chat as a bottom sheet under the video (like the Twitch app). The Chat pill scrolls the video to the top
   and opens chat in the space below it, so you watch and chat at once. ×, Back or a swipe down closes it.
   Nothing may cover the video: Twitch pauses (and won't autoplay) a player that is overlapped at all — see style.css. */
(function () {
  var chat = document.getElementById('twchat'); if (!chat) return;
  var html = document.documentElement, ms = document.getElementById('mediasec');
  /* the chat iframe loads when it's first shown (on phones: when the sheet opens), not on page load */
  var cf = chat.querySelector('iframe[data-src]'), narrow = matchMedia('(max-width:700px)');
  function loadChat() { if (cf && !cf.getAttribute('src')) cf.src = cf.dataset.src; }
  if (!narrow.matches) loadChat(); else narrow.addEventListener('change', function (e) { if (!e.matches) { loadChat(); close(); } });
  /* squad with several members live: one chat tab per channel */
  chat.addEventListener('click', function (e) {
    var b = e.target.closest('[data-chatch]'); if (!b || !cf) return; var ch = b.dataset.chatch;
    cf.dataset.src = 'https://www.twitch.tv/embed/' + encodeURIComponent(ch) + '/chat?parent=' + encodeURIComponent(cf.dataset.host || location.hostname) + '&darkpopout';
    if (cf.getAttribute('src')) cf.src = cf.dataset.src; cf.title = 'Twitch chat for ' + ch;
    var po = chat.querySelector('.ph a.vod'); if (po) po.href = 'https://www.twitch.tv/popout/' + encodeURIComponent(ch) + '/chat?popout=';
    [].forEach.call(chat.querySelectorAll('[data-chatch]'), function (x) { var on = x === b; x.classList.toggle('on', on); x.setAttribute('aria-selected', String(on)); });
  });
  var tab = document.createElement('button'); tab.type = 'button'; tab.className = 'chattab'; tab.setAttribute('aria-label', 'Open live chat'); tab.innerHTML = '<i></i>Chat';
  var x = document.createElement('button'); x.type = 'button'; x.className = 'chatx'; x.setAttribute('aria-label', 'Close chat'); x.textContent = '×';
  var ph = chat.querySelector('.ph'); if (ph) ph.appendChild(x);
  document.body.append(tab);
  function fixedTop() { var t = document.querySelector('.top'); if (!t) return 0; var p = getComputedStyle(t).position; return (p === 'sticky' || p === 'fixed') ? t.getBoundingClientRect().bottom : 0; }
  function place() {
    var e = document.querySelector('#player .embed'); if (!e) return;
    window.scrollBy(0, e.getBoundingClientRect().top - fixedTop() - 6);
    html.style.setProperty('--sheet-top', Math.round(e.getBoundingClientRect().bottom + 8) + 'px');
  }
  function open(on) { if (on) { loadChat(); place(); } html.classList.toggle('chat-open', on); tab.setAttribute('aria-expanded', String(on));
    if (on) { try { history.pushState({ chat: 1 }, ''); } catch (e) {} } }
  function close() { if (!html.classList.contains('chat-open')) return; html.classList.remove('chat-open'); if (history.state && history.state.chat) history.back(); }
  tab.onclick = function () { open(true); }; x.onclick = close;
  window.addEventListener('popstate', function () { html.classList.remove('chat-open'); });
  window.addEventListener('resize', function () { if (html.classList.contains('chat-open')) place(); });
  document.addEventListener('keydown', function (e) { if (e.key === 'Escape') close(); });
  var sy = null; if (ph) { ph.addEventListener('touchstart', function (e) { sy = e.touches[0].clientY; }, { passive: true });
    ph.addEventListener('touchend', function (e) { if (sy != null && e.changedTouches[0].clientY - sy > 60) close(); sy = null; }, { passive: true }); }
  /* the Chat pill waits until the video is playing (or 10s): on small phones it can sit over the video, which stops
     Twitch's autoplay. No pill while the stream section is collapsed. */
  var ready = false, waited = 0, wv = setInterval(function () { waited += 500; var go = waited >= 10000;
    try { go = go || (window.__sp && !window.__sp.isPaused() && window.__sp.getCurrentTime() > 0); } catch (e) {}
    if (go) { clearInterval(wv); ready = true; sync(); } }, 500);
  function sync() { tab.hidden = !ready || !!(ms && !ms.open); if (ms && !ms.open) close(); clear(); }
  /* …and steps aside whenever it would touch the video (short phones, or scrolled so the video is at the bottom) */
  var emb = document.querySelector('#player .embed');
  function clear() { if (!emb || tab.hidden) return; var v = emb.getBoundingClientRect(), t = tab.getBoundingClientRect();
    tab.classList.toggle('off', v.bottom > t.top - 6 && v.top < t.bottom && v.right > t.left && v.left < t.right); }
  window.addEventListener('scroll', clear, { passive: true }); window.addEventListener('resize', clear);
  if (ms) ms.addEventListener('toggle', sync); sync();
})();

/* "Stats only" on the live panel: hide the stream + chat (the player isn't even created), the stats keep rolling in;
   remembered per device. "Show stream" brings it back. */
(function () {
  var html = document.documentElement;
  function sync() { var on = html.classList.contains('statsonly');
    [].forEach.call(document.querySelectorAll('[data-statsonly]'), function (b) { b.setAttribute('aria-pressed', String(on)); }); }
  document.addEventListener('click', function (e) {
    var b = e.target.closest('[data-statsonly]'); if (!b) return;
    var on = !html.classList.contains('statsonly');
    function apply() { html.classList.toggle('statsonly', on);
      try { localStorage.setItem('ct-statsonly', on ? '1' : '0'); } catch (x) {}
      if (on) { try { window.__sp && window.__sp.pause(); } catch (x) {} html.classList.remove('chat-open'); }
      else { if (window.CTInitSide) window.CTInitSide(); }
      window.dispatchEvent(new Event('resize')); if (window.ctSideFit) window.ctSideFit(); sync(); }
    /* the video blurs away and the live dashboard rises into its place (View Transitions; instant where unsupported) */
    var calm = window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches;
    /* back to the stream: start it once the animation is over (the transition layer covers the video, and Twitch ignores
       play() on a covered player), then keep nudging for a few seconds — the hidden player was reset and reloads */
    function resume() { if (on) return; var n = 0, iv = setInterval(function () { n++;
      try { var p = window.__sp; if (p && !p.isPaused() && p.getCurrentTime() > 0) { clearInterval(iv); return; } if (p) p.play(); } catch (x) {}
      if (n > 20 || html.classList.contains('statsonly')) clearInterval(iv); }, 500); }
    if (document.startViewTransition && !calm) { html.classList.add(on ? 'vt-to-stats' : 'vt-to-stream'); var vt = document.startViewTransition(apply);
      vt.finished.finally(function () { html.classList.remove('vt-to-stats', 'vt-to-stream'); resume(); }); }
    else { apply(); resume(); }
  });
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', sync); else sync();
  new MutationObserver(sync).observe(document.body, { childList: true, subtree: true });
})();

/* live session-vs-usual on phones: All stats / Key stats only (remembered; html.lvall, set early in base.html) */
document.addEventListener('click', function (e) {
  if (!e.target.closest('[data-lvall]')) return;
  var on = document.documentElement.classList.toggle('lvall');
  try { localStorage.setItem('ct-lvall', on ? '1' : '0'); } catch (x) {}
});

/* live: a muted stream gets paused while the tab is in the background (browser power saving / Twitch). Coming back to
   the tab starts every stream that was playing again — at the live edge — retrying while the player wakes up. */
(function () {
  if (!document.getElementById('player')) return;
  function all() { var l = window.__sp ? [window.__sp] : []; if (window.ctLiveMulti) l = l.concat(window.ctLiveMulti.players()); return l; }
  var was = [];
  document.addEventListener('visibilitychange', function () {
    if (document.hidden) { was = all().filter(function (p) { try { return !p.isPaused(); } catch (e) { return false; } }); return; }
    if (document.documentElement.classList.contains('statsonly')) { was = []; return; }
    var list = was; was = []; if (!list.length) return; var n = 0, iv = setInterval(function () { n++;
      var left = list.filter(function (p) { try { if (p.isPaused()) { p.play(); return true; } } catch (e) {} return false; });
      if (!left.length || n > 12 || document.hidden) clearInterval(iv); }, 500);
  });
})();
