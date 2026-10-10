import sys,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
import match_detail as md
import web

MID='12345678-1234-1234-1234-123456789abc'
def fixture(teams=True):
    return {'match_info':{'teams_enabled':teams},'teams':[{'team_id':0,'outcome':2,'stats':{'core_stats':{'score':50}}}], 'players':[
        {'player_id':'xuid(1234)','last_team_id':0,'outcome':2,'rank':1,'participation_info':{},'player_team_stats':[{'team_id':0,'stats':{'core_stats':{'kills':20,'deaths':10,'assists':3,'accuracy':55.2,'medals':[{'name_id':1,'count':2}]},'oddball_stats':{'time_as_skull_carrier':'PT20S'}}}]},
        {'player_id':'xuid(5678)','last_team_id':1,'outcome':3,'rank':2,'participation_info':{},'player_team_stats':[{'team_id':1,'stats':{'core_stats':{'kills':10,'deaths':20,'assists':4}}}]}]}
def stored():
    return dict(match_id=MID,slug='one',gamertag='One',xuid='1234',map='Recharge',mode='Slayer',duration_s=600,started_at=1700000000,playlist='Ranked',outcome='Win',team_score=50,enemy_score=40,kills=20,deaths=10,assists=3,damage_dealt=4000)

class MatchDetailTests(unittest.TestCase):
    def test_all_players_names_medals_objectives(self):
        d=md.normalize(fixture(),{'1234':'One','5678':'Enemy <name>'},{1:'Double Kill'})
        self.assertEqual(len(d['players']),2)
        self.assertEqual(d['players'][1]['name'],'Enemy <name>')
        self.assertEqual(d['players'][0]['splits'][0]['medals'][0]['name'],'Double Kill')
        self.assertIn(('Oddball time as skull carrier','PT20S'),d['players'][0]['splits'][0]['fields'])
    def test_missing_values_not_zero(self):
        d=md.normalize(fixture(),{},{});self.assertEqual(d['players'][1]['name'],'Player …5678')
        self.assertNotIn('accuracy',d['players'][1]['splits'][0]['core'])
        self.assertEqual(md.fields({'a':None,'b':0}),[('B',0)])
    def test_switches_preserve_each_stint(self):
        raw=fixture();raw['players'][0]['player_team_stats'].append({'team_id':1,'stats':{'core_stats':{'kills':2}}})
        d=md.normalize(raw,{},{});self.assertEqual([s['core']['kills'] for s in d['players'][0]['splits']],[20,2])
    def test_render_opponents_and_safe_names(self):
        d=md.normalize(fixture(),{'1234':'One','5678':'<script>evil</script>'},{})
        with patch.object(md,'known',return_value=[stored()]),patch.object(md,'ensure',return_value=(d,'ready')),patch('xbox.status',return_value={'connected':True}):
            r=web.app.test_client().get('/match/'+MID)
        self.assertEqual(r.status_code,200);self.assertIn(b'Opponents',r.data);self.assertIn(b'&lt;script&gt;',r.data)
        self.assertNotIn(b'<script>evil',r.data)
    def test_public_page_never_flags_other_tracked_players(self):
        d=md.normalize(fixture(),{'1234':'One','5678':'Mate'},{})
        mate=dict(stored(),slug='mate',gamertag='Mate',xuid='5678')
        with patch.object(md,'known',return_value=[stored(),mate]),patch.object(md,'ensure',return_value=(d,'ready')),patch('xbox.status',return_value={'connected':True}):
            r=web.app.test_client().get('/match/'+MID+'?player=one')
        self.assertEqual(r.status_code,200)
        self.assertNotIn(b'tracked',r.data);self.assertNotIn(b'Watch every angle',r.data);self.assertNotIn(b'href="/p/mate"',r.data)
    def test_ffa_does_not_claim_team(self):
        d=md.normalize(fixture(False),{'1234':'One'},{})
        with patch.object(md,'known',return_value=[stored()]),patch.object(md,'ensure',return_value=(d,'ready')),patch('xbox.status',return_value={'connected':True}):
            r=web.app.test_client().get('/match/'+MID)
        self.assertIn(b'Free-for-all',r.data);self.assertNotIn(b'Your team',r.data)
    def test_loading_and_error_have_saved_stats(self):
        for state in ['loading','error','busy']:
            with patch.object(md,'known',return_value=[stored()]),patch.object(md,'ensure',return_value=(None,state)),patch('xbox.status',return_value={'connected':True}):
                r=web.app.test_client().get('/match/'+MID)
            self.assertEqual(r.status_code,200);self.assertIn(b'20 kills',r.data);self.assertIn(b'match-retry',r.data)
    def test_unknown_game_rejected_before_queue(self):
        with patch.object(md.db,'q',return_value=[]),patch('worker.enqueue_detail') as queue:
            r=web.app.test_client().get('/match/'+MID)
        self.assertEqual(r.status_code,404);queue.assert_not_called()
    def test_error_cooldown_prevents_refetch(self):
        with patch.object(md.db,'kv_get',side_effect=[None,{'state':'error','at':100}]),patch.object(md.time,'time',return_value=110),patch('worker.enqueue_detail') as queue:
            self.assertEqual(md.ensure(MID),(None,'error'));queue.assert_not_called()

if __name__=='__main__':unittest.main()
