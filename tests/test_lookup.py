"""Lookup regressions use an isolated database and never contact Xbox/Twitch."""
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from werkzeug.datastructures import MultiDict

_tmp = tempfile.TemporaryDirectory()
os.environ['HALO_DATA_DIR'] = _tmp.name
os.environ['DB_DIR'] = _tmp.name
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'app'))
import db
import web
import twitch


class LookupTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        db.init()
        web.app.config.update(TESTING=True, SECRET_KEY='test-only')

    def setUp(self):
        self.client = web.app.test_client()
        with self.client.session_transaction() as session:
            session['csrf'] = 'test-csrf'
        self.xbox = patch.object(web.xbox, 'status', return_value={'connected': True})
        self.xbox.start()
        self.addCleanup(self.xbox.stop)
        self.enabled = patch.object(twitch, 'enabled', return_value=True)
        self.enabled.start()
        self.addCleanup(self.enabled.stop)

    def post(self, tags, channels):
        return self.client.post('/add', data=MultiDict(
            [('csrf', 'test-csrf')] + [('gamertag', x) for x in tags] + [('twitch', x) for x in channels]))

    def test_invalid_submission_preserves_escaped_rows_without_cookie_storage(self):
        response = self.post(['bad<tag>', 'CyKul'], ['', 'twitch.tv/cykul'])
        self.assertEqual(response.status_code, 400)
        html = response.get_data(as_text=True)
        self.assertIn('value="bad&lt;tag&gt;"', html)
        self.assertIn('value="CyKul"', html)
        self.assertIn('value="twitch.tv/cykul"', html)
        with self.client.session_transaction() as session:
            self.assertEqual(dict(session), {'csrf': 'test-csrf'})

    def test_duplicate_does_not_silently_discard_channel(self):
        response = self.post(['CyKul', 'cykul'], ['', 'twitch.tv/cykul'])
        self.assertEqual(response.status_code, 400)
        self.assertIn('listed twice', response.get_data(as_text=True))

    def test_success_keeps_player_channel_pairing(self):
        with patch.object(web, '_add_one', side_effect=[('cykul', 'cykul', None), ('lethul', None, None)]) as lookup:
            response = self.post(['CyKul', 'Lethul'], ['twitch.tv/cykul', ''])
        self.assertEqual(response.status_code, 302)
        # A Twitch link opens the full squad page (player, Watch together); 2026-10-08 product change.
        self.assertEqual(response.location, '/squad/cykul,lethul?tw=cykul:cykul')
        self.assertEqual(lookup.call_args_list[1].args, ('Lethul', ''))

    def test_lookup_always_opens_the_one_page_per_player_or_squad(self):
        # 2026-10-08: one page per player/squad (Halo-site layout); Twitch only adds ?tw=.
        with patch.object(web, '_add_one', return_value=('x-echo-x', 'x_echo_x', None)):
            self.assertEqual(self.post(['x Echo x'], ['twitch.tv/x_echo_x']).location, '/p/x-echo-x?tw=x_echo_x')
        with patch.object(web, '_add_one', return_value=('x-echo-x', None, None)):
            self.assertEqual(self.post(['x Echo x'], ['']).location, '/p/x-echo-x')
        with patch.object(web, '_add_one', side_effect=[('a', None, None), ('b', None, None)]):
            self.assertEqual(self.post(['A', 'B'], ['', '']).location, '/squad/a,b')

    def test_open_stats_page_checks_for_first_game_without_twitch(self):
        db.run("INSERT OR IGNORE INTO players(xuid,gamertag,slug,created_at,sync_state,last_synced) VALUES(?,?,?,?,?,?)",
               'test-first-game', 'Test Player', 'test-first-game', 0, 'ready', 0)
        with patch.object(web.worker, 'enqueue') as enqueue:
            response = self.client.get('/api/live/test-first-game')
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.json['players'][0]['live'])
        enqueue.assert_called_once()
        with patch.object(web.worker, 'enqueue'):
            response = self.client.get('/p/test-first-game')
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn('data-slug="test-first-game"', html)
        self.assertIn('No recent game yet', html)
        self.assertNotIn('id="tplayer"', html)

    def test_add_player_keeps_current_squad_without_relooking_them_up(self):
        for i, gt in enumerate(('Keep A', 'Keep B', 'New C')):
            db.run("INSERT OR IGNORE INTO players(xuid,gamertag,slug,created_at) VALUES(?,?,?,0)", f'9{i}', gt, gt.lower().replace(' ', '-'))
        r = self.client.post('/add', data=MultiDict([('csrf', 'test-csrf'), ('squad', 'keep-a,keep-b,not-a-player,../x'), ('gamertag', 'New C'), ('twitch', '')]))
        self.assertEqual(r.location, '/squad/keep-a,keep-b,new-c')      # unknown/invalid kept slugs are dropped

    def test_channel_parser_rejects_non_channel_urls(self):
        for value in ['https://evil.example/twitch.tv/cykul', 'https://nottwitch.tv/cykul', 'https://twitch.tv/videos/1234', 'https://twitch.tv/cykul/clip/example', 'https://twitch.tv:bad/cykul']:
            with self.subTest(value=value):
                self.assertIsNone(twitch.parse_login(value))
        for value in ['CyKul', '@cykul', 'twitch.tv/cykul', 'https://www.twitch.tv/cykul/videos', 'https://m.twitch.tv/cykul?ref=share']:
            with self.subTest(value=value):
                self.assertEqual(twitch.parse_login(value), 'cykul')

if __name__ == '__main__':
    unittest.main()
