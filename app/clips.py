"""Auto clip detection from the Theater-film timeline (timestamps only, nothing is rendered).

Scoring is ported from the main Halo site's clip rubric (halo/src/webapp.py CLIP_RUBRIC_SPEC,
_multikill_score, _medal_set_score, _kill_run, _play_sequence_score) so both sites agree on what a good clip is:
  - 100-point scale; the highest multikill tier sets the base (Double 8, Triple 28, Overkill 44, Killtacular 62, +8/tier)
  - Perfect +10, snipe +12, power weapon +14, rare medal +16 (Ninja +8 more), objective +10,
    killing spree 22 +14 per higher tier, 2+ different medals stacked +6
  - a clip is the WHOLE FIGHT: best moment + 50% of every other highlight in it + 6 per kill beyond the 2nd
    in the unbroken run (kills <= 10s apart, bonus capped at 8 kills)
  - a multikill's kills chain back kill-by-kill (<= 6s gaps), never a fixed window
  - clip threshold 25; a lone snipe needs 2+ kills in its run
  - (2026-10-07) also ported: medal rarity bonus (<= 18, rarest medal at the instant, empirical over every stored film:
    factor 1/.8/.6/.4/.2 at the 98/95/90/75/50th percentile), exceptional lives (210s+ & 6 kills +10, 150s+ & 6 +7),
    and CONTEXT bonuses that only amplify a play already worth context_min_merit (20): late close-game play +8
    (last 28% of a game decided by <= 5), CTF overtime +16 (film time - 29s >= 12:00). Flag-cap bonuses are not
    ported (Clutchtape doesn't know who capped).
Refresh trigger: re-port if the Halo site's rubric defaults or the fight/run rules change.
"""

MULTIKILL_ORDER = ('Double Kill', 'Triple Kill', 'Overkill', 'Killtacular', 'Killtrocity',
                   'Killamanjaro', 'Killtastrophe', 'Killpocalypse', 'Killionaire')
SPREE_ORDER = ('Killing Spree', 'Killing Frenzy', 'Running Riot', 'Rampage')
SNIPES = {'Snipe', 'No Scope', 'Counter-snipe', 'Quigley'}
POWER = {'Ballista', 'Pancake', 'Scattergunner', 'Heavy'}
RARE = {'Ninja', 'Killjoy', 'Back Smack', 'Achilles Spine', 'Sneak King', 'Kong', '360', 'Grapple-jack', 'Skyjack',
        'Splatter', 'Driveby', 'Lawnmower', 'Windshield Wiper', 'Ramming Speed', 'Boom Block', 'Stick'}
OBJECTIVE = {'Flag Joust', 'Goal Line Stand', 'Stopped Short', 'Fumble', 'Straight Balling', 'Nuclear Football',
             'Clear Reception', 'Treasure Hunter', 'Saboteur', 'Big Deal', 'Always Rotating', 'Hill Guardian',
             'Clock Stop', 'Hold This', 'Secure Line', 'Signal Block', 'Call Blocked', 'Hang Up', 'Interlinked',
             'Harpoon', 'Pull'}
SCORED = set(MULTIKILL_ORDER) | set(SPREE_ORDER) | SNIPES | POWER | RARE | OBJECTIVE | {'Perfect'}

R = {'double': 8, 'triple': 28, 'overkill': 44, 'killtacular': 62, 'mk_step': 8, 'perfect': 10, 'sniper': 12,
     'power': 14, 'rare': 16, 'ninja': 8, 'objective': 10, 'spree': 22, 'spree_step': 14, 'stacked': 6,
     'followup_share': 50, 'run_kill': 6, 'run_gap_ms': 10000, 'run_max_bonus': 8, 'threshold': 25,
     'fight_gap_ms': 20000, 'snipe_support_kills': 2,
     'rarity_max': 18, 'context_min_merit': 20, 'late_close': 8, 'overtime': 16,
     'life_long_s': 210, 'life_long_kills': 6, 'life_long_score': 10,
     'life_mid_s': 150, 'life_mid_kills': 6, 'life_mid_score': 7,
     'finish_window_ms': 15000, 'finish_base': 34, 'finish_lead_ms': 25000}
GAMEPLAY_CLOCK_OFFSET_MS = 29000        # Theater film time runs ~29s ahead of the in-game clock (Halo site constant)
CTF_REGULATION_MS = 12 * 60 * 1000
RARITY = {}                             # medal -> factor 0..1, set by set_rarity() from the stored films


def set_rarity(counts):
    """counts: {medal name: times earned across every stored film}. Same percentile bands as the Halo site."""
    pop = [c for c in counts.values() if c > 0]
    prof = {}
    for name, c in counts.items():
        if c <= 0:
            continue
        pct = sum(o >= c for o in pop) / max(1, len(pop))     # share of medal types at least this common
        prof[name] = 1.0 if pct >= .98 else .8 if pct >= .95 else .6 if pct >= .90 else .4 if pct >= .75 else .2 if pct >= .50 else 0.0
    RARITY.clear(); RARITY.update(prof)
