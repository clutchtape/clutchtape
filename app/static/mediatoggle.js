/* "Stream & clips" fold (2026-10-08): the video/clips section sits collapsed above the stats and expands in place.
   - live channels start open; offline streams and clips start collapsed on every page load
   - a VOD click opens it; a saved VOD link selects the video for the next expansion
   - the collapsed section and the expanded bar stick under the site header; collapsing scrolls you straight back to the stats
   - the Twitch player is created only on expansion; collapsing pauses playback */
(function () {
  var d = document.getElementById('mediasec'); if (!d) return;
  var top = document.querySelector('.top');
  /* everything pinned at the top: the site header, plus the squad names row when it sticks (2026-10-11) */
  function hdr() { var h = top ? top.getBoundingClientRect().height : 0, hh = document.querySelector('.hub-head');
    document.documentElement.style.setProperty('--top-h', h + 'px');
    if (hh && getComputedStyle(hh).position === 'sticky') h += hh.getBoundingClientRect().height;
    document.documentElement.style.setProperty('--hdr', h + 'px'); return h; }
  hdr(); window.addEventListener('resize', hdr);
  /* live channels start open, and so does a link to a moment in a broadcast (?vod=…, 2026-10-11) */
  d.open = d.classList.contains('live') || new URLSearchParams(location.search).has('vod');
  function opened() {
    if(d.getBoundingClientRect().top<hdr()-1)d.scrollIntoView({block:'start',behavior:'instant'});
    if(window.CTInitSide)window.CTInitSide();
    window.dispatchEvent(new Event('resize'));
    setTimeout(function () { try { if (d.open && window.__sp && window.__sp.isPaused()) window.__sp.play(); } catch (e) {} }, 300);
  }
  /* 2026-10-11: opened from the bar -> the page glides so the bar sits under the header and the video (sized to the
     screen by watchframe.js) fills the view; collapsed from the bar -> back to the top of the page. Opening it any other
     way (a ▶ in the game log) keeps that path's own scrolling. */
  var byBar = false, calm = matchMedia('(prefers-reduced-motion: reduce)').matches;
  var bar = d.querySelector(':scope > summary');
  if (bar) bar.addEventListener('click', function () { byBar = true; setTimeout(function () { byBar = false; }, 400); });
  function glide(y) { window.scrollTo({ top: Math.max(0, y), behavior: calm ? 'auto' : 'smooth' }); }
  d.addEventListener('toggle', function () {
    if (d.open) { var fromBar = byBar; opened();
      if (fromBar) requestAnimationFrame(function () { requestAnimationFrame(function () { glide(d.getBoundingClientRect().top + scrollY - (top && /sticky|fixed/.test(getComputedStyle(top).position) ? hdr() : 0)); }); });
      return; }
    try { window.__sp && window.__sp.pause(); } catch (e) {}
    if (byBar) { glide(0); return; }
    /* collapsed some other way from further down the page: land on the stats right below it */
    var y = d.getBoundingClientRect().top + scrollY - hdr() - 6;
    if (scrollY > y + 4) window.scrollTo({ top: Math.max(0, y), behavior: 'instant' in window ? 'instant' : 'auto' });
  });
  if(d.open)opened();
  /* the game log's ▶ buttons play in this player: open it first (capture phase, before the page's own handler scrolls) */
  document.addEventListener('click', function (e) {
    if (e.target.closest('.gamelog a.vod, .gamelog td.cellvod, .gamelog tr.clickrow[data-vod]') && !d.open) d.open = true;
  }, true);
  window.ctOpenMedia = function () { d.open = true; opened(); };
})();
