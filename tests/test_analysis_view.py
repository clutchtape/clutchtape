"""Analytics contracts: aligned filters, weighted rates, missing data and privacy-safe charts."""
import json
import unittest
from types import SimpleNamespace as NS
from unittest.mock import patch
from test_companion import row
import dashboard, analysis_view, stat_depth, objectives

P=[dict(id=1,slug='sample',gamertag='Sample',xuid='123',last_synced=1,sync_state='ready')]

class AnalysisTests(unittest.TestCase):
    def test_weighted_rolling_and_missing_optional_fields(self):
        a=row('a',t=100,duration_s=600,shots_fired=100,shots_hit=50,extra={'melee_kills':0})
        b=row('b',t=200,duration_s=1200,shots_fired=300,shots_hit=300,extra={})
        report=analysis_view.build(P,[b,a],{1:[b,a]})
        last=report['series'][0]['points'][-1]
        self.assertEqual(last['rolling']['acc'],87.5)
        self.assertEqual(last['rolling']['dmg_pm'],200)
        self.assertEqual(last['rolling']['melee'],0)
        self.assertEqual(next(m for m in report['players'][0]['metrics'] if m['key']=='melee')['n'],1)
        self.assertIsNone(last['values']['melee'])

    def test_range_baseline_precedes_whole_selection(self):
        rs=[row(str(i),t=i*10000) for i in range(1,6)]
        sessions=[dict(matches=[r]) for r in reversed(rs)]
        report=analysis_view.build(P,rs[2:],{1:rs},'previous',sessions)
        self.assertEqual(report['players'][0]['baseline'],1)
        self.assertEqual(report['scope_games'],3)

    def test_playlist_and_period_feed_all_views_without_changing_playlist(self):
        rs=[row('a',t=100000,playlist='Ranked A'),row('b',t=100000,playlist='Ranked B'),row('old',t=100,playlist='Ranked A')]
        with patch.object(dashboard.db,'q',return_value=rs),patch.object(dashboard.db,'q1',return_value=None),patch.object(dashboard.time,'time',return_value=100001):
            b=dashboard.load.__wrapped__(P,'mm',scope='30',playlist='Ranked A') if hasattr(dashboard.load,'__wrapped__') else dashboard.load(P,'mm',scope='30',playlist='Ranked A')
        self.assertEqual(b['playlist'],'Ranked A')
        self.assertEqual(b['summary']['games'],2)
        self.assertEqual(b['analysis']['scope_games'],2)
        self.assertEqual(sum(m['games'] for m in b['maps']),2)
        self.assertEqual(len(b['analysis']['series'][0]['points']),2)
        self.assertFalse(b['current'])

    def test_shared_game_count_and_per_player_charts(self):
        ps=P+[dict(id=2,slug='other',gamertag='Other',xuid='456')]
        a=row('shared',pid=1);b=row('shared',pid=2,kills=20)
        match=dict(a,members={1:a,2:b})
        r=analysis_view.build(ps,[match],{1:[a],2:[b]})
        self.assertEqual(r['scope_games'],1);self.assertEqual(r['player_games'],2)
        self.assertEqual(len(r['series']),2)
        self.assertTrue(r['series'][1]['points'][0]['url'].endswith('player=other'))

    def test_skill_missing_not_zero_and_death_expectations(self):
        self.assertEqual(stat_depth.skill(None),{})
        result=NS(stat_performances=NS(kills=NS(expected=12.5),deaths=NS(expected=9)),team_id=0,team_mmr=1500,team_mmrs={0:1500,1:1510})
        d=stat_depth.skill(result)
        self.assertEqual(d['expected_deaths'],9);self.assertEqual(d['enemy_mmr'],1510)
        self.assertIsNone(stat_depth.number(float('nan')))

    def test_cached_raw_extraction_does_not_need_network(self):
        r=row('one',advanced=None)
        raw={'players':[{'player_id':'xuid(123)','player_team_stats':[{'stats':{'core_stats':{'melee_kills':0,'average_life_duration':'PT23.5S'},'oddball_stats':{'time_as_skull_carrier':'PT1M2S'}}}]}],'teams':[{'team_id':0,'stats':{'core_stats':{'damage_dealt':10000}}}]}
        with patch.object(stat_depth.db,'q',return_value=[{'k':'matchraw:one','v':json.dumps(raw)}]):stat_depth.enrich([r],'123')
        self.assertEqual(r['extra']['average_life_duration'],23.5)
        self.assertEqual(r['extra']['team_damage'],10000)
        self.assertEqual(json.loads(r['objectives'])['time_as_skull_carrier']['value'],62)

    def test_longest_ball_hold_is_maximum_not_sum(self):
        rows=[dict(objectives=json.dumps(objectives.extract({'oddball_stats':{'longest_time_as_skull_carrier':v}}))) for v in (10,20)]
        self.assertEqual(analysis_view._objective_values(rows)['longest_time_as_skull_carrier']['value'],20)

    def test_rank_playlists_stay_separate_and_peak_includes_start(self):
        rs=[row('a',playlist='Ranked A',pre_csr=1600,post_csr=1590),row('b',playlist='Ranked B',pre_csr=1400,post_csr=1410)]
        r=analysis_view.build(P,rs,{1:rs})
        self.assertEqual(len(r['ranks']),2)
        self.assertEqual(r['ranks'][0]['peak'],1600)
        self.assertEqual(r['ranks'][0]['delta'],-10)


