"""Explain which session games stand out without changing their chronological order."""
from collections import defaultdict

import close_games
import db


def for_matches(matches, player_ids):
    """Count detected film moments in this session, not the capped sidebar clip list.

    Use the same eight-second duplicate window as analytics.moments, scoped to
    the selected players. A clip is a detected highlight, not a promise that a
    Twitch broadcast is still available.
    """
    games = {m['match_id']: m for m in matches if m.get('outcome') in ('Win', 'Loss', 'Tie')}
    ids = list(dict.fromkeys(player_ids))
    if not games or not ids:
        return {}
    moments = defaultdict(set)
    keys = list(games)
    for start in range(0, len(keys), 200):
        batch = keys[start:start + 200]
        rows = db.q(f"SELECT match_id, t_ms FROM moments WHERE player_id IN ({','.join('?' for _ in ids)}) "
                    f"AND match_id IN ({','.join('?' for _ in batch)})", *ids, *batch)
        for row in rows:
            moments[row['match_id']].add(row['t_ms'] // 8000)
    out = {}
    for mid, game in games.items():
        cues = []
        close = close_games.score(game)
        if close:
            margin = f"{close['margin']:g}"
            units = close['unit'] if close['margin'] != 1 else close['unit'].rstrip('s')
            cues.append({'kind': 'close', 'text': f'Close · {margin} {units}',
                         'detail': f"Final score {game['team_score']:g}–{game['enemy_score']:g}. Close for this game mode."})
        elif (game.get('outcome') == 'Tie' and game.get('team_score') is not None
              and game.get('team_score') == game.get('enemy_score')):
            cues.append({'kind': 'close', 'text': 'Tied finish', 'detail': 'The completed game ended tied.'})
        count = len(moments[mid])
        if count:
            cues.append({'kind': 'clips' if count >= 3 else 'clip', 'count': count, 'text': f"{count} clip{'s' if count != 1 else ''}",
                         'detail': f'{count} auto-detected film highlights from the selected players; duplicate squad perspectives combined. Video availability is shown by the VOD buttons.'})
        if cues:
            out[mid] = cues
    return out


def for_sessions(sessions, player_ids, vod_map=None):
    """Explain session recommendations with counts from its games, not sidebar limits."""
    cues = for_matches([m for s in sessions for m in s['matches']], player_ids)
    recorded = {m[0] for matches in (vod_map or {}).values() for m in matches}
    result = {}
    for session in sessions:
        games = session['matches']
        if not games:
            continue
        unique = {m['match_id']: m for m in games}
        clips = sum(c.get('count', 0) for mid in unique for c in cues.get(mid, []))
        close = sum(any(c['kind'] == 'close' for c in cues.get(mid, [])) for mid in unique)
        longest = run = 0
        for game in sorted(unique.values(), key=lambda m: m.get('started_at', 0)):
            run = run + 1 if game.get('outcome') == 'Win' else 0
            longest = max(longest, run)
        reasons = []
        if close:
            reasons.append(f"{close} close game{'s' if close != 1 else ''}")
        if clips:
            reasons.append(f"{clips} detected clip{'s' if clips != 1 else ''}")
        if longest >= 3:
            reasons.append(f'{longest}-game win streak')
        standout = close >= 2 or clips >= 6 or longest >= 4
        available = len(set(unique) & recorded)
        interesting = standout or close >= 1 or clips >= 3 or longest >= 3
        worth = bool(available) and interesting
        result[games[-1]['match_id']] = dict(
            label=('Stats only' if not available else 'Worth a look' if worth else 'No strong signal yet'),
            recommended=worth, interesting=interesting, reasons=reasons, recorded=available,
            standout=standout, score=close * 3 + min(clips, 30) + min(longest, 6) * 2,
        )
    # Distinguish a few sessions even when most nights contain something interesting.
    ranked = sorted((p for p in result.values() if p['standout'] and p['recorded']), key=lambda p: p['score'], reverse=True)
    for pick in ranked[:3]:
        pick['label'] = 'Top pick'
    peak = max((p['score'] for p in result.values() if p['recommended']), default=1) or 1
    for pick in result.values():
        pick['heat'] = max(1, min(5, round(pick['score'] / peak * 5))) if pick['recommended'] else 0
    return result
