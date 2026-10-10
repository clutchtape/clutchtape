"""2026-10-09 squad lineups: exact same-team groups by stack size, best per size, partners, with/without."""
import unittest
import dashboard

def row(pid, mid, team, outcome, kills=10):
    return dict(player_id=pid, match_id=mid, team_id=team, outcome=outcome, kills=kills, deaths=5, assists=3, duration_s=600,
                damage_dealt=3000, damage_taken=2500, personal_score=1000, team_pscore=4000, headshots=1, pre_csr=None, post_csr=None,
                advanced=None, objectives=None, mode='Slayer')

class Lineups(unittest.TestCase):
    def test_sizes_best_pairs_without(self):
        ps = [dict(id=1, gamertag='A'), dict(id=2, gamertag='B'), dict(id=3, gamertag='C')]
        h = {1: [], 2: [], 3: []}
        for i in range(4):                                   # A+B duo: 3-1
            for pid in (1, 2): h[pid].append(row(pid, f'd{i}', 0, 'Win' if i < 3 else 'Loss'))
        for i in range(3):                                   # A+B+C trio: 1-2
            for pid in (1, 2, 3): h[pid].append(row(pid, f't{i}', 0, 'Win' if i == 0 else 'Loss'))
        h[3].append(row(3, 'opp', 1, 'Win')); h[1].append(row(1, 'opp', 0, 'Loss'))   # opponents: not a lineup
        la = dashboard.lineup_analysis(ps, h)
        duo, trio = la['sizes'][0], la['sizes'][1]
        self.assertEqual((duo['size'], duo['best']['names'], duo['best']['record']), (2, ['A', 'B'], '3-1'))
        self.assertEqual((trio['best']['record'], trio['best']['win_pct']), ('1-2', 33))
        self.assertEqual(la['pairs'][('A', 'B')]['games'], 7)                        # duo + trio games
        c = next(w for w in la['without'] if w['name'] == 'C')
        self.assertEqual((c['with_pct'], c['without_pct']), (33, 75))

if __name__ == '__main__':
    unittest.main()
