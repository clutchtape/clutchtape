"""Optional Halo fields. Missing values remain unknown, including in old history."""
import json
import math
import re
import db

CORE = ('average_life_duration', 'melee_kills', 'grenade_kills', 'power_weapon_kills',
        'vehicle_destroys', 'driver_assists', 'hijacks', 'emp_assists', 'spawns',
        'suicides', 'betrayals', 'objectives_completed', 'rounds_won', 'rounds_lost', 'rounds_tied')

def number(value):
    if hasattr(value, 'total_seconds'): value = value.total_seconds()
    if isinstance(value, str) and value.startswith('P'):
        m = re.fullmatch(r'PT(?:(\d+(?:\.\d+)?)H)?(?:(\d+(?:\.\d+)?)M)?(?:(\d+(?:\.\d+)?)S)?', value)
        if m: value = sum(float(v or 0)*s for v,s in zip(m.groups(), (3600,60,1)))
    return round(value, 3) if isinstance(value, (int,float)) and not isinstance(value,bool) and math.isfinite(value) and value >= 0 else None


def extract(core):
    out={k:v for k in CORE if (v:=number(core.get(k) if isinstance(core,dict) else getattr(core,k,None))) is not None}
    if out:out['_version']=2
    return out


def skill(result):
    out = {}
    perf = getattr(result, 'stat_performances', None)
    for key in ('kills','deaths'):
        value=number(getattr(getattr(perf,key,None),'expected',None))
        if value is not None:out['expected_'+key]=value
    value=number(getattr(result,'team_mmr',None))
    if value is not None:out['team_mmr']=value
    others=[number(v) for k,v in (getattr(result,'team_mmrs',None) or {}).items() if str(k)!=str(getattr(result,'team_id',None))]
    others=[v for v in others if v is not None]
    if len(others)==1:out['enemy_mmr']=others[0]
    return out


def enrich(rows, xuid):
    """Reuse existing cached match bodies in bounded batches; no upstream calls."""
    missing=[]
    for r in rows:
        try:r['extra']=json.loads(r.get('advanced') or '{}')
        except (ValueError,TypeError):r['extra']={}
        if 'advanced' in r and r['extra'].get('_version',0)<2:missing.append(r)
    for start in range(0,len(missing),100):
        batch=missing[start:start+100]
        keys=[prefix+r['match_id'] for r in batch for prefix in ('matchraw:','matchdetail:')]
        cache={r['k']:json.loads(r['v']) for r in db.q('SELECT k,v FROM kv WHERE k IN ('+','.join('?' for _ in keys)+')',*keys)}
        for r in batch:
            raw=cache.get('matchraw:'+r['match_id']);detail=cache.get('matchdetail:'+r['match_id'])
            core={}
            if raw:
                p=next((p for p in raw.get('players',[]) if re.sub(r'\D','',p.get('player_id',''))==str(xuid)),{})
                splits=p.get('player_team_stats',[])
                if splits:
                    stats=splits[0].get('stats',{});core=stats.get('core_stats',{})
                    import objectives
                    r['objectives']=json.dumps(objectives.extract(stats))
                    team=next((t for t in raw.get('teams',[]) if t.get('team_id')==r.get('team_id')),{})
                    damage=number(team.get('stats',{}).get('core_stats',{}).get('damage_dealt'))
                    if damage is not None:r['extra']['team_damage']=damage
            elif detail:
                p=next((p for p in detail.get('players',[]) if p.get('xuid')==str(xuid)),{})
                if p.get('splits'):core=p['splits'][0].get('core',{})
            r['extra'].update(extract(core))
