"""What each tracked channel streamed, and when it switched games (2026-10-08).

Twitch's API only reports the CURRENT category of a live stream, never its history, so this polls every tracked channel
every POLL_S seconds (one Helix call per 100 channels) and stores one row per category stint:
  stream_log(login, stream_start, game, game_id, title, first_seen, last_seen)
Only channels from the deployment config (FEATURED_PLAYERS / PRIVATE_CHANNELS) are logged; channels typed into page URLs
(?tw=) are never stored, matching the site's privacy rule. A stint's edges are accurate to ~POLL_S; the first stint of a
stream starts at the stream start when we saw it within FIRST_GRACE_S of going live, otherwise at first sight
("unknown" before that). Refresh trigger: change POLL_S if Twitch rate limits tighten (800 req/min app limit, 2026-10)."""
import logging
import os
import threading
import time

import db
import twitch

POLL_S = 120
FIRST_GRACE_S = 10 * 60
SCHEMA = """
CREATE TABLE IF NOT EXISTS stream_log (login TEXT NOT NULL, stream_start REAL NOT NULL, game TEXT, game_id TEXT, title TEXT,
  first_seen REAL NOT NULL, last_seen REAL NOT NULL);
CREATE INDEX IF NOT EXISTS idx_stream_log ON stream_log(login, stream_start, first_seen);
"""
_uid = {}
log = logging.getLogger(__name__)


def init():
    db.conn().executescript(SCHEMA)


def channels():
    out = []
    for var in ("FEATURED_PLAYERS", "PRIVATE_CHANNELS"):
        for spec in os.getenv(var, "").split(","):
            login = twitch.parse_login(spec.partition("|")[2].strip()) if "|" in spec else None
            if login and login not in out:
                out.append(login)
    return out


def record(login, st, now=None):
    """Store one observation of a live stream (st = twitch.stream() dict + 'game_id')."""
    now = now or time.time()
    start = st.get("started") or now
    last = db.q1("SELECT rowid, game_id FROM stream_log WHERE login=? AND stream_start=? ORDER BY first_seen DESC LIMIT 1", login, start)
    if last and last["game_id"] == st.get("game_id"):
        db.run("UPDATE stream_log SET last_seen=?, title=? WHERE rowid=?", now, st.get("title"), last["rowid"])
        return
    first = start if (not last and now - start <= FIRST_GRACE_S) else now
    db.run("INSERT INTO stream_log(login, stream_start, game, game_id, title, first_seen, last_seen) VALUES(?,?,?,?,?,?,?)",
           login, start, st.get("game"), st.get("game_id"), st.get("title"), first, now)


def poll():
    logins = channels()
    for login in logins:
        if login not in _uid:
            u = twitch.lookup_user(login)
            if u:
                _uid[login] = u["id"]
    ids = [_uid[l] for l in logins if l in _uid]
    by_id = {v: k for k, v in _uid.items()}
    for i in range(0, len(ids), 100):
        for st in twitch._get("streams", user_id=ids[i:i + 100]):
            login = by_id.get(st.get("user_id"))
            if login:
                record(login, twitch.stream_from(st))


def segments(login, stream_start, now=None):
    """Category stints of one broadcast, oldest first: [{game, halo, start, end, unknown_before}] in epoch seconds."""
    now = now or time.time()
    rows = db.q("SELECT * FROM stream_log WHERE login=? AND stream_start=? ORDER BY first_seen", login, stream_start)
    out = []
    if rows and rows[0]["first_seen"] > stream_start + FIRST_GRACE_S:     # we started logging mid-stream: say so
        out.append({"game": "Not tracked yet", "halo": False, "unknown": True, "start": stream_start, "end": rows[0]["first_seen"]})
    for i, r in enumerate(rows):
        nxt = rows[i + 1]["first_seen"] if i + 1 < len(rows) else None
        end = nxt or (now if now - r["last_seen"] < 3 * POLL_S else r["last_seen"])
        out.append({"game": r["game"] or "Unknown", "halo": r["game_id"] == twitch.HALO_INFINITE_GAME_ID,
                    "start": r["first_seen"], "end": end})
    return out


def _loop():
    while True:
        try:
            if twitch.enabled():
                poll()
        except Exception:
            log.exception("stream log poll failed")
        time.sleep(POLL_S)


def start():
    init()
    threading.Thread(target=_loop, name="streamlog", daemon=True).start()
