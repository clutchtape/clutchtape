/* Home for returning visitors (2026-10-11 compact rewrite): saved/followed players & squads as one row of chips (Edit
   reveals ✕ to remove a saved one — the separate "Saved" list is gone), live follows, "Worth watching" as three
   one-line rows (More for the rest), and recent alerts only when there are any. Private to this browser. */
(() => {
  'use strict';
  const q = id => document.getElementById(id);
  const el = (tag, text, cls) => { const n = document.createElement(tag); if (text !== undefined) n.textContent = text; if (cls) n.className = cls; return n; };
  const KEY = 'clutchtape.saved.v1';
  let feed = null, loading = false, expanded = false, editing = false;
  const home = document.querySelector('.personal-home');
  function url(value) { const u = new URL(value, location.origin); return u.origin === location.origin ? u.pathname + u.search : '/'; }
  function savedList() { try { const a = JSON.parse(localStorage.getItem(KEY) || '[]'); return Array.isArray(a) ? a.filter(x => x && typeof x.url === 'string').slice(0, 20) : []; } catch { return []; } }
  function saved() { return savedList().map(x => url(x.url)); }
  function unsave(path) {
    try { localStorage.setItem(KEY, JSON.stringify(savedList().filter(x => url(x.url) !== path))); } catch {}
    window.dispatchEvent(new Event('ct-saved-changed'));
  }
  function chip(c) {
    const wrap = el('span', undefined, 'personal-chipwrap');
    const a = el('a', undefined, 'personal-chip'); a.href = url(c.url);
    a.append(el('strong', c.label));
    a.append(el('small', c.latest ? c.latest.record + ' · ' + c.latest.games + (c.latest.games === 1 ? ' game' : ' games') : 'no shared games yet'));
    wrap.append(a);
    if (saved().includes(url(c.url))) {
      const x = el('button', '✕', 'personal-x'); x.type = 'button'; x.title = 'Remove from this device'; x.setAttribute('aria-label', 'Remove ' + c.label);
      x.onclick = () => unsave(url(c.url)); wrap.append(x);
    }
    return wrap;
  }
  function pickRow(s) {
    const a = el('a', undefined, 'personal-pick'); a.href = url(s.url);
    a.dataset.heat = s.score >= 25 ? 'high' : s.score >= 12 ? 'medium' : 'low';
    a.append(el('strong', s.label));
    a.append(el('span', s.record + ' · ' + new Date(s.at * 1000).toLocaleDateString([], { month: 'short', day: 'numeric' })));
    a.append(el('em', (s.reasons || []).slice(0, 3).join(' · ')));
    a.title = (s.reasons || []).join('\n');
    return a;
  }
  function picks() {
    const box = q('home-picks'); box.replaceChildren();
    const rows = [...(feed?.picks || [])];
    if (q('home-sort').value === 'recent') rows.sort((a, b) => b.at - a.at);
    q('home-more').hidden = expanded || rows.length <= 3;
    (expanded ? rows : rows.slice(0, 3)).forEach(s => box.append(pickRow(s)));
    q('home-picks-section').hidden = !rows.length;
  }
  function inbox(state) {
    home.dataset.hasAlerts = String(state.events.length > 0);
    const box = q('home-inbox'); box.replaceChildren();
    let read = 0; try { read = Number(localStorage.getItem('ct-alert-read') || 0); } catch {}
    const unread = state.events.filter(e => e.id > read).length;
    q('home-unread').textContent = unread ? '· ' + unread + ' unread' : '';
    state.events.slice(0, 3).forEach(e => {
      const a = el('a', undefined, 'personal-pick' + (e.id > read ? ' unread' : '')); a.href = url(e.url);
      a.append(el('strong', e.title)); a.append(el('span', new Date(e.at * 1000).toLocaleString([], { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' }))); a.append(el('em', e.body || ''));
      box.append(a);
    });
  }
  async function load() {
    if (loading) return; loading = true; q('home-retry').hidden = true;
    const controller = new AbortController(), timer = setTimeout(() => controller.abort(), 45000);
    try {
      const r = await fetch('/api/alerts/home', { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': JSON.parse(q('app-csrf').textContent) }, body: JSON.stringify({ targets: saved() }), signal: controller.signal });
      if (!r.ok) throw Error();
      feed = await r.json();
      home.dataset.empty = String(!feed.cards.length);
      const box = q('home-cards'); box.replaceChildren(); feed.cards.forEach(c => box.append(chip(c)));
      q('home-edit').hidden = !feed.cards.some(c => saved().includes(url(c.url)));
      const live = q('home-live'); live.replaceChildren();
      feed.live.forEach(p => { const a = el('a', undefined, 'personal-chip live'); a.href = url(p.url); a.append(el('strong', '● ' + p.name)); a.append(el('small', p.title || 'live now')); live.append(a); });
      q('home-live-section').hidden = !feed.live.length;
      picks();
      q('home-status').textContent = feed.unavailable ? 'Some saved links are unavailable.' : '';
    } catch {
      q('home-status').textContent = 'Could not update your home.'; q('home-retry').hidden = false;
    } finally { clearTimeout(timer); loading = false; }
  }
  home.dataset.empty = String(!saved().length);   /* show the section straight away for returning visitors; hidden for new ones */
  q('home-edit').onclick = () => { editing = !editing; home.classList.toggle('editing', editing); q('home-edit').textContent = editing ? 'Done' : 'Edit'; };
  q('home-sort').onchange = () => { expanded = false; picks(); };
  q('home-more').onclick = () => { expanded = true; picks(); };
  q('home-retry').onclick = load;
  let followKey = '';
  window.addEventListener('ct-alert-state', e => { inbox(e.detail); const next = JSON.stringify(e.detail.follows.map(f => f.url)); if (followKey && next !== followKey) load(); followKey = next; });
  window.addEventListener('ct-saved-changed', load); window.addEventListener('storage', load);
  load(); setInterval(() => { if (!document.hidden) load(); }, 60000);
})();
