"""One background worker runs player syncs one at a time (keeps the shared Xbox login well under Halo's rate limits).
2026-10-11: a priority line, not first-come-first-served — player syncs (a finished game showing up) first, then
match-page loads, then film reads, and a film job reads at most FILM_BATCH games before the rest go back in line, so
a live squad's games never wait minutes behind a long film read."""
import asyncio
import logging
import os
import queue
import threading
import time

import db
import ingest

log = logging.getLogger("clutchtape.worker")
_q = queue.PriorityQueue()   # items: (priority, seq, job)
_seq = 0
PRI_SYNC, PRI_DETAIL, PRI_FILM = 0, 1, 2
FILM_BATCH = 3
_queued = set()
_lock = threading.Lock()
RESYNC_AFTER_S = 10 * 60
MAX_PENDING = int(os.getenv("MAX_QUEUE", "25"))
_metrics = {"started": 0, "completed": 0, "errors": 0, "job_started_at": 0, "last_completed_at": 0}
_running = None


def _put(job, pri):
    global _seq
    with _lock:
        _seq += 1
        n = _seq
    _q.put((pri, n, job))


def enqueue(player_id, reset=False):
    with _lock:
        if player_id in _queued or len(_queued)>=MAX_PENDING:
            return False
        if reset:db.run("UPDATE players SET sync_state='queued',sync_error=NULL WHERE id=?",player_id)
        _queued.add(player_id)
    _put(player_id, PRI_SYNC)
    return True


_film_pending = {}
_film_rest = {}


def enqueue_film(player_id, match_ids):
    """Queue a film read for games inside a saved broadcast (runs after any pending syncs, same single worker)."""
    ids = [m for m in match_ids if m][:40]
    if not ids:
        return False
    key = ("film", player_id)
    with _lock:
        if key in _queued or len(_queued)>=MAX_PENDING:
            return False
        _queued.add(key)
    _film_pending[player_id] = ids
    _put(key, PRI_FILM)
    return True


def enqueue_detail(mid):
    key = ('detail', mid)
    with _lock:
        if key in _queued:
            return True
        if len(_queued) >= MAX_PENDING:
            return False
        db.kv_set('matchload:' + mid, {'state': 'loading', 'at': time.time()})
        _queued.add(key)
    _put(key, PRI_DETAIL)
    return True


def position(pid):
    """1-based place in line (1 = running/next), or 0 if not queued."""
    with _lock:
        if pid not in _queued:
            return 0
    with _q.mutex:
        items = [x[2] for x in sorted(_q.queue) if not isinstance(x[2], tuple)]
    return (items.index(pid) + 1) if pid in items else 1


def backlog():
    return _q.qsize()


ACTIVE_RESYNC_S = 30
STREAMING_RESYNC_S = 20


def stale(player, active=False, streaming=False):
    """Players on a live stream refresh every 20s (a finished game shows up fast while you watch), players who played
    in the last couple of hours every 30s (only while someone has their page open), everyone else every 10 min."""
    limit = STREAMING_RESYNC_S if streaming else ACTIVE_RESYNC_S if active else RESYNC_AFTER_S
    return (not player["last_synced"]) or time.time() - player["last_synced"] > limit


def metrics():
    with _lock:return dict(_metrics, pending=len(_queued), running=_running is not None)


async def _job(pid):
    async with asyncio.timeout(180):
        if isinstance(pid,tuple) and pid[0]=='detail':
            import match_detail
            await match_detail.fetch_detail(pid[1])
        elif isinstance(pid,tuple) and pid[0]=='history':
            await ingest.backfill_player(pid[1])
        elif isinstance(pid,tuple):
            ids=_film_pending.pop(pid[1],[])
            if ids[FILM_BATCH:]:_film_rest[pid[1]]=ids[FILM_BATCH:]     # the rest goes back in line (after any syncs)
            await ingest.film_matches(pid[1],ids[:FILM_BATCH])
        else:await ingest.sync_player(pid)


