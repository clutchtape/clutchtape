"""Public full-roster match reviews; on-demand reads share the ingestion worker."""
import asyncio
import logging
import re
import time
from flask import Blueprint, abort, jsonify, render_template, request
import db
import privacy

bp = Blueprint('match_detail', __name__)
OUTCOMES = {0: 'Left', 1: 'Tie', 2: 'Win', 3: 'Loss', 4: 'Dnf'}


def known(mid):
    if privacy.blocked(mid):abort(404)
    if not re.fullmatch(r'[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}', mid):
        abort(404)
    rows = db.q('SELECT m.*,p.slug,p.gamertag,p.xuid FROM matches m JOIN players p ON p.id=m.player_id WHERE match_id=?', mid)
    # test-only players (PRIVATE_PLAYERS) are not served on public hosts: a match only they track is not found there
    rows = [r for r in rows if not any(privacy.hidden(r[k]) or privacy.blocked(r[k]) for k in ('slug','gamertag','xuid'))]
    if not rows:
        abort(404)
    return [dict(r) for r in rows]


def fields(data, prefix=''):
    """Keep every supplied scalar stat, including mode-specific fields and zeroes."""
    result = []
    for key, value in data.items():
        label = (prefix + ' ' + key.replace('_', ' ')).strip().capitalize()
        if value is None or key in ('medals', 'personal_scores'):
            continue
        if isinstance(value, dict):
            result.extend(fields(value, '' if key == 'core_stats' else label.replace(' stats', '')))
        elif isinstance(value, (int, float, str, bool)):
            result.append((label, round(value, 2) if isinstance(value, float) else value))
    return result


def normalize(raw, names, medals):
    players = []
    for i, p in enumerate(raw['players']):
        pid = p['player_id']; xuid = re.sub(r'\D', '', pid)
        if privacy.blocked(xuid) or privacy.blocked(names.get(xuid)):continue
        name = names.get(xuid) or ('Bot ' + str(i + 1) if not pid.startswith('xuid') else 'Player …' + xuid[-4:])
        splits = []
        for split in p.get('player_team_stats', []):
            stats = split.get('stats', {}); core = stats.get('core_stats', {})
            splits.append(dict(team=split['team_id'], core=core, fields=fields(stats), medals=[
                dict(name=medals.get(int(m['name_id']), 'Medal ' + str(m['name_id'])), count=m['count'])
                for m in core.get('medals', [])]))
        players.append(dict(name=name, xuid=xuid, team=p['last_team_id'], outcome=OUTCOMES.get(p.get('outcome'), 'Unknown'),
                            rank=p.get('rank'), splits=splits, participation=fields(p.get('participation_info', {}))))
    return dict(players=players, teams_enabled=raw['match_info'].get('teams_enabled', True),
                teams=[dict(id=t['team_id'], outcome=OUTCOMES.get(t.get('outcome'), 'Unknown'),
                            score=t.get('stats', {}).get('core_stats', {}).get('score'),
                            fields=fields(t.get('stats', {}))) for t in raw.get('teams', [])])


async def fetch_detail(mid):
    import ingest, xbox
    from aiohttp import ClientSession
    from spnkr import HaloInfiniteClient
    from spnkr.film.api import read_highlight_events
    try:
        async with asyncio.timeout(100):
            async with ClientSession() as session:
                client = HaloInfiniteClient(session=session, requests_per_second=3, **xbox.client_args())
                raw = db.kv_get('matchraw:' + mid)
                if not raw:
                    ms = await (await ingest._retry(lambda: client.stats.get_match_stats(mid))).parse()
                    raw = privacy.sanitize_match(ms.model_dump(mode='json'))
                names = {r['xuid']: r['gamertag'] for r in db.q('SELECT xuid,gamertag FROM players')}
                names.update({r['xuid']: r['gt'] for r in db.q('SELECT DISTINCT xuid,gt FROM events WHERE match_id=? AND gt IS NOT NULL', mid)})
                xuids = [ingest.xuid_of(p['player_id']) for p in raw['players'] if p['player_id'].startswith('xuid')]
                try:
                    users = await (await ingest._retry(lambda: client.profile.get_users_by_id(xuids))).parse() if xuids else []
                    names.update({str(u.xuid): str(u.gamertag) for u in users})
                except Exception:
                    logging.getLogger(__name__).info('Roster names unavailable for %s', mid)
                await ingest._load_medals(client)
                detail = normalize(raw, names, ingest._medal_names)
                db.kv_set('matchdetail:' + mid, detail)
                db.run('DELETE FROM kv WHERE k=?', 'matchraw:' + mid)
                db.kv_set('matchload:' + mid, {'state': 'ready', 'at': time.time()})
                if not db.q1('SELECT 1 FROM filmed WHERE match_id=?', mid):
                    try:
                        events = list(await ingest._retry(lambda: read_highlight_events(client, mid), 2))
                        ingest._store_events(mid, events)
                    except Exception:
                        logging.getLogger(__name__).info('Film unavailable for %s', mid)
    except Exception:
        logging.getLogger(__name__).exception('Match review fetch failed: %s', mid)
        if not db.kv_get('matchdetail:' + mid):
            db.kv_set('matchload:' + mid, {'state': 'error', 'at': time.time()})


