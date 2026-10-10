"""2026-10-08 live panel: games since the stream started, and the 'probably another account' hint."""
import sqlite3,time,unittest
from unittest.mock import patch
import db,web

class OnAir(unittest.TestCase):
    def setUp(self):
        self.conn=sqlite3.connect(':memory:',isolation_level=None,check_same_thread=False);self.conn.row_factory=sqlite3.Row
        self.p=patch.object(db,'conn',return_value=self.conn);self.p.start();db.init()
        self.addCleanup(self.conn.close);self.addCleanup(self.p.stop)
        self.conn.execute("INSERT INTO players(id,xuid,gamertag,slug,created_at) VALUES(1,'1','Pro','pro',0)")
        self.player=dict(self.conn.execute('SELECT * FROM players').fetchone())
    def g(self,ids=(1,)): return [(self.player,list(ids))]
    def add(self,ago,outcome='Win',pid=1,kills=10,adv=None,pre=None,post=None):
        self.conn.execute("INSERT INTO matches(player_id,match_id,started_at,duration_s,mode,outcome,kills,deaths,assists,damage_dealt,advanced,pre_csr,post_csr) VALUES(?,?,?,600,'Ranked:Slayer',?,?,5,2,3000,?,?,?)",
                          (pid,f'm{pid}-{ago}',time.time()-ago,outcome,kills,adv,pre,post))
    def test_quiet_when_live_in_halo_without_games(self):
        o=web._onair(self.g(),{'started':time.time()-40*60,'halo':True,'title':'RANKED'},'pro')
        self.assertTrue(o['quiet']);self.assertEqual(o['per'][0]['games'],0)
    def test_not_quiet_early_or_other_game(self):
        self.assertFalse(web._onair(self.g(),{'started':time.time()-5*60,'halo':True},'pro')['quiet'])
        self.assertFalse(web._onair(self.g(),{'started':time.time()-60*60,'halo':False},'pro')['quiet'])
    def test_counts_games_since_stream_start_including_pregame(self):
        self.add(30*60);self.add(55*60,'Loss');self.add(5*3600)          # 5h-old game is from an earlier session
        o=web._onair(self.g(),{'started':time.time()-45*60,'halo':True},'pro')
        self.assertEqual(o['per'][0]['games'],2);self.assertFalse(o['quiet'])
        self.assertEqual((o['per'][0]['a']['wins'],o['per'][0]['a']['losses']),(1,1))
    def test_lobby_read_milestones_and_strip(self):
        import json
        self.add(10*86400,kills=30)                                                      # history: best 30 kills
        self.add(50*60,adv=json.dumps({'team_mmr':1500,'enemy_mmr':1600}),pre=1480,post=1492)
        self.add(35*60,kills=31,adv=json.dumps({'team_mmr':1600,'enemy_mmr':1500}),pre=1492,post=1503)
        self.add(20*60,adv=json.dumps({'team_mmr':1500,'enemy_mmr':1510}),pre=1503,post=1511)
        x=web._onair(self.g(),{'started':time.time()-60*60,'halo':True},'pro')['per'][0]
        self.assertEqual((x['lobby']['dog'],x['lobby']['fav'],x['lobby']['even']),('1-0','1-0','1-0'))
        texts=' | '.join(t for _,t in x['milestones'])
        self.assertIn('+31 CSR this stream',texts);self.assertIn('Reached Onyx (1511)',texts);self.assertIn('3-game win streak',texts)
        self.assertIn('Most kills in a game on record: 31',texts)
        self.assertEqual(len(x['strip']),3);self.assertLess(x['strip'][0]['t'],x['strip'][-1]['t'])
    def test_alt_games_fold_into_tonight(self):
        self.conn.execute("INSERT INTO players(id,xuid,gamertag,slug,created_at) VALUES(2,'2','Pro Alt','pro-alt',0)")
        self.add(20*60,pid=2)
        self.assertEqual(web._onair(self.g((1,2)),{'started':time.time()-30*60,'halo':True},'pro')['per'][0]['games'],1)
        self.assertEqual(web._onair(self.g((1,)),{'started':time.time()-30*60,'halo':True},'pro')['per'][0]['games'],0)
    def test_customs_hidden_when_long_history_has_no_customs(self):
        # 2026-10-10: Halo doesn't share a player's customs unless they allow it; 50+ games and not one custom = hidden
        for d in range(50): self.add((2+d)*86400)
        self.conn.execute("UPDATE matches SET playlist='Ranked Arena'")
        o=web._onair(self.g(),{'started':time.time()-40*60,'halo':True,'title':'scrims','game':'Halo Infinite','viewers':3},'pro')
        self.assertTrue(o['per'][0]['customs_hidden'])
        with web.app.test_request_context('/p/pro'):
            self.assertIn('In custom games?',web.render_template('_onair.html',onair=o))
        self.conn.execute("UPDATE matches SET playlist=NULL WHERE match_id=(SELECT MIN(match_id) FROM matches)")   # one custom on record
        self.assertFalse(web._onair(self.g(),{'started':time.time()-40*60,'halo':True},'pro')['per'][0]['customs_hidden'])
    def test_offline_is_none(self):
        self.assertIsNone(web._onair(self.g(),None,'pro'))

if __name__=='__main__':
    unittest.main()


class OnAirRender(OnAir):
    """2026-10-10: the live panel renders with the usual-tinted numbers and grouped extras (template-level check:
    nobody has to be live for this to run)."""
    def test_panel_renders_with_tint_against_usual(self):
        for d in range(5):
            self.add((3 + d) * 86400, kills=8)                          # usual: 8 kills a game
        self.add(20 * 60, kills=20)                                     # this stream: 20
        o = web._onair(self.g(), {'started': time.time() - 60 * 60, 'halo': True, 'title': 'Ranked', 'game': 'Halo Infinite', 'viewers': 3}, 'pro')
        self.assertIsNotNone(o['per'][0]['usual'])
        with web.app.test_request_context('/p/pro'):
            html = web.render_template('_onair.html', onair=o)
        self.assertIn('class="lv up"', html)                            # K/game well above usual
        self.assertIn('usual 8', html)
        self.assertIn('oa-grp', html); self.assertIn('Stats only', html)


class LiveVsRender(OnAir):
    """2026-10-10: under the stream on phones the session-vs-usual table becomes stat tiles (player page) or
    stats-as-rows (squad); key stats first, the rest behind "All stats"."""
    def _rows(self, n, kills, pid=1):
        from test_companion import row
        return [row(f'm{pid}-{kills}-{i}', 1000 + i, kills=kills, deaths=5, pid=pid) for i in range(n)]

    def _render(self, pt, squad=False):
        import player_table
        with web.app.test_request_context('/p/pro'):
            return web.render_template('_live_vs.html', onair={'channel': 'x'}, pt=player_table.build(pt), sess_current=True, squad_view=squad)

    def test_player_tiles(self):
        html = self._render([('This session', self._rows(2, 20), None), ('Usual', self._rows(6, 8), '6 games')])
        self.assertIn('class="lvm-grid"', html)
        self.assertIn('usual 8', html)                                  # K tile carries the usual value
        self.assertIn('lvm-x', html)                                    # extras hidden until "All stats"
        self.assertIn('data-lvall', html)

    def test_squad_rows(self):
        html = self._render([('A', self._rows(2, 20), None), ('B', self._rows(2, 8, 2), None), ('C', self._rows(2, 10, 3), None)], squad=True)
        self.assertIn('lvm-rows', html); self.assertNotIn('lvm-grid', html)
