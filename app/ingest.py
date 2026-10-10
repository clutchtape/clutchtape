import stat_depth
import objectives
import privacy
"""Pull one player's public Halo match history + per-match stats into SQLite."""
import asyncio
import json
import logging
import os
import re
import time

from aiohttp import ClientSession, ClientResponseError, ClientTimeout
from spnkr import HaloInfiniteClient

import clips
import db
import xbox

log = logging.getLogger("clutchtape.ingest")
FIRST_SYNC_MATCHES = int(os.getenv("FIRST_SYNC_MATCHES", "200"))
FILM_MATCHES = int(os.getenv("FILM_MATCHES", "50"))          # how many of the newest games get clip-detection
CONCURRENCY = int(os.getenv("INGEST_CONCURRENCY", "3"))
OUTCOMES = {0: "Left", 1: "Tie", 2: "Win", 3: "Loss", 4: "Dnf"}
_meta_cache = {}          # "kind:asset:version" -> name
_medal_names = {}         # medal name_id -> display name


async def _retry(make, tries=6):
    """Run an API call; on Halo's 429 wait (Retry-After, else 2,4,8.. s) and try again instead of failing the sync."""
    for i in range(tries):
        try:
            return await make()
        except ClientResponseError as e:
            if e.status != 429 or i == tries - 1:
                raise
            try:
                wait = float(e.headers.get("Retry-After", 0)) or 2 * (2 ** i)
            except (TypeError, ValueError):
                wait = 2 * (2 ** i)
            await asyncio.sleep(min(30, wait))


def xuid_of(x):
    return re.sub(r"\D", "", str(x))


async def _name(client, kind, asset_id, version_id):
    if not asset_id:
        return None
    key = f"{kind}:{asset_id}:{version_id}"
    if key in _meta_cache:
        return _meta_cache[key]
    name = None
    try:
        fn = {"map": client.discovery_ugc.get_map,
              "mode": client.discovery_ugc.get_ugc_game_variant,
              "playlist": client.discovery_ugc.get_playlist}[kind]
        d = await (await fn(asset_id, version_id)).parse()
        for a in ("public_name", "name", "asset_name", "display_name", "title"):
            if getattr(d, a, None):
                name = str(getattr(d, a))
                break
    except Exception as exc:
        log.debug("metadata %s failed: %s", key, exc)
    _meta_cache[key] = name
    return name


async def _load_medals(client):
    if _medal_names:
        return
    try:
        m = await (await client.gamecms_hacs.get_medal_metadata()).parse()
        for x in m.medals:
            _medal_names[int(x.name_id)] = x.name.value if hasattr(x.name, "value") else str(x.name)
    except Exception as exc:
        log.warning("medal metadata failed: %s", exc)


async def resolve_gamertag(gamertag):
    """-> (xuid, canonical gamertag) or None if no such account."""
    args = xbox.client_args()
    async with ClientSession(timeout=ClientTimeout(total=25)) as s:
        c = HaloInfiniteClient(session=s, **args)
        try:
            u = await (await c.profile.get_user_by_gamertag(gamertag)).parse()
        except ClientResponseError as e:
            if e.status in (400, 404):
                return None
            if e.status == 401:
                xbox.ensure_fresh(force=True)
            raise
        return str(u.xuid), str(u.gamertag)


