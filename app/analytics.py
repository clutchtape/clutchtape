import capacity
"""Everything the profile page shows, computed from one player's rows in SQLite."""
import json
import time
from collections import defaultdict

import db
import teamwork

SESSION_GAP_S = 90 * 60


def clean_map(n):
    n = (n or "").strip()
    for suf in (" - Ranked", " - Tactical", " - Social", " - Arena"):
        if n.endswith(suf):
            n = n[: -len(suf)]
    return n or None


def clean_mode(n):
    n = (n or "").strip()
    for pre in ("Ranked:", "Arena:", "Tactical:", "Social:", "Assault:"):
        if n.startswith(pre):
            n = n[len(pre):]
    return n or None


KINDS = [("ranked", "Ranked"), ("custom", "Customs"), ("all", "All")]   # 2026-10-09: Ranked (Ranked Arena) is the default view; "mm" stays valid for old links


MIN_GAME_S = 120     # shorter = quit / remake / lobby crash (2026-10-09: 347 of 3,484 games, incl. 0-0 34s "Wins"); never counted


def kind_ok(r, kind):
    """Game type filter: playlist missing = custom/private game, 'ranked' flag = ranked, anything else = matchmaking.
    Games shorter than MIN_GAME_S are dropped under every filter (unknown length is kept)."""
    dur = r["duration_s"] if "duration_s" in r.keys() else None      # works for dicts and sqlite3.Row
    if dur is not None and dur < MIN_GAME_S:
        return False
    if kind == "ranked":
        return bool(r["ranked"])
    if kind == "mm":
        return r["playlist"] is not None
    if kind == "custom":
        return r["playlist"] is None
    return True


def kind_sql(kind):
    return "COALESCE(m.duration_s, 999) >= %d AND " % MIN_GAME_S + {"ranked": "m.ranked=1", "mm": "m.playlist IS NOT NULL", "custom": "m.playlist IS NULL"}.get(kind, "1=1")


def kda(k, d, a):
    """Halo's KDA: kills + assists/3 - deaths."""
    return (k or 0) + (a or 0) / 3.0 - (d or 0)


def derive(r):
    """Per-game advanced metrics (the same ones the main Halo site tracks)."""
    k, d, a_ = r["kills"] or 0, r["deaths"] or 0, r["assists"] or 0
    mins = (r["duration_s"] or 0) / 60.0
    r["kda"] = round(kda(k, d, a_), 1)
    r["kd"] = round(k / max(1, d), 2)
    r["dmg_diff"] = (r["damage_dealt"] or 0) - (r["damage_taken"] or 0)
    r["dmg_pm"] = round((r["damage_dealt"] or 0) / mins) if mins >= 1 else None
    r["sc_pct"] = round(100 * (r["personal_score"] or 0) / r["team_pscore"], 1) if r.get("team_pscore") else None
    r["hs_pct"] = round(100 * (r["headshots"] or 0) / k) if k else None
    r["dmg_ka"] = round((r["damage_dealt"] or 0) / (k + a_)) if (k + a_) and r.get("damage_dealt") is not None else None
    # Advanced (stored by ingest/stat_depth; absent on old or custom games, shown as unknown, never zero)
    try:
        x = json.loads(r.get("advanced") or "{}") or {}
    except (ValueError, TypeError):
        x = {}
    r["extra_stats"] = x
    pre, post = r.get("pre_csr"), r.get("post_csr")
    r["csr_d"] = post - pre if pre is not None and post is not None and pre > 0 else None
    xk, xd = x.get("expected_kills"), x.get("expected_deaths")
    r["xk"] = round(k - xk, 1) if xk is not None else None            # kills above Halo's expectation for this lobby
    r["xd"] = round(xd - d, 1) if xd is not None else None            # deaths below expectation (positive = good)
    td = r["team_dmg"] = x.get("team_damage")
    r["dmg_share"] = round(100 * (r["damage_dealt"] or 0) / td) if td else None
    r["life"] = round(x["average_life_duration"]) if x.get("average_life_duration") is not None else None
    tm, em = x.get("team_mmr"), x.get("enemy_mmr")
    r["mmr_edge"] = round(tm - em) if tm is not None and em is not None else None
    r["obj"] = objective_line(r.get("objectives"), r.get("mode"))
    return r


