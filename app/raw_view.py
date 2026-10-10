"""Raw data view (2026-10-10): every stored stat for each game of a session, one plain table.

The "Summary" view picks and styles a few numbers; this one shows everything the match row, the advanced stats,
the mode objectives and the medals hold. Objective and medal columns are built from what the session's games actually
contain, so a Slayer-only night has no flag columns. Refresh trigger: a new field stored by ingest/stat_depth."""
import json

import analytics

# (key, label, help, avg) — avg: "avg" (mean per game), "agg:<_agg key>" (session rate) or None. Values come from _val().
BASE = [
    ("time", "Time", None, None), ("map", "Map", None, None), ("mode", "Mode", None, None),
    ("playlist", "Playlist", None, None), ("outcome", "Result", None, None), ("score", "Score", "Team – enemy", None),
    ("len", "Length", None, "avg"),
    ("kills", "K", "Kills", "avg"), ("deaths", "D", "Deaths", "avg"), ("assists", "A", "Assists", "avg"),
    ("kd", "K/D", None, "agg:kd"), ("kda", "KDA", "Kills + assists/3 - deaths", "agg:kda"),
    ("sc_pct", "SC%", "Share of the team's personal score", "agg:sc_pct"),
    ("personal_score", "Pers. score", "Personal score", "avg"), ("team_pscore", "Team score", "Team's total personal score", "avg"),
    ("damage_dealt", "Dmg dealt", None, "avg"), ("damage_taken", "Dmg taken", None, "avg"),
    ("dmg_diff", "Dmg ±", "Dealt minus taken", "avg"), ("dmg_pm", "Dmg/min", None, "agg:dmg_pm"),
    ("dmg_ka", "Dmg/KA", "Damage per kill + assist", "agg:dmg_ka"), ("dmg_share", "Dmg%", "Share of the team's damage", "agg:dmg_share"),
    ("team_dmg", "Team dmg", None, "avg"),
    ("shots_fired", "Shots", "Shots fired", "avg"), ("shots_hit", "Hits", "Shots hit", "avg"), ("accuracy", "Acc%", None, "agg:acc"),
    ("headshots", "HS kills", "Headshot kills", "avg"), ("hs_pct", "HS%", None, "agg:hs_pct"),
    ("max_spree", "Spree", "Best killing spree", "avg"), ("callouts", "Callouts", "Callout assists", "avg"),
    ("melee_kills", "Melee K", None, "avg"), ("grenade_kills", "Grenade K", None, "avg"),
    ("power_weapon_kills", "Power K", "Power weapon kills", "avg"),
    ("expected_kills", "xKills", "Kills Halo expected for this lobby", "avg"), ("xk", "xK±", "Kills above expectation", "avg"),
    ("expected_deaths", "xDeaths", "Deaths Halo expected", "avg"), ("xd", "xD±", "Deaths avoided vs expectation", "avg"),
    ("life", "Life (s)", "Average life in seconds", "agg:life"), ("spawns", "Spawns", None, "avg"),
    ("suicides", "Suicides", None, "avg"), ("betrayals", "Betrayals", None, "avg"),
    ("vehicle_destroys", "Veh. destroys", None, "avg"), ("hijacks", "Hijacks", None, "avg"),
    ("driver_assists", "Driver A", "Driver assists", "avg"), ("emp_assists", "EMP A", "EMP assists", "avg"),
    ("objectives_completed", "Obj. done", "Objectives completed", "avg"),
    ("rounds", "Rounds", "Rounds won–lost(–tied)", None),
    ("team_mmr", "Team MMR", None, "avg"), ("enemy_mmr", "Enemy MMR", None, "avg"), ("mmr_edge", "Lobby ±", "Team MMR minus enemy", "avg"),
    ("pre_csr", "CSR before", None, None), ("post_csr", "CSR after", None, None), ("csr_d", "CSR ±", None, "avg"),
]
# Subtle heat (2026-10-10): "hi" = higher is better, "lo" = lower is better; other columns stay plain.
HI = {"kills", "assists", "kd", "kda", "sc_pct", "personal_score", "damage_dealt", "dmg_diff", "dmg_pm", "dmg_share",
      "shots_hit", "accuracy", "headshots", "hs_pct", "max_spree", "callouts", "melee_kills", "grenade_kills",
      "power_weapon_kills", "xk", "xd", "life", "vehicle_destroys", "hijacks", "driver_assists", "emp_assists",
      "objectives_completed", "csr_d"}
LO = {"deaths", "damage_taken", "dmg_ka", "suicides", "betrayals"}
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


def _tint(s):
    """0 (worst) .. 1 (best) -> a faint green/red background; the middle stays plain."""
    a = round(abs(s - .5) * 2 * .2, 3)
    if a < .03:
        return None
    return f"rgba(63,191,117,{a})" if s > .5 else f"rgba(224,96,79,{a})"


