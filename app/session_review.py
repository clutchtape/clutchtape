"""Session comparisons and film-recap choices, independent of Twitch."""
from analytics import _agg


def _summary(matches):
    rows = [row for match in matches for row in (list(match['members'].values()) if 'members' in match else [match])]
    result = _agg(rows)
    wins = sum(m['outcome'] == 'Win' for m in matches)
    losses = sum(m['outcome'] == 'Loss' for m in matches)
    result.update(games=len(matches), wins=wins, losses=losses, record=f'{wins}-{losses}',
                  win_pct=round(100 * wins / (wins + losses), 1) if wins + losses else None)
    return result


def comparison(sessions, selected=0, baseline='previous'):
    if not sessions:
        return None
    selected = max(0, min(selected, len(sessions) - 1))
    # Only earlier sessions enter the recent baseline; never compare a session with itself.
    prior = sessions[selected + 1:selected + (6 if baseline == 'recent' else 2)]
    current = sessions[selected]
    a = _summary(current['matches'])
    b = _summary([m for s in prior for m in s['matches']]) if prior else None
    metrics = []
    squad = any('members' in m for m in current['matches'])
    for key, label, suffix in [('win_pct', 'Win rate', '%'), ('kd', 'K/D', ''),
                               ('kda', 'KDA / player-game' if squad else 'KDA / game', ''),
                               ('dmg_pm', 'Damage / minute', ''), ('dmg_ka', 'Damage / (K+A)', ''),
                               ('dmg_diff_pg', 'Damage ± / game', ''), ('sc_pct', 'Score share', '%')]:
        value, old = a.get(key), b.get(key) if b else None
        delta = round(value - old, 1 if key == 'kda' else 2) if value is not None and old is not None else None
        metrics.append(dict(label=label, value=value, old=old, delta=delta, suffix=suffix,
                            delta_suffix=' pp' if suffix == '%' else ''))
    return dict(current=a, baseline=b, metrics=metrics, mode=baseline, start=current['start'],
                prior_count=len(prior), prior_start=prior[-1]['start'] if prior else None,
                prior_end=prior[0]['start'] if prior else None, squad=squad)


def recap_matches(matches):
    return [dict(id=m['match_id'], label=' · '.join(str(x) for x in (m.get('map') or 'Unknown map', m.get('mode'), m.get('outcome')) if x),
                 started_at=m['started_at'], duration=m.get('duration_s') or 0)
            for m in matches]
