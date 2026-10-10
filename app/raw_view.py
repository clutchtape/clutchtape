"""Raw data view (2026-10-10): every stored stat for each game of a session, one plain table.

The "Summary" view picks and styles a few numbers; this one shows everything the match row, the advanced stats,
the mode objectives and the medals hold. Objective and medal columns are built from what the session's games actually
contain, so a Slayer-only night has no flag columns. Refresh trigger: a new field stored by ingest/stat_depth."""
import json

import analytics

# (key, label, help, total) — total: "sum", "avg", "agg:<_agg key>" or None. Values come from _val().
BASE = [
    ("time", "Time", None, None), ("map", "Map", None, None), ("mode", "Mode", None, None),
    ("playlist", "Playlist", None, None), ("outcome", "Result", None, None), ("score", "Score", "Team – enemy", None),
    ("len", "Length", None, "sum"),
    ("kills", "K", "Kills", "sum"), ("deaths", "D", "Deaths", "sum"), ("assists", "A", "Assists", "sum"),
    ("kd", "K/D", None, "agg:kd"), ("kda", "KDA", "Kills + assists/3 - deaths", "agg:kda"),
    ("sc_pct", "SC%", "Share of the team's personal score", "agg:sc_pct"),
    ("personal_score", "Pers. score", "Personal score", "sum"), ("team_pscore", "Team score", "Team's total personal score", "sum"),
    ("damage_dealt", "Dmg dealt", None, "sum"), ("damage_taken", "Dmg taken", None, "sum"),
    ("dmg_diff", "Dmg ±", "Dealt minus taken", "sum"), ("dmg_pm", "Dmg/min", None, "agg:dmg_pm"),
    ("dmg_ka", "Dmg/KA", "Damage per kill + assist", "agg:dmg_ka"), ("dmg_share", "Dmg%", "Share of the team's damage", "agg:dmg_share"),
    ("team_dmg", "Team dmg", None, "sum"),
    ("shots_fired", "Shots", "Shots fired", "sum"), ("shots_hit", "Hits", "Shots hit", "sum"), ("accuracy", "Acc%", None, "agg:acc"),
    ("headshots", "HS kills", "Headshot kills", "sum"), ("hs_pct", "HS%", None, "agg:hs_pct"),
    ("max_spree", "Spree", "Best killing spree", "max"), ("callouts", "Callouts", "Callout assists", "sum"),
    ("melee_kills", "Melee K", None, "sum"), ("grenade_kills", "Grenade K", None, "sum"),
    ("power_weapon_kills", "Power K", "Power weapon kills", "sum"),
    ("expected_kills", "xKills", "Kills Halo expected for this lobby", "sum"), ("xk", "xK±", "Kills above expectation", "sum"),
    ("expected_deaths", "xDeaths", "Deaths Halo expected", "sum"), ("xd", "xD±", "Deaths avoided vs expectation", "sum"),
    ("life", "Life (s)", "Average life in seconds", "agg:life"), ("spawns", "Spawns", None, "sum"),
    ("suicides", "Suicides", None, "sum"), ("betrayals", "Betrayals", None, "sum"),
    ("vehicle_destroys", "Veh. destroys", None, "sum"), ("hijacks", "Hijacks", None, "sum"),
    ("driver_assists", "Driver A", "Driver assists", "sum"), ("emp_assists", "EMP A", "EMP assists", "sum"),
    ("objectives_completed", "Obj. done", "Objectives completed", "sum"),
    ("rounds", "Rounds", "Rounds won–lost(–tied)", None),
    ("team_mmr", "Team MMR", None, "avg"), ("enemy_mmr", "Enemy MMR", None, "avg"), ("mmr_edge", "Lobby ±", "Team MMR minus enemy", "avg"),
    ("pre_csr", "CSR before", None, None), ("post_csr", "CSR after", None, None), ("csr_d", "CSR ±", None, "sum"),
]
ADV = {"melee_kills", "grenade_kills", "power_weapon_kills", "expected_kills", "expected_deaths", "spawns", "suicides",
       "betrayals", "vehicle_destroys", "hijacks", "driver_assists", "emp_assists", "objectives_completed",
       "team_mmr", "enemy_mmr"}


