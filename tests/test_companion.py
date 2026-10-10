"""Companion analytics and stable links, with no external services."""
import os
import sys
import tempfile
import unittest
from datetime import timedelta
from types import SimpleNamespace as NS
from unittest.mock import patch
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
import dashboard, objectives


def row(mid='a',t=1000,pid=1,team=0,win=True,**kwargs):
    r=dict(match_id=mid,started_at=t,player_id=pid,team_id=team,outcome='Win' if win else 'Loss',duration_s=600,playlist='Ranked',mode='Slayer',map='Recharge',kills=10,deaths=5,assists=3,damage_dealt=3000,damage_taken=2500,shots_fired=100,shots_hit=50,personal_score=1000,team_pscore=4000,max_spree=4,headshots=5,ranked=1,pre_csr=1500,post_csr=1508,film_state=1,objectives=None)
    r.update(kwargs);dashboard.analytics.derive(r);return r


class CompanionTests(unittest.TestCase):
    def test_stable_session_survives_new_sessions_and_history_expansion(self):
        old={'matches':[row('b'),row('a')]}
        self.assertEqual(dashboard.anchor(old),'a')
        self.assertEqual(dashboard.select_session([old],'a'),0)
        self.assertEqual(dashboard.select_session([{'matches':[row('new')]},old],'a'),1)
        old['matches'].append(row('older'))
        self.assertEqual(dashboard.select_session([old],'a'),0)
        self.assertIsNone(dashboard.select_session([old],'missing'))

    def test_progress_excludes_future_other_modes_and_too_small_samples(self):
        ps=[dict(id=1,gamertag='A')]
        selected=[row('now',100000)]
        earlier=[row(str(i),i*1000) for i in range(1,7)]
        allrows=earlier+[row('future',110000,kills=100),row('wrong-mode',99000,mode='Oddball',kills=200)]+selected
        p,r=dashboard.progress(ps,{1:allrows},selected)
        self.assertEqual(p[0]['baseline'],6)
        self.assertEqual(p[0]['metrics'][0]['delta'],0)
        self.assertIsNone(p[0]['metrics'][-1]['delta'])
        p,r=dashboard.progress(ps,{1:earlier[:2]+selected},selected)
        self.assertTrue(all(m['delta'] is None for m in p[0]['metrics']))

    def test_personal_records_use_matching_playlist_mode_and_prior_history(self):
        r=row('new',10000,kills=30)
        earlier=[row(str(i),i*1000,kills=20) for i in range(1,7)]
        _,records=dashboard.progress([dict(id=1,gamertag='A')],{1:earlier+[r,row('future',20000,kills=50)]},[r])
        self.assertEqual(records[0]['value'],30)
        self.assertEqual(records[0]['previous'],20)
        self.assertEqual(records[0]['games'],6)

    def test_lineups_require_same_team_and_count_match_once(self):
        ps=[dict(id=i,gamertag=str(i)) for i in (1,2,3)]
        data={1:[row('a',pid=1),row('b',pid=1)],2:[row('a',pid=2),row('b',pid=2,team=1)],3:[row('a',pid=3)]}
        result=dashboard.lineups(ps,data)
        self.assertEqual(len(result),1);self.assertEqual(result[0]['games'],1);self.assertEqual(result[0]['names'],['1','2','3'])

    def test_map_mode_summary_counts_squad_games_once(self):
        a=row('a');a['members']={1:row('a'),2:row('a',pid=2,kills=30,shots_hit=90)}
        result=dashboard.map_modes([a])[0]
        self.assertEqual(result['games'],1);self.assertEqual(result['wins'],1);self.assertEqual(result['acc'],70)

    def test_rates_are_weighted_and_consistency_needs_three_games(self):
        rs=[row('a',duration_s=600),row('b',duration_s=1200)]
        a=dashboard.rates(rs);self.assertEqual(a['death_pm'],.33);self.assertIsNone(a['spread'])
        self.assertEqual(dashboard.rates(rs+[row('c')])['spread'],0)

    def test_review_without_twitch_and_window_is_clamped(self):
        events=[dict(xuid='x',t_ms=t,k='kill') for t in range(0,30000,5000)]
        with patch.object(dashboard.db,'q1',return_value={'n':6}),patch.object(dashboard.db,'q',return_value=events):
            m=dashboard.review_moments([row()],[dict(id=1,xuid='x',gamertag='A')])
        self.assertEqual(m[0]['category'],'Strong stretch');self.assertGreater(m[0]['duration'],0);self.assertGreaterEqual(m[0]['at'],0)

    def test_objective_extraction_missing_zero_and_duration(self):
        s=NS(capture_the_flag_stats=NS(flag_captures=0,flag_returns=2,time_as_flag_carrier=timedelta(seconds=67)),oddball_stats=None)
        values=objectives.extract(s)
        self.assertEqual(values['flag_captures']['value'],0)
        self.assertEqual(values['time_as_flag_carrier']['value'],67)
        self.assertNotIn('time_as_skull_carrier',values)
        import json
        result=objectives.summarize([{'objectives':None},{'objectives':'{}'},{'objectives':json.dumps(values)}])
        self.assertEqual(result['checked'],2);self.assertEqual(result['total'],3)
        self.assertEqual(next(x['display'] for x in result['metrics'] if x['label']=='Flag carry'),'1:07')

    def test_links_encode_and_do_not_depend_on_session_position(self):
        url=dashboard.link('a,b','ranked','match-1','match-2',at=-4,map='A&B')
        self.assertIn('session=match-1',url);self.assertIn('at=0',url);self.assertIn('A%26B',url);self.assertNotIn('?s=',url)

