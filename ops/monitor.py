"""Independent health monitor; alerts go to a private webhook (HTTPS JSON) and/or ntfy, never player data.
2026-10-11: says WHAT is wrong (the readiness alerts: sync stalled, Halo login problem, backups, disk) and can push to
ntfy (NTFY_URL, e.g. http://ntfy.lan:2586/alerts — keep it on your LAN). One alert per problem set, a re-nag every 6 h,
and a recovery notice."""
import json,os,time,urllib.request,urllib.error
from pathlib import Path

def check(url):
    """-> (ok, [alert texts])"""
    try:
        with urllib.request.urlopen(urllib.request.Request(url,headers={'Host':'localhost'}),timeout=10) as r:return r.status==200,[]
    except urllib.error.HTTPError as e:
        try:alerts=json.loads(e.read().decode() or '{}').get('alerts') or []
        except Exception:alerts=[]
        return False,alerts or [f'readiness returned {e.code}']
    except Exception:return False,['site not answering']

def webhook(url,text):
    if not url.startswith('https://'):raise ValueError('Alert webhooks require HTTPS')
    body=json.dumps({'text':text,'content':text}).encode()
    with urllib.request.urlopen(urllib.request.Request(url,data=body,headers={'Content-Type':'application/json'}),timeout=15) as r:
        if r.status>=300:raise RuntimeError('Alert delivery failed')

def ntfy(url,title,text,recovered=False):
    req=urllib.request.Request(url,data=text.encode(),headers={'Title':title,'Tags':'white_check_mark' if recovered else 'warning','Priority':'3' if recovered else '4'})
    with urllib.request.urlopen(req,timeout=15) as r:
        if r.status>=300:raise RuntimeError('ntfy delivery failed')

def send(text,recovered=False):
    sent=False
    path=Path(os.getenv('ALERT_WEBHOOK_FILE','/config/alert_webhook'))
    hook=path.read_text().strip() if path.exists() else ''
    if hook:webhook(hook,text);sent=True
    if os.getenv('NTFY_URL'):ntfy(os.getenv('NTFY_URL'),'Clutchtape recovered' if recovered else 'Clutchtape needs attention',text,recovered);sent=True
    if not sent:print('Alert (no destination configured): '+text,flush=True)

class QueuePressure:
    """Queue capacity is advisory: ten minutes sustained, hourly at most, no recovery ping."""
    def __init__(self):
        self.since = None
        self.sent_at = None

    def due(self, full, now):
        if not full:
            self.since = None
            return False
        if self.since is None:
            self.since = now
        return (now-self.since >= 600
                and (self.sent_at is None or now-self.sent_at >= 3600))


def run():
    failures=0;active=None;last=0;pressure=QueuePressure()
    while True:
        ok,alerts=check(os.getenv('HEALTH_URL','http://clutchtape:8140/readyz'))
        queue_full=any('Halo queue is full' in alert for alert in alerts)
        if queue_full:
            alerts=[alert for alert in alerts if 'Halo queue is full' not in alert]
            ok=not alerts
        failures=0 if ok else failures+1
        try:
            if pressure.due(queue_full,time.time()):
                send('Clutchtape: Halo processing has stayed at capacity for 10 minutes. Saved stats remain available; new details may be delayed.')
                pressure.sent_at=time.time()
            if failures>=3:
                key=sorted(alerts)
                if key!=active or time.time()-last>6*3600:
                    send('Clutchtape needs attention: '+'; '.join(alerts));active=key;last=time.time()
            elif ok and active is not None:
                send('Clutchtape recovered: readiness checks pass.',True);active=None
        except Exception as e:print(f'Alert delivery failed ({type(e).__name__}); retrying next check.',flush=True)
        Path('/tmp/monitor-heartbeat').write_text(str(time.time()))
        time.sleep(30)
if __name__=='__main__':run()