# Headline objective stat: (key, short label, seconds?). KOTH and Strongholds both report stronghold_* fields.
OBJ_HEADLINE = {"ctf": ("flag_captures", "caps", False), "oddball": ("time_as_skull_carrier", "ball", True),
                "koth": ("stronghold_occupation_time", "hill", True), "strongholds": ("stronghold_captures", "zone caps", False)}


def objective_line(raw, mode):
    """'2 caps', '71s ball', '45s hill', '5 zone caps' or None (non-objective modes, or no data)."""
    m = (mode or "").lower()
    fam = "ctf" if "ctf" in m else "oddball" if "oddball" in m else "koth" if "hill" in m else "strongholds" if "stronghold" in m else None
    if not fam:
        return None
    try:
        o = json.loads(raw or "{}") or {}
    except (ValueError, TypeError):
        return None
    key, label, secs = OBJ_HEADLINE[fam]
    v = (o.get(key) or {}).get("value")
    if v is None:
        return None
    return f"{round(v)}s {label}" if secs else f"{round(v)} {label}"


MULTI_MEDALS = ("Double Kill", "Triple Kill", "Overkill", "Killtacular", "Killtrocity", "Killamanjaro", "Killtastrophe",
                "Killpocalypse", "Killionaire")
MEDAL_GROUPS = {"perfect_pg": ("Perfect",), "multi_pg": MULTI_MEDALS, "snipe_pg": ("Snipe", "No Scope"),
                "killjoy_pg": ("Killjoy",), "reversal_pg": ("Reversal",)}
# per game OF THAT MODE: (key, mode word, objective field)
OBJ_AVG = (("caps_pg", "ctf", "flag_captures"), ("returns_pg", "ctf", "flag_returns"), ("ball_pg", "oddball", "time_as_skull_carrier"),
           ("hill_pg", "hill", "stronghold_occupation_time"), ("zcaps_pg", "stronghold", "stronghold_captures"))


def _medal_obj(rows):
    """Medals per game (Perfect, multikills, snipes, killjoys, reversals, all medals), callouts per game, and objective
    averages per game of the matching mode (flag caps/returns per CTF game, ball time per Oddball game, hill time per
    KOTH game, zone caps per Strongholds game). Unknown stays None."""
    n = len(rows)
    out = {k: 0 for k in MEDAL_GROUPS}
    allm, have = 0, 0
    for r in rows:
        try:
            m = json.loads(r.get("medals") or "null")
        except (ValueError, TypeError):
            m = None
        if m is None or (not m and r.get("playlist") is None):   # custom games often carry no medal data: unknown, not zero
            continue
        have += 1
        allm += sum(m.values())
        for key, names in MEDAL_GROUPS.items():
            out[key] += sum(m.get(x, 0) for x in names)
    out = {k: (round(v / have, 2) if have else None) for k, v in out.items()}
    out["medals_pg"] = round(allm / have, 1) if have else None
    out["callouts_pg"] = round(sum(r.get("callouts") or 0 for r in rows) / n, 1) if n else None
    for key, word, field in OBJ_AVG:
        vals = []
        for r in rows:
            if word not in (r.get("mode") or "").lower():
                continue
            try:
                v = ((json.loads(r.get("objectives") or "{}") or {}).get(field) or {}).get("value")
            except (ValueError, TypeError, AttributeError):
                v = None
            if v is not None:
                vals.append(v)
        out[key] = round(sum(vals) / len(vals), 1) if vals else None
    return out


def _mean(vals, nd=1):
    vals = [v for v in vals if v is not None]
    if not vals:
        return None
    v = round(sum(vals) / len(vals), nd)
    return int(v) if nd == 0 else v


