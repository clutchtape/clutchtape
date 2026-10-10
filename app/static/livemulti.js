/* Squad live multistream (2026-10-10). With 2+ squad members streaming (#lmbar, web.squad onair.streams) every live
   channel plays at once: side by side on wide screens, stacked on phones. Stream 0 is the page's main player
   (#tplayer, created by the squad page script); the others get their own Twitch players once it exists.
   - All start muted (Twitch only autoplays muted); the 🔊 buttons pick whose sound you hear.
   - "One stream" shows only the picked one (others pause); remembered per device (localStorage ct-livemulti).
   - Clicking a ▶ to a past match (squad go()) calls ctLiveMulti.solo() so the replay gets the whole box.
   - Nothing is drawn over the videos (Twitch pauses a covered player) and each stays ≥300px wide (its autoplay minimum).
   watchframe.js sizes the box from embed.dataset.ar (height/width of the whole grid). */
(function () {
  var bar = document.getElementById('lmbar'), player = document.getElementById('player'); if (!bar || !player) return;
  var streams; try { streams = JSON.parse(bar.dataset.streams || '[]'); } catch (e) { return; }
  if (streams.length < 2) return;
  var embed = player.querySelector('.embed'), main = document.getElementById('tplayer'); if (!embed || !main) return;
  var html = document.documentElement, wide = matchMedia('(min-width:1200px)');
  var mode = 'all', aud = 0, players = [], made = false;
  try { if (localStorage.getItem('ct-livemulti') === 'one') mode = 'one'; } catch (e) {}

  var grid = document.createElement('div'); grid.className = 'lm-grid';
  var cells = streams.map(function (s, i) {
    var c = document.createElement('div'); c.className = 'lm-cell'; c.dataset.i = i;
    if (i === 0) c.appendChild(main); else { var d = document.createElement('div'); d.id = 'lmp' + i; c.appendChild(d); }
    grid.appendChild(c); return c;
  });
  embed.appendChild(grid); embed.classList.add('lm'); player.classList.add('lm-on');

  function shown() { return mode === 'all' ? cells.map(function (_, i) { return i; }) : [aud]; }
  var lastShape = '';
  function shape() {
    var vis = shown(), n = vis.length, w = embed.clientWidth || player.clientWidth;
    var c = n === 1 ? 1 : (w >= 800 || wide.matches ? 2 : 1), r = Math.ceil(n / c);   /* 2-up only when each video gets ~400px */
    cells.forEach(function (cell, i) { cell.hidden = vis.indexOf(i) < 0; });
    embed.style.setProperty('--lmc', c); embed.style.setProperty('--lmr', r);
    embed.dataset.ar = String((r * 9) / (c * 16));
    if (wide.matches) embed.style.removeProperty('aspect-ratio');            /* desktop: watchframe sizes the box */
    else embed.style.setProperty('aspect-ratio', (c * 16) + '/' + (r * 9), 'important');
    bar.classList.toggle('one', mode === 'one');
    var key = c + 'x' + r; if (key !== lastShape) { lastShape = key; window.dispatchEvent(new Event('resize')); }
  }
  function sound() {
    players.forEach(function (p, i) { if (!p) return; try { p.setMuted(i !== aud); if (i === aud) p.setVolume(Math.max(.5, p.getVolume() || 0)); } catch (e) {} });
    [].forEach.call(bar.querySelectorAll('.lm-aud'), function (b) { var on = +b.dataset.i === aud; b.classList.toggle('on', on); b.setAttribute('aria-pressed', String(on)); });
  }
  function playing() {
    var vis = shown();
    players.forEach(function (p, i) { if (!p || i === 0) return; try { if (vis.indexOf(i) < 0) p.pause(); else p.play(); } catch (e) {} });
  }
  function make() {
    if (made || html.classList.contains('statsonly') || !window.__sp) return;
    made = true; players[0] = window.__sp;
    streams.forEach(function (s, i) {
      if (!i || !s.channel) return;
      players[i] = new Twitch.Player('lmp' + i, { parent: [location.hostname], channel: s.channel, autoplay: true, muted: true, width: '100%', height: '100%' });
      if (mode === 'one' && i !== aud) players[i].addEventListener(Twitch.Player.PLAYING, function once() { if (mode === 'one' && i !== aud) try { players[i].pause(); } catch (e) {} });
    });
  }
  /* the main player appears when the stream section opens (squad page script); add the others right after */
  var wait = setInterval(function () { if (window.__sp) { clearInterval(wait); make(); } }, 300);
  setTimeout(function () { clearInterval(wait); }, 120000);

  bar.addEventListener('click', function (e) {
    var a = e.target.closest('.lm-aud'), m = e.target.closest('[data-lmmode]');
    if (a) { aud = +a.dataset.i; if (mode === 'one') { shape(); playing(); } sound(); }
    if (m) { mode = mode === 'all' ? 'one' : 'all'; try { localStorage.setItem('ct-livemulti', mode); } catch (x) {} shape(); playing(); sound(); }
  });
  /* stats-only: no videos at all, so stop the extra players too */
  new MutationObserver(function () { if (html.classList.contains('statsonly')) players.forEach(function (p, i) { if (p && i) try { p.pause(); } catch (e) {} }); else { make(); playing(); } })
    .observe(html, { attributes: true, attributeFilter: ['class'] });
  window.addEventListener('resize', function () { if (!wide.matches || embed.style.aspectRatio) shape(); });
  wide.addEventListener('change', shape);
  window.ctLiveMulti = { solo: function (i) { aud = i || 0; mode = 'one'; shape(); playing(); sound(); } };
  shape();
})();