def _row(player_xuid, ms, hist_item):
    """Flatten one match + this player's stats into a matches row (dict) or None."""
    me = next((p for p in ms.players if xuid_of(p.player_id) == player_xuid), None)
    if me is None or not me.player_team_stats:
        return None
    ts = me.player_team_stats[0]
    cs = ts.stats.core_stats
    my_team = me.last_team_id
    scores, pscores = {}, {}
    for t in (ms.teams or []):
        try:
            scores[t.team_id] = t.stats.core_stats.score
            pscores[t.team_id] = t.stats.core_stats.personal_score
        except Exception:
            pass
    enemy = [v for k, v in scores.items() if k != my_team]
    medals = {}
    for md in (cs.medals or []):
        nm = _medal_names.get(int(md.name_id)) or f"Medal {int(md.name_id)}"
        medals[nm] = medals.get(nm, 0) + int(md.count)
    started = ms.match_info.start_time.timestamp()
    dur = ms.match_info.duration
    try:                                    # the Theater film starts at EndTime - Duration (StartTime is a lobby stamp)
        film_t0 = ms.match_info.end_time.timestamp() - dur.total_seconds()
    except Exception:
        film_t0 = None
    advanced=stat_depth.extract(cs)
    team=next((t for t in (ms.teams or []) if t.team_id==my_team),None)
    damage=stat_depth.number(getattr(getattr(getattr(team,"stats",None),"core_stats",None),"damage_dealt",None))
    if damage is not None:advanced["team_damage"]=damage
    return {
        "started_at": started, "duration_s": int(dur.total_seconds()) if hasattr(dur, "total_seconds") else None,
        "outcome": OUTCOMES.get(int(me.outcome), "Unknown"),
        "kills": cs.kills, "deaths": cs.deaths, "assists": cs.assists, "accuracy": cs.accuracy,
        "damage_dealt": cs.damage_dealt, "damage_taken": cs.damage_taken, "score": cs.score,
        "advanced": json.dumps(advanced), "objectives": json.dumps(objectives.extract(ts.stats)), "personal_score": cs.personal_score, "headshots": cs.headshot_kills, "shots_fired": cs.shots_fired,
        "shots_hit": cs.shots_hit, "max_spree": cs.max_killing_spree, "callouts": cs.callout_assists,
        "team_score": scores.get(my_team), "enemy_score": (max(enemy) if enemy else None),
        "medals": json.dumps(medals), "film_t0": film_t0, "team_pscore": pscores.get(my_team), "team_id": my_team, "_mi": ms.match_info,
    }


async def _one_match(client, sem, player_xuid, match_id, hist_item):
    async with sem:
        if privacy.blocked(match_id) or privacy.blocked(player_xuid):return None
        ms = await (await _retry(lambda: client.stats.get_match_stats(match_id))).parse()
        if privacy.blocked(player_xuid) or ms.match_info.start_time.timestamp() < time.time()-180*86400:return None
        if not db.kv_get('matchdetail:' + match_id):
            db.kv_set('matchraw:' + match_id, privacy.sanitize_match(ms.model_dump(mode='json')))
        row = _row(player_xuid, ms, hist_item)
        if row is None:
            return None
        mi = row.pop("_mi")
        gv, mv, pl = mi.ugc_game_variant, mi.map_variant, getattr(mi, "playlist", None)
        row["mode"] = await _name(client, "mode", gv.asset_id, gv.version_id)
        row["map"] = await _name(client, "map", mv.asset_id, mv.version_id)
        row["playlist"] = await _name(client, "playlist", pl.asset_id, pl.version_id) if pl else None
        row["ranked"] = 1 if row["playlist"] and "ranked" in row["playlist"].lower() else 0
        row["pre_csr"] = row["post_csr"] = None
        if row["ranked"]:
            try:
                sk = await (await _retry(lambda: client.skill.get_match_skill(match_id=match_id, xuids=[player_xuid]), 3)).parse()
                for e in getattr(sk, "value", None) or []:
                    extra=json.loads(row["advanced"]);extra.update(stat_depth.skill(getattr(e,"result",None)));row["advanced"]=json.dumps(extra)
                    rr = getattr(getattr(e, "result", None), "rank_recap", None)
                    if rr:
                        pre, post = getattr(rr, "pre_match_csr", None), getattr(rr, "post_match_csr", None)
                        row["pre_csr"] = getattr(pre, "value", None) if pre else None
                        row["post_csr"] = getattr(post, "value", None) if post else None
                    break
            except Exception:
                pass
        return match_id, row


INSERT = ("INSERT OR REPLACE INTO matches(player_id,match_id,started_at,duration_s,map,mode,playlist,ranked,outcome,"
          "kills,deaths,assists,accuracy,damage_dealt,damage_taken,score,personal_score,headshots,shots_fired,"
          "shots_hit,max_spree,callouts,team_score,enemy_score,pre_csr,post_csr,medals,film_t0,team_pscore,team_id,objectives,advanced) "
          "VALUES(:player_id,:match_id,:started_at,:duration_s,:map,:mode,:playlist,:ranked,:outcome,:kills,:deaths,"
          ":assists,:accuracy,:damage_dealt,:damage_taken,:score,:personal_score,:headshots,:shots_fired,:shots_hit,"
          ":max_spree,:callouts,:team_score,:enemy_score,:pre_csr,:post_csr,:medals,:film_t0,:team_pscore,:team_id,:objectives,:advanced)")


class _Ev:
    __slots__ = ("xuid", "gamertag", "event_type", "time_ms", "medal_name")

    def __init__(self, xuid, gt, k, t, medal):
        self.xuid, self.gamertag, self.event_type, self.time_ms, self.medal_name = xuid, gt, k, t, medal


