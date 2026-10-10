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
    if (table.classList.contains('rawtable')) { swipe(wrap); rawStick(table); return; }   /* raw data: always scroll, frozen name/time */
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

/* ⋯ header menu: open it toward the side with room, close on an outside tap or Escape */
(function () {
  document.addEventListener('toggle', function (e) {
    var d = e.target; if (!d.classList || !d.classList.contains('hub-more') || !d.open) return;
    d.classList.remove('edge-left'); var m = d.querySelector('.hub-menu'); if (m && m.getBoundingClientRect().left < 8) d.classList.add('edge-left');
  }, true);
  document.addEventListener('click', function (e) {
    [].forEach.call(document.querySelectorAll('details.hub-more[open]'), function (d) { if (!d.contains(e.target)) d.open = false; });
  });
  document.addEventListener('keydown', function (e) {
    if (e.key !== 'Escape') return;
    [].forEach.call(document.querySelectorAll('details.hub-more[open]'), function (d) { d.open = false; d.querySelector('summary').focus(); });
  });
})();

/* "+ Add player" (player and squad headers): opening it puts the cursor in the gamertag box */
document.addEventListener('toggle', function (e) {
  var d = e.target; if (d.classList && d.classList.contains('addmem') && d.open) { var i = d.querySelector('input[name=gamertag]'); if (i) i.focus(); }
}, true);