def ensure(mid):
    import worker
    detail = db.kv_get('matchdetail:' + mid)
    state = db.kv_get('matchload:' + mid, {})
    if not detail and time.time() - state.get('at', 0) > (180 if state.get('state') == 'loading' else 60):
        if worker.enqueue_detail(mid):
            state = {'state': 'loading', 'at': time.time()}
        else:
            state = {'state': 'busy'}
    return detail, state.get('state', 'loading')


@bp.get('/api/match/<mid>/detail')
def status(mid):
    known(mid)
    detail, state = ensure(mid)
    response = jsonify(state='ready' if detail else state)
    response.headers['Cache-Control'] = 'no-store'
    return response


# ------------------------------------------------------------------ full lobby scoreboard (match page v2, 2026-10-08)
CORE_COLS = ('score', 'personal_score', 'kills', 'deaths', 'assists', 'kda', 'damage_dealt', 'damage_taken', 'accuracy',
             'headshot_kills', 'melee_kills', 'grenade_kills', 'power_weapon_kills', 'callout_assists', 'max_killing_spree',
             'average_life_duration', 'spawns', 'shots_fired', 'shots_hit', 'suicides', 'betrayals', 'objectives_completed',
             'vehicle_destroys', 'driver_assists', 'hijacks', 'emp_assists', 'rounds_won', 'rounds_lost', 'rounds_tied')
# short column names for mode stats (labels come from Halo's field names, prefixed with the mode group)
MODE_SHORT = {'Kills as skull carrier': 'Carrier K', 'Longest time as skull carrier': 'Longest hold', 'Skull carriers killed': 'Carrier kills',
              'Skull grabs': 'Grabs', 'Time as skull carrier': 'Ball time', 'Skull scoring ticks': 'Ticks',
              'Flag captures': 'Caps', 'Flag returns': 'Returns', 'Flag capture assists': 'Cap assists', 'Time as flag carrier': 'Carry time',
              'Flag grabs': 'Grabs', 'Flag steals': 'Steals', 'Flag secures': 'Secures', 'Flag carriers killed': 'Carrier kills',
              'Kills as flag carrier': 'Carrier K', 'Stronghold occupation time': 'Zone time', 'Stronghold captures': 'Zone caps',
              'Stronghold defensive kills': 'Def kills', 'Stronghold offensive kills': 'Off kills', 'Stronghold secures': 'Secures',
              'Zone occupation time': 'Hill time', 'Zone captures': 'Hill caps', 'Zone defensive kills': 'Def kills', 'Zone offensive kills': 'Off kills',
              'Zone secures': 'Secures', 'Zone scoring ticks': 'Ticks'}
MODE_SHORT_L = {k.lower(): v for k, v in MODE_SHORT.items()}
SKIP_FIELD = re.compile(r'^(pvp |kda$)', re.I)
BASE_LABELS = None


def _num(v):
    from stat_depth import number
    return number(v) if not isinstance(v, bool) else None