def _stored_events(mid):
    if not db.q1("SELECT 1 FROM filmed WHERE match_id=?", mid):
        return None
    return [_Ev(r["xuid"], r["gt"], r["k"], r["t_ms"], r["medal"])
            for r in db.q("SELECT xuid,gt,t_ms,k,medal FROM events WHERE match_id=? ORDER BY t_ms", mid)]


def _store_events(mid, events):
    rows = [(mid, str(e.xuid), e.gamertag, int(e.time_ms), e.event_type, e.medal_name)
            for e in events if e.event_type in ("kill", "death", "medal", "mode") and not privacy.blocked(str(e.xuid)) and not privacy.blocked(e.gamertag)]
    with db.tx() as c:
        c.execute("DELETE FROM events WHERE match_id=?", (mid,))
        c.executemany("INSERT INTO events(match_id,xuid,gt,t_ms,k,medal) VALUES(?,?,?,?,?,?)", rows)
        c.execute("INSERT OR REPLACE INTO filmed(match_id,n,at) VALUES(?,?,?)", (mid, len(rows), time.time()))


async def film_pass(client, player_id, xuid, limit, match_ids=None):
    """Find highlight moments in the newest games' Theater films (timestamps only, nothing is rendered)."""
    try:
        from spnkr.film.api import read_highlight_events
    except Exception as exc:
        log.warning("film api unavailable: %s", exc)
        return
    # Only the newest `limit` games are ever filmed (space): older ones are left alone, every new game shifts the window.
    if match_ids:          # explicit list: games that sit inside a saved Twitch broadcast (clips need their film)
        ph = ",".join("?" * len(match_ids))
        rows = db.q(f"SELECT match_id, started_at, film_t0 FROM matches WHERE player_id=? AND film_state=0 "
                    f"AND match_id IN ({ph})", player_id, *match_ids)
    else:
        rows = db.q("SELECT match_id, started_at, film_t0 FROM (SELECT * FROM matches WHERE player_id=? "
                    "ORDER BY started_at DESC LIMIT ?) WHERE film_state=0", player_id, limit)
    for r in rows:
        mid, t0 = r["match_id"], r["film_t0"]
        try:
            if t0 is None:
                ms = await (await _retry(lambda: client.stats.get_match_stats(mid))).parse()
                t0 = ms.match_info.end_time.timestamp() - ms.match_info.duration.total_seconds()
            events = _stored_events(mid)
            if events is None:                # one film read serves every tracked player in the match
                events = list(await _retry(lambda: read_highlight_events(client, mid), 4))
                _store_events(mid, events)
            found = clips.find_moments(events, xuid, _game_ctx(player_id, mid))
            with db.tx() as c:
                c.execute("DELETE FROM moments WHERE player_id=? AND match_id=?", (player_id, mid))
                for m in found:
                    c.execute("INSERT OR REPLACE INTO moments(player_id,match_id,t_ms,at,dur_s,label,kills,score) "
                              "VALUES(?,?,?,?,?,?,?,?)",
                              (player_id, mid, m["t_ms"], t0 + m["t_ms"] / 1000.0, m["dur_s"], m["label"], m["kills"], m["score"]))
                c.execute("UPDATE matches SET film_state=1, film_t0=? WHERE player_id=? AND match_id=?", (t0, player_id, mid))
        except ClientResponseError as e:
            if e.status in (401, 403, 429):
                return                       # auth hiccup or rate limit: try again on the next sync, keep film_state=0
            young = time.time() - (r["started_at"] or 0) < 2 * 3600
            if not young:
                db.run("UPDATE matches SET film_state=2 WHERE player_id=? AND match_id=?", player_id, mid)
        except Exception as exc:
            log.info("film skipped %s: %s", mid[:8], str(exc)[:100])
            if time.time() - (r["started_at"] or 0) > 2 * 3600:
                db.run("UPDATE matches SET film_state=2 WHERE player_id=? AND match_id=?", player_id, mid)
        await asyncio.sleep(0.25)


