"""One bounded Halo worker, durable import admission, and demand-aware refresh scheduling.

Foreground refreshes take priority over detail, film and background syncs.
Accepted imports remain in SQLite until serviced; an in-memory queue is only
the next small batch, not the full waiting list.
"""
import asyncio
import heapq
import logging
from itertools import zip_longest
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


def enqueue(player_id, reset=False, background=False):
    with _lock:
        if player_id in _queued:
            if not background:
                # A viewer opening an already scheduled profile promotes that
                # job instead of leaving it behind the import backlog.
                with _q.mutex:
                    for i, (pri, seq, job) in enumerate(_q.queue):
                        if job == player_id and pri > PRI_SYNC:
                            _q.queue[i] = (PRI_SYNC, seq, job)
                            heapq.heapify(_q.queue)
                            break
            return False
        if len(_queued)>=(max(1, MAX_PENDING//2) if background else MAX_PENDING):
            return False
        if reset:db.run("UPDATE players SET sync_state='queued',sync_error=NULL WHERE id=?",player_id)
        _queued.add(player_id)
    _put(player_id, 3 if background else PRI_SYNC)
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
        pending = pid in _queued
    if not pending:
        p = db.q1("SELECT id FROM players WHERE id=? AND sync_state='queued'", pid)
        if not p:
            return 0
        return db.q1("SELECT COUNT(*) n FROM players WHERE sync_state IN ('queued','syncing') AND id<=?", pid)['n']
    with _q.mutex:
        items = [x[2] for x in sorted(_q.queue) if not isinstance(x[2], tuple)]
    return (items.index(pid) + 1) if pid in items else 1


def backlog():
    return _q.qsize()


ACTIVE_RESYNC_S = 30
STREAMING_RESYNC_S = 20


def touch(player_id):
    """A short viewing lease; repeated viewers never create extra jobs."""
    now = time.time()
    db.run("UPDATE players SET last_view=? WHERE id=? AND (last_view IS NULL OR last_view<?)",
           now, player_id, now-60)


def viewing_interval():
    # Budget two seconds per distinct watched player, leaving room for detail/film work.
    # This is an admission budget, not a promise of upstream throughput.
    n = db.q1("SELECT COUNT(*) n FROM players WHERE last_view>? AND sync_state IN ('ready','error')",
              time.time()-180)['n']
    return max(STREAMING_RESYNC_S, n * 2)


def stale(player, active=False, streaming=False):
    touch(player["id"])
    limit = max(STREAMING_RESYNC_S if streaming else ACTIVE_RESYNC_S if active else RESYNC_AFTER_S,
                viewing_interval())
    return not player["last_synced"] or time.time()-player["last_synced"] > limit


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
        try:
            schedule()
        except Exception:
            log.exception("scheduler refill failed")
        time.sleep(0.5)


# Recently viewed players back off progressively after their viewing lease ends.
# Featured/followed players retain an hourly background check.
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
    """Fair oldest-first background work, with inactivity backoff and no per-player match queries."""
    now = now or time.time()
    names, slugs = _followed_names()
    interval = max(ACTIVE_RESYNC_S, viewing_interval())
    due = []
    for p in db.q("SELECT id,gamertag,slug,sync_state,last_synced,last_view FROM players WHERE sync_state IN ('ready','error')"):
        age = now - (p['last_view'] or 0)
        followed = p['gamertag'].lower() in names or (p['slug'] or '').lower() in slugs
        if age <= 180:
            limit = interval
        elif age <= 3600:
            limit = 15 * 60
        elif age <= 86400 or followed:
            limit = 3600
        elif age <= WATCHED_DAYS * 86400:
            limit = 24 * 3600
        else:
            continue
        if now - (p['last_synced'] or 0) > limit:
            due.append((p['last_synced'] or 0, p['id']))
    return [pid for _, pid in sorted(due)]


def schedule():
    # Accepted imports live in SQLite, including across restarts. Keep most of a
    # large backlog out of RAM and reserve capacity for foreground requests.
    imports = [p['id'] for p in db.q("SELECT id FROM players WHERE sync_state='queued' ORDER BY id LIMIT ?", MAX_PENDING)]
    for pair in zip_longest(imports, refresh_due()):
        for pid in pair:
            if pid is not None:
                enqueue(pid, background=True)
            with _lock:
                if len(_queued) >= max(1, MAX_PENDING//2):
                    return


def _refresher():
    while True:
        try:
            schedule()
        except Exception:
            log.exception("refresher tick failed")
        time.sleep(REFRESH_TICK_S)


def start():
    db.run("UPDATE players SET sync_state='queued' WHERE sync_state='syncing'")
    threading.Thread(target=_loop, name="sync-worker", daemon=True).start()
    threading.Thread(target=_refresher, name="refresher", daemon=True).start()
