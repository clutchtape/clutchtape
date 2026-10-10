/* The original table remains the single source for heat, sorting, links and replay data.
   On small screens its rows become labelled cards; desktop keeps the table. */
(function () {
  'use strict';
  let serial = 0;
  function enhance(table) {
    if (table.classList.contains('mobile-cards') || table.closest('#multi') || !table.tHead) return;
    /* 2026-10-09 : session totals are the most important numbers on a phone. They stay a real table, always
       shown, swiped sideways with the player column pinned (style: mobile.css "session totals"), never cards. */
    if (table.classList.contains('nightper')) return;
    const heads = Array.from(table.tHead.rows[0].cells).filter(h => !h.classList.contains('colnav'));
    if ((heads.length < 6 && !table.closest('.chart-table') && !table.classList.contains('metric-table')) || heads.some(h => h.colSpan > 1)) return;
    const labels = heads.map(h => h.textContent.trim()), game = labels[0] === '#', session = !!table.closest('.hub-sessions'), analysis = table.classList.contains('stat-grid');
    const previous=table.parentElement.previousElementSibling;
    if(previous?.matches('.swipehint,.mobile-sort'))previous.remove();
    table.classList.add('mobile-cards');
    if (game) table.classList.add('mobile-games');
    const identity = game ? 2 : 0;
    let primary = game ? [2, 3, 4] : session ? [0, labels.indexOf('Record'), labels.indexOf('Games'), labels.indexOf('Win %')] : [0];
    /* 2026-10-09: game cards lead with the numbers people scan for (solo: K/D/A, KDA, Dmg/min, SC%; squad: every
       player's K/D/A · KDA line) instead of hiding them behind "More stats" */
    if (game) labels.forEach((l, i) => { if (/^(K\/D\/A|KDA|Dmg\/min|SC%|Dmg\/KA|Dmg ±)$/i.test(l) || /K\/D\/A\s*·\s*KDA/i.test(l)) primary.push(i); });
    if (!game && !session) {
      ['Games', 'SC%', 'KDA', 'Dmg/min', 'WIN%', 'Win%','K/D'].forEach(label => {
        const i = labels.findIndex(l => l.toLowerCase() === label.toLowerCase());
        if (i > 0 && primary.length < 5 && !primary.includes(i)) primary.push(i);
      });
      for (let i=1; primary.length < Math.min(5,heads.length); i++) if(!primary.includes(i)) primary.push(i);
    }
    Array.from(table.tBodies).flatMap(b => Array.from(b.rows)).forEach(row => {
      const cells = Array.from(row.cells).filter(c => !c.classList.contains('colnav'));
      if (cells.length !== heads.length) return;
      row.classList.add('mobile-card');
      cells.forEach((cell, i) => {
        cell.dataset.mobileLabel = labels[i] || 'Watch';
        cell.classList.add('mobile-field');
        if (i === identity) cell.classList.add('mobile-identity');
        if (game && /K\/D\/A\s*·\s*KDA/i.test(labels[i])) {      // squad player line: label = gamertag only; hide players not in this game
          cell.classList.add('mobile-member'); cell.dataset.mobileLabel = labels[i].replace(/\s*K\/D\/A\s*·\s*KDA\s*$/i, '');
          if (cell.classList.contains('none') || cell.textContent.trim() === '—') cell.classList.add('mobile-absent');
        }
        const action = !labels[i] && !!cell.querySelector('a,button');
        if (action) cell.classList.add('mobile-actions');
        if (!analysis && !primary.includes(i) && !action) cell.classList.add('mobile-extra');
      });
      if (analysis) return; // Existing stat group buttons select these fields.
      const button = document.createElement('button');button.type = 'button';button.className = 'mobile-expand';button.textContent = 'More';button.setAttribute('aria-expanded','false');
      const id = 'mobile-card-' + (++serial);row.id ||= id;button.setAttribute('aria-controls',row.id);
      button.setAttribute('aria-label','More stats: '+cells[identity].textContent.trim());
      button.addEventListener('click',e => {e.stopPropagation();const open=row.classList.toggle('mobile-expanded');button.textContent=open?'Less':'More';button.setAttribute('aria-expanded',String(open));});
      cells[identity].append(button);
    });
    // Preserve table sorting on a phone without forcing users to find a column header.
    if (table.tBodies[0]?.rows.length > 1 && !analysis) {
      const controls=document.createElement('label');controls.className='mobile-sort';controls.append(document.createTextNode('Sort '));
      const select=document.createElement('select');select.setAttribute('aria-label','Sort '+(game?'games':session?'sessions':labels[0]||'players'));
      select.add(new Option('Original order',''));
      heads.forEach((h,i)=>{if(labels[i])select.add(new Option(labels[i],String(i)));});
      const original=Array.from(table.tBodies[0].rows);
      select.addEventListener('change',()=>{if(select.value==='')original.forEach(r=>table.tBodies[0].append(r));else{delete heads[+select.value].dataset.dir;heads[+select.value].click();}});
      controls.append(select);table.parentElement.before(controls);
    }
    if(table.classList.contains('nightper')){
      const wrap=table.parentElement,fold=document.createElement('details'),summary=document.createElement('summary');fold.className='mobile-totals';summary.textContent='Session player stats · '+table.tBodies[0].rows.length+' player'+(table.tBodies[0].rows.length===1?'':'s');fold.append(summary);wrap.before(fold);
      const sort=fold.previousElementSibling;if(sort?.matches('.mobile-sort'))fold.append(sort);fold.append(wrap);
      const mq=matchMedia('(max-width:700px)');fold.open=!mq.matches;mq.addEventListener('change',e=>{fold.open=!e.matches;});
    }
    window.ctPage?.(table.parentElement);
  }
  function scan(){document.querySelectorAll('main .tablewrap>table,main table.heat,main .chart-table>table').forEach(enhance);}
  scan();
  let pending=false;new MutationObserver(records=>{
    if(pending||!records.some(r=>Array.from(r.addedNodes).some(n=>n.nodeType===1&&(n.matches?.('table')||n.querySelector?.('table')))))return;
    pending=true;queueMicrotask(()=>{pending=false;scan();});
  }).observe(document.querySelector('main'),{childList:true,subtree:true});
})();
