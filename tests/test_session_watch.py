import sqlite3
import unittest
from unittest.mock import patch

import db
import session_watch


class SessionWatch(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(':memory:')
        self.conn.row_factory = sqlite3.Row
        self.conn.execute('CREATE TABLE moments(player_id INTEGER, match_id TEXT, t_ms INTEGER)')
        self.p = patch.object(db, 'conn', return_value=self.conn)
        self.p.start()
        self.addCleanup(self.conn.close)
        self.addCleanup(self.p.stop)

    def game(self, mid='a', mode='Slayer', team=50, enemy=49, outcome='Win'):
        return dict(match_id=mid, mode=mode, team_score=team, enemy_score=enemy, outcome=outcome)

    def test_close_finish_is_mode_specific_and_loss_is_not_called_win(self):
        result = session_watch.for_matches([self.game(outcome='Loss', team=49, enemy=50),
                                           self.game('b', 'CTF 3 Captures', 3, 1)], [1])
        self.assertEqual(result['a'][0]['text'], 'Close · 1 kill')
        self.assertNotIn('b', result)

    def test_counts_whole_session_deduplicates_and_scopes_players(self):
        rows = [(1, 'a', n * 16000) for n in range(16)]
        rows += [(2, 'a', 1000), (99, 'a', 999999), (1, 'other-session', 0)]
        self.conn.executemany('INSERT INTO moments VALUES (?,?,?)', rows)
        result = session_watch.for_matches([self.game()], [1, 2])
        self.assertEqual(result['a'][-1]['text'], '16 clips')

    def test_no_scores_no_clips_and_unfinished_are_not_promoted(self):
        self.conn.execute("INSERT INTO moments VALUES (1,'dnf',1000)")
        games = [self.game(team=None), self.game('blowout', enemy=20), self.game('dnf', outcome='Dnf')]
        self.assertEqual(session_watch.for_matches(games, [1]), {})
        self.assertEqual(session_watch.for_matches([], [1]), {})

    def test_known_tie_and_single_clip(self):
        self.conn.execute("INSERT INTO moments VALUES (1,'a',1000)")
        cues = session_watch.for_matches([self.game(team=2, enemy=2, outcome='Tie')], [1])['a']
        self.assertEqual([c['text'] for c in cues], ['Tied finish', '1 clip'])

    def test_session_reasons_count_games_once_and_use_chronological_streak(self):
        games = [dict(self.game(str(i)), started_at=i) for i in range(4)]
        self.conn.executemany('INSERT INTO moments VALUES (?,?,?)',
                              [(1, '0', 0), (2, '0', 1000), (1, '1', 9000)])
        session = dict(matches=list(reversed(games)))
        result = session_watch.for_sessions([session], [1, 2], {'123': [['0', 0], ['0', 1]]})['0']
        self.assertEqual(result['label'], 'Top pick')
        self.assertEqual(result['reasons'], ['4 close games', '2 detected clips', '4-game win streak'])
        self.assertEqual(result['recorded'], 1)

    def test_session_does_not_invent_reasons_and_loss_breaks_streak(self):
        games = [dict(self.game(str(i), enemy=20, outcome=outcome), started_at=i)
                 for i, outcome in enumerate(['Win', 'Win', 'Loss', 'Win', 'Win'])]
        pick = session_watch.for_sessions([dict(matches=games)], [1])['4']
        self.assertEqual(pick['label'], 'No strong signal yet')
        self.assertEqual(pick['reasons'], [])
        self.assertEqual(pick['recorded'], 0)