def board(detail, focus_xuid, team_id, tracked_xuids):
    """Rows for every player (one per team stint) with derived stats + the mode's own fields; team totals; compare bars."""
    import analytics
    global BASE_LABELS
    rows, mode_cols = [], []
    for p in detail['players']:
        played = next((_num(v) for k, v in p.get('participation', []) if k == 'Time played'), None)
        for sp in p['splits'] or []:
            c = sp['core']
            k, d, a = (c.get('kills') or 0), (c.get('deaths') or 0), (c.get('assists') or 0)
            dealt, taken = c.get('damage_dealt'), c.get('damage_taken')
            mins = (played or 0) / 60
            r = dict(name=p['name'], xuid=p['xuid'], team=sp['team'], rank=p.get('rank'), outcome=p['outcome'],
                     you=p['xuid'] == focus_xuid, tracked=p['xuid'] in tracked_xuids, mine=team_id is not None and sp['team'] == team_id,
                     k=k, d=d, a=a, kda=round(analytics.kda(k, d, a), 1), kd=round(k / max(1, d), 2),
                     pscore=c.get('personal_score'), dmg=dealt, taken=taken,
                     dd=(dealt - taken) if dealt is not None and taken is not None else None,
                     dpm=round(dealt / mins) if dealt is not None and mins >= 1 else None,
                     dka=round(dealt / (k + a)) if dealt is not None and (k + a) else None,
                     acc=round(c['accuracy'], 1) if c.get('accuracy') is not None else None,
                     hs=c.get('headshot_kills'), melee=c.get('melee_kills'), nade=c.get('grenade_kills'), power=c.get('power_weapon_kills'),
                     callouts=c.get('callout_assists'), spree=c.get('max_killing_spree'), life=_num(c.get('average_life_duration')),
                     spawns=c.get('spawns'), shots=c.get('shots_fired'), hit=c.get('shots_hit'), played=played,
                     medals=sorted(sp['medals'], key=lambda m: -m['count']), medal_n=sum(m['count'] for m in sp['medals']), mode={})
            for label, value in sp['fields']:
                key = label.lower().replace(' ', '_')
                if key in CORE_COLS or SKIP_FIELD.search(label) or label in ('Medals',):
                    continue
                v = _num(value)
                if v is None:
                    continue
                r['mode'][label] = round(v, 1)
                if label not in mode_cols:
                    mode_cols.append(label)
            rows.append(r)
    # mode stats: drop the redundant "skull scoring ticks" style duplicates of the team score and shorten labels
    short = {}
    for lab in mode_cols:
        bare = re.sub(r'^(oddball|capture the flag|zones|stronghold|strongholds|king of the hill|extraction)\s+', '', lab, flags=re.I).lower()
        hit = MODE_SHORT_L.get(lab.lower()) or MODE_SHORT_L.get(bare)
        if hit:
            short[lab] = hit
            continue
        s2 = re.sub(r'^(Oddball|Capture the flag|Zones|Stronghold|King of the hill|Extraction|Elimination|Stockpile|Total control)\s+', '', lab, flags=re.I)
        short[lab] = s2[:1].upper() + s2[1:]
    # SC%: share of the team's personal score (the site's headline performance number)
    team_ps = {}
    for r in rows:
        team_ps[r['team']] = team_ps.get(r['team'], 0) + (r['pscore'] or 0)
    for r in rows:
        r['sc'] = round(100 * r['pscore'] / team_ps[r['team']], 1) if r['pscore'] is not None and team_ps.get(r['team']) else None
    rows.sort(key=lambda r: (not r['mine'], r['rank'] or 999, r['name']))
    teams = {}
    for r in rows:
        t = teams.setdefault(r['team'], dict(k=0, d=0, a=0, dmg=0, taken=0, hs=0, callouts=0, shots=0, hit=0, medals=0, mode={}))
        for key, src in (('k', 'k'), ('d', 'd'), ('a', 'a'), ('dmg', 'dmg'), ('taken', 'taken'), ('hs', 'hs'), ('callouts', 'callouts'),
                         ('shots', 'shots'), ('hit', 'hit'), ('medals', 'medal_n')):
            t[key] += r.get(src) or 0
        for lab, v in r['mode'].items():
            t['mode'][lab] = t['mode'].get(lab, 0) + v
    return rows, mode_cols, short, teams


def compare(teams, team_id, mode_cols, short):
    """Your team vs the other team for the stats that decide games (only for 2-team matches)."""
    ids = [t for t in teams if t is not None]
    if team_id is None or len(ids) != 2:
        return []
    you, them = teams[team_id], teams[[t for t in ids if t != team_id][0]]
    acc = lambda t: round(100 * t['hit'] / t['shots'], 1) if t['shots'] else None
    out = [('Kills', you['k'], them['k'], ''), ('Damage', you['dmg'], them['dmg'], ''), ('Assists', you['a'], them['a'], ''),
           ('Accuracy', acc(you), acc(them), '%'), ('Headshot kills', you['hs'], them['hs'], ''), ('Callouts', you['callouts'], them['callouts'], ''),
           ('Medals', you['medals'], them['medals'], '')]
    for lab in mode_cols:
        if 'ticks' in lab.lower() or 'longest' in lab.lower():
            continue
        a, b = you['mode'].get(lab), them['mode'].get(lab)
        if a is None and b is None:
            continue
        unit = 's' if 'time' in lab.lower() else ''
        out.append((short.get(lab, lab), round(a or 0), round(b or 0), unit))
    return [dict(label=l, you=a, them=b, unit=u, share=(a / (a + b) if a is not None and b is not None and (a + b) else 0.5)) for l, a, b, u in out if a is not None and b is not None]


