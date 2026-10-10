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
