"""Close-games ranking (close_games.py): which games count, and in what order."""
import unittest
import close_games as cg

def m(mode,ts,es,outcome='Win',dur=600): return {'mode':mode,'team_score':ts,'enemy_score':es,'outcome':outcome,'duration_s':dur}

class CloseGames(unittest.TestCase):
    def test_one_kill_slayer_to_the_cap(self):
        s=cg.score(m('Ranked:Slayer',50,49))
        self.assertEqual(s['reasons'],['Won by 1','Went to the cap']);self.assertEqual(s['final'],'50–49');self.assertEqual(s['rank'],69)
    def test_blowouts_ties_and_dnf_are_not_listed(self):
        self.assertIsNone(cg.score(m('Ranked:Slayer',50,30)))
        self.assertIsNone(cg.score(m('Ranked:Slayer',50,50,'Tie')))
        self.assertIsNone(cg.score(m('Ranked:Slayer',50,49,'Dnf')))
        self.assertIsNone(cg.score(m('Ranked:Slayer',None,49)))
    def test_non_competitive_modes_are_ignored(self):
        for mode in ('1000 bots','HEFR:Aimbotz Unlimited','CTF:BTB Fiesta','1V1 OCTAGON SHIELD RECHARGE'):
            self.assertIsNone(cg.family(mode),mode)
        self.assertEqual(cg.family('Ranked:Doubles Slayer'),'doubles')
    def test_ctf_overtime_and_cap_from_name(self):
        s=cg.score(m('Ranked:CTF 3 Captures',3,2,dur=800))
        self.assertIn('Overtime',s['reasons']);self.assertEqual(s['unit'],'caps')
        self.assertIn('Went to the cap',cg.score(m('Ranked:CTF 5 Captures',5,4,dur=500))['reasons'])
    def test_pro_vs_pro_and_best_play_raise_rank(self):
        base=cg.score(m('Ranked:Strongholds',250,240))['rank']
        self.assertGreater(cg.score(m('Ranked:Strongholds',250,240),pro_vs_pro=True)['rank'],base)
        self.assertGreater(cg.score(m('Ranked:Strongholds',250,240),best_play=80)['rank'],base)
        self.assertLessEqual(cg.score(m('Ranked:Slayer',50,49),80,True)['rank'],100)

class Finishes(unittest.TestCase):
    def ev(self,*items): return [(t,k,gt,med) for t,k,gt,med in items]
    def test_slayer_cap_names_the_game_winning_kill(self):
        g=cg.score(m('Ranked:Slayer',50,49))
        f=cg.finish(g,self.ev((100000,'kill','A',None),(395000,'kill','B',None),(398000,'medal','B','Triple Kill'),(400000,'kill','Pro',None),(400000,'death','X',None)))
        self.assertEqual(f['decider'],('Game-winning kill','Pro'));self.assertEqual(f['kills'],2)
        self.assertIn('Triple Kill · B',f['reasons']);self.assertEqual(f['start_ms'],365000)
    def test_objective_modes_get_no_decider(self):
        g=cg.score(m('Ranked:Strongholds',250,249))
        f=cg.finish(g,self.ev((500000,'kill','A',None),(505000,'mode','B',None)))
        self.assertIsNone(f['decider']);self.assertIn('1 objective play',f['reasons'])
    def test_common_medals_are_not_big_plays(self):
        g=cg.score(m('Ranked:Slayer',50,49))
        quiet=cg.finish(g,self.ev((1000,'kill','A',None),(1000,'medal','A','Perfect')))
        loud=cg.finish(g,self.ev((1000,'kill','A',None),(1000,'medal','A','Off the Rack')))
        self.assertGreater(loud['rank'],quiet['rank'])
    def test_no_film_or_no_action(self):
        g=cg.score(m('Ranked:Slayer',50,49))
        self.assertIsNone(cg.finish(g,[]));self.assertIsNone(cg.finish(g,self.ev((1000,'medal','A','Perfect'))))

if __name__=='__main__': unittest.main()