def _agg(rows):
    n = len(rows)
    if not n:
        return {"games": 0}
    w = sum(1 for r in rows if r["outcome"] == "Win")
    l = sum(1 for r in rows if r["outcome"] == "Loss")
    k = sum(r["kills"] or 0 for r in rows); d = sum(r["deaths"] or 0 for r in rows); a = sum(r["assists"] or 0 for r in rows)
    fired = sum(r["shots_fired"] or 0 for r in rows); hit = sum(r["shots_hit"] or 0 for r in rows)
    return {
        "games": n, "wins": w, "losses": l, "win_pct": round(100 * w / max(1, w + l), 1),
        "kd": round(k / max(1, d), 2), "kda": round(kda(k, d, a) / n, 1),
        "kills_pg": round(k / n, 1), "deaths_pg": round(d / n, 1), "assists_pg": round(a / n, 1),
        "acc": round(100 * hit / fired, 1) if fired else None,
        "dmg_pg": round(sum(r["damage_dealt"] or 0 for r in rows) / n),
        "score_pg": round(sum(r["personal_score"] or 0 for r in rows) / n),
        "best_spree": max((r["max_spree"] or 0) for r in rows),
        "dmg_diff_pg": round(sum((r["damage_dealt"] or 0) - (r["damage_taken"] or 0) for r in rows) / n),
        "dmg_pm": (lambda m: round(sum(r["damage_dealt"] or 0 for r in rows) / m) if m >= 1 else None)(
            sum((r["duration_s"] or 0) for r in rows) / 60.0),
        "sc_pct": (lambda ts: round(100 * sum(r["personal_score"] or 0 for r in rows if r.get("team_pscore")) / ts, 1)
                   if ts else None)(sum(r["team_pscore"] or 0 for r in rows)),
        "hs_pct": round(100 * sum(r["headshots"] or 0 for r in rows) / k) if k else None,
        # advanced: averages over the games that report each value
        "xk_pg": _mean(r.get("xk") for r in rows), "xd_pg": _mean(r.get("xd") for r in rows),
        "dmg_share": (lambda gs: round(100 * sum(r["damage_dealt"] or 0 for r in gs) / sum(r["team_dmg"] for r in gs)) if gs else None)(
            [r for r in rows if r.get("team_dmg")]),
        "life": _mean((r.get("life") for r in rows), 0),
        "mmr_edge": _mean((r.get("mmr_edge") for r in rows), 0),
        "csr_net": sum(r["csr_d"] for r in rows if r.get("csr_d") is not None) if any(r.get("csr_d") is not None for r in rows) else None,
        "upsets": (lambda dogs: {"games": len(dogs), "wins": sum(1 for r in dogs if r["outcome"] == "Win")} if dogs else None)(
            [r for r in rows if (r.get("mmr_edge") or 0) <= -25 and r["outcome"] in ("Win", "Loss")]),
        "spree": max((r["max_spree"] or 0) for r in rows),
        "dmg_ka": (lambda ka: round(sum(r["damage_dealt"] or 0 for r in rows) / ka) if ka else None)(k + a),
        **_medal_obj(rows),
    }


def sessions(rows):
    """Group matches (newest first) into nights separated by > SESSION_GAP_S of inactivity."""
    out, cur = [], []
    for r in rows:
        if cur and cur[-1]["started_at"] - r["started_at"] > SESSION_GAP_S:
            out.append(cur); cur = []
        cur.append(r)
    if cur:
        out.append(cur)
    res = []
    for g in out:
        a = _agg(g)
        res.append({"start": g[-1]["started_at"], "end": g[0]["started_at"], "games": len(g),
                    "record": f"{a['wins']}-{a['losses']}", "kda": a["kda"], "kd": a["kd"], "win_pct": a["win_pct"],
                    "matches": g, "adv": a})
    return res


