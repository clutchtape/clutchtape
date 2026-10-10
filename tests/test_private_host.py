"""Owner-designated players stay unlisted but are available to explicit public lookups."""
import sqlite3,unittest
from unittest.mock import patch
import db,privacy,web

class PrivateHost(unittest.TestCase):
    def setUp(self):
        self.conn=sqlite3.connect(':memory:',isolation_level=None);self.conn.row_factory=sqlite3.Row
        self.p=patch.object(db,'conn',return_value=self.conn);self.p.start();db.init()
        self.addCleanup(self.conn.close);self.addCleanup(self.p.stop)
        for k,v in (('PRIVATE',{'xghostx'}),('PRIVATE_HOSTS',{'test.clutchtape.example'})):
            q=patch.object(privacy,k,v);q.start();self.addCleanup(q.stop)
        db.run("INSERT INTO players(xuid,gamertag,slug,created_at,sync_state) VALUES('x1','x Ghost x','x-ghost-x',0,'ready')")
        old=web.app.config.get('TRUSTED_HOSTS')
        web.app.config.update(TESTING=True,TRUSTED_HOSTS=['clutchtape.com','test.clutchtape.example'])
        self.addCleanup(web.app.config.update,TRUSTED_HOSTS=old);self.c=web.app.test_client()
    def test_explicit_lookup_allowed_on_public_host(self):
        with patch.object(web.worker,'enqueue'):
            self.assertEqual(self.c.get('/p/x-ghost-x',base_url='https://clutchtape.com').status_code,200)
            self.assertEqual(self.c.get('/live/x-ghost-x',base_url='https://clutchtape.com',follow_redirects=True).status_code,200)
            self.assertEqual(len(self.c.get('/api/live/x-ghost-x',base_url='https://clutchtape.com').json['players']),1)
        self.assertTrue(privacy.private('x Ghost x'))
        self.assertFalse(privacy.hidden('x Ghost x'))
    def test_served_on_private_host_and_not_indexed(self):
        with patch.object(web.worker,'enqueue'):
            r=self.c.get('/p/x-ghost-x',base_url='https://test.clutchtape.example')
        self.assertEqual(r.status_code,200);self.assertEqual(r.headers['X-Robots-Tag'],'noindex, nofollow')
    def test_matching_ignores_case_spaces_and_twitch_login_form(self):
        self.assertTrue(privacy.private('X GHOST X'));self.assertTrue(privacy.private('xghostx'));self.assertFalse(privacy.private('CyKul'))
        self.assertFalse(privacy.hidden('x Ghost x'))      # unlisted is not blocked

if __name__=='__main__': unittest.main()
