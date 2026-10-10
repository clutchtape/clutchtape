"""One filtered dataset feeds summaries, charts and their accessible tables."""
from collections import defaultdict
from statistics import mean
import json
import analytics
import objectives

METRICS = [   # display order (2026-10-09): SC%, KDA, damage first
    ('sc_pct','Team score share','%'),
    ('kda','KDA / game',''),
    ('dmg_pm','Damage / minute',''),
    ('dmg_ka','DMG / (kills + assists)',''),
    ('dmg_diff','Damage difference / game',''),
    ('kd','K/D',''),
    ('kills','Kills / game',''),
    ('deaths','Deaths / game',''),
    ('assists','Assists / game',''),
    ('team_damage_share','Team damage share','%'),
    ('callouts','Callout assists / game',''),
    ('acc','Accuracy','%'),
    ('life','Average life','s'),
    ('dmg_dealt','Damage dealt / game',''),
    ('dmg_taken','Damage taken / game',''),
    ('dmg_death','Damage / death',''),
    ('shots_fired','Shots fired / game',''),
    ('shots_hit','Shots hit / game',''),
    ('headshots','Headshot kills / game',''),
    ('hs_pct','Headshot kill rate','%'),
    ('melee','Melee kills / game',''),
    ('grenade','Grenade kills / game',''),
    ('power','Power weapon kills / game',''),
    ('death_pm','Deaths / minute',''),
    ('spree','Best spree / game',''),
    ('score','Personal score / game',''),
    ('game_score','Game score / game',''),
    ('duration','Duration / game','s'),
    ('medals','Medals / game',''),
    ('spawns','Spawns / game',''),
    ('suicides','Suicides / game',''),
    ('betrayals','Betrayals / game',''),
    ('vehicles','Vehicles destroyed / game',''),
    ('drivers','Driver assists / game',''),
    ('hijacks','Hijacks / game',''),
    ('emp','EMP assists / game',''),
    ('obj_completed','Objectives completed / game',''),
    ('rounds_won','Rounds won / game',''),
    ('rounds_lost','Rounds lost / game',''),
    ('rounds_tied','Rounds tied / game',''),
]
EXTRA={'life':'average_life_duration','melee':'melee_kills','grenade':'grenade_kills','power':'power_weapon_kills',
       'spawns':'spawns','suicides':'suicides','betrayals':'betrayals','vehicles':'vehicle_destroys','drivers':'driver_assists',
       'hijacks':'hijacks','emp':'emp_assists','obj_completed':'objectives_completed',
       'rounds_won':'rounds_won','rounds_lost':'rounds_lost','rounds_tied':'rounds_tied'}
BASE={'kills':'kills','deaths':'deaths','assists':'assists','dmg_dealt':'damage_dealt','dmg_taken':'damage_taken',
      'game_score':'score','duration':'duration_s','callouts':'callouts','shots_fired':'shots_fired','shots_hit':'shots_hit','headshots':'headshots','score':'personal_score','spree':'max_spree'}
KEYS=['kills','deaths','assists','kd','kda','dmg_ka','dmg_diff','callouts','dmg_pm','acc','sc_pct','life']
DAMAGE=['dmg_dealt','dmg_taken','dmg_diff','dmg_pm','dmg_ka','dmg_death','team_damage_share']
COMBAT=['kills','deaths','assists','kd','kda','callouts','acc','shots_fired','shots_hit','headshots','hs_pct','melee','grenade','power','death_pm','life','spree']
SHORT={'kills':'K','deaths':'D','assists':'A','kd':'K/D','kda':'KDA','dmg_ka':'DMG/KA','dmg_diff':'DMG ±','callouts':'CALL',
       'dmg_pm':'DMG/M','dmg_dealt':'DMG +','dmg_taken':'DMG −','dmg_death':'DMG/D','team_damage_share':'DMG%T',
       'acc':'ACC','shots_fired':'FIRED','shots_hit':'HIT','headshots':'HS','hs_pct':'HS%','melee':'MELEE','grenade':'NADE',
       'power':'POWER','death_pm':'D/M','life':'LIFE','spree':'SPREE','score':'SCORE','sc_pct':'SC%','medals':'MEDALS',
       'spawns':'SPAWNS','suicides':'SUIC','betrayals':'BETR','vehicles':'VEH','drivers':'DRVA','hijacks':'HIJ','emp':'EMP',
       'obj_completed':'OBJ','game_score':'GAME SCORE','duration':'TIME','rounds_won':'RND W','rounds_lost':'RND L','rounds_tied':'RND T'}