def _json(v):
    try:
        return json.loads(v or "null") or {}
    except (ValueError, TypeError):
        return {}


def _num(v, nd=1):
    if v is None or v == "":
        return None
    if isinstance(v, float):
        v = round(v, nd)
        return int(v) if v == int(v) and abs(v) >= 100 else v
    return v


def _val(m, key):
    x = m.get("extra_stats") or _json(m.get("advanced"))
    if key == "time":
        return m["started_at"]
    if key == "len":
        return m.get("duration_s")
    if key == "score":
        if m.get("team_score") is None:
            return None
        return f"{round(m['team_score'])}–{round(m['enemy_score']) if m.get('enemy_score') is not None else '?'}"
    if key == "rounds":
        w, l, t = x.get("rounds_won"), x.get("rounds_lost"), x.get("rounds_tied")
        return None if w is None or (not w and not l and not t) else f"{w}–{l}" + (f"–{t}" if t else "")
    if key == "life":
        return _num(m.get("life") if m.get("life") is not None else x.get("average_life_duration"))
    if key == "accuracy":
        return _num(m.get("accuracy"))
    if key in ("expected_kills", "expected_deaths"):
        return _num(x.get(key))
    if key in ADV:
        return _num(x.get(key))
    return _num(m.get(key))


def build(matches):
    """-> dict(cols=[dict(key,label,help,group)], rows=[dict(match_id, outcome, cells=[...])], total=[...])"""
    if not matches:
        return None
    games = list(reversed(matches))                   # oldest first, like the game log
    objs, medals = {}, {}
    for m in games:
        for k, v in _json(m.get("objectives")).items():
            if k.startswith("pvp_stats:") or not isinstance(v, dict):
                continue
            objs.setdefault(k, (v.get("label") or k.split(":")[-1].replace("_", " ").title(), v.get("unit") or ""))
        for k, v in _json(m.get("medals")).items():
            medals[k] = medals.get(k, 0) + (v or 0)
    cols = [dict(key=k, label=lbl, help=h, total=t, group="core") for k, lbl, h, t in BASE]
    for k, (lbl, unit) in objs.items():
        cols.append(dict(key="obj:" + k, label=lbl + (f" ({unit})" if unit else ""), help="Objective stat", total="sum", group="obj"))
    cols.append(dict(key="medals_all", label="Medals", help="All medals in the game", total="sum", group="medal"))
    for name, _ in sorted(medals.items(), key=lambda kv: (-kv[1], kv[0])):
        cols.append(dict(key="medal:" + name, label=name, help="Medal", total="sum", group="medal"))
    rows = []
    for m in games:
        ob, md = _json(m.get("objectives")), _json(m.get("medals"))
        cells = []
        for c in cols:
            k = c["key"]
            if k.startswith("obj:"):
                v = (ob.get(k[4:]) or {}).get("value") if isinstance(ob.get(k[4:]), dict) else None
                cells.append(_num(v))
            elif k == "medals_all":
                cells.append(sum(md.values()) if md else None)
            elif k.startswith("medal:"):
                cells.append(md.get(k[6:], 0) if md else None)
            else:
                cells.append(_val(m, k))
        rows.append(dict(match_id=m["match_id"], outcome=(m.get("outcome") or "").lower(), cells=cells))
    agg = analytics._agg(matches)
    total = []
    for i, c in enumerate(cols):
        vals = [r["cells"][i] for r in rows if isinstance(r["cells"][i], (int, float))]
        t = c["total"]
        if not t or not vals:
            total.append(None)
        elif t == "sum":
            total.append(_num(sum(vals)))
        elif t == "max":
            total.append(max(vals))
        elif t == "avg":
            total.append(_num(sum(vals) / len(vals), 0))
        else:
            total.append(agg.get(t[4:]))
    return dict(cols=cols, rows=rows, total=total)
