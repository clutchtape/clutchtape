"""Mode-specific contributions. Missing data is never represented as zero."""
import json
import math

FIELDS = {
    'capture_the_flag_stats': [('flag_captures','Captures',''), ('flag_returns','Returns',''), ('flag_capture_assists','Capture assists',''), ('time_as_flag_carrier','Flag carry','s'), ('flag_grabs','Flag grabs',''), ('flag_steals','Flag steals',''), ('flag_secures','Flag secures',''), ('flag_carriers_killed','Flag carrier kills',''), ('kills_as_flag_carrier','Kills carrying flag','')],
    'oddball_stats': [('time_as_skull_carrier','Ball time','s'), ('skull_carriers_killed','Carrier kills',''), ('longest_time_as_skull_carrier','Longest ball hold','s'), ('skull_grabs','Ball grabs',''), ('kills_as_skull_carrier','Kills carrying ball','')],
    'zones_stats': [('stronghold_occupation_time','Zone time','s'), ('stronghold_captures','Zone captures',''), ('stronghold_defensive_kills','Zone defense kills',''), ('stronghold_offensive_kills','Zone offense kills',''), ('stronghold_secures','Zone secures','')],
}

def extract(stats):
    out = {}
    for group, fields in FIELDS.items():
        obj = stats.get(group) if isinstance(stats, dict) else getattr(stats, group, None)
        if obj is None:
            continue
        for key, label, unit in fields:
            value = obj.get(key) if isinstance(obj, dict) else getattr(obj, key, None)
            from stat_depth import number
            value = number(value)
            if hasattr(value, 'total_seconds'):
                value = value.total_seconds()
            if isinstance(value, (int, float)) and math.isfinite(value) and value >= 0:
                out[key] = dict(label=label, value=round(value, 1), unit=unit)
    raw=stats if isinstance(stats,dict) else stats.model_dump() if hasattr(stats,'model_dump') else vars(stats)
    from stat_depth import number
    for group,obj in raw.items():
        if group=='core_stats' or not group.endswith('_stats') or not isinstance(obj,dict):continue
        known={key for key,_,_ in FIELDS.get(group,[])}
        for key,raw_value in obj.items():
            if key in known:continue
            value=number(raw_value)
            if value is None:continue
            unit='s' if 'time' in key or 'duration' in key else ''
            out[group+':'+key]=dict(label=key.replace('_',' ').capitalize(),value=value,unit=unit)
    return out

def summarize(rows):
    totals, checked = {}, 0
    for row in rows:
        raw = row.get('objectives')
        if raw is None:
            continue
        try:
            data = json.loads(raw)
        except (ValueError, TypeError):
            continue
        checked += 1
        for key, val in data.items():
            if not isinstance(val, dict) or not isinstance(val.get('value'), (int, float)):
                continue
            entry = totals.setdefault(key, dict(label=val['label'], unit=val['unit'], value=0, games=0))
            entry['value'] = max(entry['value'], val['value']) if key=='longest_time_as_skull_carrier' else entry['value'] + val['value']; entry['games'] += 1
    for entry in totals.values():
        v = entry['value']
        entry['display'] = f'{int(v)//60}:{int(v)%60:02d}' if entry['unit'] == 's' else f'{v:g}'
    return dict(checked=checked, total=len(rows), metrics=list(totals.values()))
