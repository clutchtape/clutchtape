"""Device isolation, opt-in lifecycle and durable alert delivery without sending push."""
import base64
import json
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
import time
import unittest
from unittest.mock import patch, Mock
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'app'))
import alerts
import db
import web

class AlertTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.conn = sqlite3.connect(':memory:', isolation_level=None); self.conn.row_factory=sqlite3.Row
        self.patches=[patch.object(db,'conn',return_value=self.conn),patch.object(alerts,'data_path',side_effect=lambda name:Path(self.temp.name)/name),patch.object(web.xbox,'status',return_value={'connected':True}),patch.object(alerts.privacy,'PRIVATE_HOSTS',{'localhost'}),patch.object(alerts.privacy,'HASHES',set()),patch.object(alerts.privacy,'PRIVATE',set()),patch.dict(os.environ,{'FEATURED_PLAYERS':'Player A|player_a'})]
        for p in self.patches:p.start()
        db.init();web.app.config.update(TESTING=True,SECRET_KEY='test-key')
        import capacity
        capacity.limiter=capacity.Limiter()
        self.a=web.app.test_client();self.b=web.app.test_client()
        for c in (self.a,self.b):
            with c.session_transaction() as s:s['csrf']='test-csrf'
            c.get('/api/alerts/state')
        for i in (1,2):db.run('INSERT INTO players(id,xuid,gamertag,slug,created_at,sync_state) VALUES(?,?,?,?,?,?)',i,str(i),'Player '+('A' if i==1 else 'B'),'player-'+('a' if i==1 else 'b'),1,'ready')
        db.run('INSERT INTO squad_links VALUES(?,?,?)','abc123','player-a,player-b',1)
        self.now=time.time()
        self.sub=dict(endpoint='https://fcm.googleapis.com/wp/test',keys=dict(p256dh=base64.urlsafe_b64encode(b'\x04'+b'a'*64).rstrip(b'=').decode(),auth=base64.urlsafe_b64encode(b'a'*16).rstrip(b'=').decode()))
    def tearDown(self):
        for p in reversed(self.patches):p.stop()
        self.conn.close();self.temp.cleanup()
    def post(self,client,path,data):return client.post('/api/alerts/'+path,json=data,headers={'X-CSRF-Token':'test-csrf'})
    def follow(self,client=None,targets=None,**settings):
        return self.post(client or self.a,'preferences',dict(targets=targets or ['/p/player-a'],settings=settings or dict(streams=True,results=True)))
    def match(self,id,start,duration=300,player=1,outcome='Win'):
        db.run('INSERT INTO matches(player_id,match_id,started_at,duration_s,outcome,kills,deaths,assists) VALUES(?,?,?,?,?,?,?,?)',player,id,start,duration,outcome,20,10,5)
    def test_device_isolation_and_csrf(self):
        self.assertEqual(self.a.post('/api/alerts/preferences',json={}).status_code,400)
        self.assertEqual(self.follow().status_code,200)
        self.assertEqual(len(self.a.get('/api/alerts/state').json['follows']),1)
        self.assertEqual(self.b.get('/api/alerts/state').json['follows'],[])
        self.assertEqual(self.post(self.b,'unsubscribe',{}).status_code,200)
        self.assertEqual(len(self.a.get('/api/alerts/state').json['follows']),1)
    def test_resolve_scopes_private_and_external_urls(self):
        f=self.a.get('/api/alerts/resolve?target=/sq/abc123/g/12345678').json
        self.assertEqual(len(f['players']),2);self.assertEqual(f['players'][0]['channel'],'player_a')
        for target in ['https://evil.example/p/player-a','//evil.example/p/player-a','/p/missing']:
            self.assertIn(self.a.get('/api/alerts/resolve',query_string={'target':target}).status_code,(400,404))
        with patch.object(alerts.privacy,'HASHES',{alerts.privacy.digest('Player A')}):
            self.assertEqual(self.a.get('/api/alerts/resolve?target=/p/player-a').status_code,404)
    def test_subscription_validation_ownership_and_off(self):
        self.assertEqual(self.post(self.a,'subscribe',self.sub).status_code,400)
        self.follow();self.follow(self.b)
        for endpoint in ['http://fcm.googleapis.com/a','https://127.0.0.1/a','https://fcm.googleapis.com.evil.example/a','https://fcm.googleapis.com:bad/a','https://user@fcm.googleapis.com/a']:
            self.assertEqual(self.post(self.a,'subscribe',{**self.sub,'endpoint':endpoint}).status_code,400)
        self.assertEqual(self.post(self.a,'subscribe',{**self.sub,'keys':{}}).status_code,400)
        self.assertTrue(self.post(self.a,'subscribe',self.sub).json['enabled'])
        self.assertEqual(self.post(self.b,'subscribe',self.sub).status_code,409)
        self.assertFalse(self.post(self.a,'unsubscribe',{}).json['enabled'])
        self.assertEqual(self.post(self.a,'test',{}).status_code,400)
    def test_result_settlement_no_backfill_and_dedupe(self):
        f=self.follow(targets=['/sq/abc123']).json['follows'][0];since=f['since']
        self.match('old',since-7200)
        self.match('new',since+10);self.match('new',since+10,player=2,outcome='Loss')
        self.assertEqual(alerts.result_events(f,since,since+2000,'localhost'),[])
        events=alerts.result_events(f,since,since+2200,'localhost');self.assertEqual(len(events),1)
        self.assertIn('1 games',events[0][1]['title']);self.assertIn('1W–0L',events[0][1]['body']);self.assertIn('0W–1L',events[0][1]['body'])
        with patch.object(twitch:=alerts.twitch,'enabled',return_value=False):
            alerts.collect(since+2200);alerts.collect(since+2300)
        self.assertEqual(db.q1('SELECT COUNT(*) AS n FROM alert_events')['n'],1)
    def test_stream_once_per_broadcast_and_disabled_types(self):
        self.follow(streams=True,results=False)
        st={'user_login':'player_a','id':'broadcast1','title':'Playing Halo'}
        with patch.object(alerts.twitch,'enabled',return_value=True),patch.object(alerts.twitch,'_get',return_value=[st]):
            alerts.collect();alerts.collect()
        self.assertEqual(db.q1('SELECT COUNT(*) AS n FROM alert_events')['n'],1)
        self.assertEqual(len(self.a.get('/api/alerts/state').json['events']),1)
        self.follow(streams=False,results=False)
        with patch.object(alerts.twitch,'enabled',return_value=True),patch.object(alerts.twitch,'_get') as fetch:
            alerts.collect();fetch.assert_not_called()
        self.assertEqual(db.q1('SELECT COUNT(*) AS n FROM alert_events')['n'],1)
    def test_new_follow_does_not_replay_old_results(self):
        self.follow();db.run('UPDATE alert_devices SET created=?',self.now-86400)
        self.match('old-b',self.now-4000,player=2)
        self.follow(targets=['/p/player-a','/p/player-b'])
        with patch.object(alerts.twitch,'enabled',return_value=False):alerts.collect(self.now+10)
        self.assertEqual(db.q1('SELECT COUNT(*) AS n FROM alert_events')['n'],0)
    def test_delivery_retry_and_expired_subscription(self):
        self.follow();self.post(self.a,'subscribe',self.sub);self.post(self.a,'test',{})
        with patch('pywebpush.webpush',side_effect=RuntimeError('temporary')):
            alerts.deliver(self.now+1)
        row=db.q1('SELECT * FROM alert_events');self.assertEqual(row['delivered'],0);self.assertEqual(row['attempts'],1)
        with patch('pywebpush.webpush',return_value=Mock(status_code=201)) as send:
            alerts.deliver(self.now+2);send.assert_not_called()
            alerts.deliver(self.now+200);self.assertEqual(send.call_count,1)
        self.assertEqual(db.q1('SELECT delivered FROM alert_events')['delivered'],1)
        self.post(self.a,'test',{})
        from pywebpush import WebPushException
        with patch('pywebpush.webpush',side_effect=WebPushException('gone',response=Mock(status_code=410))):alerts.deliver(self.now+300)
        self.assertIsNone(db.q1('SELECT subscription FROM alert_devices')['subscription'])
    def test_test_only_targets_own_device(self):
        self.follow();self.follow(self.b);self.post(self.a,'subscribe',self.sub)
        self.post(self.b,'subscribe',{**self.sub,'endpoint':self.sub['endpoint']+'-b'})
        self.post(self.a,'test',{})
        with patch('pywebpush.webpush',return_value=Mock(status_code=201)) as send:
            alerts.deliver();self.assertEqual(send.call_count,1);self.assertEqual(send.call_args.kwargs['subscription_info']['endpoint'],self.sub['endpoint'])
    def test_real_webpush_encryption_and_no_redirects(self):
        from cryptography.hazmat.primitives.asymmetric import ec
        from cryptography.hazmat.primitives import serialization
        key=ec.generate_private_key(ec.SECP256R1()).public_key().public_bytes(serialization.Encoding.X962,serialization.PublicFormat.UncompressedPoint)
        self.sub['keys']['p256dh']=base64.urlsafe_b64encode(key).rstrip(b'=').decode()
        self.follow();self.post(self.a,'subscribe',self.sub);self.post(self.a,'test',{})
        with patch('requests.Session.post',return_value=Mock(status_code=201,text='',content=b'')) as transport:
            alerts.deliver()
        self.assertEqual(transport.call_count,1)
        kwargs=transport.call_args.kwargs
        self.assertFalse(kwargs['allow_redirects'])
        self.assertEqual(kwargs['timeout'],10)
        self.assertEqual(kwargs['headers']['content-encoding'],'aes128gcm')
        self.assertGreater(len(kwargs['data']),100)
        self.assertEqual(db.q1('SELECT delivered FROM alert_events')['delivered'],1)

    def test_worker_and_manifest(self):
        r=self.a.get('/sw.js');self.assertEqual(r.status_code,200);self.assertEqual(r.headers['Service-Worker-Allowed'],'/');self.assertIn("worker-src 'self'",r.headers['Content-Security-Policy']);self.assertIn('no-cache',r.headers['Cache-Control'])
        r.close()
        with self.a.get('/static/manifest.webmanifest') as response:manifest=response.json
        self.assertEqual(manifest['scope'],'/');self.assertEqual(manifest['display'],'standalone')
        first=alerts.keys()[0];self.assertEqual(first,alerts.keys()[0]);self.assertEqual((Path(self.temp.name)/'clutchtape-vapid.pem').stat().st_mode&0o777,0o600)

if __name__=='__main__':unittest.main()
