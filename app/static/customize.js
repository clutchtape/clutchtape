/* Customize the live view (2026-10-10; _customize.html). One setting object per device (localStorage ct-layout):
     chat: auto | beside | below | hidden   (desktop; auto = beside when the right side is wide enough, heat.js)
     side: left | right                     (chat's side when beside)
     vs:   true | false                     (the session-vs-usual table under the video)
     pins: ['kda', ...]                     (live box headline numbers, in order; [] = the default set)
   Layout = classes on <html> (lay-chat-*, lay-chat-right, lay-novs), set early by base.html so nothing jumps.
   Pins move the matching [data-k] stats into the headline row of each live card (and first among the phone tiles);
   live.js matches stats by data-k, so rolling numbers survive the move. Re-applied after every live.js swap. */
(function () {
  'use strict';
  var KEY = 'ct-layout', html = document.documentElement, DEF = { chat: 'auto', side: 'left', vs: true, pins: [] };
  function load() { try { var v = JSON.parse(localStorage.getItem(KEY) || '{}'); return Object.assign({}, DEF, v); } catch (e) { return Object.assign({}, DEF); } }
  function save(s) { try { localStorage.setItem(KEY, JSON.stringify(s)); } catch (e) {} }
  var s = load();

  function layout() {
    ['auto', 'beside', 'below', 'hidden'].forEach(function (c) { html.classList.toggle('lay-chat-' + c, s.chat === c && c !== 'auto'); });
    html.classList.toggle('lay-chat-right', s.side === 'right');
    html.classList.toggle('lay-novs', !s.vs);
    window.dispatchEvent(new Event('resize')); if (window.ctSideFit) window.ctSideFit();
  }

  var applying = false;
  function pins() {
    if (applying) return; applying = true;
    try {
      [].forEach.call(document.querySelectorAll('#onair .oa-card'), function (card) {
        var nums = card.querySelector('.oa-nums'), more = card.querySelector('.oa-more'); if (!nums) return;
        if (!nums.dataset.home) { nums.dataset.home = [].map.call(nums.querySelectorAll('[data-k]'), function (e) { return e.dataset.k; }).join(','); }
        var want = s.pins.length ? s.pins : nums.dataset.home.split(',');
        var other = card.querySelector('.oa-unpinned');
        var now = [].map.call(nums.querySelectorAll(':scope>[data-k]'), function (e) { return e.dataset.k; }).join(',');
        var have = want.filter(function (k) { return card.querySelector('[data-k="' + k + '"]'); }).join(',');
        if (now === have) return;                                         /* already in place: touch nothing */
        want.forEach(function (k) { var el = card.querySelector('[data-k="' + k + '"]'); if (el) nums.appendChild(el); });
        [].forEach.call(nums.querySelectorAll('[data-k]'), function (el) {
          if (want.indexOf(el.dataset.k) >= 0) return;
          if (!more) { el.remove(); return; }
          if (!other) { other = document.createElement('div'); other.className = 'oa-grp oa-unpinned'; other.innerHTML = '<span class="lab">Also</span>'; more.insertBefore(other, more.firstChild); }
          other.appendChild(el);
        });
        if (other && !other.querySelector('[data-k]')) other.remove();
      });
      var grid = document.querySelector('#livevs .lvm-grid');
      if (grid && grid.dataset.pins !== s.pins.join(',')) { grid.dataset.pins = s.pins.join(',');
        [].forEach.call(grid.querySelectorAll('.lvm-pin'), function (t) { t.classList.remove('lvm-pin'); });
        s.pins.slice().reverse().forEach(function (k) { var t = grid.querySelector('[data-k="' + k + '"]'); if (t) { t.classList.add('lvm-pin'); grid.insertBefore(t, grid.firstChild); } }); }
    } finally { applying = false; }
  }

  function form() {
    var f = document.querySelector('.laycard'); if (!f) return;
    function fill() {
      [].forEach.call(f.querySelectorAll('input[name=chat]'), function (i) { i.checked = i.value === s.chat; });
      [].forEach.call(f.querySelectorAll('input[name=side]'), function (i) { i.checked = i.value === s.side; });
      f.querySelector('input[name=vs]').checked = !!s.vs;
      [].forEach.call(f.querySelectorAll('input[name=pin]'), function (i) { i.checked = s.pins.indexOf(i.value) >= 0;
        var n = s.pins.indexOf(i.value); i.parentElement.dataset.order = n >= 0 ? n + 1 : ''; });
      var full = s.pins.length >= 6; [].forEach.call(f.querySelectorAll('input[name=pin]'), function (i) { i.disabled = full && !i.checked; });
    }
    f.addEventListener('change', function (e) {
      var i = e.target;
      if (i.name === 'chat') s.chat = i.value; else if (i.name === 'side') s.side = i.value; else if (i.name === 'vs') s.vs = i.checked;
      else if (i.name === 'pin') { s.pins = s.pins.filter(function (k) { return k !== i.value; }); if (i.checked) s.pins.push(i.value); }
      save(s); fill(); layout(); pins();
    });
    f.querySelector('[data-layreset]').onclick = function () { s = Object.assign({}, DEF, { pins: [] }); save(s); fill(); layout(); pins(); };
    f.querySelector('[data-layclose]').onclick = function () { f.closest('details').open = false; };
    document.addEventListener('click', function (e) { var d = f.closest('details'); if (d.open && !d.contains(e.target)) d.open = false; });
    document.addEventListener('keydown', function (e) { if (e.key === 'Escape') f.closest('details').open = false; });
    fill();
    /* the open card covers part of the video and Twitch pauses a covered player: start it again on close */
    var d = f.closest('details'), was = [];
    function players() { var l = window.__sp ? [window.__sp] : []; return window.ctLiveMulti ? l.concat(window.ctLiveMulti.players()) : l; }
    d.addEventListener('toggle', function () {
      if (d.open) { was = players().filter(function (p) { try { return !p.isPaused(); } catch (e) { return false; } }); return; }
      var list = was, n = 0; was = []; if (!list.length) return;
      var iv = setInterval(function () { n++; var left = list.filter(function (p) { try { if (p.isPaused()) { p.play(); return true; } } catch (e) {} return false; });
        if (!left.length || n > 12) clearInterval(iv); }, 400);
    });
  }

  function ready() {
    form(); layout(); pins();
    /* live.js replaces #onair / #livevs on every finished game: pin again */
    new MutationObserver(function (ms) {
      for (var i = 0; i < ms.length; i++) for (var j = 0; j < ms[i].addedNodes.length; j++) { var n = ms[i].addedNodes[j];
        if (n.id === 'onair' || n.id === 'livevs') { requestAnimationFrame(pins); return; } }
    }).observe(document.body, { childList: true, subtree: true });
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', ready); else ready();
})();
