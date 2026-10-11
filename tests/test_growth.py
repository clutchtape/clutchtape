"""Result semantics and private-room authorization, with isolated SQLite."""
import os,sys,tempfile,sqlite3,unittest,time
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
_tmp=tempfile.TemporaryDirectory()
os.environ["DB_DIR"]=_tmp.name
os.environ["HALO_DATA_DIR"]=_tmp.name
import db,web,growth
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

class RoomsOffTests(unittest.TestCase):
    def test_rooms_and_accounts_are_gone(self):   # removed 2026-10-11
        web.app.config.update(TESTING=True,SECRET_KEY='unit-test-only');c=web.app.test_client()
        for path in ['/rooms','/rooms/x','/join/x/y']:self.assertEqual(c.get(path).status_code,404)
        self.assertEqual(c.post('/account').status_code,404)

