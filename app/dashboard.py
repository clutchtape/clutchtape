import capacity
"""Stats-first session companion. Everything is derived from loaded Halo history."""
from collections import defaultdict
from types import SimpleNamespace
from urllib.parse import urlencode
import hashlib
import json
import time
import statistics

import analytics
import db
import objectives
import session_review
import teamwork
import stat_depth
import analysis_view


def anchor(session):
    return session['matches'][-1]['match_id']


def select_session(sessions, key=None, match=None, legacy=0, skip_unfinished=False):
    if key or match:
        target = key or match
        # links carry the first 8 characters of a match id (see web._short_id); full ids still work
        hit = (lambda m: m['match_id'] == target) if len(target) < 8 else (lambda m: m['match_id'].startswith(target))
        return next((i for i, s in enumerate(sessions) if any(hit(m) for m in s['matches'])), None)
    if skip_unfinished and not legacy:
        # Default view: don't headline a "0-0" session made only of quit/unfinished games (Dnf/Left) when a real one exists.
        return next((i for i, s in enumerate(sessions) if any(m.get('outcome') in ('Win', 'Loss', 'Tie') for m in s['matches'])), 0)
    return max(0, min(len(sessions) - 1, legacy)) if sessions else 0


def link(slugs, kind='mm', session=None, match=None, at=None, **extra):
    qs = {'kind': kind, **extra}
    if session: qs['session'] = session
    if match: qs['match'] = match
    if at is not None: qs['at'] = max(0, int(at))
    return '/live/' + slugs + '?' + urlencode(qs) + ('#recap' if match else '')


def rows_of(matches):
    return [r for m in matches for r in (list(m['members'].values()) if 'members' in m else [m])]


def rates(rows):
    if not rows: return {}
    a = analytics._agg(rows)
    duration = sum(r.get('duration_s') or 0 for r in rows) / 60
    a['spread'] = round(statistics.pstdev(analytics.kda(r['kills'],r['deaths'],r['assists']) for r in rows),2) if len(rows)>=3 else None
    a['death_pm'] = round(sum(r.get('deaths') or 0 for r in rows) / duration, 2) if duration else None
    return a


def progress(players, histories, selected):
    out, records = [], []
    for p in players:
        current = [r for r in rows_of(selected) if r['player_id'] == p['id']]
        if not current: continue
        start = min(r['started_at'] for r in current)
        modes = {(r['playlist'], r['mode']) for r in current}
        baseline = [r for r in histories[p['id']] if start - 30*86400 <= r['started_at'] < start and (r['playlist'], r['mode']) in modes]
        a, b = rates(current), rates(baseline)
        metrics = []
        for key, label, unit, lower in [('dmg_pm','Damage / min','',False), ('death_pm','Deaths / min','',True), ('acc','Accuracy','%',False), ('kda','KDA / game','',False), ('spread','KDA spread','',True)]:
            v, old = a.get(key), b.get(key)
            delta = round(v-old,2) if v is not None and old is not None and len(baseline)>=5 else None
            metrics.append(dict(label=label,value=v,old=old,unit=unit,delta=delta,note='Need 3 session & 5 earlier games' if key=='spread' else 'Need 5 earlier games',better=(delta<0 if lower else delta>0) if delta is not None else None))
        out.append(dict(name=p['gamertag'],metrics=metrics,games=len(current),baseline=len(baseline)))
        for r in current:
            earlier = [x for x in histories[p['id']] if x['started_at'] < r['started_at'] and x['playlist']==r['playlist'] and x['mode']==r['mode'] and (x['duration_s'] or 0)>=180]
            if len(earlier)<5 or (r['duration_s'] or 0)<180: continue
            for key,label in [('kills','kills'),('dmg_pm','damage/min')]:
                old = [x[key] for x in earlier if x.get(key) is not None]
                if old and r.get(key) is not None and r[key]>max(old):
                    records.append(dict(name=p['gamertag'],label=label,value=r[key],previous=max(old),games=len(old),match=r['match_id'],map=r['map'],mode=r['mode']))
    return out, records[:8]


