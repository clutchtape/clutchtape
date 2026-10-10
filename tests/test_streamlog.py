"""2026-10-08 stream log: category stints per broadcast (Twitch only reports the current category)."""
import sqlite3,unittest
from unittest.mock import patch
import db,streamlog,web

class StreamLog(unittest.TestCase):
    def setUp(self):
        self.conn=sqlite3.connect(':memory:',isolation_level=None,check_same_thread=False);self.conn.row_factory=sqlite3.Row
        self.p=patch.object(db,'conn',return_value=self.conn);self.p.start();db.init()
        self.addCleanup(self.conn.close);self.addCleanup(self.p.stop)
    def st(self,game,gid,start=1000): return {'game':game,'game_id':gid,'title':'t','started':start}
    def test_switches_become_stints(self):
        H='506416'
        streamlog.record('pro',self.st('Halo Infinite',H),now=1100)           # seen 100s after going live: stint starts at stream start
        streamlog.record('pro',self.st('Halo Infinite',H),now=1220)
        streamlog.record('pro',self.st('Gears of War: E-Day','999'),now=4000)
        streamlog.record('pro',self.st('Gears of War: E-Day','999'),now=4120)
        segs=streamlog.segments('pro',1000,now=4150)
        self.assertEqual([(g['game'],g['halo'],g['start'],g['end']) for g in segs],
                         [('Halo Infinite',True,1000,4000),('Gears of War: E-Day',False,4000,4150)])
    def test_late_first_sight_does_not_claim_the_start(self):
        streamlog.record('pro',self.st('Halo Infinite','506416'),now=1000+3600)
        segs=streamlog.segments('pro',1000,now=1000+3700)
        self.assertTrue(segs[0]['unknown']);self.assertEqual((segs[0]['start'],segs[1]['start']),(1000,1000+3600))
    def test_only_configured_channels(self):
        with patch.dict('os.environ',{'FEATURED_PLAYERS':'A|twitch.tv/aaa,B','PRIVATE_CHANNELS':'C|ccc'}):
            self.assertEqual(streamlog.channels(),['aaa','ccc'])
    def test_onair_counts_only_halo_time_for_the_alt_hint(self):
        self.conn.execute("INSERT INTO players(id,xuid,gamertag,slug,created_at) VALUES(1,'1','Pro','pro',0)")
        p=dict(self.conn.execute('SELECT * FROM players').fetchone())
        import time
        now=time.time();start=now-3600
        streamlog.record('pro',{'game':'Gears','game_id':'9','title':'t','started':start},now=start+60)
        streamlog.record('pro',{'game':'Halo Infinite','game_id':'506416','title':'t','started':start},now=now-10*60)
        with patch.object(streamlog,'channels',return_value=['pro']):
            o=web._onair([(p,[1])],{'game':'Halo Infinite','game_id':'506416','halo':True,'started':start,'title':'t'},'pro')
        self.assertTrue(o['switched']);self.assertLess(o['halo_s'],15*60);self.assertFalse(o['quiet'])   # 10 min of Halo: too early to suspect an alt

if __name__=='__main__':
    unittest.main()