def _heat(cols, rows):
    for i, c in enumerate(cols):
        how = c["heat"]
        if not how:
            continue
        vals = [r["cells"][i] for r in rows if isinstance(r["cells"][i], (int, float))]
        if len(vals) < 3:
            continue
        lo, hi = min(vals), max(vals)
        if how == "medal":              # medals: only light up the games that earned more, never red
            lo = 0
        if hi == lo:
            continue
        for r in rows:
            v = r["cells"][i]
            if isinstance(v, (int, float)):
                x = (v - lo) / (hi - lo)
                if how == "lo":
                    x = 1 - x
                if how == "medal":
                    x = .5 + x / 2 if v else .5
                r["heat"][i] = _tint(x)


def _avg(cols, rows, src):
    """One average row: mean per game, or the session rate from analytics._agg for ratio columns."""
    agg = analytics._agg(src)
    out = []
    for i, c in enumerate(cols):
        vals = [r["cells"][i] for r in rows if isinstance(r["cells"][i], (int, float))]
        t = c["total"]
        if not t or not vals:
            out.append(None)
        elif t == "avg":
            m = sum(vals) / len(vals)
            out.append(_num(m, 0 if abs(m) >= 100 or c["key"] in ("len", "mmr_edge") else 1))   # 3056, not 3055.7
        else:
            out.append(agg.get(t[4:]))
    return dict(who=None, games=len(rows), wins=sum(r["outcome"] == "win" for r in rows),
                losses=sum(r["outcome"] == "loss" for r in rows), cells=out)


def build(matches, squad=None):
    """Player page: build(matches) with the session's match rows (newest first).
    Squad page: build(night, squad=[(pid, gamertag), ...]) with the night's games, each holding members {pid: row};
    one table row per player per game, a Player column, and one average row per player.
    -> dict(cols=[dict(key,label,help,group,heat)], rows=[dict(match_id,outcome,gnum,who,cells,heat)], avg=[dict(...)])"""
    if not matches:
        return None
    entries = []                                      # (game number, match row, gamertag) oldest first, like the game log
    for n, g in enumerate(reversed(matches), 1):
        if squad:
            entries += [(n, g["members"][pid], gt) for pid, gt in squad if pid in g["members"]]
        else:
            entries.append((n, g, None))
    objs, medals = {}, {}
    for _, m, _ in entries:
        for k, v in _json(m.get("objectives")).items():
            if k.startswith("pvp_stats:") or not isinstance(v, dict):
                continue
            objs.setdefault(k, (v.get("label") or k.split(":")[-1].replace("_", " ").title(), v.get("unit") or ""))
        for k, v in _json(m.get("medals")).items():
            medals[k] = medals.get(k, 0) + (v or 0)
    cols = [dict(key="who", label="Player", help=None, total=None, group="core", heat=None)] if squad else []
    cols += [dict(key=k, label=lbl, help=h, total=t, group="core", heat="hi" if k in HI else "lo" if k in LO else None)
             for k, lbl, h, t in BASE]
    for k, (lbl, unit) in objs.items():
        cols.append(dict(key="obj:" + k, label=lbl + (f" ({unit})" if unit else ""), help="Objective stat", total="avg", group="obj", heat="hi"))
    cols.append(dict(key="medals_all", label="Medals", help="All medals in the game", total="avg", group="medal", heat="hi"))
    for name, _ in sorted(medals.items(), key=lambda kv: (-kv[1], kv[0])):
        cols.append(dict(key="medal:" + name, label=name, help="Medal", total="avg", group="medal", heat="medal"))
    rows = []
    for n, m, who in entries:
        ob, md = _json(m.get("objectives")), _json(m.get("medals"))
        cells = []
        for c in cols:
            k = c["key"]
            if k == "who":
                cells.append(who)
            elif k.startswith("obj:"):
                v = (ob.get(k[4:]) or {}).get("value") if isinstance(ob.get(k[4:]), dict) else None
                cells.append(_num(v))
            elif k == "medals_all":
                cells.append(sum(md.values()) if md else None)
            elif k.startswith("medal:"):
                cells.append(md.get(k[6:], 0) if md else None)
            else:
                cells.append(_val(m, k))
        rows.append(dict(match_id=m["match_id"], outcome=(m.get("outcome") or "").lower(), gnum=n, who=who,
                         cells=cells, heat=[None] * len(cells), src=m))
    _heat(cols, rows)
    if squad:
        avg = []
        for _, gt in squad:
            mine = [r for r in rows if r["who"] == gt]
            if mine:
                avg.append(dict(_avg(cols, mine, [r["src"] for r in mine]), who=gt))
    else:
        avg = [_avg(cols, rows, matches)]
    for r in rows:
        del r["src"]
    return dict(cols=cols, rows=rows, avg=avg, squad=bool(squad))
