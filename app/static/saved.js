/* Explicit opt-in, device-local bookmarks. Never save lookup input automatically. */
(function () {
  'use strict';
  var key = 'clutchtape.saved.v1', button = document.querySelector('[data-save-profile]');
  var panel = document.getElementById('saved-profiles'), list = document.getElementById('saved-list');
  function valid(entry) {
    if (!entry || typeof entry.label !== 'string' || typeof entry.url !== 'string') return false;
    try { var u = new URL(entry.url, location.origin); return u.origin === location.origin && /^\/(p|squad|live|sq)\/[a-z0-9,-]+$/.test(u.pathname); } catch (_) { return false; }
  }
  function read() {
    var values = JSON.parse(localStorage.getItem(key) || '[]');
    return Array.isArray(values) ? values.filter(valid).slice(0, 20) : [];
  }
  function current() {
    var u = new URL(location.href);
    // Save the player or squad, not a stale selected night, clip, or comparison.
    u.search = ''; u.hash = '';   // never save a Twitch channel in a link (2026-10-10)
    return {label: button.dataset.label.slice(0, 180), url: u.pathname + u.search};
  }
  function notice(message) { if (window.toast) window.toast(message); }
  function render() {
    try {
      var entries = read();
      if (button) { var saved = entries.some(function (e) { return e.url === current().url; }); button.textContent = location.pathname.startsWith('/live/') ? (saved?'✓ Saved':'Save') : saved ? '✓ Saved on this device' : (/^\/(squad|sq)\//.test(location.pathname) ? 'Save squad' : 'Save player'); button.setAttribute('aria-pressed', String(saved)); }
      if (!panel) return;
      panel.hidden = !entries.length; list.replaceChildren();
      entries.forEach(function (entry) {
        var row = document.createElement('div'), link = document.createElement('a'), remove = document.createElement('button');
        row.className = 'saved-entry'; link.textContent = entry.label; link.href = entry.url;
        remove.type = 'button'; remove.className = 'secondary'; remove.textContent = 'Remove'; remove.setAttribute('aria-label', 'Remove ' + entry.label);
        remove.addEventListener('click', function () {
          try { localStorage.setItem(key, JSON.stringify(read().filter(function (e) { return e.url !== entry.url; }))); render(); window.dispatchEvent(new Event('ct-saved-changed')); notice('Removed from this device'); }
          catch (_) { notice('Could not update device storage.'); }
        });
        row.append(link, remove); list.appendChild(row);
      });
    } catch (_) {
      if (panel) { panel.hidden = false; document.getElementById('saved-status').textContent = 'Saved players are unavailable because browser storage is blocked or unreadable.'; }
      if (button) button.textContent = 'Save on this device';
    }
  }
  if (button) button.addEventListener('click', function () {
    try {
      var entry = current(), entries = read();
      if (entries.some(function (e) { return e.url === entry.url; })) {
        localStorage.setItem(key, JSON.stringify(entries.filter(function (e) { return e.url !== entry.url; }))); notice('Removed from this device');
      } else {
        if (entries.length >= 20) { notice('You have 20 saved entries. Remove one on the home page first.'); return; }
        entries.unshift(entry); localStorage.setItem(key, JSON.stringify(entries)); notice('Saved on this device');
      }
      render();
    } catch (_) { notice('Could not save. Browser storage may be disabled or full.'); }
  });
  addEventListener('storage', function (event) { if (event.key === key || event.key === null) render(); });
  render();
})();
