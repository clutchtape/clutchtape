/* Evidence-based stretches from Theater events; no inferred match-score swings. */
(function (root) {
  'use strict';
  function highlights(events, names, duration) {
    var selected = new Set(Array.from(names, n => String(n).toLowerCase()));
    var mine = n => selected.has(String(n || '').toLowerCase());
    var source = events.filter(e => Array.isArray(e) && Number.isFinite(e[1]) && e[1] >= 0)
      .sort((a, b) => a[1] - b[1]);
    var special = /^(Triple Kill|Overkill|Killtacular|Killtrocity|Killamanjaro|Killtastrophe|Killpocalypse|Killionaire|Killing Spree|Killing Frenzy|Running Riot|Rampage|Nightmare|Boogeyman|Grim Reaper|Demon|Extermination|Ninja|Quigley|Hail Mary|Perfection|Goal Line Stand|Clock Stop|Stopped Short)$/;
    var candidates = [];
    function stretch(start, end, title, weight) {
      start = Math.max(0, start); end = Math.min(duration, end);
      if (end <= start) return;
      var rows = source.filter(e => e[1] / 1000 >= start && e[1] / 1000 <= end);
      var kills = rows.filter(e => e[0] === 'k' && mine(e[2])).length;
      var deaths = rows.filter(e => (e[0] === 'k' || e[0] === 'd') && mine(e[3])).length;
      var objectives = rows.filter(e => e[0] === 'o' && mine(e[2])).length;
      candidates.push({start, end, title, kills, deaths, objectives, weight});
    }
    source.forEach(e => {
      if (e[0] === 'm' && mine(e[2]) && special.test(e[3]))
        stretch(e[1] / 1000 - 15, e[1] / 1000 + 8, e[3] + ' · ' + e[2], 100);
    });
    for (var start = 0; start < duration; start += 15) {
      var end = Math.min(duration, start + 30);
      var rows = source.filter(e => e[1] / 1000 >= start && e[1] / 1000 < end);
      var k = rows.filter(e => e[0] === 'k' && mine(e[2])).length;
      var d = rows.filter(e => (e[0] === 'k' || e[0] === 'd') && mine(e[3])).length;
      var o = rows.filter(e => e[0] === 'o' && mine(e[2])).length;
      if (k >= 3 && k - d >= 2) stretch(start, end, 'Strong stretch', 20 + k - d);
      else if (d >= 4 && d - k >= 3) stretch(start, end, 'Under pressure', 10 + d - k);
      else if (o >= 2) stretch(start, end, 'Objective activity', 15 + o);
    }
    var chosen = [];
    candidates.sort((a, b) => b.weight - a.weight || b.kills - a.kills || a.start - b.start).forEach(s => {
      if (chosen.length < 6 && !chosen.some(p => s.start < p.end + 5 && s.end > p.start - 5)) chosen.push(s);
    });
    return chosen.sort((a, b) => a.start - b.start);
  }
  if (typeof module !== 'undefined') module.exports = highlights;
  else root.ClutchHighlights = highlights;
})(typeof window !== 'undefined' ? window : globalThis);
