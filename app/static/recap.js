(function () {
  'use strict';
  var root = document.getElementById('recap'), choose = document.getElementById('recap-match');
  if (!root || !choose) return;
  var q = function (id) { return document.getElementById('recap-' + id); };
  var names = new Set(JSON.parse(root.dataset.names).map(function (n) { return n.toLowerCase(); }));
  var pageSize = matchMedia('(max-width:900px)').matches ? 20 : 60;
  var defaultNames = new Set(names);
  var events = [], time = null, limit = pageSize, duration = 1, controller, range = null;
  var vods = JSON.parse(root.dataset.vm || '{}');
  function mine(name) { return names.has(String(name || '').toLowerCase()); }
  function involved(e) { return mine(e[2]) || (e[0] === 'k' || e[0] === 'd') && mine(e[3]); }
  function death(e) { return (e[0] === 'd' || e[0] === 'k') && mine(e[3]); }
  function clock(t) { t = Math.max(0, Math.floor(t)); return Math.floor(t / 60) + ':' + String(t % 60).padStart(2, '0'); }
  function label(e) {
    if (e[0] === 'k') return (e[2] || 'Unknown player') + (e[3] ? ' → ' + e[3] + ' (estimated)' : ' got a kill');
    if (e[0] === 'd') return (e[3] || 'Unknown player') + ' died';
    if (e[0] === 'm') return (e[2] || 'Unknown player') + ' · ' + (e[3] || 'Medal');
    return (e[2] || 'Unknown player') + ' · ' + (e[3] || 'Objective event');
  }
  function render() {
    var kind = q('kind').value;
    var filtered = events.filter(function (e) {
      return (!q('mine').checked || involved(e)) &&
        (kind === 'all' || (kind === 'd' ? (e[0] === 'd' || e[0] === 'k' && e[3]) && (!q('mine').checked || mine(e[3])) : e[0] === kind)) &&
        (range ? e[1] / 1000 >= range.start && e[1] / 1000 <= range.end : time === null || Math.abs(e[1] / 1000 - time) <= 15);
    });
    q('selection').textContent = range ? ' · ' + clock(range.start) + '–' + clock(range.end) : '';
    q('clock').textContent = range ? clock(range.start) + '–' + clock(range.end) : time === null ? 'All events' : clock(time) + ' ±15 seconds';
    q('events').replaceChildren();
    filtered.slice(0, limit).forEach(function (e) {
      var row = document.createElement('div'), stamp = document.createElement('button'), text = document.createElement('span');
      row.className = 'recap-event'; stamp.type = 'button'; stamp.className = 'secondary'; stamp.textContent = clock(e[1] / 1000);
      stamp.setAttribute('aria-label', 'Explore events at ' + stamp.textContent);
      stamp.addEventListener('click', function () { range = null; time = e[1] / 1000; q('time').value = time; limit = pageSize; render(); q('time').focus(); });
      text.textContent = label(e); row.append(stamp, text); q('events').appendChild(row);
    });
    if (!filtered.length) q('events').textContent = 'No events match this time and filter.';
    q('more').hidden = filtered.length <= limit;
    q('status').textContent = events.length + ' film events loaded · showing ' + Math.min(limit, filtered.length) + ' of ' + filtered.length + ' matching events.';
  }
  function draw() {
    var kills = 0, deaths = 0, medals = 0, net = 0, points = [[0,0]], max = 4;
    events.forEach(function (e) {
      var delta = 0;
      if (e[0] === 'k' && mine(e[2])) { kills++; delta++; }
      if (death(e)) { deaths++; delta--; }
      if (e[0] === 'm' && mine(e[2])) medals++;
      if (delta) { points.push([e[1]/1000,net]); net += delta; points.push([e[1]/1000,net]); max = Math.max(max,Math.abs(net)); }
    });
    points.push([duration,net]);
    q('summary').textContent = 'Selected players: ' + kills + ' kills · ' + deaths + ' deaths · ' + medals + ' medals';
    // SVG coordinates come only from validated finite numbers.
    var path = points.map(function (p,i) { return (i?'L':'M') + (Math.min(duration,p[0])/duration*1000).toFixed(1) + ' ' + (80-p[1]/max*65).toFixed(1); }).join(' ');
    q('chart').innerHTML = '<line x1="0" x2="1000" y1="80" y2="80" stroke="#75695b"/><path d="'+path+'" fill="none" stroke="#ff8a3d" stroke-width="3" vector-effect="non-scaling-stroke"/>';
  }
  function momentURL(start, end) {
    var u = new URL(location.href);
    ['vod','watch','s'].forEach(k => u.searchParams.delete(k));
    u.searchParams.set('match', choose.value); u.searchParams.set('at', Math.floor(start));
    if (end != null) u.searchParams.set('until', Math.ceil(end)); else u.searchParams.delete('until');
    if(q('player')&&q('player').value)u.searchParams.set('recap_player',q('player').value);else u.searchParams.delete('recap_player');
    u.hash = 'recap'; return u;
  }
  function highlightCards() {
    var stretches = window.ClutchHighlights(events, names, duration);
    q('highlights').replaceChildren();
    stretches.forEach(function(s, index) {
      var card = document.createElement('article'); card.className = 'recap-highlight';
      var heading = document.createElement('h4'); heading.textContent = (index + 1) + '. ' + s.title;
      var stamp = document.createElement('span'); stamp.className = 'highlight-time'; stamp.textContent = clock(s.start) + '–' + clock(s.end);
      var facts = document.createElement('p'); facts.textContent = s.kills + (s.kills===1?' kill · ':' kills · ') + s.deaths + (s.deaths===1?' death':' deaths') + (s.objectives ? ' · ' + s.objectives + (s.objectives===1?' objective event':' objective events') : '');
      var actions = document.createElement('div'); actions.className = 'highlight-actions';
      var link = document.createElement('a'); link.className = 'secondary'; link.href = momentURL(s.start, s.end); link.textContent = 'Review events';
      function select(e) {
        if (e && (e.metaKey || e.ctrlKey || e.shiftKey || e.button > 0)) return;
        if (e) {e.preventDefault();e.stopPropagation();}
        range = s; time = s.start; limit = pageSize; q('time').value = time;
        q('kind').value = 'all'; q('mine').checked = true;
        history.pushState(null, '', momentURL(s.start, s.end)); q('detail').open = true; render();
        q('detail').scrollIntoView({block:'center',behavior:'smooth'});
      }
      link.addEventListener('click', select); actions.append(link);
      var recording;
      Object.keys(vods).some(function(id) {
        if (!/^\d+$/.test(id)) return false;
        var match = vods[id].find(m => m[0] === choose.value && Number.isFinite(m[1]));
        if (match) {recording = 'https://www.twitch.tv/videos/' + id + '?t=' + Math.max(0, Math.floor(match[1] + s.start)) + 's'; return true;}
      });
      if (recording) { var watch = document.createElement('a'); watch.className = 'vod secondary'; watch.href = recording; watch.target = '_blank'; watch.rel = 'noopener'; watch.textContent = '▶ Watch'; actions.append(watch); }
      card.append(stamp, heading, facts, actions); q('highlights').append(card);
      var band = document.createElementNS('http://www.w3.org/2000/svg','rect');
      band.setAttribute('x',s.start/duration*1000); band.setAttribute('width',(s.end-s.start)/duration*1000); band.setAttribute('y','0'); band.setAttribute('height','160'); band.setAttribute('class','highlight-band');
      band.setAttribute('role','link'); band.setAttribute('tabindex','0'); band.setAttribute('aria-label',s.title+' · '+stamp.textContent+' · review events');
      band.addEventListener('click',select); band.addEventListener('keydown',function(e){if(e.key==='Enter'||e.key===' '){e.preventDefault();select();}});
      q('chart').append(band);
      var number=document.createElementNS('http://www.w3.org/2000/svg','text');number.setAttribute('x',(s.start+s.end)/2/duration*1000);number.setAttribute('y','20');number.setAttribute('text-anchor','middle');number.setAttribute('fill','#ffd09a');number.setAttribute('font-size','15');number.style.pointerEvents='none';number.textContent=index+1;q('chart').append(number);
    });
    if (!stretches.length) q('highlights').textContent = 'No standout stretches detected for these players in this film. You can still browse individual events below.';
  }
  async function load() {
    if (controller) controller.abort();
    var request = controller = new AbortController();
    q('content').hidden = true; q('retry').hidden = true; root.setAttribute('aria-busy','true'); q('status').textContent = 'Loading Theater events…';
    events = []; time = null; range = null; limit = pageSize; q('detail').open = false;
    try {
      var response = await fetch('/api/match/' + encodeURIComponent(choose.value) + '/events', {signal:request.signal});
      if (request !== controller) return;
      if (response.status === 404) { q('status').textContent = 'Film events are not available for this game yet. New films can take a few minutes; some games have no readable film.'; q('retry').hidden = false; return; }
      if (!response.ok) throw new Error('unavailable');
      var data = await response.json();
      if (request !== controller) return;
      events = (data.e || []).filter(function(e) { return Array.isArray(e) && ['k','d','m','o'].includes(e[0]) && Number.isFinite(e[1]) && e[1] >= 0; });
      if (!events.length) { q('status').textContent = 'This film has no readable events.'; q('retry').hidden = false; return; }
      duration = Math.max(1, Number(choose.selectedOptions[0].dataset.duration) || 0, ...events.map(function(e){return e[1]/1000;}));
      q('time').max = Math.ceil(duration); q('time').value = 0;
      q('content').hidden = false; var t=Number(new URLSearchParams(location.search).get('at'));if(new URLSearchParams(location.search).has('at')&&Number.isFinite(t)){time=Math.max(0,Math.min(duration,t));q('time').value=time;} var until=Number(new URLSearchParams(location.search).get('until'));if(time!==null){if(Number.isFinite(until)&&until>time)range={start:time,end:Math.min(duration,until)};q('detail').open=true;} draw(); highlightCards(); render();
    } catch (error) {
      if (error.name !== 'AbortError' && request === controller) { q('status').textContent = 'Could not load events. Your stats are still available. Try again.'; q('retry').hidden = false; }
    } finally { if (request === controller) root.removeAttribute('aria-busy'); }
  }
  choose.addEventListener('change',load); q('retry').addEventListener('click',load);
  q('time').addEventListener('input',function(){range=null;q('detail').open=true;time=Number(this.value);limit=pageSize;render();});
  q('all').addEventListener('click',function(){range=null;time=null;limit=pageSize;render();});
  ['kind','mine'].forEach(function(id){q(id).addEventListener('change',function(){limit=pageSize;render();});});
  q('more').addEventListener('click',function(){limit+=pageSize;render();});
  function selectPlayer(){
    names=q('player').value?new Set([q('player').value.toLowerCase()]):new Set(defaultNames);
    q('mine').checked=true;range=null;time=null;limit=pageSize;draw();highlightCards();render();
  }
  if(q('player'))q('player').addEventListener('change',selectPlayer);
  document.addEventListener('click',function(e){var b=e.target.closest('[data-recap-player]');if(!b||!q('player'))return;q('player').value=b.dataset.recapPlayer;selectPlayer();root.scrollIntoView({block:'start',behavior:'smooth'});});
  function state(){
    if(!choose.value)return null;
    var u=momentURL(time===null?0:time,range?range.end:null);
    return {url:u.pathname+u.search+u.hash,label:choose.selectedOptions[0].textContent+' · '+clock(time===null?0:time)};
  }

  window.ClutchRecap={state:state};
  var defaultMatch=choose.value;
  var initial=new URLSearchParams(location.search).get('match');
  if(initial&&[].some.call(choose.options,o=>o.value===initial))choose.value=initial;
  choose.addEventListener('change',function(){var u=new URL(location.href);u.searchParams.set('match',choose.value);u.searchParams.delete('at');u.searchParams.delete('until');history.replaceState(null,'',u);});
  document.addEventListener('click',function(e){var a=e.target.closest('a[href]');if(!a||e.metaKey||e.ctrlKey||e.shiftKey||e.button!==0||a.target)return;var u=new URL(a.href);if(u.origin!==location.origin||u.pathname!==location.pathname)return;var mid=u.searchParams.get('match');if(!mid||![].some.call(choose.options,o=>o.value===mid))return;e.preventDefault();history.pushState(null,'',u);choose.value=mid;load();root.scrollIntoView({behavior:matchMedia('(prefers-reduced-motion:reduce)').matches?'instant':'smooth',block:'start'});});
  addEventListener('popstate',function(){
    var params=new URLSearchParams(location.search),mid=params.get('match')||defaultMatch;
    if(![].some.call(choose.options,o=>o.value===mid))return;
    choose.value=mid;
    if(q('player')){
      var player=params.get('recap_player')||'';
      q('player').value=[].some.call(q('player').options,o=>o.value===player)?player:'';
      names=q('player').value?new Set([q('player').value.toLowerCase()]):new Set(defaultNames);
    }
    load();
  });
  var requestedPlayer=new URLSearchParams(location.search).get('recap_player');
  if(q('player')&&requestedPlayer&&Array.from(q('player').options).some(o=>o.value===requestedPlayer)){q('player').value=requestedPlayer;names=new Set([requestedPlayer.toLowerCase()]);}
  load();
})();