def map_modes(matches):
    groups=defaultdict(list)
    for m in matches: groups[(m['map'] or 'Unknown map',m['mode'] or 'Unknown mode')].append(m)
    out=[]
    for (map_,mode),ms in groups.items():
        a=session_review._summary(ms)
        out.append(dict(map=map_,mode=mode,**a,ids=[m['match_id'] for m in ms]))
    return sorted(out,key=lambda x:(-x['games'],x['map'],x['mode']))


def lineups(players, histories):
    matches=defaultdict(list); groups=defaultdict(list)
    names={p['id']:p['gamertag'] for p in players}
    for rows in histories.values():
        for r in rows: matches[r['match_id']].append(r)
    for rs in matches.values():
        teams=defaultdict(list)
        for r in rs:
            if r.get('team_id') is not None: teams[r['team_id']].append(r)
        for team in teams.values():
            ids=tuple(sorted(r['player_id'] for r in team))
            if len(ids)>=2:
                groups[ids].append(team[0])
    return sorted([dict(names=[names[x] for x in ids],**session_review._summary(ms)) for ids,ms in groups.items()],key=lambda x:-x['games'])


def lineup_analysis(players, histories, min_games=3):
    """Squad lineups (2026-10-09): which combination of tracked players wins.
    A lineup = the exact set of tracked players on one team in one match (team_id). Returns
      sizes: [{size, rows:[lineup...]}]  lineup = names, ids, games, record, win_pct, sc (stack's combined score share,
             avg per game), kda/dpm (avg per player-game), dd (stack's damage ± per game), csr (net), small (< min_games)
      best:  best lineup per size by win % (min_games decided games, ties -> more games)
      pairs: {(a,b): {games, win_pct}} any lineup containing both; names in order
      without: per player: win % in squad games with them vs squad games without them."""
    names = {p['id']: p['gamertag'] for p in players}
    order = [p['id'] for p in players]
    by_match = defaultdict(list)
    for rows in histories.values():
        for r in rows:
            by_match[r['match_id']].append(r)
    groups = defaultdict(list)            # ids -> [(outcome, [member rows])]
    for rs in by_match.values():
        teams = defaultdict(list)
        for r in rs:
            if r.get('team_id') is not None:
                teams[r['team_id']].append(r)
        for team in teams.values():
            ids = tuple(sorted({r['player_id'] for r in team}, key=order.index))
            if len(ids) >= 2:
                groups[ids].append((team[0]['outcome'], [analytics.derive(dict(r)) for r in team]))
    def summary(ids, games):
        dec = [o for o, _ in games if o in ('Win', 'Loss')]
        w = sum(o == 'Win' for o in dec)
        rows = [r for _, ms in games for r in ms]
        avg = lambda vals: round(sum(vals) / len(vals), 1) if vals else None
        sc = [sum(r['sc_pct'] for r in ms if r.get('sc_pct') is not None) for _, ms in games if any(r.get('sc_pct') is not None for r in ms)]
        dd = [sum((r.get('dmg_diff') or 0) for r in ms) for _, ms in games]
        csr = [r['csr_d'] for r in rows if r.get('csr_d') is not None]
        return dict(names=[names[i] for i in ids], ids=list(ids), size=len(ids), games=len(games), wins=w, losses=len(dec) - w,
                    record=f"{w}-{len(dec) - w}", win_pct=round(100 * w / len(dec)) if dec else None,
                    sc=(lambda v: v if v is not None and v < 99.5 else None)(avg(sc)),   # a full team's share is always 100%: not informative
                    kda=avg([r['kda'] for r in rows if r.get('kda') is not None]),
                    dpm=(lambda v: round(v) if v is not None else None)(avg([r['dmg_pm'] for r in rows if r.get('dmg_pm') is not None])),
                    dd=round(sum(dd) / len(dd)) if dd else None, csr=sum(csr) if csr else None, small=len(dec) < min_games)
    lineups = [summary(ids, g) for ids, g in groups.items()]
    rank = lambda l: (not l['small'], l['win_pct'] if l['win_pct'] is not None else -1, l['games'])
    sizes = []
    for n in sorted({l['size'] for l in lineups}):
        rows = sorted([l for l in lineups if l['size'] == n], key=rank, reverse=True)
        sizes.append(dict(size=n, rows=rows, best=next((l for l in rows if not l['small']), None)))
    pairs = {}
    for i, a in enumerate(order):
        for b in order[i + 1:]:
            games = [g for ids, gs in groups.items() if a in ids and b in ids for g in gs]
            dec = [o for o, _ in games if o in ('Win', 'Loss')]
            if games:
                pairs[(names[a], names[b])] = dict(games=len(games), win_pct=round(100 * sum(o == 'Win' for o in dec) / len(dec)) if dec else None)
    without = []
    for pid in order:
        with_g = [o for ids, gs in groups.items() if pid in ids for o, _ in gs if o in ('Win', 'Loss')]
        wo_g = [o for ids, gs in groups.items() if pid not in ids for o, _ in gs if o in ('Win', 'Loss')]
        pct = lambda os: round(100 * sum(o == 'Win' for o in os) / len(os)) if os else None
        without.append(dict(name=names[pid], with_games=len(with_g), with_pct=pct(with_g), without_games=len(wo_g), without_pct=pct(wo_g),
                            swing=(pct(with_g) - pct(wo_g)) if with_g and wo_g else None))
    return dict(sizes=sizes, pairs=pairs, names=[names[i] for i in order], without=without)