async def sync_player(player_id, first_try=True):
    p = db.q1("SELECT * FROM players WHERE id=?", player_id)
    if not p or privacy.blocked(p["xuid"]):
        return
    db.run("UPDATE players SET sync_state='syncing', sync_error=NULL WHERE id=?", player_id)
    xuid = p["xuid"]
    known = {r["match_id"] for r in db.q("SELECT match_id FROM matches WHERE player_id=?", player_id)}
    featured = {s.split("|")[0].strip().lower() for s in os.getenv("FEATURED_PLAYERS", "CyKul|cykul").split(",")}
    if not known:
        limit = 25                     # first page quickly; deeper history runs during quiet periods
    elif p["gamertag"].lower() in featured:
        limit = 600                     # the public example gets a deep history so it reaches saved broadcasts
    else:
        limit = FIRST_SYNC_MATCHES if not known else 200
    try:
        args = xbox.client_args()
        async with ClientSession(timeout=ClientTimeout(total=25)) as s:
            client = HaloInfiniteClient(session=s, requests_per_second=3, **args)
            await _load_medals(client)
            new_items, start, done = [], 0, False
            while not done and len(new_items) < limit:
                page = await (await _retry(lambda: client.stats.get_match_history(xuid, start=start, count=25))).parse()
                await asyncio.sleep(0.6)
                if not page.results:
                    if start == 0 and not known:      # nothing at all: hidden in Xbox privacy settings (or never played)
                        db.run("UPDATE players SET sync_state='private', last_synced=? WHERE id=?", time.time(), player_id)
                        return
                    break
                for it in page.results:
                    if str(it.match_id) in known:
                        done = True          # history is newest-first: everything older is already stored
                        break
                    new_items.append(it)
                start += 25
            if new_items:          # don't clobber the counters when a quick refresh finds nothing new
                db.run("UPDATE players SET matches_total=?, matches_done=0 WHERE id=?", len(new_items), player_id)
            sem = asyncio.Semaphore(CONCURRENCY)
            finished = 0
            for i in range(0, len(new_items), 12):
                chunk = new_items[i:i + 12]
                res = await asyncio.gather(*[_one_match(client, sem, xuid, str(it.match_id), it) for it in chunk],
                                           return_exceptions=True)
                with db.tx() as c:
                    for r in res:
                        if isinstance(r, Exception) or r is None:
                            continue
                        mid, row = r
                        row.update(player_id=player_id, match_id=mid)
                        if not privacy.blocked(xuid) and c.execute("SELECT 1 FROM players WHERE id=?",(player_id,)).fetchone():c.execute(INSERT, row)
                finished += len(chunk)
                db.run("UPDATE players SET matches_done=? WHERE id=?", finished, player_id)
            # Gradually enrich existing history without deleting rows or re-reading films.
            for old in db.q("SELECT match_id FROM matches WHERE player_id=? AND (objectives IS NULL OR advanced IS NULL OR COALESCE(json_extract(advanced,'$._version'),0)<2) ORDER BY started_at DESC LIMIT 3", player_id):
                try:
                    result = await _one_match(client, sem, xuid, old['match_id'], None)
                    if result and not privacy.blocked(xuid):
                        _,row=result
                        db.run("UPDATE matches SET objectives=?,advanced=? WHERE player_id=? AND match_id=?", row['objectives'], row['advanced'], player_id, old['match_id'])
                except Exception:
                    log.warning("Objective enrichment deferred for player %s", player_id)
                    break
        db.run("UPDATE players SET sync_state='ready', last_synced=? WHERE id=?", time.time(), player_id)
        if not known and len(new_items)>=25:
            db.kv_set('history_pending:'+str(player_id),dict(start=25,target=600 if p['gamertag'].lower() in featured else FIRST_SYNC_MATCHES,at=time.time()))
        # Film reads are bounded separately and yield to other queued players.
        import worker
        worker.enqueue_film(player_id,[r['match_id'] for r in db.q("SELECT match_id FROM matches WHERE player_id=? AND film_state=0 ORDER BY started_at DESC LIMIT 5",player_id)])
        return
    except ClientResponseError as e:
        if e.status == 401 and first_try:
            xbox.ensure_fresh(force=True)
            return await sync_player(player_id, first_try=False)
        if e.status == 429:                      # Halo asked us to slow down: requeue quietly and try again shortly
            wait = 45
            try:
                wait = min(300, max(20, int(e.headers.get("Retry-After", wait))))
            except Exception:
                pass
            db.run("UPDATE players SET sync_state='queued', sync_error=NULL WHERE id=?", player_id)
            import threading, worker
            threading.Timer(wait, worker.enqueue, [player_id]).start()
            log.warning("Halo 429 for player %s at %s; retrying in %ss", player_id, getattr(getattr(e, "request_info", None), "url", "?"), wait)
            return
        state = "private" if e.status in (403, 404) else "error"
        db.run("UPDATE players SET sync_state=?, sync_error=? WHERE id=?", state, f"Halo API {e.status}", player_id)
    except Exception as exc:
        log.exception("sync failed for player %s", player_id)
        db.run("UPDATE players SET sync_state='error', sync_error=? WHERE id=?", str(exc)[:200], player_id)


