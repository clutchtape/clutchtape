"""Private, device-selected home feed; never exposes the global player directory."""
from urllib.parse import urlencode
from werkzeug.exceptions import HTTPException
from flask import jsonify, request
import alerts
import analytics
import db
import session_watch
import twitch


def build(follow):
    ids = [r['id'] for p in follow['players'] if (r := db.q1('SELECT id FROM players WHERE slug=?', p['slug']))]
    data = analytics.squad(ids, "ranked") if len(ids) > 1 else analytics.profile(ids[0], "ranked")
    sessions = []
    for source in data.get('nights') or data.get('sessions') or []:
        games = [m for m in source['matches'] if m.get('outcome') in ('Win', 'Loss', 'Tie')]
        if not games:
            continue
        wins = sum(m['outcome'] == 'Win' for m in games)
        losses = sum(m['outcome'] == 'Loss' for m in games)
        ties = sum(m['outcome'] == 'Tie' for m in games)
        record = f'{wins}-{losses}'+(f' · {ties} tied' if ties else '')
        sessions.append(dict(source, matches=games, record=record))
        if len(sessions) == 8:
            break
    picks = session_watch.for_sessions(sessions, ids)
    result = []
    for s in sessions:
        games = s['matches']
        if not games:
            continue
        pick = dict(picks.get(games[-1]['match_id'], {}))
        reasons = list(pick.get('reasons', []))
        rows = [r for m in games for r in (m['members'].values() if 'members' in m else [m])]
        standout = max(rows, key=lambda r: (r.get('kills') or 0)-(r.get('deaths') or 0), default={})
        net = (standout.get('kills') or 0)-(standout.get('deaths') or 0)
        if net >= 15:
            reasons.append(f"Standout game · {standout['kills']}/{standout['deaths']} K/D")
        run = worst = 0
        for m in reversed(games):
            run = run+1 if m['outcome'] == 'Loss' else 0
            worst = max(worst, run)
        if worst >= 3:
            reasons.append(f'{worst}-game losing stretch to review')
        score = pick.get('score', 0)+(5 if net >= 15 else 0)+(3 if worst >= 3 else 0)
        result.append(dict(label=follow['label'], url=follow['url']+('&' if '?' in follow['url'] else '?')+urlencode({'session':games[-1]['match_id'],'tab':'sessions'}), at=s['start'], record=s['record'], games=len(games), reasons=reasons, score=score, recommended=pick.get('recommended', False) or net >= 15 or worst >= 3))
    return result


@alerts.bp.post('/api/alerts/home')
def home():
    alerts.check_write("home-feed", 120)
    identifier, _, host = alerts.identity()
    data = request.get_json(silent=True) or {}
    targets = data.get('targets', []) if isinstance(data, dict) else None
    if not isinstance(targets, list) or len(targets) > 20:
        return jsonify(error='Choose up to 20 saved players or squads.'), 400
    row = db.q1('SELECT follows FROM alert_devices WHERE id=?', identifier)
    import json
    follows = json.loads(row['follows']) if row else []
    chosen, unavailable = {}, 0
    for target in [f['url'] for f in follows]+targets:
        try:
            follow = alerts.resolve(target, host)
            chosen[follow['key']] = follow
        except (HTTPException, ValueError):
            unavailable += 1
    from web import _cached
    cards, feed, live = [], [], {}
    for f in list(chosen.values())[:20]:
        sessions = _cached('personal-home', (host, f['key'], f['url']), 60, lambda f=f: build(f))
        if sessions is None:
            return jsonify(error='Session data is temporarily unavailable. Try again shortly.'), 503
        cards.append(dict(label=f['label'], url=f['url'], latest=sessions[0] if sessions else None))
        feed.extend(s for s in sessions if s['recommended'])
        for p in f['players']:
            ch = p.get('channel')
            if not ch or ch in live or not twitch.enabled():
                continue
            try:
                streams = _cached('home-channel', ch, 60, lambda ch=ch: twitch._get('streams', user_login=[ch]))
                if streams:
                    st = streams[0]
                    live[ch] = dict(name=p['name'], title=st.get('title', 'Live on Twitch'), url='/p/'+p['slug'])
            except Exception:
                pass
    feed.sort(key=lambda s: (-s['score'], -s['at']))
    response = jsonify(cards=cards, picks=feed[:12], live=list(live.values()), unavailable=unavailable)
    response.headers['Cache-Control'] = 'no-store'
    return response
