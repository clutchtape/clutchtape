"""Teamwork moments for a squad, from the Theater-film timeline (who killed / died, and when).

The film has no positions and no killer->victim pairing, so this is timing based and labelled as such:
  good: squad kill chains (several kills by different members close together, few squad deaths),
        trade chains (a squadmate dies and another gets a kill within seconds, repeatedly)
  bad : squad wipes (several squad deaths close together with almost no kills back),
        feeding (one member dying again and again while nobody else scores)
"""

CHAIN_WIN_MS = 9000
TRADE_MS = 4000
WIPE_WIN_MS = 8000
FEED_WIN_MS = 30000
LEAD_MS = 9000
TAIL_MS = 6000


def _merge(cands, gap=6000):
    cands.sort(key=lambda c: c["start"])
    out = []
    for c in cands:
        if out and c["start"] <= out[-1]["end"] + gap:
            o = out[-1]
            if c["score"] > o["score"]:
                c["start"], c["end"] = min(c["start"], o["start"]), max(c["end"], o["end"])
                out[-1] = c
            else:
                o["end"] = max(o["end"], c["end"])
        else:
            out.append(c)
    return out


def analyze(events, squad):
    """events: rows with .xuid .event_type .time_ms; squad: {xuid: gamertag} of members on the same team this match.
    Returns [{kind, label, start, end, score, members}] with start/end in ms from the film start."""
    sx = set(squad)
    if len(sx) < 2:
        return []
    kills = sorted((int(e.time_ms), str(e.xuid)) for e in events if e.event_type == "kill" and str(e.xuid) in sx)
    deaths = sorted((int(e.time_ms), str(e.xuid)) for e in events if e.event_type == "death" and str(e.xuid) in sx)
    n = len(sx)
    good, bad = [], []

    # ---- kill chains: >=3 squad kills by >=2 members inside 9s, at most one squad death around it
    for i, (t, _) in enumerate(kills):
        win = [(k, x) for k, x in kills if t <= k <= t + CHAIN_WIN_MS]
        who = {x for _, x in win}
        if len(win) >= 3 and len(who) >= 2:
            last = win[-1][0]
            d = sum(1 for dt, _ in deaths if t - 2000 <= dt <= last + 1000)
            if d <= 1:
                good.append({"kind": "good", "label": f"Team chain · {len(win)} kills by {len(who)}",
                             "start": t - LEAD_MS, "end": last + TAIL_MS,
                             "score": len(win) * 8 + len(who) * 8 - d * 6, "members": sorted(squad[x] for x in who)})

    # ---- trades: a squad death answered by another member's kill within 4s
    trades = []
    for dt, dx in deaths:
        ans = next(((kt, kx) for kt, kx in kills if dt < kt <= dt + TRADE_MS and kx != dx), None)
        if ans:
            trades.append((dt, ans[0], dx, ans[1]))
    for tr in trades:
        run = [x for x in trades if tr[0] <= x[0] <= tr[0] + 20000]
        if len(run) >= 2:
            good.append({"kind": "good", "label": f"Trade chain · {len(run)} trades",
                         "start": tr[0] - 6000, "end": run[-1][1] + TAIL_MS, "score": len(run) * 14,
                         "members": sorted({squad[r[2]] for r in run} | {squad[r[3]] for r in run})})

    # ---- squad wipes: lots of squad deaths close together and (almost) no kills back
    need = max(2, min(3, n))
    for dt, _ in deaths:
        win = [(d, x) for d, x in deaths if dt <= d <= dt + WIPE_WIN_MS]
        if len(win) >= need and len({x for _, x in win}) >= 2:
            k = sum(1 for kt, _ in kills if dt - 1000 <= kt <= win[-1][0] + 5000)
            if k <= 1:
                bad.append({"kind": "bad", "label": f"Squad wipe · {len(win)} down, {k} back",
                            "start": dt - LEAD_MS, "end": win[-1][0] + TAIL_MS,
                            "score": len(win) * 12 - k * 6, "members": sorted({squad[x] for _, x in win})})

    # ---- feeding: one member dies 3+ times in 30s while the squad scores nothing meaningful
    for dt, dx in deaths:
        mine = [d for d, x in deaths if x == dx and dt <= d <= dt + FEED_WIN_MS]
        if len(mine) >= 3:
            k = sum(1 for kt, _ in kills if dt <= kt <= mine[-1] + 3000)
            if k <= 1:
                bad.append({"kind": "bad", "label": f"{squad[dx]} caught feeding · {len(mine)} deaths in {round((mine[-1] - dt) / 1000)}s",
                            "start": dt - 8000, "end": mine[-1] + TAIL_MS, "score": len(mine) * 9 - k * 5,
                            "members": [squad[dx]]})
    out = []
    for c in momentum(kills, deaths, squad):          # long runs are their own category: never merged into short chains
        c["dur_s"] = max(10, round((c["end"] - c["start"]) / 1000))
        c["t_ms"] = max(0, c["start"])
        out.append(c)
    for lst in (good, bad):
        for c in _merge(lst):
            c["dur_s"] = max(10, round((c["end"] - c["start"]) / 1000))
            c["t_ms"] = max(0, c["start"])
            out.append(c)
    return out


