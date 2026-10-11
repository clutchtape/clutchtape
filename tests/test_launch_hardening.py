import sqlite3,tempfile,time,unittest,re
from pathlib import Path
from unittest.mock import patch
import db,web,privacy,data_rights,retention,capacity

class LaunchHardeningTests(unittest.TestCase):
    def setUp(self):
        self.c=sqlite3.connect(':memory:',isolation_level=None);self.c.row_factory=sqlite3.Row
        p=patch.object(db,'conn',return_value=self.c);p.start();self.addCleanup(self.c.close);self.addCleanup(p.stop);db.init()
        web.app.config.update(TESTING=True,SECRET_KEY='launch-test');self.client=web.app.test_client()
        p=patch('xbox.status',return_value={'connected':True});p.start();self.addCleanup(p.stop)
        p=patch.object(capacity,'limiter',capacity.Limiter());p.start();self.addCleanup(p.stop)
        with self.client.session_transaction() as s:s['csrf']='csrf'
    def test_unique_nonce_matches_all_page_scripts(self):
        seen=[]
        for _ in range(2):
            r=self.client.get('/privacy');self.assertEqual(r.status_code,200)
            nonce=re.search("'nonce-([^']+)'",r.headers['Content-Security-Policy']).group(1);seen.append(nonce)
            scripts=re.findall(r'<script[^>]*>',r.get_data(as_text=True))
            self.assertTrue(scripts);self.assertTrue(all('nonce="'+nonce+'"' in s for s in scripts))
            self.assertNotIn("'unsafe-inline'",r.headers['Content-Security-Policy'].split('script-src ')[1].split(';')[0])
        self.assertNotEqual(*seen)
    def test_removal_request_private_requires_csrf_and_admin(self):
        self.assertEqual(self.client.post('/privacy',data={'gamertag':'ExamplePlayer'}).status_code,400)
        r=self.client.post('/privacy',data={'csrf':'csrf','gamertag':'ExamplePlayer'});self.assertEqual(r.status_code,303)
        receipt=self.client.get(r.location);self.assertEqual(receipt.status_code,200);self.assertNotIn(b'ExamplePlayer',receipt.data)
        self.assertEqual(receipt.headers['Referrer-Policy'],'no-referrer');self.assertEqual(receipt.headers['Cache-Control'],'no-store')
        self.assertEqual(self.client.get('/admin/privacy').status_code,403)
        self.assertEqual(self.client.get('/privacy/request/not-found').status_code,404)
        self.assertEqual(db.q1('SELECT state FROM removal_requests')['state'],'pending')
    def test_verified_removal_persists_and_scrubs_request(self):
        with tempfile.TemporaryDirectory() as folder,patch.object(privacy,'data_path',side_effect=lambda n:Path(folder)/n),patch.object(privacy,'HASHES',set()):
            db.run("INSERT INTO players(xuid,gamertag,slug,created_at) VALUES('999','ExamplePlayer','exampleplayer',0)")
            db.run("INSERT INTO removal_requests VALUES('id','ExamplePlayer','challenge',?,'pending')",time.time())
            self.assertTrue(data_rights.approve('id'));self.assertTrue(privacy.blocked('ExamplePlayer'));self.assertTrue(privacy.blocked('999'))
            self.assertIsNone(db.q1('SELECT * FROM players'));self.assertEqual(db.q1('SELECT gamertag FROM removal_requests')['gamertag'],'')
            self.assertTrue((Path(folder)/'privacy_exclusions.json').exists());self.assertFalse(data_rights.approve('id'))
    def test_unblock_lifts_gamertag_and_xuid_and_admin_only(self):
        with tempfile.TemporaryDirectory() as folder,patch.object(privacy,'data_path',side_effect=lambda n:Path(folder)/n),patch.object(privacy,'HASHES',set()):
            db.run("INSERT INTO players(xuid,gamertag,slug,created_at) VALUES('999','Example Player','example-player',0)")
            db.run("INSERT INTO removal_requests VALUES('id','Example Player','challenge',?,'pending')",time.time())
            self.assertTrue(data_rights.approve('id'))
            self.assertEqual(self.client.post('/admin/privacy',data={'csrf':'csrf','action':'unblock','gamertag':'Example Player'}).status_code,403)
            import hmac
            with patch.object(web,'ADMIN_PASSWORD','test-admin'),patch.object(data_rights,'_xuid_for',return_value='999'):
                with self.client.session_transaction() as s:
                    s.update(admin=True,admin_at=time.time(),admin_version=hmac.new(web.app.secret_key.encode(),b'test-admin','sha256').hexdigest())
                r=self.client.post('/admin/privacy',data={'csrf':'csrf','action':'unblock','gamertag':'example-player'})
                self.assertEqual(r.status_code,200);self.assertIn(b'Unblocked',r.data)
                self.assertFalse(privacy.blocked('Example Player'));self.assertFalse(privacy.blocked('999'));self.assertFalse(privacy.blocked('example-player'))
                self.assertIn('"hashes": []',(Path(folder)/'privacy_exclusions.json').read_text())
                self.assertEqual(self.client.post('/admin/privacy',data={'csrf':'csrf','action':'unblock','gamertag':'Nobody'}).status_code,400)
    def test_retention_preserves_active_profiles(self):
        now=time.time()
        for i,(name,view) in enumerate([('Active',now),('Inactive',now-91*86400),('CyKul',now-91*86400)],1):
            db.run('INSERT INTO players(id,xuid,gamertag,slug,created_at,last_view) VALUES(?,?,?,?,?,?)',i,str(i),name,name.lower(),view,view)
        db.run("INSERT INTO matches(player_id,match_id,started_at) VALUES(1,'expired',?)",now-181*86400)
        db.run("INSERT INTO matches(player_id,match_id,started_at) VALUES(1,'keep',?)",now)
        db.run("INSERT INTO events VALUES('expired','1','Active',1,'kill',NULL)");db.kv_set('matchdetail:expired',{})
        result=retention.sweep(now)
        self.assertEqual(result['profiles'],1);self.assertIsNotNone(db.q1("SELECT 1 FROM players WHERE slug='active'"));self.assertIsNotNone(db.q1("SELECT 1 FROM players WHERE slug='cykul'"))
        self.assertEqual(db.q1('SELECT COUNT(*) n FROM events')['n'],0);self.assertIsNone(db.kv_get('matchdetail:expired'))
