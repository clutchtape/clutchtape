/* Live box detail views (2026-10-10). In the live panel (#onair), clicking a game (game chips, the timeline, "Last:")
   slides that game's own numbers into the box — tinted against the player's usual — with "← Live stats" to go back
   and "Full game stats ↗" to the match page. Clicking a best play (or ▶ in a game view) plays it inside the box from
   the stream's recording while the live stream keeps playing beside it; the live sound is muted while the clip
   plays and restored after. Nothing is drawn over the live video (Twitch pauses a covered player).
   - The game views are <template class="oa-gtpl"> in _onair.html; their data-k keys are dropped on the copy so
     pinning (customize.js) and live.js's stat matching only ever see the live numbers.
   - live.js replaces #onair after each finished game: an open game view is reopened on the new panel; while a clip
     plays the panel is held (data-hold) and live.js applies the update when the clip closes.
   - Ctrl/⌘/middle-click still opens the match page. */
(function () {
  'use strict';
  var calm = matchMedia('(prefers-reduced-motion: reduce)').matches, open = null, clipPlayer = null, liveMuted = null;

  function card(el) { return el && el.closest('#onair .oa-card'); }
  function anim(el, frames, ms) { if (calm || !el.animate) return { finished: Promise.resolve() }; return el.animate(frames, { duration: ms, easing: 'cubic-bezier(.2,.7,.2,1)' }); }

  function show(c, view, still) {
    var old = c.querySelector(':scope > .oa-view'); if (old) old.remove();
    view.classList.add('oa-view'); c.insertBefore(view, c.firstChild); c.classList.add('det-on');
    var oa = c.closest('#onair'); if (oa) oa.scrollTop = 0;
    if (matchMedia('(max-width:1199px)').matches) { var r = c.getBoundingClientRect(); if (r.top < 0 || r.top > innerHeight - 120) c.scrollIntoView({ block: 'start', behavior: calm ? 'auto' : 'smooth' }); }
    if (!still) { anim(view, [{ opacity: 0, transform: 'translateX(26px)' }, { opacity: 1, transform: 'none' }], 300);
      if (window.ctCountUp) [].forEach.call(view.querySelectorAll('.oa-nums b, .od-kda b'), window.ctCountUp); }
  }
  function back() {
    var oa = document.getElementById('onair'), c = oa && oa.querySelector('.oa-card.det-on'); stopClip();
    open = null; if (!c) return;
    var v = c.querySelector(':scope > .oa-view');
    var done = function () { if (v) v.remove(); c.classList.remove('det-on');
      [].forEach.call(c.children, function (k) { anim(k, [{ opacity: 0, transform: 'translateX(-14px)' }, { opacity: 1, transform: 'none' }], 260); }); };
    if (v) anim(v, [{ opacity: 1 }, { opacity: 0, transform: 'translateX(26px)' }], 180).finished.then(done, done); else done();
    release();
  }

  function gameView(c, gid, still) {
    var tpl = c.querySelector('template.oa-gtpl[data-g="' + gid + '"]'); if (!tpl) return false;
    var v = document.createElement('div'); v.appendChild(tpl.content.cloneNode(true));
    [].forEach.call(v.querySelectorAll('[data-k]'), function (e) { e.removeAttribute('data-k'); });
    stopClip(); show(c, v, still); open = { kind: 'game', g: gid, ci: [].indexOf.call(c.parentElement.children, c) }; return true;
  }

  function parse(url) { var m = String(url || '').match(/videos\/(\d+)\?t=([0-9hms]+)/); return m ? { id: m[1], t: m[2] } : null; }
  function clipView(c, url, label, gid, tclip) {
    var src = parse(url); if (!tclip && (!src || !window.Twitch || !Twitch.Player)) return false;
    stopClip();
    var v = document.createElement('div');
    v.innerHTML = '<div class="od-head"><button type="button" class="od-back" data-odback>← Live stats</button>' +
      (gid && c.querySelector('template.oa-gtpl[data-g="' + gid + '"]') ? '<button type="button" class="od-gamebtn" data-odgame="' + gid + '">Game stats</button>' : '') +
      '<a class="od-full" target="_blank" rel="noopener">Open on Twitch ↗</a></div><div class="od-cliplab"></div><div class="od-vid"><div id="odclip"></div></div>' +
      '<p class="od-note">The live stream keeps playing; its sound is off until you go back.</p>';
    v.querySelector('.od-full').href = tclip ? 'https://clips.twitch.tv/' + encodeURIComponent(tclip) : url;
    v.querySelector('.od-cliplab').textContent = '▶ ' + (label || 'Clip') + (tclip ? ' · viewer clip' : '');
    show(c, v, false); open = { kind: 'clip' };
    var oa = document.getElementById('onair'); if (oa) oa.setAttribute('data-hold', '');     /* live.js waits until we're done */
    try { if (window.__sp && liveMuted === null) { liveMuted = window.__sp.getMuted(); window.__sp.setMuted(true); } } catch (e) {}
    if (tclip) {   /* no recording of this stream: a clip a viewer made right after the play (Twitch clip embed) */
      var f = document.createElement('iframe'); f.src = 'https://clips.twitch.tv/embed?clip=' + encodeURIComponent(tclip) + '&parent=' + encodeURIComponent(location.hostname) + '&autoplay=true&muted=false';
      f.allow = 'autoplay; fullscreen'; f.allowFullscreen = true; f.title = 'Twitch clip'; v.querySelector('#odclip').appendChild(f);
      clipPlayer = { pause: function () { f.remove(); } };
    } else clipPlayer = new Twitch.Player('odclip', { video: 'v' + src.id, time: src.t, parent: [location.hostname], autoplay: true, muted: false, width: '100%', height: '100%' });
    return true;
  }
  function stopClip() {
    if (clipPlayer) { try { clipPlayer.pause(); } catch (e) {} clipPlayer = null; }
    if (liveMuted !== null) { try { window.__sp.setMuted(liveMuted); window.__sp.play(); } catch (e) {} liveMuted = null; }
  }
  function release() {
    var oa = document.getElementById('onair'); if (!oa || !oa.hasAttribute('data-hold')) return;
    oa.removeAttribute('data-hold');
    if (oa.__next) { var n = oa.__next; oa.__next = null; oa.replaceWith(n); }
  }

  document.addEventListener('click', function (e) {
    if (e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
    var t = e.target;
    if (t.closest('[data-odback]')) { e.preventDefault(); back(); return; }
    var c = card(t); if (!c) return;
    var gb = t.closest('[data-odgame]'); if (gb) { e.preventDefault(); gameView(c, gb.dataset.odgame); return; }
    var cl = t.closest('[data-clip]');
    if (cl && (cl.dataset.clip || cl.dataset.tclip)) { if (clipView(c, cl.dataset.clip, cl.dataset.cliplabel, cl.dataset.g, cl.dataset.tclip)) { e.preventDefault(); } return; }
    var g = t.closest('a[data-g]'); if (g && gameView(c, g.dataset.g)) e.preventDefault();
  });
  /* while live, ▶ on an auto clip or a game's recording (under the video) plays in the live box too, instead of
     switching the big player away from the live stream */
  document.addEventListener('click', function (e) {
    if (e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
    var a = e.target.closest('a.vod[href*="/videos/"]'); if (!a || a.closest('#twchat, #onair')) return;
    var c = document.querySelector('#onair .oa-card'); if (!c) return;
    var row = a.closest('.mo, tr, .oa-g'), lab = row && row.querySelector('b') ? row.querySelector('b').textContent.trim() : 'Clip';
    if (clipView(c, a.href, lab, null)) { e.preventDefault(); e.stopImmediatePropagation(); }
  }, true);
  document.addEventListener('keydown', function (e) { if (e.key === 'Escape' && open) back(); });

  /* live.js swapped in a new panel: put an open game view back (no animation) */
  new MutationObserver(function (ms) {
    if (!open || open.kind !== 'game') return;
    for (var i = 0; i < ms.length; i++) for (var j = 0; j < ms[i].addedNodes.length; j++) if (ms[i].addedNodes[j].id === 'onair') {
      var cs = document.querySelectorAll('#onair .oa-card'), c = cs[open.ci] || cs[0]; if (c && !gameView(c, open.g, true)) open = null; return; }
  }).observe(document.body, { childList: true, subtree: true });
  window.ctLiveDetail = { back: back };
})();
