"""Independent health monitor; optional private JSON webhook, never player data."""
import json,os,time,urllib.request,urllib.error
from pathlib import Path

def check(url):
    try:
        with urllib.request.urlopen(urllib.request.Request(url,headers={'Host':'localhost'}),timeout=10) as r:return r.status==200
    except Exception:return False

def notify(url,text):
    if not url.startswith('https://'):raise ValueError('Alert webhooks require HTTPS')
    body=json.dumps({'text':text,'content':text}).encode()
    with urllib.request.urlopen(urllib.request.Request(url,data=body,headers={'Content-Type':'application/json'}),timeout=15) as r:
        if r.status>=300:raise RuntimeError('Alert delivery failed')

def run():
    failures=0;sent=False;last=0
    while True:
        ok=check(os.getenv('HEALTH_URL','http://clutchtape:8140/readyz'));failures=0 if ok else failures+1
        try:
            path=Path(os.getenv('ALERT_WEBHOOK_FILE','/config/alert_webhook'))
            webhook=path.read_text().strip() if path.exists() else ''
            if failures>=3 and (not sent or time.time()-last>3600):
                if webhook:notify(webhook,'Clutchtape needs attention: readiness checks failed three times. Check private service operations.');sent=True;last=time.time()
                else:print('Clutchtape readiness failed; alert destination is not configured.',flush=True)
            elif ok and sent:
                notify(webhook,'Clutchtape recovered: readiness checks pass.');sent=False
        except Exception:print('Alert delivery failed; retrying next check.',flush=True)
        Path('/tmp/monitor-heartbeat').write_text(str(time.time()))
        time.sleep(30)
if __name__=='__main__':run()