LEAD_MS, TAIL_MS = 8000, 5000
MAX_PER_MATCH = 5
MEDAL_WEIGHT = {m: 1 for m in SCORED}          # kept for callers that only need "is this a scored medal"


def medal_set_score(medals):
    """Score one instant's medals (the Halo site's _medal_set_score, minus site-only rarity data)."""
    ms = set(medals) & SCORED
    score, parts = 0, []
    mk = [m for m in MULTIKILL_ORDER if m in ms]
    if mk:
        tier = MULTIKILL_ORDER.index(mk[-1])
        score += (R['double'], R['triple'], R['overkill'])[tier] if tier < 3 else R['killtacular'] + (tier - 3) * R['mk_step']
        parts.append(mk[-1])
    if 'Perfect' in ms:
        score += R['perfect']; parts.append('Perfect')
    sp = [m for m in SPREE_ORDER if m in ms]
    if sp:
        score += R['spree'] + SPREE_ORDER.index(sp[-1]) * R['spree_step']; parts.append(sp[-1])
    if ms & SNIPES:
        score += R['sniper']; parts.append(sorted(ms & SNIPES)[0])
    if ms & POWER:
        score += R['power']; parts.append(sorted(ms & POWER)[0])
    if ms & RARE:
        score += R['rare']; parts.append(sorted(ms & RARE)[0])
    if 'Ninja' in ms:
        score += R['ninja']
    if ms & OBJECTIVE:
        score += R['objective']; parts.append(sorted(ms & OBJECTIVE)[0])
    if len(ms) >= 2:
        score += R['stacked']
    mk_top = [m for m in MULTIKILL_ORDER if m in ms][-1:]          # a multikill chain counts once (its top tier)
    rare = max((RARITY.get(m, 0.0) for m in (ms - set(MULTIKILL_ORDER)) | set(mk_top)), default=0.0)
    score += int(round(R['rarity_max'] * rare))
    return min(100, score), parts


def _kill_run(kills, lo, hi):
    inside = [i for i, k in enumerate(kills) if lo - 1500 <= k <= hi + 1500]
    if not inside:
        return []
    a, b = inside[0], inside[-1]
    while a > 0 and kills[a] - kills[a - 1] <= R['run_gap_ms']:
        a -= 1
    while b < len(kills) - 1 and kills[b + 1] - kills[b] <= R['run_gap_ms']:
        b += 1
    return kills[a:b + 1]


def _life_bonus(kills, deaths, lo, hi, end_ms):
    """The life the fight happened in: proven kills inside it (match totals are not local proof)."""
    start = max([d for d in deaths if d <= lo] or [0])
    stop = min([d for d in deaths if d >= hi] or [end_ms or hi])
    secs, n = (stop - start) / 1000, sum(1 for k in kills if start < k <= stop)
    if secs >= R['life_long_s'] and n >= R['life_long_kills']:
        return R['life_long_score']
    if secs >= R['life_mid_s'] and n >= R['life_mid_kills']:
        return R['life_mid_score']
    return 0