def review_moments(matches, players):
    """Find distinct strong/rough/recovery windows, from event metadata, even without a video."""
    candidates=[]; names={str(p['xuid']):p['gamertag'] for p in players}
    for match in matches[:30]:
        if not db.q1('SELECT 1 FROM filmed WHERE match_id=?',match['match_id']): continue
        members = set(match['members']) if 'members' in match else {match['player_id']}
        selected={str(p['xuid']):p['gamertag'] for p in players if p['id'] in members}
        events=db.q('SELECT xuid,t_ms,k FROM events WHERE match_id=? ORDER BY t_ms',match['match_id'])
        kills=[(e['t_ms'],str(e['xuid'])) for e in events if e['k']=='kill' and str(e['xuid']) in selected]
        deaths=[(e['t_ms'],str(e['xuid'])) for e in events if e['k']=='death' and str(e['xuid']) in selected]
        for c in teamwork.momentum(kills,deaths,selected):
            cat='Recovery' if c['label'].startswith('Comeback') else 'Strong stretch' if c['net']>0 else 'Review this stretch'
            candidates.append(dict(category=cat,net=c['net'],score=c['score'],match=match['match_id'],at=max(0,c['start'])/1000,duration=max(1,round((c['end']-max(0,c['start']))/1000)),map=match['map'],mode=match['mode']))
    return [max([c for c in candidates if c['category']==cat],key=lambda x:x['score']) for cat in ['Strong stretch','Review this stretch','Recovery'] if any(c['category']==cat for c in candidates)]