def group(rows, key, limit=12):
    buckets = defaultdict(list)
    for r in rows:
        if r[key]:
            buckets[r[key]].append(r)
    out = []
    for name, rs in buckets.items():
        a = _agg(rs)
        out.append({"name": name, **a})
    out.sort(key=lambda x: (-x["games"], x["name"]))
    return out[:limit]


def medals(rows, top=14):
    tot = defaultdict(int)
    for r in rows:
        try:
            for k, v in json.loads(r["medals"] or "{}").items():
                tot[k] += v
        except ValueError:
            pass
    return sorted(tot.items(), key=lambda kv: -kv[1])[:top]


def csr_series(rows):
    """Rating over time for the playlist the player ranks in most (mixing playlists made the line spiky)."""
    cnt = defaultdict(int)
    for r in rows:
        if r["post_csr"]:
            cnt[r["playlist"]] += 1
    if not cnt:
        return []
    main = max(cnt, key=cnt.get)
    return [(r["started_at"], r["post_csr"]) for r in reversed(rows) if r["playlist"] == main and r["post_csr"]]


def streaks(rows):
    """(current, longest_win) over Win/Loss games, newest first. current>0 = win streak, <0 = loss streak."""
    wl = [r["outcome"] for r in rows if r["outcome"] in ("Win", "Loss")]
    cur = 0
    for o in wl:
        if cur == 0:
            cur = 1 if o == "Win" else -1
        elif (cur > 0) == (o == "Win"):
            cur += 1 if cur > 0 else -1
        else:
            break
    best = run = 0
    for o in reversed(wl):
        run = run + 1 if o == "Win" else 0
        best = max(best, run)
    return cur, best


def insights(rows, maps, sess):
    out = []
    cand = [m for m in maps if m["games"] >= 5 and m.get("win_pct") is not None]
    if cand:
        b = max(cand, key=lambda m: (m["win_pct"], m["kda"]))
        out.append({"label": "Best map", "big": b["name"], "sub": f"{b['win_pct']}% wins over {b['games']} games"})
        w = min(cand, key=lambda m: (m["win_pct"], m["kda"]))
        if w["name"] != b["name"]:
            out.append({"label": "Toughest map", "big": w["name"], "sub": f"{w['win_pct']}% wins over {w['games']} games"})
    nights = [x for x in sess if x["games"] >= 3]
    if nights:
        n = max(nights, key=lambda x: x["kda"])
        out.append({"label": "Best night", "big": n["record"], "sub": f"KDA {n['kda']} on {datetime_fmt(n['start'])}",
                    "fresh": _fresh(n["start"])})
    _, longest = streaks(rows)
    if longest >= 3:
        out.append({"label": "Longest win streak", "big": f"{longest} in a row", "sub": "in the games we loaded"})
    decent = [r for r in rows if (r["duration_s"] or 0) >= 180]
    if decent:
        g = max(decent, key=lambda r: kda(r["kills"], r["deaths"], r["assists"]))
        out.append({"label": "Best game", "big": f"{g['kills']}/{g['deaths']}/{g['assists']}",
                    "sub": f"{g['map'] or 'Unknown map'} · {datetime_fmt(g['started_at'])}", "match": g["match_id"],
                    "fresh": _fresh(g["started_at"])})
    return out


def _fresh(ts, days=7):
    """A record set in the last week gets a NEW chip and a one-time shine on the Records tab (2026-10-10)."""
    import time as _t
    return bool(ts) and _t.time() - ts < days * 86400


def datetime_fmt(ts):
    import datetime as _d
    return _d.datetime.fromtimestamp(ts).strftime("%b %-d")


