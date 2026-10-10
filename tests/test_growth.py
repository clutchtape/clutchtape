"""Result semantics and private-room authorization, with isolated SQLite."""
import os,sys,tempfile,sqlite3,unittest,time
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
_tmp=tempfile.TemporaryDirectory()
os.environ["DB_DIR"]=_tmp.name
os.environ["HALO_DATA_DIR"]=_tmp.name
import db,web,growth,rooms
# Other test modules may import db before setting DB_DIR. Keep discovery isolated.
db.DB_PATH=os.path.join(_tmp.name,"clutchtape.db")
from test_companion import row

class GrowthTests(unittest.TestCase):
    def test_close_games_only_supported_scores_and_finished_results(self):
        self.assertTrue(growth.close_game(row(team_score=50,enemy_score=48)))
        self.assertFalse(growth.close_game(row(mode='Oddball',team_score=2,enemy_score=1)))
        self.assertFalse(growth.close_game(row(outcome='Left',team_score=50,enemy_score=48)))
        self.assertFalse(growth.close_game(row(team_score=None,enemy_score=48)))
    def test_search_filters_are_combined(self):
        rs=[row('a',map='Recharge',team_score=50,enemy_score=48),row('b',map='Aquarius',win=False,team_score=40,enemy_score=50)]
        self.assertEqual([r['match_id'] for r in growth.search(rs,{'q':'recharge slayer','close':'1'})],['a'])
        self.assertEqual(growth.search(rs,{'q':'recharge','outcome':'Loss'}),[])
        self.assertEqual(growth.search(rs,{'playlist':'Custom'}),[])
    def test_records_exclude_future_short_and_different_modes(self):
        history=[row('best',10000,damage_dealt=10000)]+[row(str(i),9000-i,damage_dealt=2000) for i in range(5)]
        self.assertEqual(growth.records(history),{'best'})
        history[0]['duration_s']=10
        self.assertEqual(growth.records(history),set())
    def test_week_is_half_open_utc_and_no_future_comparison(self):
        end=86400*10
        b={'history':[row('end',end),row('start',end-7*86400),row('old',end-8*86400),row('inside',end-1)]}
        with web.app.test_request_context('/'):
            w=growth.weekly(b,'1970-01-11')
        self.assertEqual({r['match_id'] for r in w['matches']},{'start','inside'})
        self.assertEqual(w['prior']['games'],1)

class RoomTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.conn=sqlite3.connect(self.tmp.name+'/test.db',isolation_level=None);self.conn.row_factory=sqlite3.Row
        self.patch=patch.object(db,'conn',return_value=self.conn);self.patch.start();db.init()
        web.app.config.update(TESTING=True,SECRET_KEY='unit-test-only')
        self.xbox=patch.object(web.xbox,'status',return_value={'connected':True});self.xbox.start()
        self.a=web.app.test_client();self.b=web.app.test_client();self.c=web.app.test_client()
        self.register(self.a,'owner');self.register(self.b,'member');self.register(self.c,'outside')
        r=self.post(self.a,'/rooms',name='Private practice');self.url=r.location;self.rid=self.url.split('/')[-1]
    def tearDown(self): self.xbox.stop();self.patch.stop();self.conn.close();self.tmp.cleanup()
    def post(self,client,path,**kwargs):
        with client.session_transaction() as s: s.setdefault('csrf','test');csrf=s['csrf']
        return client.post(path,data=dict(csrf=csrf,**kwargs))
    def register(self,c,name): self.assertEqual(self.post(c,'/account',name=name,password='a strong test password',action='register').status_code,303)
    def invite(self):
        self.post(self.a,self.url+'/manage',action='invite')
        token='test-capability';db.run('UPDATE review_rooms SET invite_hash=?,invite_until=? WHERE id=?',rooms.digest(token),time.time()+100,self.rid)
        return '/join/'+self.rid+'/'+token
    def test_outsiders_cannot_read_or_post_or_manage(self):
        self.assertEqual(self.c.get(self.url).status_code,404)
        self.assertEqual(self.post(self.c,self.url,body='intrusion').status_code,404)
        self.assertEqual(self.post(self.c,self.url+'/manage',action='invite').status_code,404)
        self.assertEqual(web.app.test_client().get(self.url).status_code,401)
    def test_invite_join_remove_and_owner_only_controls(self):
        invite=self.invite();self.assertEqual(self.post(self.b,invite).status_code,303)
        self.assertEqual(self.b.get(self.url).status_code,200)
        self.assertEqual(self.post(self.b,self.url+'/manage',action='invite').status_code,403)
        uid=db.q1('SELECT id FROM review_users WHERE name=?','member')['id']
        self.post(self.a,self.url+'/manage',action='remove',user=uid)
        self.assertEqual(self.b.get(self.url).status_code,404)
        self.assertEqual(self.post(self.b,self.url,body='removed').status_code,404)
    def test_revoked_expired_invites_and_get_does_not_join(self):
        invite=self.invite();self.b.get(invite);self.assertEqual(self.b.get(self.url).status_code,404)
        self.post(self.a,self.url+'/manage',action='revoke');self.assertEqual(self.post(self.b,invite).status_code,404)
        invite=self.invite();db.run('UPDATE review_rooms SET invite_until=0');self.assertEqual(self.b.get(invite).status_code,404)
    def test_csrf_is_required_for_every_mutation(self):
        self.assertEqual(self.a.post(self.url,data={'body':'unsafe'}).status_code,400)
        self.assertEqual(self.a.post('/account/logout').status_code,400)
    def test_logout_invalidates_server_session(self):
        with self.a.session_transaction() as s: token=s['review_token']
        self.post(self.a,'/account/logout')
        with self.a.session_transaction() as s: s['review_token']=token
        self.assertEqual(self.a.get(self.url).status_code,401)
    def test_posts_escape_markup_and_reject_arbitrary_links(self):
        self.assertEqual(self.post(self.a,self.url,body='<script>bad()</script>').status_code,303)
        html=self.a.get(self.url).data
        self.assertIn(b'&lt;script&gt;bad()',html)
        self.assertEqual(self.post(self.a,self.url,body='link',url='https://evil.example/').status_code,400)
        self.assertEqual(self.post(self.a,self.url,body='reply',parent='missing').status_code,404)
    def test_passwords_are_hashed_and_login_rotates_session(self):
        u=db.q1('SELECT * FROM review_users WHERE name=?','owner')
        self.assertTrue(u['password'].startswith('scrypt:'))
        with self.a.session_transaction() as s: old=s['review_token']
        self.post(self.a,'/account',action='login',name='owner',password='a strong test password')
        self.assertIsNone(db.q1('SELECT * FROM review_sessions WHERE token=?',rooms.digest(old)))
        self.assertEqual(self.post(self.c,'/account',action='login',name='owner',password='wrong password value').status_code,400)
    def test_private_responses_are_not_cached(self):
        r=self.a.get(self.url);self.assertEqual(r.headers['Cache-Control'],'no-store');self.assertEqual(r.headers['Referrer-Policy'],'no-referrer')
    def test_rate_limiter_bounds_attempts(self):
        with web.app.test_request_context('/'):
            rooms.limit('sample',2);rooms.limit('sample',2)
            from werkzeug.exceptions import TooManyRequests
            with self.assertRaises(TooManyRequests):rooms.limit('sample',2)
