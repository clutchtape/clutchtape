"""2026-10-08 review fixes: Halo-only default VOD, no 0-0 quit-only headline session, Halo-only Twitch clips."""
import sqlite3,unittest
from unittest.mock import patch
import db,dashboard,twitch,web

def sess(*outcomes):
    return {'matches':[{'match_id':f'm{i}','outcome':o} for i,o in enumerate(outcomes)]}

class SessionDefault(unittest.TestCase):
    def test_skips_quit_only_latest_session(self):
        self.assertEqual(dashboard.select_session([sess('Dnf'),sess('Win','Loss')],skip_unfinished=True),1)
    def test_keeps_latest_when_it_has_a_result(self):
        self.assertEqual(dashboard.select_session([sess('Dnf','Win'),sess('Loss')],skip_unfinished=True),0)
    def test_all_quit_falls_back_to_latest(self):
        self.assertEqual(dashboard.select_session([sess('Left'),sess('Dnf')],skip_unfinished=True),0)
    def test_explicit_choice_is_respected(self):
        self.assertEqual(dashboard.select_session([sess('Dnf'),sess('Win')],legacy=0),0)
        self.assertEqual(dashboard.select_session([sess('Dnf'),sess('Win')],'m0'),0)

class QuitGames(unittest.TestCase):
    def test_short_games_never_count(self):
        import analytics
        self.assertFalse(analytics.kind_ok({'duration_s':34,'ranked':1,'playlist':'r'},'ranked'))
        self.assertTrue(analytics.kind_ok({'duration_s':600,'ranked':1,'playlist':'r'},'ranked'))
        self.assertTrue(analytics.kind_ok({'duration_s':None,'ranked':1,'playlist':'r'},'ranked'))   # unknown length kept
        import sqlite3                                                    # raw DB rows (dashboard.load) must work too
        c=sqlite3.connect(':memory:');c.row_factory=sqlite3.Row;row=c.execute("SELECT 34 AS duration_s, 1 AS ranked, 'r' AS playlist").fetchone()
        self.assertFalse(analytics.kind_ok(row,'ranked'))

class HaloVod(unittest.TestCase):
    def setUp(self):
        self.conn=sqlite3.connect(':memory:',isolation_level=None);self.conn.row_factory=sqlite3.Row
        self.p=patch.object(db,'conn',return_value=self.conn);self.p.start();db.init()
        self.addCleanup(self.conn.close);self.addCleanup(self.p.stop)
        self.conn.execute("INSERT INTO matches(player_id,match_id,started_at) VALUES(1,'a',5000)")
    def test_newest_vod_without_halo_is_skipped(self):
        vods=[{'id':'rl','start':9000,'dur_s':3000},{'id':'halo','start':4000,'dur_s':3000}]
        self.assertEqual(web._halo_vod(vods,1)['id'],'halo')
    def test_falls_back_to_newest(self):
        vods=[{'id':'new','start':9000,'dur_s':100},{'id':'old','start':100,'dur_s':100}]
        self.assertEqual(web._halo_vod(vods,1)['id'],'new')
        self.assertEqual(web._halo_vod(vods,None)['id'],'new')

class HaloClips(unittest.TestCase):
    def test_other_games_are_dropped(self):
        raw=[{'id':str(i),'title':'t','url':'u','view_count':1,'thumbnail_url':'x','created_at':'c','duration':5,
              'game_id':twitch.HALO_INFINITE_GAME_ID if i%2 else '417969'} for i in range(10)]
        with patch.object(twitch,'enabled',return_value=True),patch.object(twitch,'_get',return_value=raw):
            got=twitch.recent_clips('u1',n=3)
        self.assertEqual([c['id'] for c in got],['1','3','5'])

if __name__=='__main__':
    unittest.main()