def group_for(key):
    return 'damage' if key in DAMAGE else 'combat' if key in COMBAT else 'objectives' if key.startswith('obj:') else 'other'

def measure(rows):
    if not rows:return {}
    agg=analytics._agg(rows);out={k:agg.get(k) for k in ('dmg_pm','acc','kda','kd','hs_pct','sc_pct')}
    valid=[r for r in rows if r.get('duration_s') and r.get('deaths') is not None]
    out['death_pm']=round(sum(r['deaths'] for r in valid)/(sum(r['duration_s'] for r in valid)/60),2) if valid else None
    for key,field in dict(EXTRA,**BASE).items():
        values=[r.get('extra',{}).get(field) if key in EXTRA else r.get(field) for r in rows]
        values=[v for v in values if v is not None]
        out[key]=round(mean(values),2) if values else None;out[key+'_n']=len(values)
        if key not in ('life','spree'):out[key+'_total']=round(sum(values),2) if values else None
    for key,fields in [('dmg_ka',('kills','assists')),('dmg_death',('deaths',))]:
        valid=[r for r in rows if r.get('damage_dealt') is not None and all(r.get(f) is not None for f in fields)]
        denominator=sum(sum(r[f] for f in fields) for r in valid)
        out[key]=round(sum(r['damage_dealt'] for r in valid)/denominator,2) if denominator else None;out[key+'_n']=len(valid)
    valid=[r for r in rows if r.get('damage_dealt') is not None and r.get('damage_taken') is not None]
    out['dmg_diff']=round(mean(r['damage_dealt']-r['damage_taken'] for r in valid),2) if valid else None;out['dmg_diff_n']=len(valid)
    out['dmg_diff_total']=sum(r['damage_dealt']-r['damage_taken'] for r in valid) if valid else None
    valid=[r for r in rows if r.get('extra',{}).get('team_damage') and r.get('damage_dealt') is not None]
    out['team_damage_share']=round(100*sum(r['damage_dealt'] for r in valid)/sum(r['extra']['team_damage'] for r in valid),2) if valid else None;out['team_damage_share_n']=len(valid)
    medals=[]
    for r in rows:
        if r.get('medals') is not None:
            try:medals.append(sum(json.loads(r['medals']).values()))
            except (TypeError,ValueError):pass
    out['medals']=round(mean(medals),2) if medals else None;out['medals_n']=len(medals)
    out['medals_total']=sum(medals) if medals else None
    for k,v in _objective_values(rows).items():
        key='obj:'+k
        out[key]=round(v['value'] if k=='longest_time_as_skull_carrier' else v['value']/v['games'],2)
        out[key+'_n']=v['games'];out[key+'_total']=v['value']
    return out