@bp.get('/match/<mid>')
def page(mid):
    rows = known(mid)
    focus = next((r for r in rows if r['slug'] == request.args.get('player')), rows[0])
    detail, state = ensure(mid)
    names = [focus['gamertag']]
    teams = []
    team_id = None
    if detail:
        detail = dict(detail, players=[p for p in detail['players'] if not any(privacy.hidden(p.get(k)) or privacy.blocked(p.get(k)) for k in ('name','xuid'))])
        mine = next((p for p in detail['players'] if p['xuid'] == focus['xuid']), None)
        team_id = mine['team'] if mine and detail['teams_enabled'] else None
        if team_id is not None:
            names = [p['name'] for p in detail['players'] if p['team'] == team_id]
        ids = sorted({s['team'] for p in detail['players'] for s in p['splits']})
        if any(not p['splits'] for p in detail['players']):
            ids += [None]
        for tid in ids:
            meta = next((t for t in detail['teams'] if t['id'] == tid), {})
            members = []
            for p in detail['players']:
                for s in p['splits'] or [dict(team=None, core={}, fields=[], medals=[])]:
                    if s['team'] == tid:
                        members.append(dict(p, stats=s, selected=p['xuid'] == focus['xuid']))
            teams.append(dict(id=tid, label='Stats unavailable' if tid is None else ('Your team' if tid == team_id else 'Opponents') if detail['teams_enabled'] else 'Free-for-all',
                              members=sorted(members, key=lambda p: (p['rank'] or 999, p['name'])), score=meta.get('score'), outcome=meta.get('outcome')))
    # Never advertise which other lobby players are tracked here (they may have been looked up by someone else).
    # Only the owner's private test host shows tracked teammates, their tags and the Watch-every-angle link.
    try:
        reveal = request.host.split(':', 1)[0].lower() in privacy.PRIVATE_HOSTS
    except Exception:
        reveal = False
    tracked = {r['xuid'] for r in rows} if reveal else {focus['xuid']}
    brows, mode_cols, short, tteams = board(detail, focus['xuid'], team_id, tracked) if detail else ([], [], {}, {})
    bars = compare(tteams, team_id, mode_cols, short) if detail else []
    import analytics, json as _json
    for r in rows:                      # tolerate partial rows (old history / tests): missing stats stay unknown
        for key in ('kills', 'deaths', 'assists', 'duration_s', 'damage_dealt', 'damage_taken', 'personal_score', 'team_pscore', 'headshots',
                    'pre_csr', 'post_csr', 'advanced', 'objectives', 'mode'):
            r.setdefault(key, None)
        analytics.derive(r)
    # display copy (cleaned map/mode) AFTER derive, so the hero's stats exist on every host
    focus = dict(focus, map=analytics.clean_map(focus.get('map')), mode=analytics.clean_mode(focus.get('mode')))
    mine_rows = ([r for r in rows if detail is None or team_id is None or r['xuid'] in {b['xuid'] for b in brows if b['mine']}] if reveal else [focus]) or [focus]
    # previous / next game for this player
    pid = focus.get('player_id')
    prev_m = db.q1('SELECT match_id FROM matches WHERE player_id=? AND started_at<? ORDER BY started_at DESC LIMIT 1', pid, focus['started_at']) if pid else None
    next_m = db.q1('SELECT match_id FROM matches WHERE player_id=? AND started_at>? ORDER BY started_at ASC LIMIT 1', pid, focus['started_at']) if pid else None
    squad_slugs = sorted({r['slug'] for r in mine_rows}) if len(mine_rows) > 1 else []
    roster = [dict(n=b['name'], t=b['team'], mine=b['mine'], you=b['you'], tr=b['tracked'], k=b['k'], d=b['d'], a=b['a']) for b in brows]
    return render_template('match.html', m=focus, detail=detail, state=state, teams=teams, board=brows, mode_cols=mode_cols, short=short,
                           bars=bars, team_scores=detail['teams'] if detail else [], team_id=team_id, tracked_rows=mine_rows,
                           prev_m=prev_m, next_m=next_m, squad_slugs=squad_slugs, roster=roster,
                           recap_names=names, recap_players=[p['name'] for p in detail['players']] if detail else [], recap_matches=[dict(id=mid, duration=focus['duration_s'], started_at=focus['started_at'], label=(focus['map'] or 'Unknown map') + ' · ' + (focus['mode'] or ''))])
