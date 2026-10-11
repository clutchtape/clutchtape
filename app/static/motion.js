/* Motion across the site (2026-10-10). Small, one-time animations that explain a change; never on a loop, never drawn
   over a playing video (Twitch pauses a covered player), and none at all for prefers-reduced-motion.
   - Numbers count up the first time they are on screen (KPI tiles, CSR/streak badges, records, live tiles).
   - Summary <-> Raw crossfades, and a table's heat colours fade in when it first shows.
   - Chart lines draw left to right, their dots pop in after.
   - Sorting a table slides the rows to their new places (FLIP) instead of jumping.
   - Opening a game: the clicked row morphs into the match page header (cross-document view transition, names set
     here and in the head script of base.html; see style.css "page transitions").
   Refresh trigger: a new big-number element or chart class — add its selector below. */
(function () {
  'use strict';
  var reduce = window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches;
  if (reduce) return;
  var html = document.documentElement;

  /* ---- count-up -------------------------------------------------------------------------------------------- */
  var COUNT = '.hubkpi b, .hub-actions .pill, .ins b, .sb-tile b, .lvm-t b, .mh-score b, .pb-val';
  var NUM = /^([^\d\-+]*)([\-+]?)(\d[\d,]*)(\.\d+)?(.*)$/;
  function textNode(el) { for (var n = el.firstChild; n; n = n.nextSibling) if (n.nodeType === 3 && n.nodeValue.trim()) return n; return null; }
  function count(el) {
    var t = textNode(el); if (!t) return;
    var raw = t.nodeValue, m = raw.trim().match(NUM);
    if (!m || /\d/.test(m[5]) || /\d/.test(m[1])) return;                    /* "1-1", "3:20" etc: leave alone */
    var whole = m[3].replace(/,/g, ''), dec = m[4] ? m[4].length - 1 : 0, target = parseFloat(whole + (m[4] || ''));
    if (!isFinite(target) || target === 0) return;
    var comma = m[3].indexOf(',') >= 0, lead = raw.match(/^\s*/)[0], trail = raw.match(/\s*$/)[0];
    var dur = 700, t0 = null;
    function fmt(v) { var s = v.toFixed(dec); if (comma) s = s.replace(/\B(?=(\d{3})+(?!\d))/g, ','); return lead + m[1] + m[2] + s + m[5] + trail; }
    function step(now) { if (t0 === null) t0 = now; var k = Math.min(1, (now - t0) / dur), e = 1 - Math.pow(1 - k, 3);
      t.nodeValue = fmt(target * e); if (k < 1) requestAnimationFrame(step); else t.nodeValue = raw; }
    t.nodeValue = fmt(0); requestAnimationFrame(step);
  }

  window.ctCountUp = count;   /* livedetail.js: numbers in a newly shown game view */

  /* ---- chart lines draw in ----------------------------------------------------------------------------------- */
  var LINES = 'path.tr-line, svg path.race-line, .an-chart path[fill="none"], svg.growth path[fill="none"]';
  function draw(svg) {
    [].forEach.call(svg.querySelectorAll(LINES), function (p, i) {
      if (p.dataset.drawn) return; p.dataset.drawn = '1';
      p.setAttribute('pathLength', '1'); p.style.strokeDasharray = '1'; p.style.strokeDashoffset = '1';
      p.animate([{ strokeDashoffset: 1 }, { strokeDashoffset: 0 }], { duration: 900, delay: 80 * i, easing: 'cubic-bezier(.3,.7,.2,1)', fill: 'forwards' })
        .finished.then(function () { p.style.strokeDasharray = ''; p.style.strokeDashoffset = ''; p.removeAttribute('pathLength'); }).catch(function () {});
    });
    [].forEach.call(svg.querySelectorAll('circle.tr-dot'), function (c, i) {
      c.animate([{ opacity: 0, transform: 'scale(.2)' }, { opacity: 1, transform: 'none' }], { duration: 260, delay: 500 + Math.min(i * 12, 500), easing: 'ease-out', fill: 'backwards' });
    });
  }

  /* ---- heat fades in ----------------------------------------------------------------------------------------- */
  function heat(table) { if (table.dataset.heated) return; table.dataset.heated = '1'; table.classList.add('heat-in'); setTimeout(function () { table.classList.remove('heat-in'); }, 1400); }

  /* first time on screen */
  var seen = new WeakSet(), io = 'IntersectionObserver' in window ? new IntersectionObserver(function (es) {
    es.forEach(function (e) { if (!e.isIntersecting) return; var el = e.target; io.unobserve(el);
      if (el.matches('svg')) draw(el); else if (el.matches('table')) heat(el); else count(el); });
  }, { threshold: .2 }) : null;
  function scan(root) {
    if (!io) return;
    [].forEach.call(root.querySelectorAll(COUNT), function (el) { if (!seen.has(el) && !el.closest('#onair')) { seen.add(el); io.observe(el); } });
    [].forEach.call(root.querySelectorAll('svg'), function (s) { if (!seen.has(s) && s.querySelector(LINES)) { seen.add(s); io.observe(s); } });
    [].forEach.call(root.querySelectorAll('table.ptable, table.rawtable'), function (t) { if (!seen.has(t)) { seen.add(t); io.observe(t); } });
  }
  function ready() { scan(document);
    /* charts are drawn by script after load (analysis tab), and live.js swaps sections in: pick up new ones */
    new MutationObserver(function (ms) { for (var i = 0; i < ms.length; i++) if (ms[i].addedNodes.length) { scan(document); break; } })
      .observe(document.body, { childList: true, subtree: true });
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', ready); else ready();

  /* ---- sorting: rows slide to their new places ----------------------------------------------------------------- */
  document.addEventListener('click', function (e) {
    var th = e.target.closest('thead th'); if (!th) return;
    var tb = th.closest('table'); tb = tb && tb.tBodies[0]; if (!tb || tb.rows.length > 120) return;
    var before = new Map(); [].forEach.call(tb.rows, function (r) { before.set(r, r.getBoundingClientRect().top); });
    requestAnimationFrame(function () { requestAnimationFrame(function () {
      [].forEach.call(tb.rows, function (r) { var b = before.get(r); if (b == null) return; var dy = b - r.getBoundingClientRect().top;
        if (Math.abs(dy) > 1) r.animate([{ transform: 'translateY(' + dy + 'px)' }, { transform: 'none' }], { duration: 320, easing: 'cubic-bezier(.2,.7,.2,1)' }); });
    }); });
  }, true);

  /* ---- Summary <-> Raw: crossfade (heat.js toggles html.rawview on [data-view]) ------------------------------- */
  var passing = false;
  document.addEventListener('click', function (e) {
    var b = e.target.closest('[data-view]'); if (!b || passing || !document.startViewTransition) return;
    var want = b.dataset.view === 'raw'; if (want === html.classList.contains('rawview')) return;
    if (document.querySelector('#player .embed iframe') && document.querySelector('#mediasec[open]')) return;   /* never cover a playing video */
    e.stopImmediatePropagation(); e.preventDefault();
    html.classList.add('vt-view');
    var vt = document.startViewTransition(function () { passing = true; try { b.click(); } finally { passing = false; } });
    vt.finished.finally(function () { html.classList.remove('vt-view'); var t = document.querySelector(want ? 'table.rawtable' : 'table.ptable'); if (t) { t.dataset.heated = ''; heat(t); } });
  }, true);

  /* ---- page transitions: which way to slide (read by the head script in base.html on the next page) ----------- */
  document.addEventListener('click', function (e) {
    var a = e.target.closest('a[href]'); if (!a || e.defaultPrevented || a.target === '_blank') return; var d = '';
    if (a.closest('.hub-tabs, .kinds')) { var all = [].slice.call(a.parentElement.querySelectorAll('a')), cur = a.parentElement.querySelector('a.on');
      d = cur && all.indexOf(a) < all.indexOf(cur) ? 'back' : 'fwd'; }
    else if (a.rel === 'prev') d = 'back'; else if (a.rel === 'next') d = 'fwd';
    try { sessionStorage.setItem('ct-vt-dir', d); } catch (x) {}
  });

  /* ---- opening a game: name the clicked row so it morphs into the match header (style.css + base.html) -------- */
  document.addEventListener('click', function (e) {
    var a = e.target.closest('a[href^="/match/"]'); if (!a || e.defaultPrevented || e.metaKey || e.ctrlKey || e.shiftKey) return;
    var row = a.closest('tr, .gcard, .mo, .oa-g, li') || a;
    try { sessionStorage.setItem('ct-vt', 'match'); } catch (x) {}
    document.querySelectorAll('.vt-hero').forEach(function (x) { x.classList.remove('vt-hero'); });
    row.classList.add('vt-hero');
  });
})();