def build(players, matches, histories, baseline='previous', sessions=None, idx=0):
    rows=[r for m in matches for r in (m.get('members') or {m['player_id']:m}).values()]
    start=min((r['started_at'] for r in rows),default=0)
    prior_sessions=[s for s in (sessions or []) if max(m['started_at'] for m in s['matches'])<start][:5 if baseline=='recent' else 1]
    prior_ids={m['match_id'] for s in prior_sessions for m in s['matches']}
    objective_fields={}
    for history in histories.values():objective_fields.update(_objective_values(history))
    metric_defs=METRICS+[("obj:"+k,v['label']+(' (best)' if k=='longest_time_as_skull_carrier' else ' / game'),v['unit']) for k,v in objective_fields.items()]
    reports=[]; series=[]; ranks=[]; bars=[]; expectation=[]; objective_bars=[];medal_rows=[]
    for p in players:
        rs=sorted([r for r in rows if r['player_id']==p['id']],key=lambda r:r['started_at'])
        modes={(r['playlist'],r['mode']) for r in rs}
        before=[r for r in histories[p['id']] if r['started_at']<start and (r['playlist'],r['mode']) in modes and
                (r['started_at']>=start-30*86400 if baseline=='month' else r['match_id'] in prior_ids)]
        a,b=measure(rs),measure(before)
        metrics=[]
        for key,label,unit in metric_defs:
            value,old=a.get(key),b.get(key)
            metrics.append(dict(key=key,label=label,short=SHORT.get(key,label.replace(' / game','')),group=group_for(key),key_stat=key in KEYS,unit=unit,value=value,old=old,total=a.get(key+'_total'),old_total=b.get(key+'_total'),n=a.get(key+'_n',0 if key.startswith('obj:') else len(rs)),baseline_n=b.get(key+'_n',0 if key.startswith('obj:') else len(before)),delta=round(value-old,2) if value is not None and old is not None else None))
        medal_counts=defaultdict(int)
        for r in rs:
            try:
                for name,count in json.loads(r.get('medals') or '{}').items():medal_counts[name]+=count
            except (ValueError,TypeError):pass
        medal_rows.extend(dict(player=p['gamertag'],name=name,count=count) for name,count in sorted(medal_counts.items(),key=lambda item:-item[1]))
        reports.append(dict(name=p['gamertag'],games=len(rs),baseline=len(before),metrics=metrics))
        points=[]; ranked=defaultdict(list)
        for i,r in enumerate(rs):
            link='/match/'+r['match_id']+'?player='+p['slug']
            vals=measure([r]);rolling=measure(rs[max(0,i-4):i+1])
            metric_keys={k for k,_,_ in metric_defs}
            vals={k:v for k,v in vals.items() if k in metric_keys};rolling={k:v for k,v in rolling.items() if k in metric_keys}
            points.append(dict(label=r['map']+' · '+r['mode'],map=r['map'],mode=r['mode'],at=r['started_at'],outcome=r['outcome'],url=link,values=vals,rolling=rolling))
            if r.get('post_csr') and r.get('pre_csr'):
                ranked[r['playlist']].append(dict(value=r['post_csr'],pre=r['pre_csr'],url=link,at=r['started_at'],label=r['map'],outcome=r['outcome']))
            extra=r.get('extra',{})
            if extra.get('expected_kills') is not None or extra.get('expected_deaths') is not None:
                expectation.append(dict(name=p['gamertag'],map=r['map'],url=link,at=r['started_at'],kills=r['kills'],deaths=r['deaths'],expected_kills=extra.get('expected_kills'),expected_deaths=extra.get('expected_deaths'),team_mmr=extra.get('team_mmr'),enemy_mmr=extra.get('enemy_mmr')))
        series.append(dict(name=p['gamertag'],points=points))
        for playlist,pts in ranked.items():
            ranks.append(dict(name=p['gamertag'],playlist=playlist,points=pts,current=pts[-1]['value'],peak=max([x['value'] for x in pts]+[x['pre'] for x in pts]),delta=sum(x['value']-x['pre'] for x in pts)))
        # Team share is weighted by each match's whole team, not just tracked players.
        total_damage=sum(r.get('damage_dealt') or 0 for r in rs)
        bars.append(dict(name=p['gamertag'],damage=total_damage,assists=sum(r.get('assists') or 0 for r in rs),games=len(rs),damage_share=round(100*total_damage/sum(r['extra']['team_damage'] for r in rs),1) if rs and all(r.get('extra',{}).get('team_damage') for r in rs) else None))
        for k,v in _objective_values(rs).items():objective_bars.append(dict(key=k,name=p['gamertag'],**v))
    # rows: best score share first; players with no games in the selection last
    def _sc(r):
        m=next((x for x in r['metrics'] if x['key']=='sc_pct'),None)
        return (r['games']>0, m['value'] if m and m['value'] is not None else -1)
    reports.sort(key=_sc,reverse=True)
    return dict(medals=medal_rows,players=reports,series=series,ranks=ranks,expectation=expectation,bars=bars,objectives=objective_bars,metrics=[dict(key=k,label=l,short=SHORT.get(k,l.replace(' / game','')),group=group_for(k),key_stat=k in KEYS,unit=u) for k,l,u in metric_defs],baseline=baseline,player_games=len(rows),scope_games=len(matches),coverage=sum(bool(r.get('extra')) for r in rows))


def _objective_values(rows):
    totals={}
    for r in rows:
        try: data=json.loads(r.get('objectives') or '{}')
        except (ValueError,TypeError):continue
        for k,v in data.items():
            if not isinstance(v,dict) or not isinstance(v.get('value'),(int,float)):continue
            t=totals.setdefault(k,dict(label=v['label'],unit=v['unit'],value=0,games=0))
            t['value']=max(t['value'],v['value']) if k=='longest_time_as_skull_carrier' else t['value']+v['value'];t['games']+=1
    return totals


def explanations(board):
    out=[]
    for p in board['analysis']['players']:
        m=next((m for m in p['metrics'] if m['key']=='dmg_pm'),None)
        if not m or m['delta'] is None or p['games']<2 or p['baseline']<5:continue
        out.append(dict(title=p['name']+' · damage output',text=f"{m['value']} damage/min, {m['delta']:+g} versus the selected baseline ({p['games']} selected games; {p['baseline']} earlier games with matching playlists and modes).",url='#progress'))
    return out[:4]
