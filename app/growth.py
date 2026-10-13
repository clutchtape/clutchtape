"""Practice tools built only from loaded results; no streaming account required."""
from collections import defaultdict
from datetime import datetime, timezone, timedelta
import json
from urllib.parse import urlencode
from flask import Blueprint, abort, render_template, request, Response
import analytics, dashboard, db, privacy, session_review

bp = Blueprint('growth', __name__)

def data(slugs, kind=None):
    names=list(dict.fromkeys(slugs.split(',')))
    if not 1<=len(names)<=4: abort(404)
    ps=[]
    for name in names:
        p=db.q1('SELECT * FROM players WHERE slug=?',name)
        if not p or privacy.blocked(name) or privacy.hidden(name): abort(404)
        ps.append(dict(p))
    kind=kind or request.args.get('kind','mm')
    if kind not in dict(analytics.KINDS): kind='mm'
    return dashboard.load(ps,kind,days=0)

def close_game(m):
    """Only score systems with an explicit, meaningful threshold."""
    a,b=m.get('team_score'),m.get('enemy_score')
    if a is None or b is None or m['outcome'] not in ('Win','Loss'): return False
    mode=(m.get('mode') or '').lower()
    limit=5 if 'slayer' in mode else 1 if 'ctf' in mode or 'capture the flag' in mode else None
    return limit is not None and abs(a-b)<=limit

def records(history):
    best={}; counts=defaultdict(int); ids=set()
    for m in reversed(history):
        for r in dashboard.rows_of([m]):
            key=(r['player_id'],r['playlist'],r['mode'])
            val=r.get('dmg_pm')
            if (r.get('duration_s') or 0)<180 or val is None: continue
            if counts[key]>=5 and val>best[key]: ids.add(m['match_id'])
            counts[key]+=1;best[key]=max(best.get(key,0),val)
    return ids

def search(history, args):
    q=args.get('q','')[:100].casefold().split()
    best=records(history) if args.get('best') else set()
    out=[]
    for m in history:
        if not all(t in ' '.join(str(m.get(k) or '') for k in ('map','mode','outcome','playlist')).casefold() for t in q): continue
        if any(args.get(k) and (m.get(k) or ('Custom' if k=='playlist' else ''))!=args[k] for k in ('map','mode','outcome','playlist')): continue
        day=datetime.fromtimestamp(m['started_at'],timezone.utc).strftime('%Y-%m-%d')
        if args.get('from') and day<args['from']: continue
        if args.get('to') and day>args['to']: continue
        if args.get('close') and not close_game(m): continue
        if args.get('best') and m['match_id'] not in best: continue
        out.append(m)
    return out

def explanations(b):
    if not b['selected']: return []
    current=b['matches']; start=min(m['started_at'] for m in current)
    earlier=[m for m in b['history'] if start-30*86400<=m['started_at']<start]
    out=[]
    groups=defaultdict(list)
    for m in current: groups[(m['map'],m['mode'],m['playlist'])].append(m)
    for (map_,mode,playlist),games in groups.items():
        prev=[m for m in earlier if (m['map'],m['mode'],m['playlist'])==(map_,mode,playlist)]
        if len(games)<2 or len(prev)<5: continue
        a,z=dashboard.rates(dashboard.rows_of(games)),dashboard.rates(dashboard.rows_of(prev))
        delta=round(a['dmg_pm']-z['dmg_pm'],1)
        out.append(dict(title=f'{map_} · {mode}',text=f'Damage/min {a["dmg_pm"]} vs {z["dmg_pm"]} ({delta:+g}). {len(games)} session games vs {len(prev)} earlier games in the same playlist, map and mode.',url='/history/'+b['slugs']+'?'+urlencode(dict(kind=b['kind'],map=map_,mode=mode,playlist=playlist or 'Custom',**{'from':datetime.fromtimestamp(start-30*86400,timezone.utc).strftime('%Y-%m-%d'),'to':datetime.fromtimestamp(max(m['started_at'] for m in current),timezone.utc).strftime('%Y-%m-%d')}))))
    if b['sessions']:
        idx=next((i for i,s in enumerate(b['sessions']) if s['key']==b['anchor']),None)
        if idx is not None and idx+1<len(b['sessions']):
            prior=b['sessions'][idx+1]
            now=session_review._summary(current);old=prior['summary']
            out.insert(0,dict(title='The session result',text=f'{now["record"]} across {now["games"]} games; the previous session was {old["record"]} across {old["games"]}. Different maps, teammates and opponents can change this comparison.',url=prior['url']))
    return out[:4]