@capacity.memo(lambda players,kind='mm',session=None,match=None,days=30,scope='session',playlist='',baseline='previous':(tuple((p['id'],p.get('last_synced'),p.get('sync_state')) for p in players),kind,session,match,days,scope,playlist,baseline))
def load(players, kind='mm', session=None, match=None, days=30, scope='session', playlist='', baseline='previous'):
    histories={}; playlists=set()
    for p in players:
        rs=[dict(r) for r in db.q('SELECT * FROM matches WHERE player_id=? ORDER BY started_at DESC',p['id']) if analytics.kind_ok(r,kind)]
        playlists.update(r['playlist'] for r in rs if r.get('playlist'))
        if playlist: rs=[r for r in rs if r['playlist']==playlist]
        stat_depth.enrich(rs,p['xuid'])
        for r in rs:
            r['map'],r['mode']=analytics.clean_map(r['map']),analytics.clean_mode(r['mode']);analytics.derive(r)
        histories[p['id']]=rs
    if len(players)==1:
        history=histories[players[0]['id']]; sessions=analytics.sessions(history)
    else:
        by_match=defaultdict(list)
        for rs in histories.values():
            for r in rs: by_match[r['match_id']].append(r)
        history=[]
        for rs in by_match.values():
            teams=defaultdict(list)
            for r in rs:
                if r.get('team_id') is not None: teams[r['team_id']].append(r)
            team=max(teams.values(),key=len,default=[])
            if len(team)<2: continue
            m=dict(team[0]);m['members']={r['player_id']:r for r in team};history.append(m)
        history.sort(key=lambda m:-m['started_at'])
        sessions=analytics.sessions(history)
    idx=select_session(sessions,session,match)
    selected=sessions[idx] if sessions and idx is not None else None
    if scope!='session':
        cutoff=time.time()-int(scope)*86400 if scope in ('30','90') else 0
        window=[m for m in history if m['started_at']>=cutoff]
        selected=dict(matches=window,start=min(m['started_at'] for m in window),games=len(window)) if window else None
    matches=selected['matches'] if selected else []
    slugs=','.join(p['slug'] for p in players)
    summary=session_review._summary(matches) if matches else None
    akey=anchor(selected) if selected else None
    for s in sessions:
        s['key']=anchor(s);s['url']=link(slugs,kind,session=s['key']);s['summary']=session_review._summary(s['matches'])
    for m in matches:
        m['review_url']=link(slugs,kind,session=akey,match=m['match_id'])
    prog,records=progress(players,histories,matches) if scope=='session' else ([],[])
    moments=review_moments(matches,players)
    for item in moments+records:
        item['url']=link(slugs,kind,session=akey,match=item['match'],at=item.get('at',0))
    cutoff=time.time()-days*86400 if days else 0
    filtered=matches
    chosen_ids={m['match_id'] for m in matches}
    line_hist={pid:[r for r in rs if r['match_id'] in chosen_ids] for pid,rs in histories.items()}
    # lineups need samples: never less than the last 90 days (2026-10-10); longer selections use the selection
    if scope in ('session','30'):
        lu_cut=time.time()-90*86400;lu_hist={pid:[r for r in rs if r['started_at']>=lu_cut] for pid,rs in histories.items()};lu_label='Last 90 days'
    else:
        lu_hist=line_hist;lu_label=None
    maps=map_modes(filtered)
    for item in maps: item['url']=link(slugs,kind,session=akey,map=item['map'],mode=item['mode'],days=days or 'all')+'#map-modes'
    rank=[]
    for p in players:
        groups=defaultdict(list)
        for r in rows_of(matches):
            if r['player_id']==p['id'] and r.get('post_csr') and r.get('pre_csr'): groups[r['playlist']].append(r)
        for rank_playlist,rs in groups.items():
            rs.sort(key=lambda r:r['started_at'])
            rank.append(dict(name=p['gamertag'],playlist=rank_playlist,current=rs[-1]['post_csr'],delta=sum(r['post_csr']-r['pre_csr'] for r in rs),games=len(rs)))
    covered=sum(bool(db.q1('SELECT 1 FROM filmed WHERE match_id=? AND n>0',m['match_id'])) for m in matches)
    latest=matches[0] if matches else None
    latest_stats=session_review._summary([latest]) if latest else None
    prior_stats=session_review._summary([matches[1]]) if len(matches)>1 else None
    end=latest['started_at']+(latest['duration_s'] or 0) if latest else 0
    analysis=analysis_view.build(players,matches,histories,baseline,sessions,idx or 0)
    return dict(analysis=analysis,scope=scope,scope_label=('Selected session' if scope=='session' else 'Last '+scope+' days' if scope in ('30','90') else 'All loaded history'),playlist=playlist,playlists=sorted(playlists),players=players,slugs=slugs,kind=kind,sessions=sessions,selected=selected,missing=scope=='session' and idx is None,anchor=akey,matches=matches,summary=summary,
                latest=latest,latest_stats=latest_stats,prior_stats=prior_stats,progress=prog,records=records,moments=moments,maps=maps,lineups=lineups(players,line_hist),lineup_analysis=lineup_analysis(players,lu_hist),lineup_label=lu_label,rank=rank,
                comparison=session_review.comparison(sessions,idx or 0),objectives=objectives.summarize(rows_of(matches)),coverage=dict(stats=len(matches),events=covered),
                current=scope=='session' and not session and not match,active=bool(scope=='session' and latest and time.time()-end<7200),ended=end,days=days,history=history,filtered=filtered,
                stable_url=link(slugs,kind,session=akey) if akey else link(slugs,kind),title=' + '.join(p['gamertag'] for p in players))


def version(players):
    bits=[]
    for p in players:
        r=db.q1('SELECT COUNT(*) n, MAX(started_at) t, COUNT(objectives) o, COUNT(advanced) a, SUM(film_state) f FROM matches WHERE player_id=?',p['id'])
        bits.append([p['id'],list(r)])
    return hashlib.sha256(json.dumps(bits).encode()).hexdigest()[:20]
