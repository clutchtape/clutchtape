"""Close games to watch: rank the pros' finished games (matchmaking and scrims) by how close they were.

Rank (0-100) = 60 x closeness + 15 x went-the-distance + 10 x best play + 15 x pro vs pro.
  closeness   1 - final margin / CLOSE_MARGIN for the mode (a 50-49 Slayer game is ~0.9; a 50-40 game is 0).
  distance    the losing team reached 90% of the score cap (one short of a small cap), or CTF overtime.
  best play   the strongest auto clip in the game (clips.py score; 80+ counts fully).
  pro vs pro  tracked pros on opposite teams (team_id), or 4+ pros in the lobby (Theater film names).
Only Win/Loss games with a known final score in a competitive arena mode are ranked. Scrims (custom games) count:
pros playing pros is the point. Games with video get a Watch link; the rest link to
the match recap. Lead changes can't be scored: Theater events don't say which team each opponent was on.
Refresh trigger: re-tune CLOSE_MARGIN / CAPS if Halo changes score limits or a new ranked mode appears."""
import re

# family: (margin at which a game stops counting as close, score cap or None, unit word)
FAMILIES = {
    "doubles": (5, 25, "kills"),
    "slayer": (10, 50, "kills"),
    "ctf": (2.5, None, "caps"),          # cap read from the mode name ("CTF 3 Captures")
    "koth": (3, 4, "hills"),
    "strongholds": (75, 250, "points"),
    "oddball": (60, None, "points"),
}
MIN_CLOSENESS = 0.5          # below this a game isn't "close" and isn't listed
CTF_OVERTIME_S = 749         # CTF still running past 12:29 = overtime (same rule as the clip rubric)
EXCLUDE = re.compile(r"bot|aim|fiesta|husky|infection|octagon|warmup|1v1|\$", re.I)


def family(mode):
    m = (mode or "").lower()
    if not m or EXCLUDE.search(m):
        return None
    if "doubles" in m:
        return "doubles"
    for key, fam in (("slayer", "slayer"), ("ctf", "ctf"), ("king of the hill", "koth"), ("strongholds", "strongholds"), ("oddball", "oddball")):
        if key in m:
            return fam
    return None


# Showcase pros (featured players, demo squads and their verified frequent teammates, 2026-10-08). Used for the
# "pro vs pro" signal and to choose which tracked players' games are scanned. Override with PRO_GAMERTAGS.
PRO_GAMERTAGS = ("CyKul", "LethuL", "Falcated", "RoyaI 2", "ItzTheLastShot", "Tripppey", "iTz So Frosty", "Luciid TW",
                 "Druk RN", "Lqgend", "HoaXfactor", "TylrHitsButtons", "Pznguin", "Kuhlect", "Bound", "Renegade JW", "StelluR")


def score(m, best_play=0, pro_vs_pro=False):
    """m: a matches row (mode, outcome, team_score, enemy_score, duration_s). None if not a rankable close game."""
    fam = family(m.get("mode"))
    ts, es = m.get("team_score"), m.get("enemy_score")
    if not fam or m.get("outcome") not in ("Win", "Loss") or ts is None or es is None:
        return None
    close_m, cap, unit = FAMILIES[fam]
    if fam == "ctf":
        caps = re.search(r"(\d+)\s*capture", m["mode"], re.I)
        cap = int(caps.group(1)) if caps else None
    margin = abs(ts - es)
    if margin == 0:
        return None
    closeness = max(0.0, 1 - margin / close_m)
    if closeness < MIN_CLOSENESS:
        return None
    reasons = ["Won by 1" if margin == 1 else f"Decided by {margin} {unit}"]
    overtime = fam == "ctf" and (m.get("duration_s") or 0) >= CTF_OVERTIME_S
    # loser got within 10% of the cap, or within one of a small cap (5-4 CTF, 4-3 hills)
    distance = bool(cap) and (min(ts, es) >= 0.9 * cap or (cap <= 5 and min(ts, es) >= cap - 1))
    if overtime:
        reasons.append("Overtime")
    elif distance:
        reasons.append("Went to the cap")
    if pro_vs_pro:
        reasons.append("Pro vs pro")
    play = min(1.0, (best_play or 0) / 80)
    rank = round(100 * (0.60 * closeness + 0.15 * (overtime or distance) + 0.10 * play + 0.15 * bool(pro_vs_pro)))
    return {"rank": rank, "family": fam, "margin": margin, "unit": unit, "reasons": reasons, "closeness": closeness,
            "cap_reached": bool(cap) and max(ts, es) >= cap, "final": f"{max(ts, es)}–{min(ts, es)}"}


# ------------------------------------------------------------------ clutch finishes (the last 30s of close games)
FINISH_WINDOW_MS = 30000
MULTI = ("Double Kill", "Triple Kill", "Overkill", "Killtacular", "Killtrocity", "Killamanjaro", "Killtastrophe", "Killpocalypse", "Killionaire")
# "Big play" medals: Triple Kill and up, plus medals rarer than ~1 per 100 games in our film data (2026-10-08 counts:
# Perfect 25.6k, Snipe 19.8k and No Scope 11.0k are too common; Off the Rack 520, 360 485, Hail Mary 358, Ninja 83).
BIG_MEDALS = MULTI[1:] + ("Extermination", "Ninja", "Hail Mary", "360", "Quigley", "Off the Rack", "Last Shot", "Sharpshooter",
                          "Clock Stop", "Goal Line Stand", "Stopped Short", "Counter-snipe", "Bank Shot", "Cluster Luck",
                          "Mind the Gap", "Sneak King", "Remote Detonation", "Nade Shot", "Whiplash")


def finish(game, events):
    """The final FINISH_WINDOW_MS of a ranked close game.
    game: a score() result (uses family, closeness, cap_reached).
    events: [(t_ms, kind, gamertag, medal)] for this match (any order).
    Rank (0-100) = 55 x game closeness + 25 x action (kills in the window, 8+ counts fully) + 20 x big play
    (a multikill or standout medal in the window). Returns None when the film has no usable ending."""
    if not events:
        return None
    end = max(e[0] for e in events)
    win = sorted(e for e in events if e[0] >= end - FINISH_WINDOW_MS)
    kills = [e for e in win if e[1] == "kill"]
    obj = [e for e in win if e[1] == "mode"]
    medals = [e for e in win if e[1] == "medal" and e[3]]
    big = [e for e in medals if e[3] in BIG_MEDALS]
    if not kills and not obj:
        return None
    # Only name a decider when the film proves it: Slayer ends on the kill that reaches the cap. Objective modes end on
    # points/caps the film doesn't label (a 'mode' event can be a grab, a return or a tick), so they get no decider.
    decider = ("Game-winning kill", kills[-1][2]) if game["family"] in ("slayer", "doubles") and game.get("cap_reached") and kills else None
    reasons = [f"{len(kills)} kills in the last 30s"] if kills else []
    if obj:
        reasons.append(f"{len(obj)} objective play{'s' if len(obj) > 1 else ''}")
    best = max(big, key=lambda e: (e[3] in MULTI, MULTI.index(e[3]) if e[3] in MULTI else 0), default=None)
    if best:
        reasons.append(f"{best[3]} · {best[2]}")
    closeness = game["closeness"]
    action = min(1.0, len(kills) / 8)
    rank = round(100 * (0.55 * closeness + 0.25 * action + 0.20 * bool(best)))
    return {"rank": rank, "start_ms": max(0, end - FINISH_WINDOW_MS - 5000), "end_ms": end, "reasons": reasons,
            "decider": decider, "kills": len(kills)}
