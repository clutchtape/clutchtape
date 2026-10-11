"""2026-10-08 short URLs: /sq/<code> squad links, 8-character session ids, test-host channel defaults."""
import sqlite3,unittest
from unittest.mock import patch
import db,dashboard,privacy,web

class ShortSquad(unittest.TestCase):
    def setUp(self):
        self.conn=sqlite3.connect(':memory:',isolation_level=None,check_same_thread=False);self.conn.row_factory=sqlite3.Row
        self.p=patch.object(db,'conn',return_value=self.conn);self.p.start();db.init()
        self.addCleanup(self.conn.close);self.addCleanup(self.p.stop)
        for i,s in enumerate(('aa','bb')):
            self.conn.execute("INSERT INTO players(xuid,gamertag,slug,created_at) VALUES(?,?,?,0)",(str(i),s.upper(),s))
    def test_code_is_stable_and_short(self):
        with web.app.test_request_context('/'):
            a=web.squad_code('aa,bb');self.assertEqual(len(a),6);self.assertEqual(web.squad_code('AA,bb,'),a)
            self.assertNotEqual(web.squad_code('bb,aa'),a)       # order is the column order, so it is part of the squad
    def test_long_url_redirects_with_query(self):
        r=web.app.test_client().get('/squad/aa,bb?tab=sessions')
        self.assertEqual(r.status_code,302);self.assertRegex(r.location,r'^/sq/[0-9a-f]{6}\?tab=sessions$')
    def test_game_link_validates(self):
        c=web.app.test_client()
        with web.app.test_request_context('/'):code=web.squad_code('aa,bb')
        self.assertEqual(c.get('/sq/zzzzzz/g/a1b2c3d4').status_code,404)          # unknown squad
        self.assertEqual(c.get(f'/sq/{code}/g/not-hex!').status_code,404)          # junk game id
        self.assertEqual(c.get(f'/sq/{code}/g/a1b2c3d4').status_code,404)          # game not in this squad's history
    def test_apart_squad_still_leads_with_overall_table(self):
        # 2026-10-11: two players who never played together (and one private) still get the overall table
        import time
        for i in range(6):
            self.conn.execute("INSERT INTO matches(player_id,match_id,started_at,duration_s,mode,playlist,outcome,kills,deaths,assists,damage_dealt) VALUES(1,?,?,600,'Ranked:Slayer','Ranked Arena','Win',12,6,3,3200)",(f'a{i}',time.time()-86400-i*900))
        self.conn.execute("UPDATE players SET sync_state='private' WHERE slug='bb'")
        with web.app.test_request_context('/'):code=web.squad_code('aa,bb')
        h=web.app.test_client().get(f'/sq/{code}').get_data(as_text=True)
        self.assertIn('id="sqtable"',h);self.assertIn('not played together yet',h)
        self.assertIn('6 games, last 30 days',h)
    def test_unknown_code_404(self):
        self.assertEqual(web.app.test_client().get('/sq/zzzzzz').status_code,404)

class ShortSession(unittest.TestCase):
    def test_prefix_selects_session(self):
        ss=[{'matches':[{'match_id':'11111111-aaaa'}]},{'matches':[{'match_id':'a1b2c3d4-60d1'}]}]
        self.assertEqual(dashboard.select_session(ss,'a1b2c3d4'),1)
        self.assertEqual(dashboard.select_session(ss,'a1b2c3d4-60d1'),1)
        self.assertIsNone(dashboard.select_session(ss,'e7b'))         # too short to be a prefix

class PrivateChannels(unittest.TestCase):
    def test_only_on_private_host(self):
        with patch.object(web,'PRIVATE_CHANNEL_SPEC',['Me|mychan']),patch.object(privacy,'PRIVATE_HOSTS',{'test.example'}),patch.dict(web.app.config,{'TRUSTED_HOSTS':None}):
            with web.app.test_request_context('/',headers={'Host':'test.example'}):
                self.assertIn('Me|mychan',web._channel_specs())
            with web.app.test_request_context('/',headers={'Host':'public.example'}):
                self.assertNotIn('Me|mychan',web._channel_specs())

if __name__=='__main__':
    unittest.main()