def _loop():
    global _running
    while True:
        queued=True
        try:pid=_q.get(timeout=2)[2]
        except queue.Empty:
            # Deep history yields to foreground jobs between batches.
            pending=db.q1("SELECT k FROM kv WHERE k LIKE 'history_pending:%' AND json_extract(v,'$.at')<=? ORDER BY json_extract(v,'$.at') LIMIT 1",time.time())
            if not pending:continue
            pid=('history',int(pending['k'].split(':')[1]));queued=False
        with _lock:
            _running=pid;_metrics['started']+=1;_metrics['job_started_at']=time.time()
        try:
            asyncio.run(_job(pid))
            with _lock:_metrics['completed']+=1;_metrics['last_completed_at']=time.time()
        except Exception:
            with _lock:_metrics['errors']+=1
            log.exception('worker job failed: %s',pid)
            if not isinstance(pid,tuple):db.run("UPDATE players SET sync_state='error',sync_error='Sync interrupted; retrying later',last_synced=? WHERE id=?",time.time(),pid)
            elif pid[0]=='history':
                key='history_pending:'+str(pid[1]);state=db.kv_get(key,{})
                state['attempts']=state.get('attempts',0)+1;state['at']=time.time()+300
                if state['attempts']<5:db.kv_set(key,state)
                else:db.run('DELETE FROM kv WHERE k=?',key)
        finally:
            with _lock:_queued.discard(pid);_running=None
            if queued:_q.task_done()
            if isinstance(pid,tuple) and pid[0]=='film' and pid[1] in _film_rest:enqueue_film(pid[1],_film_rest.pop(pid[1]))
        time.sleep(0.5)


# Background refresh (2026-10-07): syncs used to happen only when someone opened a page, so the demo squad sat
# 90h stale between visits and LIVE badges / "new game in" never fired unattended. Every REFRESH_TICK_S the refresher
# queues: featured/demo players and anyone viewed in the last WATCHED_DAYS — every REFRESH_S normally, every
# ACTIVE_RESYNC_S while they're mid-session (a game ended < 2h ago). Syncs stop at the first stored game, so idle
# refreshes cost one history page each (well inside Halo's rate limits with the single worker).
REFRESH_TICK_S = 60
REFRESH_S = 15 * 60
WATCHED_DAYS = 7


def _followed_names():
    names = {s.split("|")[0].strip().lower() for s in os.getenv("FEATURED_PLAYERS", "CyKul|cykul").split(",") if s.strip()}
    names |= {s.strip().lower() for s in os.getenv("DEMO_SOLO", "").split(",") if s.strip()}
    slugs = set()
    for spec in filter(None, os.getenv("DEMO_SQUADS", "").split(";")):
        slugs |= {x.strip().lower() for x in spec.partition("=")[2].split(",") if x.strip()}
    import alerts
    slugs |= alerts.followed_slugs()
    return names, slugs


def refresh_due(now=None):
    """Player ids the refresher should queue right now (pure: reads the DB, queues nothing)."""
    now = now or time.time()
    names, slugs = _followed_names()
    due = []
    for p in db.q("SELECT id, gamertag, slug, sync_state, last_synced, last_view FROM players WHERE sync_state IN ('ready','error','queued','syncing')"):
        if p['sync_state'] in ('queued','syncing'):
            due.append(p['id']);continue
        followed = p["gamertag"].lower() in names or (p["slug"] or "").lower() in slugs
        watched = (p["last_view"] or 0) > now - WATCHED_DAYS * 86400
        if not (followed or watched):
            continue
        row = db.q1("SELECT MAX(started_at + COALESCE(duration_s, 0)) AS t FROM matches WHERE player_id=?", p["id"])
        last_game = (row["t"] if row else 0) or 0
        limit = ACTIVE_RESYNC_S if now - last_game < 2 * 3600 else REFRESH_S
        if not p["last_synced"] or now - p["last_synced"] > limit:
            due.append(p["id"])
    return due


def _refresher():
    while True:
        time.sleep(REFRESH_TICK_S)
        try:
            if backlog() > 20:           # visitors' first syncs come first
                continue
            for pid in refresh_due():
                if backlog()>=MAX_PENDING-3:break
                enqueue(pid)
        except Exception:
            log.exception("refresher tick failed")


def start():
    for r in db.q("SELECT id FROM players WHERE sync_state IN ('queued','syncing')"):
        enqueue(r["id"])
    threading.Thread(target=_loop, name="sync-worker", daemon=True).start()
    threading.Thread(target=_refresher, name="refresher", daemon=True).start()
