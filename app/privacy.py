"""Deployment-private removal policy. The published source contains no removal identities."""
import hashlib
import json
import re
from pathlib import Path
from halo_paths import data_path


def digest(value):
    return hashlib.sha256(re.sub(r'[^a-z0-9]', '', str(value).casefold()).encode()).hexdigest()


def _policy():
    path=data_path('privacy_exclusions.json')
    if not path.exists():return set()
    # A malformed configured removal policy must stop startup rather than expose removed data.
    value=json.loads(path.read_text())
    return set(value['hashes'])

HASHES=_policy()


def blocked(value):
    return bool(value) and digest(value) in HASHES


def sanitize_match(raw):
    raw['players']=[p for p in raw.get('players',[]) if not blocked(re.sub(r'\D','',p.get('player_id','')))]
    return raw


def enforce():
    """Apply removal policy before workers/web/backup start, including orphaned cached films."""
    import db
    if not HASHES:return
    signature=hashlib.sha256(''.join(sorted(HASHES)).encode()).hexdigest()
    people=[p for p in db.q('SELECT id,xuid,gamertag,slug FROM players') if any(blocked(p[k]) for k in ('xuid','gamertag','slug'))]
    if db.kv_get('privacy_revision')==signature and not people:return
    db.run('PRAGMA secure_delete=ON')
    mids={r['match_id'] for r in db.q('SELECT DISTINCT match_id FROM matches') if blocked(r['match_id'])}
    for p in people:mids.update(r['match_id'] for r in db.q('SELECT match_id FROM matches WHERE player_id=?',p['id']))
    with db.tx() as c:
        for mid in mids:
            for table in ('matches','moments','events','filmed'):c.execute(f'DELETE FROM {table} WHERE match_id=?',(mid,))
            for prefix in ('matchraw:','matchdetail:','matchload:'):c.execute('DELETE FROM kv WHERE k=?',(prefix+mid,))
        for p in people:
            c.execute('DELETE FROM players WHERE id=?',(p['id'],));c.execute('DELETE FROM kv WHERE k=?',('history_pending:'+str(p['id']),))
        for r in c.execute('SELECT DISTINCT xuid,gt FROM events').fetchall():
            if blocked(r['xuid']) or blocked(r['gt']):c.execute('DELETE FROM events WHERE xuid=? OR gt=?',(r['xuid'],r['gt']))
        # Roster caches can contain a removed player even where another player's stats remain public.
        for r in c.execute("SELECT k,v FROM kv WHERE k LIKE 'matchraw:%' OR k LIKE 'matchdetail:%'").fetchall():
            value=json.loads(r['v'])
            if r['k'].startswith('matchraw:'):sanitize_match(value)
            else:value['players']=[p for p in value.get('players',[]) if not blocked(p.get('xuid')) and not blocked(p.get('name'))]
            c.execute('UPDATE kv SET v=? WHERE k=?',(json.dumps(value),r['k']))
        # Old auth/lookup logs are not needed for the public release.
        c.execute('DELETE FROM add_log')
    db.kv_set('privacy_revision',signature)
    # Force a fresh post-removal snapshot; old private snapshots are handled by the deployment operator.
    db.run("DELETE FROM kv WHERE k IN ('ops:backup','ops:backup_error')")

    db.run('VACUUM')


# Owner-designated players stay out of curated public discovery. They remain searchable
# by an explicit gamertag or shared link; being cached does not imply site membership.
# PRIVATE_HOSTS controls owner demo links and configured channel mappings only.
import os as _os


def _norm(value):
    return re.sub(r'[^a-z0-9]', '', str(value).casefold())


PRIVATE = {_norm(x) for x in _os.getenv("PRIVATE_PLAYERS", "").split(",") if _norm(x)}
PRIVATE_HOSTS = {h.strip().lower() for h in _os.getenv("PRIVATE_HOSTS", "").split(",") if h.strip()}


def private(value):
    """Exclude this player from curated public examples and discovery."""
    return bool(value) and _norm(value) in PRIVATE


def hidden(value):
    """Explicit lookups are allowed; private() only excludes curated discovery.

    Permanent removal requests still use blocked(). Kept as a compatibility helper
    for routes that previously treated the owner's squad as inaccessible.
    """
    return False
