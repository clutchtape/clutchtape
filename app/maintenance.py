"""Online SQLite snapshots, retention, restore verification and private operations status."""
from pathlib import Path
import logging
import os
import sqlite3
import threading
import time
import db
import worker

log=logging.getLogger('clutchtape.maintenance')
INTERVAL=6*3600
_lock=threading.Lock()


def offsite(snapshot_path):
    """2026-10-11: one gzip copy a day of a verified snapshot into OFFSITE_DIR (a folder your offsite job uploads),
    e.g. an encrypted rclone/Google Drive sync. Keeps the newest 3 (~100 MB a day uploaded instead
    of every 6-hourly 340 MB snapshot)."""
    out=os.getenv('OFFSITE_DIR')
    if not out:return None
    root=Path(out);root.mkdir(parents=True,exist_ok=True,mode=0o700)
    day=time.strftime('%Y%m%d',time.gmtime())
    target=root/f'clutchtape-{day}.sqlite.gz'
    if target.exists():return None
    import gzip,shutil
    temp=target.with_suffix('.partial')
    with open(snapshot_path,'rb') as src,gzip.open(temp,'wb',compresslevel=6) as dst:shutil.copyfileobj(src,dst,1024*1024)
    os.chmod(temp,0o600);os.replace(temp,target)
    for old in sorted(root.glob('clutchtape-????????.sqlite.gz'),reverse=True)[3:]:old.unlink()
    db.kv_set('ops:offsite',dict(at=time.time(),file=target.name,bytes=target.stat().st_size))
    return target


def snapshot(directory=None):
    """SQLite's backup API captures committed WAL content without stopping the app."""
    root=Path(directory or os.getenv('BACKUP_DIR','/backups'))
    root.mkdir(parents=True,exist_ok=True,mode=0o700)
    target=root/time.strftime('clutchtape-%Y%m%d-%H%M%S.sqlite',time.gmtime())
    temp=target.with_suffix('.partial')
    with _lock:
        try:
            src=sqlite3.connect(db.DB_PATH,timeout=30)
            dst=sqlite3.connect(temp)
            try:
                src.backup(dst,pages=128,sleep=0.05)
                result=dst.execute('PRAGMA quick_check').fetchone()[0]
                if result!='ok':raise RuntimeError('Backup integrity check failed')
            finally:dst.close();src.close()
            os.chmod(temp,0o600);os.replace(temp,target)
            db.kv_set('ops:backup',dict(at=time.time(),ok=True,bytes=target.stat().st_size))
            # Delete only our own verified snapshot names, and only after a successful replacement.
            for old in sorted(root.glob('clutchtape-????????-??????.sqlite'),reverse=True)[28:]:old.unlink()
            try:offsite(target)
            except Exception:log.exception('Offsite copy failed')   # never fails the local snapshot
            return target
        except Exception:
            temp.unlink(missing_ok=True)
            db.kv_set('ops:backup_error',dict(at=time.time(),message='Snapshot failed; inspect service logs'))
            raise


def status():
    backup=db.kv_get('ops:backup',{})
    error=db.kv_get('ops:backup_error',{})
    metrics=worker.metrics();now=time.time()
    alerts=[]
    if not backup or now-backup.get('at',0)>INTERVAL*2:alerts.append('Backup missing or older than 12 hours')
    if error.get('at',0)>backup.get('at',0):alerts.append('Last backup attempt failed')
    if metrics['running'] and now-metrics['job_started_at']>300:alerts.append('Halo worker has not yielded for over five minutes')
    if metrics['pending']>=worker.MAX_PENDING:alerts.append('Halo queue is full; new lookups are being limited')
    # 2026-10-11: the site can be up while Halo syncing has quietly stopped (expired Xbox login, API change) — visitors
    # would just see "no new games". Alert when people are viewing pages but nobody has synced for 3 hours, or when
    # several players fail with an authorization error.
    try:
        viewed=db.q1('SELECT COUNT(*) n FROM players WHERE last_view>?',now-3*3600)['n']
        synced=db.q1("SELECT MAX(last_synced) t FROM players WHERE sync_state IN ('ready','syncing','queued')")['t'] or 0
        if viewed and now-synced>3*3600:alerts.append('Halo sync stalled: pages viewed but no player synced in 3 hours')
        auth=db.q1("SELECT COUNT(*) n FROM players WHERE sync_state='error' AND (sync_error LIKE '%401%' OR lower(sync_error) LIKE '%auth%' OR lower(sync_error) LIKE '%token%' OR lower(sync_error) LIKE '%unauthor%')")['n']
        if auth>=2:alerts.append(f'Halo login problem: {auth} players failing with an authorization error')
    except Exception:alerts.append('Sync health check failed')
    root=Path(os.getenv('BACKUP_DIR','/backups'))
    try:
        stat=os.statvfs(Path(db.DB_PATH).parent)
        if stat.f_bavail*stat.f_frsize<1024**3:alerts.append('Less than 1 GB free on database storage')
    except OSError:alerts.append('Database storage check failed')
    return dict(backup=backup,worker=metrics,alerts=alerts)


def _loop():
    while True:
        try:
            import retention
            if time.time()-db.kv_get('ops:retention',{}).get('at',0)>86400:retention.sweep()
            saved=db.kv_get('ops:backup',{})
            if time.time()-saved.get('at',0)>=INTERVAL:snapshot()
            db.run('DELETE FROM add_log WHERE at<?',time.time()-86400)
            db.run("DELETE FROM kv WHERE k LIKE 'matchraw:%' AND length(v)>0 AND substr(k,10) NOT IN (SELECT match_id FROM matches)")
            state=status()
            if state['alerts']:log.warning('Operational alerts: %s','; '.join(state['alerts']))
            db.kv_set('ops:heartbeat',dict(at=time.time(),alerts=state['alerts']))
        except Exception:log.exception('Maintenance check failed')
        time.sleep(60)


def start():
    threading.Thread(target=_loop,name='maintenance',daemon=True).start()