@bp.route('/history/<slugs>')
def history(slugs):
    b=data(slugs); matches=search(b['history'],request.args)
    try: page=max(1,int(request.args.get('page',1)))
    except ValueError: page=1
    page=min(page,max(1,(len(matches)+39)//40))
    args=request.args.to_dict();args['page']=page+1
    next_url='?'+urlencode(args) if len(matches)>page*40 else None
    args['page']=page-1
    return render_template('history.html',b=b,rows=matches[(page-1)*40:page*40],total=len(matches),page=page,next_url=next_url,prev_url='?'+urlencode(args) if page>1 else None,maps=sorted({m['map'] or '' for m in b['history']}),modes=sorted({m['mode'] or '' for m in b['history']}))

@bp.route('/practice/<slugs>')
def practice(slugs):
    b=data(slugs)
    rows=[]
    for r in dashboard.rows_of(b['history']):
        try: obj=json.loads(r.get('objectives') or '{}')
        except (ValueError,TypeError): obj={}
        rows.append(dict(id=r['match_id'],player=r['player_id'],time=r['started_at'],playlist=r['playlist'] or 'Custom',mode=r['mode'],map=r['map'],outcome=r['outcome'],damage=r.get('dmg_pm'),deaths=(round((r['deaths'] or 0)*60/r['duration_s'],2) if r.get('duration_s') else None),accuracy=(100*r['shots_hit']/r['shots_fired'] if r.get('shots_fired') else None),ball=obj.get('time_as_skull_carrier',{}).get('value'),flag=obj.get('time_as_flag_carrier',{}).get('value'),zone=obj.get('stronghold_occupation_time',{}).get('value')))
    return render_template('practice.html',b=b,goal_rows=rows,playlists=sorted({r['playlist'] for r in rows}),modes=sorted({r['mode'] or '' for r in rows}))

def weekly(b, raw=None):
    try: end=datetime.strptime(raw,'%Y-%m-%d').replace(tzinfo=timezone.utc) if raw else datetime.now(timezone.utc).replace(hour=0,minute=0,second=0,microsecond=0)
    except (ValueError,TypeError): abort(400,'Choose an end date in YYYY-MM-DD format.')
    start=end-timedelta(days=7)
    matches=[m for m in b['history'] if start.timestamp()<=m['started_at']<end.timestamp()]
    prev=[m for m in b['history'] if (start-timedelta(days=7)).timestamp()<=m['started_at']<start.timestamp()]
    a=session_review._summary(matches) if matches else None
    z=session_review._summary(prev) if prev else None
    best=records(b['history']);personal=[m for m in matches if m['match_id'] in best]
    groups=dashboard.map_modes(matches)
    focus=min((g for g in groups if g['games']>=3 and g['win_pct'] is not None),key=lambda g:g['win_pct'],default=None)
    return dict(start=start.timestamp(),end=end.timestamp(),date=end.strftime('%Y-%m-%d'),matches=matches,summary=a,prior=z,records=personal,focus=focus)

@bp.route('/weekly/<slugs>')
def week(slugs):
    b=data(slugs);w=weekly(b,request.args.get('end'))
    return render_template('weekly.html',b=b,w=w)

@bp.route('/weekly/<slugs>.png')
def week_png(slugs):
    b=data(slugs);w=weekly(b,request.args.get('end'))
    if not w['summary']: abort(404,'No loaded matches in this week.')
    import ogcard
    resp=Response(ogcard.weekly_card(b,w),mimetype='image/png')
    resp.headers['Cache-Control']='no-store'
    resp.headers['Content-Disposition']='attachment; filename="clutchtape-week.png"'
    return resp