class FullStatsTests(unittest.TestCase):
    def test_damage_per_ka_uses_total_damage_and_total_kills_assists(self):
        a=row('a',kills=10,assists=0,damage_dealt=3000,damage_taken=4000,callouts=2)
        b=row('b',kills=30,assists=20,damage_dealt=9000,damage_taken=5000,callouts=4)
        r=analysis_view.measure([a,b])
        self.assertEqual(r['dmg_ka'],200)
        self.assertEqual(r['dmg_diff'],1500)
        self.assertEqual(r['dmg_diff_total'],3000)
        self.assertEqual(r['callouts'],3)
        self.assertEqual(r['callouts_total'],6)
        self.assertEqual(r['kills_total'],40)

    def test_zero_ka_and_missing_damage_are_not_invented(self):
        r=analysis_view.measure([row(kills=0,assists=0,damage_dealt=100)])
        self.assertIsNone(r['dmg_ka'])
        r=analysis_view.measure([row(damage_dealt=None,damage_taken=None,callouts=None)])
        self.assertIsNone(r['dmg_diff']);self.assertIsNone(r['callouts'])
        self.assertEqual(r['dmg_diff_n'],0)

    def test_core_rounds_and_arbitrary_mode_fields_are_kept(self):
        r=stat_depth.extract({'rounds_won':2,'rounds_lost':0,'emp_assists':3,'spawns':17})
        self.assertEqual(r['rounds_lost'],0);self.assertEqual(r['_version'],2)
        obj=objectives.extract({'bomb_stats':{'bomb_plants':2,'time_as_bomb_carrier':'PT15S'},'core_stats':{'kills':20}})
        self.assertEqual(obj['bomb_stats:bomb_plants']['value'],2)
        self.assertEqual(obj['bomb_stats:time_as_bomb_carrier']['unit'],'s')
        self.assertNotIn('kills',obj)

    def test_objectives_averages_use_reporting_games_and_totals_are_exact(self):
        rs=[row('a',objectives=json.dumps({'flag_captures':dict(label='Captures',value=3,unit='')})),row('b',objectives='{}')]
        r=analysis_view.measure(rs)
        self.assertEqual(r['obj:flag_captures'],3)
        self.assertEqual(r['obj:flag_captures_n'],1)
        self.assertEqual(r['obj:flag_captures_total'],3)