class CompanionPageTests(unittest.TestCase):
    def setUp(self):
        import web
        self.web=web
        self.ps=[dict(id=1,xuid='x',gamertag='No Games',slug='no-games',sync_state='ready',last_synced=1)]

    def test_empty_dashboard_renders_and_does_not_invent_results(self):
        with patch.object(dashboard.db,'q',return_value=[]):
            b=dashboard.load(self.ps)
        b.update(version='empty');b['coverage']['video']=0
        with patch.object(self.web,'_board_data',return_value=b),patch.object(self.web.db,'run'),patch.object(self.web.worker,'enqueue'),patch.object(self.web.xbox,'status',return_value={'connected':True}):
            response=self.web.app.test_client().get('/live/no-games')
            # 2026-10-08: the dashboard is now the Analysis tab of the player/squad page; old links redirect there.
            self.assertEqual(response.status_code,301);self.assertEqual(response.location,'/p/no-games?tab=analysis')
            with self.web.app.test_request_context('/p/no-games?tab=analysis'):
                html=self.web.render_template('_board_body.html',b=b,explanations=self.web.analysis_view.explanations(b),kinds=self.web.analytics.KINDS,recap_matches=[],recap_names=[])
        self.assertIn('Ready when you are.',html)
        self.assertNotIn('class="session-score"',html)

    def test_missing_stable_session_does_not_silently_select_latest(self):
        with patch.object(dashboard.db,'q',return_value=[row()]):
            b=dashboard.load(self.ps,session='missing')
        self.assertTrue(b['missing']);self.assertIsNone(b['selected']);self.assertEqual(b['matches'],[])

    def test_profile_legacy_and_stable_selectors(self):
        sessions=[{'matches':[row('new')]},{'matches':[row('old')]}]
        with self.web.app.test_request_context('/p/a?s=1'):
            self.assertEqual(self.web._sess_idx(sessions),1)
        with self.web.app.test_request_context('/p/a?session=old'):
            self.assertEqual(self.web._sess_idx(sessions),1)
        with self.web.app.test_request_context('/p/a?session=missing'):
            from werkzeug.exceptions import NotFound
            with self.assertRaises(NotFound): self.web._sess_idx(sessions)

    def test_poll_version_does_not_change_just_because_history_was_checked(self):
        with patch.object(dashboard.db,'q1',return_value=(3,10000,2,2)):
            a=dashboard.version([dict(id=1,last_synced=1,sync_state='ready')])
            b=dashboard.version([dict(id=1,last_synced=900,sync_state='syncing')])
        self.assertEqual(a,b)
        with patch.object(dashboard.db,'q1',return_value=(4,20000,2,2)):
            self.assertNotEqual(a,dashboard.version([dict(id=1)]))
