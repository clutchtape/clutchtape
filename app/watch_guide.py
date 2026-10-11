"""Watch guide (2026-10-11): while watching a past broadcast on a player page, the side column lists the session's games
with a ▶ for each (jumps the player there) and says which ones are worth watching, and why.

Worth = best auto-clip in the game (film moments) + a close finish + how far the game beat the player's usual, plus
a nudge for the session's best game. Plain reasons are shown with it ("Triple Kill · 6-kill run", "Close · 1 point",
"KDA 2.1× usual"). The top 3 (with a real reason) are tagged. Refresh trigger: new moment kinds or close-game rules.
"""
import analytics
import close_games


def _rel(v, u):
    if v is None or u in (None, 0):
        return None
    return (v - u) / abs(u)


def build(matches, rows_by_id, usual, moments):
    """matches: the session's games (any order); rows_by_id: match_id -> row with "vod" (or None); usual: the player's
    usual _agg (or None); moments: playable session clips (each with match_id, label, score, vod).
    -> {"games": [...oldest first], "picks": [the top games], "record": "W-L"} or None."""
    games = sorted((m for m in matches if m.get("outcome") in ("Win", "Loss", "Tie")), key=lambda m: m["started_at"])
    if not games:
        return None
    best_by = {}
    for mo in moments or []:
        if mo.get("vod") and (mo["match_id"] not in best_by or mo["score"] > best_by[mo["match_id"]]["score"]):
            best_by[mo["match_id"]] = mo
    stats = {g["match_id"]: analytics._agg([g]) for g in games}
    top_kda = max((s.get("kda") for s in stats.values() if s.get("kda") is not None), default=None)
    out = []
    for n, g in enumerate(games, 1):
        a = stats[g["match_id"]]
        worth, why = 0.0, []
        bm = best_by.get(g["match_id"])
        if bm:
            worth += bm["score"] * 0.6
            why.append(bm["label"].split(" · ")[0] if bm["score"] < 60 else " · ".join(bm["label"].split(" · ")[:2]))
        close = close_games.score(g)
        if close:
            worth += 22
            unit = close["unit"] if close["margin"] != 1 else close["unit"].rstrip("s")
            why.append(f"Close · {close['margin']:g} {unit}")
        d = _rel(a.get("kda"), (usual or {}).get("kda"))
        if d is not None and a.get("kda") is not None and a["kda"] > 0 and d > 0.25:
            worth += min(28, d * 30)
            ratio = a["kda"] / usual["kda"] if usual and usual.get("kda") and usual["kda"] > 0 else None
            why.append(f"KDA {ratio:.1f}× usual" if ratio and ratio >= 1.5 else "Above usual")
        if top_kda is not None and a.get("kda") == top_kda and len(games) > 2:
            worth += 10
            if not any(w.startswith("KDA") for w in why):
                why.append("Best game of the session")
        r = rows_by_id.get(g["match_id"]) or {}
        out.append({
            "n": n, "match_id": g["match_id"], "map": analytics.clean_map(g.get("map")), "mode": analytics.clean_mode(g.get("mode")),
            "outcome": g["outcome"], "t": g["started_at"],
            "score": f"{round(g['team_score'])}–{round(g['enemy_score'])}" if g.get("team_score") is not None and g.get("enemy_score") is not None else None,
            "k": g.get("kills"), "d": g.get("deaths"), "a": g.get("assists"), "kda": a.get("kda"), "dmg_pm": a.get("dmg_pm"), "sc_pct": a.get("sc_pct"),
            "csr_d": round(g["post_csr"] - g["pre_csr"]) if g.get("post_csr") is not None and g.get("pre_csr") is not None else None,
            "vod": r.get("vod"), "best": {"label": bm["label"], "vod": bm["vod"], "score": bm["score"]} if bm else None,
            "worth": round(worth), "why": why[:3], "pick": 0})
    ranked = sorted((x for x in out if x["why"] and x["worth"] >= 30 and (x["vod"] or x["best"])), key=lambda x: -x["worth"])[:3]
    for i, x in enumerate(ranked, 1):
        x["pick"] = i
    w = sum(g["outcome"] == "Win" for g in games)
    l = sum(g["outcome"] == "Loss" for g in games)
    return {"games": out, "picks": ranked, "record": f"{w}-{l}"}