def moments(player_ids, limit=12, kind="mm"):
    """Best auto-detected plays for one or more players (squad = several), joined with the match they came from."""
    ph = ",".join("?" * len(player_ids))
    rows = db.q(f"SELECT mo.*, m.map, m.mode, m.outcome, m.started_at AS match_started, p.gamertag "
                f"FROM moments mo JOIN matches m ON m.player_id=mo.player_id AND m.match_id=mo.match_id "
                f"JOIN players p ON p.id=mo.player_id WHERE mo.player_id IN ({ph}) "
                f"AND {kind_sql(kind)} AND COALESCE(m.outcome,'') NOT IN ('Dnf','Left') AND lower(COALESCE(m.map,'')||' '||COALESCE(m.mode,'')||' '||COALESCE(m.playlist,'')) NOT LIKE '%bot%' "
                f"AND lower(COALESCE(m.map,'')||COALESCE(m.mode,'')) NOT LIKE '%aimbotz%' "
                f"ORDER BY mo.score DESC, mo.at DESC LIMIT ?", *player_ids, limit * 3)
    out, seen = [], set()
    for r in rows:
        r = dict(r)
        r["map"], r["mode"] = clean_map(r["map"]), clean_mode(r["mode"])
        key = (r["match_id"], r["t_ms"] // 8000)          # same fight seen from two squad members = one clip
        if key in seen:
            continue
        seen.add(key)
        out.append(r)
    return out[:limit]


def clips_pending(player_ids):
    ph = ",".join("?" * len(player_ids))
    r = db.q1(f"SELECT COUNT(*) c FROM (SELECT 1 FROM matches WHERE player_id IN ({ph}) AND film_state=0 "
              f"ORDER BY started_at DESC LIMIT 50)", *player_ids)
    return r["c"]


@capacity.memo(lambda player_id,kind="mm",alt_ids=():(player_id,kind,tuple(alt_ids)))
def profile(player_id, kind="mm", alt_ids=()):
    """One player's history; alt_ids = admin-linked second accounts whose games are folded in (rank stays the main account's)."""
    ids = [player_id] + [a for a in alt_ids if a != player_id]
    ph = ",".join("?" * len(ids))
    rows = [dict(r) for r in db.q(f"SELECT * FROM matches WHERE player_id IN ({ph}) ORDER BY started_at DESC", *ids)]
    if len(ids) > 1:
        names = {r["id"]: r["gamertag"] for r in db.q(f"SELECT id, gamertag FROM players WHERE id IN ({ph})", *ids)}
        seen = set()
        rows = [r for r in rows if not (r["match_id"] in seen or seen.add(r["match_id"]))]
        for r in rows:
            r["alt"] = names.get(r["player_id"]) if r["player_id"] != player_id else None
    rows = [r for r in rows if kind_ok(r, kind)]
    for r in rows:
        r["map"] = clean_map(r["map"])
        r["mode"] = clean_mode(r["mode"])
        derive(r)
    now = time.time()
    last30 = [r for r in rows if now - r["started_at"] < 30 * 86400]
    ranked = [r for r in rows if r["ranked"]]
    csr = csr_series([r for r in ranked if r["player_id"] == player_id])      # an alt's rating is its own
    sess = sessions(rows)
    maps, modes = group(rows, "map"), group(rows, "mode")
    cur, _best = streaks(rows)
    return {
        "streak": cur, "insights": insights(rows, maps, sess),
        "moments": moments(ids, 5000, kind), "clips_pending": clips_pending(ids),
        "form": [r["outcome"] for r in reversed(rows[:20])],
        "rows": rows, "all": _agg(rows), "last30": _agg(last30), "ranked": _agg(ranked),
        "csr_now": csr[-1][1] if csr else None, "csr_peak": max((c for _, c in csr), default=None), "csr_series": csr,
        "sessions": sess, "latest_session": sess[0] if sess else None, "live": live_summary(rows),
        "maps": maps, "modes": modes, "medals": medals(rows),
        "since": rows[-1]["started_at"] if rows else None,
    }


@capacity.memo(lambda player_ids,kind="mm":(tuple(player_ids),kind))
def squad(player_ids, kind="mm"):
    """Squad view: one row per member plus the games they played on the same team (same match, result and team score)."""
    mem, by_match = [], defaultdict(dict)
    for pid in player_ids:
        rows = [dict(r) for r in db.q("SELECT * FROM matches WHERE player_id=? ORDER BY started_at DESC", pid)]
        rows = [r for r in rows if kind_ok(r, kind)]
        for r in rows:
            r["map"], r["mode"] = clean_map(r["map"]), clean_mode(r["mode"])
            derive(r)
            by_match[r["match_id"]][pid] = r
        mem.append({"pid": pid, "all": _agg(rows), "last30": _agg([r for r in rows if time.time() - r["started_at"] < 30 * 86400]),
                    "rows": rows})
    together = []
    for mid, who in by_match.items():
        if len(who) < 2:
            continue
        ref = next(iter(who.values()))
        if all(r.get("team_id") is not None for r in who.values()):      # exact: same team id in the match
            tid = max(set(r["team_id"] for r in who.values()), key=lambda t: sum(1 for r in who.values() if r["team_id"] == t))
            mates = {p: r for p, r in who.items() if r["team_id"] == tid}
        else:                                                           # older rows: same result + same team score
            mates = {p: r for p, r in who.items() if r["outcome"] == ref["outcome"] and r["team_score"] == ref["team_score"]}
        if len(mates) < 2:
            continue
        together.append({"match_id": mid, "started_at": ref["started_at"], "map": ref["map"], "mode": ref["mode"],
                         "outcome": ref["outcome"], "team_score": ref["team_score"], "enemy_score": ref["enemy_score"],
                         "duration_s": ref["duration_s"], "members": mates})
    together.sort(key=lambda m: -m["started_at"])
    w = sum(1 for m in together if m["outcome"] == "Win"); l = sum(1 for m in together if m["outcome"] == "Loss")
    maps = defaultdict(lambda: [0, 0, 0])
    for m in together:
        if m["map"]:
            b = maps[m["map"]]; b[0] += 1; b[1] += m["outcome"] == "Win"; b[2] += m["outcome"] == "Loss"
    best_maps = sorted(({"name": n, "games": b[0], "wins": b[1], "win_pct": round(100 * b[1] / max(1, b[1] + b[2]))}
                        for n, b in maps.items()), key=lambda x: (-x["games"], x["name"]))[:6]
    # every night they played together (newest first), each with per-member totals
    nights, cur = [], []
    for m in together:
        if cur and cur[-1]["started_at"] - m["started_at"] > SESSION_GAP_S:
            nights.append(cur); cur = []
        cur.append(m)
    if cur:
        nights.append(cur)
    night_list = []
    for g in nights:
        w_ = sum(1 for m in g if m["outcome"] == "Win"); l_ = sum(1 for m in g if m["outcome"] == "Loss")
        per = {}
        for pid in player_ids:
            rs = [m["members"][pid] for m in g if pid in m["members"]]
            if rs:
                per[pid] = _agg(rs)
        night_list.append({"start": g[-1]["started_at"], "games": len(g), "record": f"{w_}-{l_}",
                           "win_pct": round(100 * w_ / max(1, w_ + l_)), "matches": g, "per": per,
                           "adv": dict(_agg([r for m in g for r in m["members"].values()]),     # team totals; lobby MMR once per game
                                       mmr_edge=_mean((next(iter(m["members"].values())).get("mmr_edge") for m in g), 0))})
    night = nights[0] if nights else []
    nw = sum(1 for m in night if m["outcome"] == "Win"); nl = sum(1 for m in night if m["outcome"] == "Loss")
    tw = team_moments(player_ids, together)
    return {"members": mem, "together": together, "teamwork": tw, "rec": f"{w}-{l}", "games": len(together),
            "win_pct": round(100 * w / max(1, w + l)), "best_maps": best_maps,
            "nights": night_list, "night": night, "night_rec": f"{nw}-{nl}", "night_start": night[-1]["started_at"] if night else None,
            "moments": moments(player_ids, 5000, kind), "clips_pending": clips_pending(player_ids)}


def team_moments(player_ids, together, limit=8, window=50):
    """Best / worst squad moments across the newest shared games whose Theater film has been read."""
    ph = ",".join("?" * len(player_ids))
    xu = {r["id"]: (str(r["xuid"]), r["gamertag"]) for r in db.q(f"SELECT id,xuid,gamertag FROM players WHERE id IN ({ph})", *player_ids)}
    good, bad, pending = [], [], 0
    for m in together[:window]:
        squad = {xu[pid][0]: xu[pid][1] for pid in m["members"] if pid in xu}
        if len(squad) < 2:
            continue
        if not db.q1("SELECT 1 FROM filmed WHERE match_id=?", m["match_id"]):
            pending += 1
            continue
        from types import SimpleNamespace as NS
        evs = [NS(xuid=r["xuid"], time_ms=r["t_ms"], event_type=r["k"])
               for r in db.q("SELECT xuid,t_ms,k FROM events WHERE match_id=? ORDER BY t_ms", m["match_id"])]
        t0 = db.q1("SELECT film_t0 FROM matches WHERE match_id=? AND film_t0 IS NOT NULL LIMIT 1", m["match_id"])
        t0 = t0["film_t0"] if t0 else None
        for c in teamwork.analyze(evs, squad):
            c.update(match_id=m["match_id"], map=m["map"], mode=m["mode"], outcome=m["outcome"],
                     match_started=m["started_at"], at=(t0 + c["t_ms"] / 1000.0) if t0 else m["started_at"],
                     squad_ids=sorted(m["members"]))
            (good if c["kind"] == "good" else bad).append(c)
    def pick(lst):            # momentum swings first, but keep room for the quick team plays too
        lst.sort(key=lambda c: -c["score"])
        mo = [c for c in lst if c.get("momentum")][:5]
        rest = [c for c in lst if not c.get("momentum")][:limit - len(mo)]
        return sorted(mo + rest, key=lambda c: -c["score"])
    return {"good": pick(good), "bad": pick(bad), "pending": pending}


ACTIVE_WINDOW_S = 2 * 3600


def live_summary(rows, now=None):
    """'Tonight so far' for the newest session if the last game ended recently. rows = newest first."""
    now = now or time.time()
    import close_games          # bot / aim-trainer / warm-up customs are not "tonight" (an Aimbotz 526/0/0 is not a KDA)
    rows = [r for r in rows if not close_games.EXCLUDE.search(f"{r.get('map') or ''} {r.get('mode') or ''} {r.get('playlist') or ''}")]
    if not rows:
        return None
    sess = sessions(rows)[0]
    last = sess["matches"][0]
    ended = last["started_at"] + (last["duration_s"] or 0)
    active = now - ended < ACTIVE_WINDOW_S
    ms = sess["matches"]
    pre = next((m["pre_csr"] for m in reversed(ms) if m.get("pre_csr")), None)
    post = next((m["post_csr"] for m in ms if m.get("post_csr")), None)
    a = _agg(ms)
    return {"active": active, "record": sess["record"], "games": sess["games"], "kda": a["kda"], "kd": a["kd"],
            "win_pct": a["win_pct"], "dmg_diff_pg": a["dmg_diff_pg"], "rating": post, "delta": (post - pre) if (pre and post) else None,
            "since": sess["start"], "ended_ago": int(now - ended),
            "games_list": [{"match_id": m["match_id"], "map": m["map"], "outcome": m["outcome"], "k": m["kills"], "d": m["deaths"], "a": m["assists"]} for m in reversed(ms)][-12:], "pips": [m["outcome"].lower() for m in reversed(ms)][-30:],
            "last": {"map": last["map"], "mode": last["mode"], "outcome": last["outcome"], "k": last["kills"], "d": last["deaths"],
                     "a": last["assists"], "kda": last["kda"], "match_id": last["match_id"]}}
