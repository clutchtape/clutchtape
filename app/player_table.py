"""Player stats table (2026-10-10): one row per player for a session, per-game numbers, heat by rank.

Same idea as the main Halo site's "Player stats" table: every column is coloured by where each player ranks in it
(5 steps, best -> worst), so it's quick to see how each one played. On a player page the rows are "This session" and
"Usual" (the 90 days before), coloured against each other. Refresh trigger: a new per-game stat in analytics._agg."""
import analytics

# (key, label, help, better) — better: "hi", "lo" or None (no colour)
COLS = [
    ("games", "Gms", "Games played", None),
    ("csr_net", "CSR Δ", "Ranked CSR change", "hi"),
    ("win_pct", "Win%", None, "hi"),
    ("sc_pct", "SC%", "Share of the team's personal score", "hi"),
    ("kills_pg", "K", "Kills per game", "hi"),
    ("deaths_pg", "D", "Deaths per game", "lo"),
    ("assists_pg", "A", "Assists per game", "hi"),
    ("kd", "K/D", None, "hi"),
    ("kda", "KDA", "Kills + assists/3 - deaths, per game", "hi"),
    ("dmg_pg", "Dmg+", "Damage dealt per game", "hi"),
    ("taken_pg", "Dmg−", "Damage taken per game", "lo"),
    ("dmg_diff_pg", "Dmg±", "Damage dealt minus taken, per game", "hi"),
    ("dmg_ka", "D/KA", "Damage per kill + assist (lower = more efficient)", "lo"),
    ("dmg_pd", "D/D", "Damage dealt per death", "hi"),
    ("dmg_pm", "D/m", "Damage per minute", "hi"),
    ("dmg_share", "Dmg%", "Share of the team's damage", "hi"),
    ("fired_pg", "Fired", "Shots fired per game", None),
    ("hit_pg", "Landed", "Shots landed per game", "hi"),
    ("acc", "Acc", "Accuracy", "hi"),
    ("hs_pct", "HS%", "Headshot kills share", "hi"),
    ("score_pg", "Score", "Personal score per game", "hi"),
    ("medals_pg", "Mdls", "Medals per game", "hi"),
    ("life", "Life", "Average life (s)", "hi"),
    ("callouts_pg", "Call", "Callout assists per game", "hi"),
    ("xk_pg", "xK±", "Kills above what Halo expected, per game", "hi"),
    ("spree", "Spree", "Best killing spree", "hi"),
    ("csr", "CSR", "CSR after the last ranked game", None),
    ("mmr_edge", "Lobby", "Team MMR minus enemy MMR (negative = underdog)", None),
]
SIGNED = {"dmg_diff_pg", "xk_pg", "csr_net", "mmr_edge"}
PCT = {"win_pct", "sc_pct", "dmg_share", "acc", "hs_pct"}
LEVELS = ("h-poor", "h-below", "h-avg", "h-good", "h-ex")


def stats(rows):
    """Per-game stats for one player's games (any order)."""
    if not rows:
        return None
    a = analytics._agg(rows)
    n = len(rows)
    d = sum(r["deaths"] or 0 for r in rows)
    dealt = sum(r["damage_dealt"] or 0 for r in rows)
    ranked = sorted((r for r in rows if r.get("post_csr") is not None), key=lambda r: r["started_at"])
    out = dict(a)
    out.update(
        taken_pg=round(sum(r["damage_taken"] or 0 for r in rows) / n),
        dmg_pd=round(dealt / d) if d else None,
        fired_pg=round(sum(r["shots_fired"] or 0 for r in rows) / n),
        hit_pg=round(sum(r["shots_hit"] or 0 for r in rows) / n),
        csr=round(ranked[-1]["post_csr"]) if ranked else None,
    )
    return out


def _level(v, vals, better):
    """Rank -> one of 5 heat levels (mid-rank for ties, like the main site). Two rows (session vs usual): a gap under
    3% stays neutral so tiny differences don't light up."""
    if v is None or better is None or len(vals) < 2:
        return ""
    if len(vals) == 2:
        other = vals[0] if vals[1] == v and vals[0] != v else vals[1] if vals[0] == v else vals[0]
        base = max(abs(other), 1e-9)
        if abs(v - other) / base < .03:
            return "h-avg"
    below = sum(1 for x in vals if x < v)
    eq = sum(1 for x in vals if x == v)
    p = (below + .5 * eq) / len(vals)
    if better == "lo":
        p = 1 - p
    return LEVELS[min(4, int(p * 5))]


def build(groups):
    """groups: [(label, rows, extra)] -> dict(cols, rows=[dict(label, extra, cells=[(value, cls)])]). Rows with no
    games are skipped; a column every row leaves empty is dropped."""
    data = [(lbl, stats(rs), extra) for lbl, rs, extra in groups if rs]
    if not data:
        return None
    cols = [dict(key=k, label=l, help=h, better=b) for k, l, h, b in COLS
            if any(s.get(k) is not None for _, s, _ in data)]
    out = []
    for lbl, s, extra in data:
        cells = []
        for c in cols:
            v = s.get(c["key"])
            vals = [x.get(c["key"]) for _, x, _ in data if x.get(c["key"]) is not None]
            cells.append((v, _level(v, vals, c["better"])))
        out.append(dict(label=lbl, extra=extra, cells=cells))
    return dict(cols=cols, rows=out)
