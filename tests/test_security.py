"""Security regressions, isolated from production data and upstream services."""
import sqlite3,time,unittest
from unittest.mock import patch
import db,web,capacity,match_detail
from test_match_detail import stored,MID

class SecurityTests(unittest.TestCase):
    def setUp(self):
        self.conn=sqlite3.connect(':memory:',isolation_level=None);self.conn.row_factory=sqlite3.Row
        self.dbpatch=patch.object(db,'conn',return_value=self.conn);self.dbpatch.start();db.init()
        self.addCleanup(self.conn.close);self.addCleanup(self.dbpatch.stop)
        self.client=web.app.test_client();web.app.config.update(TESTING=True,SECRET_KEY='security-test-only')
        self.xbox=patch('xbox.status',return_value={'connected':True});self.xbox.start();self.addCleanup(self.xbox.stop)
        self.limits=patch.object(web,'_admin_limits',capacity.Limiter());self.limits.start();self.addCleanup(self.limits.stop)
    def csrf(self):
        with self.client.session_transaction() as s:s['csrf']='test-csrf'
    def test_recent_searches_never_become_demo_choices(self):
        db.run("INSERT INTO players(xuid,gamertag,slug,created_at,sync_state,last_view) VALUES('999','HiddenLookupCanary','hidden-canary',0,'ready',?)",time.time())
        with patch.object(web,'FEATURED_SPEC',['CyKul']),patch.object(web,'_cached',return_value=None):
            for path in ['/','/live']:
                r=self.client.get(path,follow_redirects=True);self.assertEqual(r.status_code,200);   # /live now redirects homeself.assertNotIn(b'HiddenLookupCanary',r.data);self.assertNotIn(b'hidden-canary',r.data)
    def test_other_cached_match_perspectives_are_not_advertised(self):
        other=dict(stored(),slug='hidden-canary',gamertag='HiddenLookupCanary')
        with patch.object(match_detail,'known',return_value=[stored(),other]),patch.object(match_detail,'ensure',return_value=(None,'loading')):
            r=self.client.get('/match/'+MID+'?player=one')
        self.assertEqual(r.status_code,200);self.assertNotIn(b'HiddenLookupCanary',r.data)
    def test_error_pages_use_site_layout_but_api_stays_plain(self):
        r=self.client.get('/no-such-page')
        self.assertEqual(r.status_code,404);self.assertIn(b'class="doc errpage"',r.data);self.assertIn(b'Not found',r.data)
        r=self.client.get('/api/no-such-thing')
        self.assertEqual(r.status_code,404);self.assertNotIn(b'errpage',r.data)
    def test_untrusted_host_and_forwarded_host_rejected(self):
        for headers in [{'Host':'evil.example'},{'X-Forwarded-Host':'evil.example'}]:
            self.assertEqual(self.client.get('/privacy',headers=headers).status_code,400)
    def test_admin_login_rotates_session_expires_and_revokes_on_password_change(self):
        with patch.object(web,'ADMIN_PASSWORD','test-admin-password'):
            self.csrf()
            r=self.client.post('/admin',data={'action':'login','password':'test-admin-password','csrf':'test-csrf'})
            self.assertEqual(r.status_code,302)
            with self.client.session_transaction() as s:
                self.assertTrue(s['admin']);self.assertNotIn('csrf',s);saved=dict(s)
            with web.app.test_request_context('/'):
                web.session.update(saved);self.assertTrue(web._is_admin())
                with patch.object(web,'ADMIN_PASSWORD','rotated-password'):self.assertFalse(web._is_admin())
                web.session['admin_at']=time.time()-3601;self.assertFalse(web._is_admin())
    def test_admin_guess_limit_and_unicode_input(self):
        with patch.object(web,'ADMIN_PASSWORD','test-admin-password'):
            self.csrf()
            for i in range(8):
                self.assertEqual(self.client.post('/admin',data={'action':'login','password':'wrongé','csrf':'test-csrf'}).status_code,302)
            self.assertEqual(self.client.post('/admin',data={'action':'login','password':'wrong','csrf':'test-csrf'}).status_code,429)
        self.assertEqual(self.client.post('/add',data={'csrf':'é'}).status_code,400)
    def test_admin_routes_and_legacy_diagnostics(self):
        for path in ['/admin/ops','/admin/teammates/example']:
            self.assertEqual(self.client.get(path).status_code,403)
        with patch.object(web.log,'info') as log:
            self.assertEqual(self.client.post('/api/clientlog',data='private-name\nforged log').status_code,204);log.assert_not_called()
    def test_security_headers(self):
        r=self.client.get('/admin',base_url='https://clutchtape.com')
        self.assertEqual(r.headers['Cache-Control'],'no-store')
        self.assertIn("form-action 'self'",r.headers['Content-Security-Policy']);self.assertIn('max-age=',r.headers['Strict-Transport-Security'])
