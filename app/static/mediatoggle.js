/* "Stream & clips" fold (2026-10-08): the video/clips section sits collapsed above the stats and expands in place.
   - live channels start open; offline streams and clips start collapsed on every page load
   - a VOD click opens it; a saved VOD link selects the video for the next expansion
   - the collapsed section and the expanded bar stick under the site header; collapsing scrolls you straight back to the stats
   - the Twitch player is created only on expansion; collapsing pauses playback */
(function () {
  var d = document.getElementById('mediasec'); if (!d) return;
  var top = document.querySelector('.top');
  function hdr() { var h = top ? top.getBoundingClientRect().height : 0; document.documentElement.style.setProperty('--hdr', h + 'px'); return h; }
  hdr(); window.addEventListener('resize', hdr);
  d.open = d.classList.contains('live');
  function opened() {
    if(d.getBoundingClientRect().top<hdr()-1)d.scrollIntoView({block:'start',behavior:'instant'});
    if(window.CTInitSide)window.CTInitSide();
    window.dispatchEvent(new Event('resize'));
    setTimeout(function () { try { if (d.open && window.__sp && window.__sp.isPaused()) window.__sp.play(); } catch (e) {} }, 300);
  }
  d.addEventListener('toggle', function () {
    if (d.open) { opened(); return; }
    try { window.__sp && window.__sp.pause(); } catch (e) {}
    /* collapsed from the sticky bar further down the page: land on the stats right below it */
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