def find_moments(events, xuid, game=None):
    """events: HighlightEvent-like objects. Returns [{t_ms, dur_s, label, kills, score}] for this player, best first.
    game (optional): {duration_s, team_score, enemy_score, mode} for the context bonuses."""
    game = game or {}
    dur_ms = int(game.get("duration_s") or 0) * 1000
    ts, es = game.get("team_score"), game.get("enemy_score")
    is_close = bool(ts or es) and abs((ts or 0) - (es or 0)) <= 5
    is_ctf = "ctf" in str(game.get("mode") or "").lower() or "capture" in str(game.get("mode") or "").lower()
    xuid = str(xuid)
    mine = [e for e in events if str(e.xuid) == xuid]
    kills = sorted(int(e.time_ms) for e in mine if e.event_type == "kill")
    deaths = sorted(int(e.time_ms) for e in mine if e.event_type == "death")
    by_t = {}
    for e in mine:
        if e.event_type == "medal" and e.medal_name in SCORED:
            by_t.setdefault(int(e.time_ms), set()).add(e.medal_name)
    instants = sorted(by_t.items())
    # group scored instants into fights: same life (no death in between), <= 20s after the previous one
    fights, cur = [], []
    for t, ms in instants:
        if cur and (t - cur[-1][0] > R['fight_gap_ms'] or any(cur[-1][0] < d < t for d in deaths)):
            fights.append(cur); cur = []
        cur.append((t, ms))
    if cur:
        fights.append(cur)
    out = []
    for f in fights:
        scored = [medal_set_score(ms) for _t, ms in f]
        members = sorted((s for s, _p in scored), reverse=True)
        run = _kill_run(kills, f[0][0], f[-1][0])
        best = members[0] + round(sum(members[1:]) * R['followup_share'] / 100)
        extra = min(max(0, len(run) - 2), R['run_max_bonus'])
        score = best + extra * R['run_kill']
        score += _life_bonus(kills, deaths, f[0][0], f[-1][0], dur_ms or max(kills + deaths + [f[-1][0]]))
        if score >= R['context_min_merit']:          # WHEN it happened only amplifies a real play
            if is_close and dur_ms and f[-1][0] >= dur_ms * 0.72:
                score += R['late_close']
            if is_ctf and f[-1][0] - GAMEPLAY_CLOCK_OFFSET_MS >= CTF_REGULATION_MS:
                score += R['overtime']
        allm = set().union(*(ms for _t, ms in f))
        if allm <= SNIPES | {'Perfect'} and len(run) < R['snipe_support_kills']:
            continue                                   # lone-snipe guard
        if score < R['threshold']:
            continue
        # label: headline medals, biggest first, plus the run length
        parts = []
        for _s, p in sorted(scored, key=lambda x: -x[0]):
            for x in p:
                if x not in parts:
                    parts.append(x)
        top_mk = max((MULTIKILL_ORDER.index(x) for x in parts if x in MULTIKILL_ORDER), default=None)
        top_sp = max((SPREE_ORDER.index(x) for x in parts if x in SPREE_ORDER), default=None)
        parts = [x for x in parts if not (x in MULTIKILL_ORDER and MULTIKILL_ORDER.index(x) != top_mk)
                 and not (x in SPREE_ORDER and SPREE_ORDER.index(x) != top_sp)]   # "Overkill", not "Overkill · Triple · Double"
        label = " · ".join(parts[:3]) + (f" · {len(run)}-kill run" if len(run) >= 3 else "")
        start = min(f[0][0], run[0] if run else f[0][0]) - LEAD_MS
        end = max(f[-1][0], run[-1] if run else f[-1][0]) + TAIL_MS
        out.append({"t_ms": max(0, start), "dur_s": max(8, round((end - max(0, start)) / 1000)), "label": label,
                    "kills": len(run), "score": min(100, score), "raw": score})
    fin = _finish(events, xuid, kills, deaths, game, dur_ms, is_close, is_ctf)
    if fin and not any(m["t_ms"] <= fin["t_ms"] + fin["dur_s"] * 1000 and fin["t_ms"] <= m["t_ms"] + m["dur_s"] * 1000
                       and m["raw"] >= fin["raw"] for m in out):
        out = [m for m in out if not (m["t_ms"] <= fin["t_ms"] + fin["dur_s"] * 1000 and fin["t_ms"] <= m["t_ms"] + m["dur_s"] * 1000)] + [fin]
    out.sort(key=lambda m: (-m["score"], -m["raw"]))
    return out[:MAX_PER_MATCH]


def _finish(events, xuid, kills, deaths, game, dur_ms, is_close, is_ctf):
    """2026-10-12: the game-winning finish. Medal fights never see it — a capture isn't a medal — so an overtime flag
    with spread-out kills before it went unclipped. A WON close or overtime game where this player made an objective
    play (film 'mode' event) in its last FINISH_WINDOW seconds gets one moment: the run-in (their kills in the 25 s
    before) through the final play."""
    ts, es = game.get("team_score"), game.get("enemy_score")
    if ts is None or es is None or ts <= es:
        return None
    end = dur_ms or max([int(e.time_ms) for e in events] or [0])
    overtime = is_ctf and end - GAMEPLAY_CLOCK_OFFSET_MS >= CTF_REGULATION_MS
    if not (overtime or is_close):
        return None
    plays = sorted(int(e.time_ms) for e in events if str(e.xuid) == xuid and e.event_type == "mode" and int(e.time_ms) >= end - R['finish_window_ms'])
    if not plays:
        return None
    last = plays[-1]
    run = [k for k in kills if last - R['finish_lead_ms'] <= k <= last]
    died = any(run[0] < d < last for d in deaths) if run else False
    score = R['finish_base'] + (R['overtime'] if overtime else 0) + R['late_close'] + min(len(run), 4) * R['run_kill'] - (6 if died else 0)
    start = max(0, min(run[0] if run else last, last - 12000) - LEAD_MS)
    what = "Game-winning capture" if is_ctf else "Game-winning objective play"
    label = what + (" in overtime" if overtime else "") + (f" · {len(run)} kills before it" if len(run) >= 2 else "")
    return {"t_ms": start, "dur_s": max(8, round((last + TAIL_MS - start) / 1000)), "label": label, "kills": len(run),
            "score": min(100, score), "raw": score, "finish": True}
