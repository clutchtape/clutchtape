/* Archived broadcasts (app/archive.py): video ids >= 99,000,000,000 are MultiTwitch archive copies of Twitch VODs
   that Twitch has deleted. This wraps Twitch.Player so the same calls (seek / play / getCurrentTime / setVideo /
   isPaused / setMuted / READY ...) drive an HTML5 <video> for those ids and the real Twitch embed for everything
   else, switching per setVideo(). Load after the Twitch library and twitch-shim.js. */
(function () {
  var Base = window.Twitch && window.Twitch.Player;
  if (!Base || Base.__hybrid) return;
  var ID_BASE = 99000000000;
  var READY = Base.READY || 'ready';
  function num(v) { return parseInt(String(v == null ? '' : v).replace(/^v/, ''), 10) || 0; }
  function isArch(v) { return num(v) >= ID_BASE; }
  function secs(t) {
    if (typeof t === 'number') return t;
    var m = String(t || '').match(/(?:(\d+)h)?(?:(\d+)m)?(?:(\d+)s)?/) || [];
    return (+m[1] || 0) * 3600 + (+m[2] || 0) * 60 + (+m[3] || 0);
  }
  function fmt(s) { s = Math.max(0, Math.floor(s)); return Math.floor(s / 3600) + 'h' + Math.floor(s % 3600 / 60) + 'm' + (s % 60) + 's'; }

  function Hybrid(id, o) {
    o = o || {};
    var host = typeof id === 'string' ? document.getElementById(id) : id, self = this, ls = {}, inner = null, vid = null,
        kind = null, cur = null, pending = null, readyFired = false;
    function fire(ev) { (ls[ev] || []).forEach(function (fn) { try { fn(); } catch (e) {} }); }
    function showTwitch(on) { host.querySelectorAll('iframe').forEach(function (f) { f.style.display = on ? '' : 'none'; }); }
    function makeVideo() {
      vid = document.createElement('video');
      vid.playsInline = true; vid.controls = true; vid.preload = 'auto';
      vid.setAttribute('playsinline', ''); vid.className = 'archvid';
      vid.style.cssText = 'width:100%;height:100%;display:block;background:#000;object-fit:contain';
      vid.muted = !!o.muted;
      vid.addEventListener('loadedmetadata', function () {
        if (pending != null) { try { vid.currentTime = pending; } catch (e) {} pending = null; }
        if (o.autoplay !== false) vid.play().catch(function () { vid.muted = true; vid.play().catch(function () {}); });
        if (!readyFired) { readyFired = true; fire(READY); }
      });
      host.appendChild(vid);
    }
    function useArchive(v, at) {
      if (inner) { try { inner.pause(); } catch (e) {} showTwitch(false); }
      if (!vid) makeVideo();
      vid.style.display = 'block'; kind = 'a';
      var note=host.closest('#player')&&host.closest('#player').querySelector('.mobile-playback-note');if(note)note.remove();
      if (String(num(v)) !== String(num(cur)) || !vid.src) { pending = at; vid.src = '/archive/file/' + num(v); }
      else { try { vid.currentTime = at; } catch (e) { pending = at; } }
      cur = v;
    }
    function useTwitch(v, at) {
      if (vid) { try { vid.pause(); } catch (e) {} vid.style.display = 'none'; }
      kind = 't'; cur = v;
      if(window.ClutchMobileEmbed)window.ClutchMobileEmbed.note(host,v,o.channel);
      if (!inner) {
        var oo = {}; for (var k in o) oo[k] = o[k];
        if (v) { oo.video = v; oo.time = fmt(at || 0); delete oo.channel; }
        inner = new Base(host, oo);
        Object.keys(ls).forEach(function (ev) { ls[ev].forEach(function (fn) { inner.addEventListener(ev, fn); }); });
      } else { showTwitch(true); if (v) inner.setVideo(String(v)[0] === 'v' ? v : 'v' + v, at || 0); }
    }
    if (o.video && isArch(o.video)) useArchive(o.video, secs(o.time));
    else useTwitch(o.video || null, secs(o.time));

    var A = function () { return kind === 'a'; };
    this.addEventListener = function (ev, fn) {
      (ls[ev] = ls[ev] || []).push(fn);
      if (inner) inner.addEventListener(ev, fn);
      if (A() && ev === READY && readyFired) setTimeout(fn, 0);
    };
    this.getCurrentTime = function () { return A() ? (pending != null ? pending : vid.currentTime) : inner.getCurrentTime(); };
    this.seek = function (s) { if (A()) { if (vid.readyState >= 1) vid.currentTime = s; else pending = s; } else inner.seek(s); };
    this.play = function () { if (A()) { var p = vid.play(); if (p && p.catch) p.catch(function () {}); } else inner.play(); };
    this.pause = function () { if (A()) vid.pause(); else inner.pause(); };
    this.isPaused = function () { return A() ? vid.paused : inner.isPaused(); };
    this.setMuted = function (m) { if (vid) vid.muted = !!m; if (inner) try { inner.setMuted(m); } catch (e) {} };
    this.getMuted = function () { return A() ? vid.muted : inner.getMuted(); };
    this.setVolume = function (x) { if (vid) vid.volume = x; if (inner && inner.setVolume) try { inner.setVolume(x); } catch (e) {} };
    this.setQuality = function (q) { if (!A() && inner && inner.setQuality) try { inner.setQuality(q); } catch (e) {} };
    this.getQualities = function () { return !A() && inner && inner.getQualities ? inner.getQualities() : []; };
    this.getVideo = function () { return cur ? String(num(cur)) : ''; };
    this.setVideo = function (v, s) { if (isArch(v)) useArchive(v, s || 0); else useTwitch(v, s || 0); };
    this.isArchive = A;
  }
  for (var k in Base) if (Object.prototype.hasOwnProperty.call(Base, k)) Hybrid[k] = Base[k];
  // SDK event constants can be inherited/non-enumerable. A for-in + own check
  // silently loses them, leaving every listener except our READY fallback unwired.
  ['READY','PLAY','PLAYING','PAUSE','SEEK','PLAYBACK_BLOCKED','ENDED','ERROR','ONLINE','OFFLINE','CAPTIONS','VIDEO_READY','VIDEO_PLAY','VIDEO_PAUSE'].forEach(function(k){if(Base[k]!=null)Hybrid[k]=Base[k];});
  Hybrid.READY = READY;
  Hybrid.__hybrid = true;
  window.Twitch.Player = Hybrid;
})();
