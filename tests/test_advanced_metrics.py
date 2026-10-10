"""2026-10-08 advanced metrics: kills vs expected, damage share, lobby MMR edge, CSR change, objective headline."""
import json,unittest
import analytics,web

def row(**kw):
    r=dict(kills=10,deaths=8,assists=3,duration_s=600,damage_dealt=3000,damage_taken=2500,personal_score=1000,team_pscore=4000,
           headshots=5,shots_fired=100,shots_hit=50,max_spree=4,outcome='Win',mode='Ranked:Slayer',pre_csr=None,post_csr=None,
           advanced=None,objectives=None)
    r.update(kw);return analytics.derive(r)

class Derive(unittest.TestCase):
    def test_advanced_fields(self):
        r=row(pre_csr=1500,post_csr=1508,advanced=json.dumps({'expected_kills':8.5,'expected_deaths':9,'team_damage':12000,
              'average_life_duration':31.4,'team_mmr':1600,'enemy_mmr':1650}))
        self.assertEqual((r['xk'],r['xd'],r['dmg_share'],r['life'],r['mmr_edge'],r['csr_d']),(1.5,1,25,31,-50,8))
    def test_missing_is_unknown_not_zero(self):
        r=row()
        for k in ('xk','xd','dmg_share','life','mmr_edge','csr_d','obj'):self.assertIsNone(r[k],k)
    def test_objective_headline_by_mode(self):
        o=json.dumps({'flag_captures':{'value':2},'time_as_skull_carrier':{'value':71.5},'stronghold_occupation_time':{'value':45.2},'stronghold_captures':{'value':5}})
        self.assertEqual(analytics.objective_line(o,'Ranked:CTF 3 Captures'),'2 caps')
        self.assertEqual(analytics.objective_line(o,'Ranked:Oddball'),'72s ball')
        self.assertEqual(analytics.objective_line(o,'Ranked:King of the Hill'),'45s hill')
        self.assertEqual(analytics.objective_line(o,'Ranked:Strongholds'),'5 zone caps')
        self.assertIsNone(analytics.objective_line(o,'Ranked:Slayer'))

class MedalsObjectives(unittest.TestCase):
    def test_per_game_medals_and_mode_objectives(self):
        rs=[row(medals=json.dumps({'Perfect':2,'Double Kill':1,'Triple Kill':1,'Snipe':1}),playlist='p',mode='Ranked:CTF 3 Captures',
                objectives=json.dumps({'flag_captures':{'value':2},'flag_returns':{'value':1}})),
            row(medals=json.dumps({}),playlist='p',mode='Ranked:Slayer'),
            row(medals=json.dumps({}),playlist=None,mode='Slayer')]                      # custom game, no medal data: skipped
        a=analytics._agg(rs)
        self.assertEqual((a['perfect_pg'],a['multi_pg'],a['snipe_pg'],a['medals_pg']),(1.0,1.0,0.5,2.5))
        self.assertEqual((a['caps_pg'],a['returns_pg'],a['ball_pg']),(2.0,1.0,None))   # per CTF game; no Oddball games = unknown

class Tiles(unittest.TestCase):
    def test_underdog_record_and_cap(self):
        rs=[row(outcome='Win',advanced=json.dumps({'team_mmr':1500,'enemy_mmr':1600})),row(outcome='Loss',advanced=json.dumps({'team_mmr':1500,'enemy_mmr':1530}))]
        self.assertEqual(analytics._agg(rs)['upsets'],{'games':2,'wins':1})
        t=web._adv_kpis({'A':rs})
        self.assertLessEqual(len(t),8)
        # the owner's priorities (2026-10-08): damage/min, damage per kill+assist, damage +/-, score share lead the row
        self.assertEqual([x['label'] for x in t[:4]],['Damage / min','Damage / (K+A)','Damage ± / game','Score share'])
    def test_dmg_ka_and_kda_format(self):
        r=row(kills=10,assists=5,damage_dealt=3000)
        self.assertEqual(r['dmg_ka'],200)
        self.assertEqual(web.kda_filter(9),'9.0');self.assertEqual(web.kda_filter(-2.333),'-2.3');self.assertEqual(web.kda_filter(None),'—')
    def test_squad_has_no_summed_csr(self):
        a=[row(pre_csr=1500,post_csr=1510)];b=[row(pre_csr=1400,post_csr=1390)]
        self.assertFalse(any(x['label']=='CSR change' for x in web._adv_kpis({'A':a,'B':b},a)))

if __name__=='__main__':
    unittest.main()


class BreakdownTests(unittest.TestCase):
    def test_session_vs_usual_modes_and_medals(self):
        import web
        from test_companion import row
        day=86400
        sess=[row('s1',100*day,kills=20,deaths=5,mode='Slayer',medals='{"Perfect": 2}'),row('s2',100*day-900,mode='Oddball',win=False,medals='{"Perfect": 1, "Boxer": 1}')]
        usual=[row(f'u{i}',100*day-day*(i+1),kills=8,deaths=8) for i in range(6)]+[row('old',100*day-200*day,kills=99)]
        b=web._breakdown(sess,sess+usual)
        self.assertEqual(b['base_games'],6)                     # the 200-day-old game and the session itself are left out
        kda=next(v for v in b['vs'] if v['label']=='KDA');self.assertTrue(kda['good']);self.assertGreater(kda['delta'],0)
        self.assertEqual({m['name'] for m in b['modes']},{'Slayer','Oddball'})
        self.assertEqual(b['medals'][0],('Perfect',3))
        self.assertEqual(web._breakdown(sess,sess)['base_games'],0)   # too few earlier games: no comparison


class RawViewTests(unittest.TestCase):
    def test_every_stat_objectives_and_medals_with_totals(self):
        import raw_view
        from test_companion import row
        a=row('a',2000,mode='Oddball',medals='{"Perfect": 1, "Boxer": 2}',advanced='{"melee_kills": 3, "team_mmr": 1500, "enemy_mmr": 1480}',
              objectives='{"time_as_skull_carrier": {"label": "Ball time", "value": 50.5, "unit": "s"}, "pvp_stats:kills": {"label": "Kills", "value": 10}}')
        b=row('b',1000,win=False,medals='{"Boxer": 1}',advanced='{"melee_kills": 1}')
        r=raw_view.build([a,b])
        keys=[c['key'] for c in r['cols']]
        self.assertIn('obj:time_as_skull_carrier',keys);self.assertNotIn('obj:pvp_stats:kills',keys)   # duplicate of K/D/A
        self.assertEqual(keys[-2:],['medal:Boxer','medal:Perfect'])                                       # most frequent first
        col=lambda k:keys.index(k)
        self.assertEqual([x['match_id'] for x in r['rows']],['b','a'])                                    # oldest first
        self.assertEqual(r['rows'][1]['cells'][col('obj:time_as_skull_carrier')],50.5);self.assertIsNone(r['rows'][0]['cells'][col('obj:time_as_skull_carrier')])
        self.assertEqual(r['total'][col('melee_kills')],4);self.assertEqual(r['total'][col('kills')],20)
        self.assertEqual(r['total'][col('medal:Boxer')],3);self.assertEqual(r['total'][col('medals_all')],4)
        self.assertEqual(r['rows'][1]['cells'][col('mmr_edge')],None if a.get('mmr_edge') is None else a['mmr_edge'])
        self.assertIsNone(raw_view.build([]))
