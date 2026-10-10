/* Clip saver: records the moment in the VISITOR's browser (tab capture, cropped to the player) and downloads the file.
   Nothing touches the server. Needs desktop Chrome/Edge for crop (Firefox records the whole tab); phones can't capture.
   Use: ClutchSave.record({el, seek: fn(cb), seconds, name, unmute: fn, restore: fn}) */
(function () {
  var supported = !!(navigator.mediaDevices && navigator.mediaDevices.getDisplayMedia) && !/Mobi|Android|iPhone|iPad/i.test(navigator.userAgent);
  function mime() {
    var c = ['video/mp4;codecs=avc1.640028,mp4a.40.2', 'video/mp4', 'video/webm;codecs=vp9,opus', 'video/webm;codecs=vp8,opus', 'video/webm'];
    for (var i = 0; i < c.length; i++) if (window.MediaRecorder && MediaRecorder.isTypeSupported(c[i])) return c[i];
    return '';
  }
  var bar;
  function status(msg, kind) {
    if (!bar) { bar = document.createElement('div'); bar.className = 'recbar'; document.body.appendChild(bar); }
    bar.className = 'recbar on ' + (kind || ''); bar.innerHTML = msg;
    if (kind === 'done' || kind === 'err') setTimeout(function () { bar.className = 'recbar'; }, 4000);
  }
  async function record(o) {
    if (!supported) { status('Saving clips needs desktop Chrome or Edge.', 'err'); return; }
    var stream;
    try {
      stream = await navigator.mediaDevices.getDisplayMedia({ video: { frameRate: 60 }, audio: true,
        preferCurrentTab: true, selfBrowserSurface: 'include', surfaceSwitching: 'exclude', systemAudio: 'include' });
    } catch (e) { status(e && e.name === 'NotAllowedError' ? 'Recording cancelled.' : 'Couldn\'t start recording (' + (e && e.name) + ').', 'err'); console.warn('clipsaver', e); return; }
    var track = stream.getVideoTracks()[0];
    try { if (window.CropTarget && track.cropTo && o.el) await track.cropTo(await CropTarget.fromElement(o.el)); } catch (e) {}
    status('● Getting the moment ready…', 'rec');
    if (o.unmute) try { o.unmute(); } catch (e) {}
    await new Promise(function (res) { o.seek(res); });
    var type = mime(), chunks = [], rec = new MediaRecorder(stream, type ? { mimeType: type, videoBitsPerSecond: 8e6 } : undefined);
    rec.ondataavailable = function (e) { if (e.data && e.data.size) chunks.push(e.data); };
    var left = Math.round(o.seconds), tick;
    rec.onstop = function () {
      clearInterval(tick); stream.getTracks().forEach(function (t) { t.stop(); });
      if (o.restore) try { o.restore(); } catch (e) {}
      var ext = (type || 'video/webm').indexOf('mp4') >= 0 ? 'mp4' : 'webm';
      var blob = new Blob(chunks, { type: (type || 'video/webm').split(';')[0] }), a = document.createElement('a');
      a.href = URL.createObjectURL(blob); a.download = (o.name || 'clutchtape-clip').replace(/[^\w.-]+/g, '_') + '.' + ext;
      document.body.appendChild(a); a.click(); setTimeout(function () { URL.revokeObjectURL(a.href); a.remove(); }, 5000);
      status('✓ Saved ' + a.download + ' (' + (blob.size / 1e6).toFixed(1) + ' MB) to your downloads', 'done');
    };
    track.addEventListener('ended', function () { if (rec.state === 'recording') rec.stop(); });   // user hit "Stop sharing"
    rec.start(1000);
    status('● Recording <b>' + left + 's</b> <button type="button" class="recstop">Stop</button>', 'rec');
    bar.querySelector('.recstop').onclick = function () { if (rec.state === 'recording') rec.stop(); };
    tick = setInterval(function () {
      left--; var b = bar.querySelector('b'); if (b) b.textContent = left + 's';
      if (left <= 0 && rec.state === 'recording') rec.stop();
    }, 1000);
  }
  window.ClutchSave = { supported: supported, record: record };
})();