async def film_matches(player_id, match_ids):
    """Read the films of specific games (the ones covered by a saved broadcast)."""
    p = db.q1("SELECT xuid FROM players WHERE id=?", player_id)
    if not p or not match_ids:
        return
    async with ClientSession(timeout=ClientTimeout(total=25)) as s:
        c = HaloInfiniteClient(session=s, requests_per_second=3, **xbox.client_args())
        await film_pass(c, player_id, p["xuid"], 0, match_ids=list(match_ids)[:40])


def _game_ctx(player_id, match_id):
    r = db.q1("SELECT duration_s, team_score, enemy_score, mode FROM matches WHERE player_id=? AND match_id=?", player_id, match_id)
    return dict(r) if r else {}


def refresh_rarity():
    """Medal rarity for the clip scorer, from every stored film timeline (clips.set_rarity)."""
    try:
        clips.set_rarity({r["medal"]: r["n"] for r in db.q("SELECT medal, COUNT(*) AS n FROM events WHERE medal IS NOT NULL AND medal != '' GROUP BY medal")})
    except Exception:
        log.exception("medal rarity refresh failed")


def rescore_all():
    """Re-run clip detection over every stored film timeline (no API calls). Used when the rubric changes."""
    refresh_rarity()
    n = 0
    for r in db.q("SELECT m.player_id, m.match_id, m.film_t0, p.xuid FROM matches m JOIN players p ON p.id=m.player_id "
                  "JOIN filmed f ON f.match_id=m.match_id WHERE m.film_t0 IS NOT NULL"):
        evs = _stored_events(r["match_id"])
        if evs is None:
            continue
        found = clips.find_moments(evs, r["xuid"], _game_ctx(r["player_id"], r["match_id"]))
        with db.tx() as c:
            c.execute("DELETE FROM moments WHERE player_id=? AND match_id=?", (r["player_id"], r["match_id"]))
            for m in found:
                c.execute("INSERT OR REPLACE INTO moments(player_id,match_id,t_ms,at,dur_s,label,kills,score) VALUES(?,?,?,?,?,?,?,?)",
                          (r["player_id"], r["match_id"], m["t_ms"], r["film_t0"] + m["t_ms"] / 1000.0, m["dur_s"], m["label"], m["kills"], m["score"]))
        n += 1
    log.info("rescored clips for %d filmed games", n)


async def backfill_player(player_id):
    """One 25-match background batch. Never delays admission of the next foreground job."""
    key='history_pending:'+str(player_id);state=db.kv_get(key)
    p=db.q1('SELECT * FROM players WHERE id=?',player_id)
    if not state or not p:return
    async with ClientSession(timeout=ClientTimeout(total=25)) as session:
        client=HaloInfiniteClient(session=session,requests_per_second=3,**xbox.client_args())
        history=await(await _retry(lambda:client.stats.get_match_history(p['xuid'],start=state['start'],count=25))).parse()
        known={r['match_id'] for r in db.q('SELECT match_id FROM matches WHERE player_id=?',player_id)}
        sem=asyncio.Semaphore(CONCURRENCY)
        for offset in range(0,len(history.results),6):
            batch=[it for it in history.results[offset:offset+6] if str(it.match_id) not in known]
            results=await asyncio.gather(*[_one_match(client,sem,p['xuid'],str(it.match_id),it) for it in batch],return_exceptions=True)
            with db.tx() as c:
                for result in results:
                    if result is None or isinstance(result,Exception):continue
                    mid,row=result;row.update(player_id=player_id,match_id=mid)
                    if not privacy.blocked(p["xuid"]) and c.execute("SELECT 1 FROM players WHERE id=?",(player_id,)).fetchone():c.execute(INSERT,row)
        count=db.q1('SELECT COUNT(*) n FROM matches WHERE player_id=?',player_id)['n']
        db.run('UPDATE players SET matches_done=?,matches_total=MAX(matches_total,?) WHERE id=?',count,count,player_id)
        next_start=state['start']+25
        if not history.results or next_start>=state['target']:db.run('DELETE FROM kv WHERE k=?',key)
        else:db.kv_set(key,dict(start=next_start,target=state['target'],at=time.time()))
