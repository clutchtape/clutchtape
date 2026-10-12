/* Clutchtape event log: every event from the Theater film (kills, deaths, medals, objectives), synced to a playing VOD.
   Top: a clickable match timeline (like MultiTwitch) with markers for the squad's kills, deaths, medals and objectives.
   Below: a running log of the last 30s. Clicking a marker, the bar, or a log row seeks the video(s) there. */
(function () {
  var cache = {};
  function load(mid) {
    if (!cache[mid]) cache[mid] = fetch('/api/match/' + mid + '/events?v=2').then(function (r) { return r.ok ? r.json() : { e: [] }; })
      .then(function (j) { return {e:j.e||[],clips:j.clips||[]}; }).catch(function () { return {e:[],clips:[]}; });
    return cache[mid];
  }
  function esc(s) { return String(s == null ? '' : s).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); }
  function clock(ms) { ms = Math.max(0, ms); var s = Math.floor(ms / 1000); return Math.floor(s / 60) + ':' + ('0' + (s % 60)).slice(-2); }
  // Per-player 45-second windows, ranked by kill/death imbalance; no medal double-counting.
  function stretches(events, names) {
    var out=[];
    names.forEach(function(name){
      var lower=name.toLowerCase(), seen={}, combat=[];
      events.forEach(function(e){
        var k=e[0]==='k'&&String(e[2]).toLowerCase()===lower;
        var d=(e[0]==='k'||e[0]==='d')&&String(e[3]).toLowerCase()===lower;
        if(!k&&!d)return;
        var key=(k?'k':'d')+':'+e[1];if(seen[key])return;seen[key]=1;
        combat.push({t:e[1],k:k?1:0,d:d?1:0});
      });
      combat.sort(function(a,b){return a.t-b.t});
      var candidates=combat.map(function(e){var list=combat.filter(function(x){return x.t>=e.t&&x.t<=e.t+45000}),k=0,d=0;list.forEach(function(x){k+=x.k;d+=x.d});return {t:Math.max(0,e.t-3000),duration:(list[list.length-1].t-e.t+6000)/1000,player:name,k:k,d:d,net:k-d};}).filter(function(c){return Math.abs(c.net)>=3});
      var selected=[];candidates.sort(function(a,b){return Math.abs(b.net)-Math.abs(a.net)||a.t-b.t}).forEach(function(c){if(selected.filter(function(x){return (x.net>0)===(c.net>0)}).length>=2||selected.some(function(x){return c.t<x.t+x.duration*1000&&x.t<c.t+c.duration*1000}))return;c.type=c.net>0?'hot':'rough';c.label=(c.net>0?'Hot stretch':'Rough stretch')+' · '+c.k+' kills / '+c.d+' deaths';selected.push(c);});
      out=out.concat(selected);
    });return out.sort(function(a,b){return a.t-b.t});
  }
  var WINDOW = 30000, MAXN = 10, LEAD = 3000, DEFAULT_DELAY = 3, SMALL = function () { return innerWidth < 700; };

  function init(o) {
    var el = o.el; if (!el) return { update: function () {} }; if (o.bar) o.bar.innerHTML = '';
    var names = {}; (o.names || []).forEach(function (n) { names[String(n).toLowerCase()] = 1; });
    var vm = o.vm || {}, cur = null, evs = [], clips = [], lastMs=0, activeClip=null, popupTimer=null, currentVideo=null, delay=DEFAULT_DELAY, lastVideoTime=0, lastList = '', squadOnly = false;
    el.innerHTML = '<div class="elh"><b>Event log</b><span class="elsub"></span>' +
      '<label class="elf"><input type="checkbox"> squad only</label></div>' +
      '<div class="etl" hidden tabindex="0" role="slider" aria-label="Match timeline. Arrow keys seek five seconds." aria-valuemin="0"><svg class="etg" preserveAspectRatio="none"></svg><div class="etm"></div><div class="etp"></div><div class="etclips"></div><select class="et-picks" aria-label="Choose clip or stretch"><option value="">Clips &amp; stretches</option></select><div class="et-popup" hidden></div><button type="button" class="et-timing" aria-label="Adjust event timing">Timing +3s</button><div class="et-sync-popup" hidden><b>Match events to video</b><p>Markers before the action? Add time. Markers after it? Subtract time. Default: +3s. Your adjustment is saved for this broadcast on this device.</p><div><button type="button" data-delay="-1">−1s</button><output>+3s</output><button type="button" data-delay="1">+1s</button><button type="button" data-delay="reset">Default +3s</button><button type="button" class="et-sync-close" aria-label="Close timing controls">×</button></div></div></div>' +
      '<div class="elist"><p class="muted elidle">Event log appears when a filmed match is playing. Click any ▶.</p></div>';
    el.classList.add('idle');
    if (o.bar) { o.bar.appendChild(el.querySelector('.etl')); }
    var sub = el.querySelector('.elsub'), bar = (o.bar || el).querySelector('.etl'), marks = bar.querySelector('.etm'),
      head = bar.querySelector('.etp'), list = el.querySelector('.elist');
    var picks=bar.querySelector('.et-picks');if(o.picks){o.picks.appendChild(picks);bar.classList.add('separate-lanes');}
    var timing=bar.querySelector('.et-timing'),syncPopup=bar.querySelector('.et-sync-popup');
    function timingLabel(){var label=(delay>0?'+':'')+delay+'s';
      /* 2026-10-09: a small ⏱ icon instead of a "Timing +3s" button over the timeline; shows the offset only once changed */
      timing.textContent=delay===DEFAULT_DELAY?'⏱':'⏱ '+label;timing.title='Event timing '+label+' · adjust if markers don\'t line up with the stream';timing.setAttribute('aria-label','Adjust event timing ('+label+')');
      timing.classList.toggle('changed',delay!==DEFAULT_DELAY);syncPopup.querySelector('output').textContent=label;}
    var popupClip=null,popup=bar.querySelector('.et-popup'),clipMarks=bar.querySelector('.etclips');
    var cb = el.querySelector('.elf input'); if (SMALL()) { squadOnly = true; cb.checked = true; el.classList.add('compact'); }
    cb.addEventListener('change', function (e) { squadOnly = e.target.checked; lastList = ''; });

    function mine(n) { return n && names[String(n).toLowerCase()]; }
    function kind(e) {                     // colour class for an event, from the squad's point of view
      if (e[0] === 'k') return mine(e[2]) ? 'good' : mine(e[3]) ? 'bad' : 'n';
      if (e[0] === 'd') return mine(e[3]) ? 'bad' : 'n';
      if (e[0] === 'm') return mine(e[2]) ? 'medal' : 'n';
      return 'obj';
    }
    function who(n) { return '<b class="' + (mine(n) ? 'me' : 'them') + '">' + esc(n || '?') + '</b>'; }
    function text(e) {
      if (e[0] === 'k') return '<i>⚔</i> ' + who(e[2]) + (e[3] ? ' <span class="arr">→</span> ' + who(e[3]) : ' <span class="arr">got a kill</span>');
      if (e[0] === 'd') return '<i>☠</i> ' + who(e[3]) + ' <span class="arr">died</span>';
      if (e[0] === 'm') return '<i>★</i> ' + who(e[2]) + ' <span class="arr">· ' + esc(e[3]) + '</span>';
      return '<i>⚑</i> ' + who(e[2]) + ' <span class="arr">· ' + esc(e[3] || objName()) + '</span>';
    }
    function objName() {               // the film doesn't name objective events; say what they are for this mode
      var m = (cur && cur[3] || '').toLowerCase();
      return /oddball/.test(m) ? 'skull play' : /ctf|capture/.test(m) ? 'flag play' : /stronghold|zone/.test(m) ? 'zone play'
        : /king|hill/.test(m) ? 'hill play' : /extraction|vip|elimination/.test(m) ? 'mode play' : 'objective';
    }
    function plain(e) { return clock(e[1]) + '  ' + text(e).replace(/<[^>]+>/g, ''); }
    function seekFilm(ms) { if (cur && o.seek) o.seek(cur[1] + delay + Math.max(0, ms - LEAD) / 1000,currentVideo); }

    function drawMarkers() {
      /* Cluster events into bins (~1.5% of the bar) per lane, like MultiTwitch: one marker per bin, sized by count. */
      var dur = Math.max(60000, (cur[2] || 0) * 1000), bins = Math.max(20, Math.round(bar.clientWidth / 7)) || 60, B = {};
      evs.forEach(function (e, i) {
        var k = kind(e); if (k === 'n') return;
        var key = k + ':' + Math.min(bins - 1, Math.floor(e[1] / dur * bins));
        (B[key] = B[key] || { k: k, i: [] }).i.push(i);
      });
      var html = '';
      Object.keys(B).forEach(function (key) {
        var c = B[key], first = evs[c.i[0]], n = c.i.length;
        var tip = c.i.slice(0, 8).map(function (i) { return plain(evs[i]); }).join('\n') + (n > 8 ? '\n+' + (n - 8) + ' more' : '');
        html += '<button type="button" class="etk ' + c.k + (n > 1 ? ' multi' : '') + '" data-i="' + c.i[0] + '" style="left:' +
          (100 * first[1] / dur).toFixed(2) + '%;--n:' + Math.min(4, n) + '" title="' + esc(tip) + '"></button>';
      });
      marks.innerHTML = html; bar.hidden = false; bar.dataset.dur = dur;
      picks.disabled=!clips.length;clipMarks.innerHTML=clips.map(function(c,i){var left=Math.max(0,100*c.t/dur),width=Math.min(100-left,100*c.duration*1000/dur);return '<button type="button" class="et-clip '+(c.type||'clip')+'" data-clip="'+i+'" style="left:'+left+'%;width:'+Math.max(.5,width)+'%" aria-label="Watch '+esc(c.label)+' at '+clock(c.t)+'"><span>▶</span></button>'}).join('');
      picks.innerHTML='<option value="">'+(clips.length?'Choose a moment ('+clips.length+')':'No detected moments')+'</option>'+clips.map(function(c,i){return '<option value="'+i+'">'+clock(c.t)+' · '+esc(c.player)+' · '+esc(c.label)+'</option>'}).join('');
      bar.setAttribute('aria-valuemax',Math.round(dur/1000));
      bar.setAttribute('aria-description',clips.length+' moments. Gold ranges are clips; green hot stretches; red rough stretches; green and red lines show kills and deaths.');
      drawMomentum(dur);
    }
    /* Momentum line: the squad's running kills-minus-deaths across the match (green above the line = on top). */
    function drawMomentum(dur) {
      var g = bar.querySelector('.etg'); if (!g) return;
      var net = 0, pts = [[0, 0]], lo = 0, hi = 0;
      evs.forEach(function (e) {
        var k = kind(e), d = (e[0] === 'k' && k === 'good') ? 1 : ((e[0] === 'k' || e[0] === 'd') && k === 'bad') ? -1 : 0;
        if (!d) return; net += d; pts.push([e[1], net]); lo = Math.min(lo, net); hi = Math.max(hi, net);
      });
      pts.push([dur, net]);
      var W = 1000, H = 100, amp = Math.max(4, hi, -lo), y = function (v) { return H / 2 - v / amp * (H / 2 - 6); };
      var d = pts.map(function (p, i) { return (i ? 'L' : 'M') + (p[0] / dur * W).toFixed(1) + ' ' + y(p[1]).toFixed(1); }).join(' ');
      /* our kills as green lines up from the middle, our deaths as red lines down */
      var ticks = '';
      evs.forEach(function (e) {
        var k = kind(e); if (e[0] !== 'k' && e[0] !== 'd') return;
        var x = (e[1] / dur * W).toFixed(1);
        if (e[0] === 'k' && k === 'good') ticks += '<line x1="' + x + '" x2="' + x + '" y1="' + (H / 2) + '" y2="4" class="tk"/>';
        else if (k === 'bad') ticks += '<line x1="' + x + '" x2="' + x + '" y1="' + (H / 2) + '" y2="' + (H - 4) + '" class="td"/>';
      });
      g.setAttribute('viewBox', '0 0 ' + W + ' ' + H);
      g.innerHTML = '<defs><clipPath id="cu"><rect x="0" y="0" width="' + W + '" height="' + H / 2 + '"/></clipPath><clipPath id="cd"><rect x="0" y="' + H / 2 + '" width="' + W + '" height="' + H / 2 + '"/></clipPath></defs>' +
        '<path d="' + d + ' L' + W + ' ' + H / 2 + ' L0 ' + H / 2 + ' Z" class="up" clip-path="url(#cu)"/>' +
        '<path d="' + d + ' L' + W + ' ' + H / 2 + ' L0 ' + H / 2 + ' Z" class="dn" clip-path="url(#cd)"/>' +
        '<line x1="0" x2="' + W + '" y1="' + H / 2 + '" y2="' + H / 2 + '" class="mid"/>' + ticks + '<path d="' + d + '" class="ln"/>';
    }
    function touchTimeline(){return matchMedia('(pointer:coarse)').matches||innerWidth<900;}
    function showPopup(ms,clip,automatic){
      if(touchTimeline()){popup.hidden=true;clearTimeout(popupTimer);return;}
      popupClip=clip;
      var near=evs.filter(function(e){return Math.abs(e[1]-ms)<=2500&&(!squadOnly||kind(e)!=='n')}).slice(0,4);
      var heading=clip?'▶ '+esc(clip.label):clock(ms)+' · '+(near.length?'What happened':'Match time');
      popup.innerHTML='<button type="button" class="et-dismiss" aria-label="Dismiss event popup">×</button><b>'+heading+'</b>'+(clip?'<small>'+esc(clip.player)+' · '+clock(clip.t)+'–'+clock(clip.t+clip.duration*1000)+'</small>':'')+(near.length?'<div>'+near.map(text).join('<br>')+'</div>':'')+'<button type="button" class="et-replay" data-ms="'+(clip?clip.t:Math.max(0,ms-LEAD))+'">▶ '+(automatic?'Replay clip':clip?'Play stretch / clip':'Play with 3s lead-in')+'</button>';
      popup.hidden=false;clearTimeout(popupTimer);
      var marker=clip?clipMarks.querySelector('[data-clip="'+clips.indexOf(clip)+'"]'):null;
      var br=bar.getBoundingClientRect(),mr=marker&&marker.getBoundingClientRect();
      var center=mr?mr.left+mr.width/2-br.left:Math.max(0,Math.min(1,ms/(+bar.dataset.dur||1)))*br.width;
      popup.style.left=Math.max(0,Math.min(br.width-popup.offsetWidth,center-popup.offsetWidth/2))+'px';
      /* 2026-10-11: the pop-up opens below the timeline (never over the video): fit it to the room left on screen, and if
         there's hardly any it scrolls inside itself */
      var room=innerHeight-br.bottom-16;popup.style.maxHeight=Math.max(96,Math.min(240,room))+'px';   /* no page scroll: moving the page would slide the video under the sticky bar and pause it */
      /* 2026-10-12: no room below (the multistream drawers sit at the bottom of the screen): open it above the timeline
         instead — but only where that covers no video (a covered Twitch player pauses) */
      popup.classList.remove('et-up');
      var pr=popup.getBoundingClientRect();
      if(pr.bottom>innerHeight-6){popup.style.maxHeight='240px';var ph=Math.min(240,popup.scrollHeight),top=br.top-8-ph;
        var hit=top<6||[].some.call(document.querySelectorAll('iframe'),function(f){var r=f.getBoundingClientRect();return r.width&&r.height&&r.left<pr.right&&r.right>pr.left&&r.top<br.top-8&&r.bottom>top;});
        if(!hit)popup.classList.add('et-up');else popup.style.maxHeight=Math.max(60,room)+'px';}
      popupTimer=setTimeout(function(){popup.hidden=true},5000);
    }
    picks.addEventListener('change',function(){if(this.value==='')return;var c=clips[+this.value];if(o.onClip)o.onClip(c.player);seekFilm(c.t+LEAD);this.value='';});
    bar.addEventListener('click',function(e){
      if(e.target.closest('.et-picks'))return;
      if(e.target.closest('.et-timing')){syncPopup.hidden=!syncPopup.hidden;e.stopPropagation();return;}
      if(e.target.closest('.et-sync-close')){syncPopup.hidden=true;e.stopPropagation();return;}
      var adjust=e.target.closest('[data-delay]');if(adjust){delay=adjust.dataset.delay==='reset'?DEFAULT_DELAY:Math.max(-30,Math.min(30,delay+Number(adjust.dataset.delay)));try{localStorage.setItem('ct-event-delay:'+currentVideo,String(delay))}catch(x){}timingLabel();if(cur)render((lastVideoTime-cur[1]-delay)*1000);e.stopPropagation();return;}
      if(e.target.closest('.et-sync-popup'))return;
      if(e.target.closest('.et-dismiss')){popup.hidden=true;e.stopPropagation();return;}
      var replay=e.target.closest('.et-replay');if(replay){if(popupClip&&o.onClip)o.onClip(popupClip.player);seekFilm(+replay.dataset.ms+LEAD);popup.hidden=true;e.stopPropagation();return;}
      if(e.target.closest('.et-popup'))return;
      var clipButton=e.target.closest('[data-clip]');if(clipButton){var c=clips[+clipButton.dataset.clip];if(o.onClip)o.onClip(c.player);seekFilm(c.t+LEAD);popup.hidden=true;return;}
      var t=e.target.closest('.etk'),r=bar.getBoundingClientRect(),ms=t?evs[+t.dataset.i][1]:Math.max(0,Math.min(1,(e.clientX-r.left)/r.width))*(+bar.dataset.dur||0);
      showPopup(ms,null,false);seekFilm(ms+(touchTimeline()?LEAD:(t?0:LEAD)));
    });
    bar.addEventListener('keydown',function(e){if(e.target!==bar)return;if(e.key==='ArrowLeft'||e.key==='ArrowRight'){e.preventDefault();seekFilm(Math.max(0,lastMs+(e.key==='ArrowRight'?5000:-5000))+LEAD);}});
    bar.addEventListener('focusin',function(e){var b=e.target.closest('[data-clip]');if(b){var c=clips[+b.dataset.clip];showPopup(c.t,c,false);}});
    popup.addEventListener('mouseenter',function(){clearTimeout(popupTimer);});
    bar.addEventListener('mouseleave',function(){clearTimeout(popupTimer);popupTimer=setTimeout(function(){popup.hidden=true},200);});
    bar.addEventListener('keydown',function(e){if(e.key==='Escape')popup.hidden=true;});
    bar.addEventListener('mouseover',function(e){var b=e.target.closest('[data-clip]');if(b){var c=clips[+b.dataset.clip];showPopup(c.t,c,false);}});
    list.addEventListener('click', function (e) { var r = e.target.closest('.ev[data-t]'); if (r) {showPopup(+r.dataset.t,null,false);seekFilm(+r.dataset.t);} });
    list.addEventListener('keydown',function(e){if((e.key==='Enter'||e.key===' ')&&e.target.matches('.ev')){e.preventDefault();e.target.click();}});

    function render(ms) {
      lastMs=ms;bar.setAttribute('aria-valuenow',Math.max(0,Math.round(ms/1000)));bar.setAttribute('aria-valuetext',clock(ms));
      var currentClip=clips.find(function(c){return ms>=c.t&&ms<c.t+c.duration*1000});
      // Playback highlights the marker; descriptions appear only when requested by hover/focus/tap.
      activeClip=currentClip||null;
      clipMarks.querySelectorAll('[data-clip]').forEach(function(b){b.classList.toggle('now',clips[+b.dataset.clip]===activeClip)});
      var dur = +bar.dataset.dur || 1; head.style.left = Math.min(100, Math.max(0, 100 * ms / dur)).toFixed(2) + '%';
      sub.textContent = (cur[3] || '') + ' · ' + clock(ms);
      var L = evs.filter(function (e) { return e[1] <= ms && e[1] > ms - WINDOW && (!squadOnly || kind(e) !== 'n'); }).slice(SMALL() ? -12 : -MAXN).reverse();
      var html = L.length ? L.map(function (e) {
        var age = ms - e[1], op = Math.max(0.4, 1 - age / WINDOW * 0.6).toFixed(2);
        return '<div role="button" tabindex="0" class="ev ' + kind(e) + '" data-t="' + e[1] + '" style="opacity:' + op + '" title="Jump here"><time>' + clock(e[1]) + '</time>' + text(e) + '</div>';
      }).join('') : '<p class="muted">Quiet moment…</p>';
      if (html !== lastList) { list.innerHTML = html; lastList = html; }
    }
    function matchFor(v, t) {
      var L = vm[String(v)]; if (!L) return null;
      for (var i = 0; i < L.length; i++) { var m = L[i]; if (t >= m[1] - 60 && t <= m[1] + m[2] + 8) return m; }   /* VOD links start a few seconds before the film does */
      return null;
    }
    return {
      update: function (video, tSec) {
        lastVideoTime=tSec;
        if(String(video)!==currentVideo){currentVideo=String(video);delay=DEFAULT_DELAY;try{var raw=localStorage.getItem('ct-event-delay:'+currentVideo),saved=raw===null?DEFAULT_DELAY:Number(raw);if(Number.isFinite(saved))delay=Math.max(-30,Math.min(30,saved));}catch(e){}timingLabel();}
        var m = matchFor(video, tSec-delay);
        if (!m) {
          el.classList.add('idle');
          if (cur) { cur = null; evs = []; clips=[]; activeClip=null; popup.hidden=true;picks.disabled=true;picks.innerHTML='<option>No moments between matches</option>'; bar.hidden = true; sub.textContent = ''; lastList = '';
            list.innerHTML = '<p class="muted elidle">Between matches. Click any ▶ to jump to one.</p>'; }
          return;
        }
        el.classList.remove('idle');
        if (!cur || cur[0] !== m[0]) {
          cur = m; evs = []; clips=[]; activeClip=null; popup.hidden=true; clipMarks.innerHTML='';picks.disabled=true;picks.innerHTML='<option>Loading moments…</option>'; marks.innerHTML = ''; lastList = '';
          load(m[0]).then(function (data) { if (cur && cur[0] === m[0]) { evs = data.e; var seen={};clips=data.clips.filter(function(c){if(!mine(c.player)||!Number.isFinite(c.t)||!Number.isFinite(c.duration)||c.duration<=0)return false;var key=Math.floor(c.t/8000);if(seen[key])return false;seen[key]=true;return true;}).concat(o.onClip?stretches(evs,o.names||[]):[]).sort(function(a,b){return a.t-b.t});drawMarkers(); } });
        }
        cur=m; // A new angle can share this match but have a different broadcast offset.
        render((tSec - m[1] - delay) * 1000);
      }
    };
  }
  window.ClutchLog = { init: init, stretches: stretches };
})();