RUN_MIN_MS, RUN_MAX_MS, RUN_MIN_NET = 20000, 150000, 5


def momentum(kills, deaths, squad):
    """Sustained swings: the stretch (20s-2.5min) where the squad's kills minus deaths is most lopsided.
    Finds the best non-overlapping dominating runs (+) and getting-run-over stretches (-), plus comebacks."""
    ev = sorted([(t, 1, x) for t, x in kills] + [(t, -1, x) for t, x in deaths])
    if len(ev) < RUN_MIN_NET:
        return []

    def best(sign, taken):
        top = None
        for i in range(len(ev)):
            if any(a <= ev[i][0] <= b for a, b in taken):
                continue
            net = 0
            for j in range(i, len(ev)):
                if ev[j][0] - ev[i][0] > RUN_MAX_MS or any(a <= ev[j][0] <= b for a, b in taken):
                    break
                net += ev[j][1] * sign
                span = ev[j][0] - ev[i][0]
                if span >= RUN_MIN_MS and net >= RUN_MIN_NET and ev[j][1] * sign > 0:
                    # prefer bigger swings, then denser ones
                    key = (net - span / 60000.0, net)
                    if not top or key > top[0]:
                        top = (key, i, j, net)
        return top

    out, taken = [], []
    for sign in (1, -1):
        for _ in range(3):                                  # up to 3 runs each way per match
            b = best(sign, taken)
            if not b:
                break
            _, i, j, net = b
            seg = ev[i:j + 1]
            k = sum(1 for e in seg if e[1] > 0); d = len(seg) - k
            s, e = seg[0][0], seg[-1][0]
            taken.append((s, e))
            who = {}
            for _t, v, x in seg:
                if v > 0:
                    who[squad[x]] = who.get(squad[x], 0) + 1
            secs = round((e - s) / 1000)
            if sign > 0:
                lead = max(who, key=who.get) if who else None
                label = f"Momentum run · +{net} ({k} kills, {d} deaths in {secs}s)" + (f" · {lead} led with {who[lead]}" if lead else "")
            else:
                label = f"Getting run over · -{net} ({k} kills, {d} deaths in {secs}s)"
            out.append({"kind": "good" if sign > 0 else "bad", "label": label, "start": s - 6000, "end": e + TAIL_MS,
                        "score": net * 14 + len(seg) * 2, "members": sorted(squad.values()), "momentum": True,
                        "net": net * sign})
    # comeback: a run-over followed within 90s by a momentum run
    for a in [c for c in out if c["net"] < 0]:
        for b in [c for c in out if c["net"] > 0]:
            if 0 <= b["start"] - a["end"] <= 90000:
                out.append({"kind": "good", "label": f"Comeback · from {a['net']} to +{b['net']}", "start": a["start"],
                            "end": b["end"], "score": (b["net"] - a["net"]) * 12, "members": sorted(squad.values()),
                            "momentum": True, "net": b["net"]})
    return out
