/* If Twitch's embed library couldn't load (ad blockers / HTTPS-filtering proxies block it), fall back to plain
   player iframes with a minimal stand-in API so pages still show video instead of crashing. */
(function () {
  if (window.Twitch && window.Twitch.Player) return;
  function Player(id, o) {
    var el = typeof id === 'string' ? document.getElementById(id) : id, t0 = Date.now(), base = 0, self = this;
    function secs(t) { var m = String(t || '').match(/(?:(\d+)h)?(?:(\d+)m)?(?:(\d+)s)?/) || []; return (+m[1] || 0) * 3600 + (+m[2] || 0) * 60 + (+m[3] || 0); }
    function src(video, channel, at) {
      var q = 'parent=' + encodeURIComponent((o.parent || [location.hostname])[0]) + '&muted=true&autoplay=true';
      return 'https://player.twitch.tv/?' + (video ? 'video=' + (String(video)[0] === 'v' ? video : 'v' + video) + '&time=' + Math.floor(at / 3600) + 'h' + Math.floor(at % 3600 / 60) + 'm' + Math.floor(at % 60) + 's' : 'channel=' + channel) + '&' + q;
    }
    var f = document.createElement('iframe'); f.allow = 'autoplay; fullscreen'; f.style.cssText = 'width:100%;height:100%;border:0';
    if(window.ClutchMobileEmbed)window.ClutchMobileEmbed.protect(f);
    base = secs(o.time); f.src = src(o.video, o.channel, base); el.appendChild(f);
    this._v = o.video;
    this.getCurrentTime = function () { return base + (Date.now() - t0) / 1000; };
    this.seek = function (s) { base = s; t0 = Date.now(); f.src = src(self._v, o.channel, s); };
    this.setVideo = function (v, s) { self._v = v; self.seek(s || 0); };
    this.play = function () {}; this.pause = function () {}; this.isPaused = function () { return false; };
    this.setMuted = function () {}; this.getMuted = function () { return true; };
    this.addEventListener = function (ev, fn) { if (ev === 'ready') setTimeout(fn, 1500); };
  }
  Player.READY = 'ready';
  window.Twitch = { Player: Player, __shim: true };
})();
