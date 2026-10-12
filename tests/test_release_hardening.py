"""2026-10-11 release hardening: stale-while-revalidate cache, separate rate-limit buckets, sync/login alerts."""
import sqlite3, threading, time, unittest
from unittest.mock import patch
import capacity, db, web


class StaleWhileRevalidate(unittest.TestCase):
    def test_expired_value_is_served_while_the_refresh_runs(self):
        c = capacity.Cache(); calls = []
        c.get('k', 60, lambda: (calls.append(1), 'old')[1], stale=True)
        c.items['k'] = (time.monotonic() - 999, 'old', 6)               # expire it
        gate = threading.Event()
        def slow(): gate.wait(2); calls.append(2); return 'new'
        t0 = time.time(); v = c.get('k', 60, slow, stale=True)
        self.assertEqual(v, 'old'); self.assertLess(time.time() - t0, 0.5)   # no waiting on the slow source
        gate.set(); time.sleep(0.2)
        self.assertEqual(c.get('k', 60, lambda: 'x', stale=True), 'new')    # the background refresh landed

    def test_without_stale_the_caller_still_waits_for_fresh(self):
        c = capacity.Cache(); c.get('k', 60, lambda: 'old')
        c.items['k'] = (time.monotonic() - 999, 'old', 6)
        self.assertEqual(c.get('k', 60, lambda: 'new'), 'new')


class RateBuckets(unittest.TestCase):
    def setUp(self):
        web.app.config.update(TESTING=True, SECRET_KEY='unit-test-only'); self.c = web.app.test_client()
        capacity.limiter.buckets.clear(); self.addCleanup(capacity.limiter.buckets.clear)

    def test_prefetch_has_its_own_budget(self):
        with patch.object(capacity.limiter, 'allow', wraps=capacity.limiter.allow) as allow:
            self.c.get('/about', headers={'Sec-Purpose': 'prefetch;prerender'})
            self.c.get('/about')
        keys = [a.args[0].split(':')[0] for a in allow.call_args_list]
        self.assertIn('prefetch', keys); self.assertIn('web', keys)


class SyncAlerts(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(':memory:', isolation_level=None, check_same_thread=False); self.conn.row_factory = sqlite3.Row
        self.p = patch.object(db, 'conn', return_value=self.conn); self.p.start(); db.init()
        self.addCleanup(self.conn.close); self.addCleanup(self.p.stop)

    def add(self, i, **kw):
        cols = dict(id=i, xuid=str(i), gamertag=f'P{i}', slug=f'p{i}', created_at=0, sync_state='ready'); cols.update(kw)
        self.conn.execute(f"INSERT INTO players({','.join(cols)}) VALUES({','.join('?' * len(cols))})", tuple(cols.values()))

    def test_stall_and_login_problem(self):
        import maintenance
        now = time.time()
        self.add(1, last_view=now - 60, last_synced=now - 5 * 3600)
        self.assertTrue(any('stalled' in a for a in maintenance.status()['alerts']))
        self.conn.execute('UPDATE players SET last_synced=?', (now - 60,))
        self.assertFalse(any('stalled' in a for a in maintenance.status()['alerts']))
        self.add(2, sync_state='error', sync_error='Halo API 401'); self.add(3, sync_state='error', sync_error='token expired')
        self.assertTrue(any('login problem' in a for a in maintenance.status()['alerts']))


if __name__ == '__main__':
    unittest.main()


class OffsiteCopy(unittest.TestCase):
    """2026-10-11: one gzip copy a day of a verified snapshot for the Google Drive job; newest 3 kept."""
    def test_daily_gzip_and_prune(self):
        import gzip, os, tempfile, maintenance
        from pathlib import Path
        with tempfile.TemporaryDirectory() as d:
            snap = Path(d) / 'snap.sqlite'; snap.write_bytes(b'SQLite format 3\x00' + b'x' * 5000)
            out = Path(d) / 'off'
            for n in range(4): out.mkdir(exist_ok=True); (out / f'clutchtape-2026010{n}.sqlite.gz').write_bytes(b'old')
            with patch.dict(os.environ, {'OFFSITE_DIR': str(out)}), patch.object(maintenance.db, 'kv_set'):
                first = maintenance.offsite(snap); again = maintenance.offsite(snap)
            self.assertIsNotNone(first); self.assertIsNone(again)                 # once a day
            self.assertEqual(gzip.decompress(first.read_bytes()), snap.read_bytes())
            self.assertEqual(len(list(out.glob('clutchtape-*.sqlite.gz'))), 3)      # newest 3 kept


class FinishClip(unittest.TestCase):
    """2026-10-12: a won close/overtime game's final objective play is a clip (medal fights never saw it)."""
    def ev(self, x, k, t, m=None):
        import types
        return types.SimpleNamespace(xuid=x, gamertag=x, event_type=k, time_ms=t, medal_name=m)
    def test_overtime_capture_is_a_clip(self):
        import clips
        evs = [self.ev('me', 'kill', 900000), self.ev('me', 'kill', 908000), self.ev('me', 'mode', 917000)]
        ms = clips.find_moments(evs, 'me', {'duration_s': 919, 'team_score': 3, 'enemy_score': 2, 'mode': 'CTF 3 Captures'})
        self.assertTrue(ms and ms[0].get('finish'))
        self.assertIn('Game-winning capture in overtime', ms[0]['label'])
    def test_lost_or_blowout_games_get_none(self):
        import clips
        evs = [self.ev('me', 'mode', 917000)]
        self.assertFalse(clips.find_moments(evs, 'me', {'duration_s': 919, 'team_score': 2, 'enemy_score': 3, 'mode': 'CTF 3 Captures'}))
        self.assertFalse(clips.find_moments(evs, 'me', {'duration_s': 600, 'team_score': 50, 'enemy_score': 20, 'mode': 'Slayer'}))


class PresenceKinds(unittest.TestCase):
    """2026-10-12: Halo rich-presence lines sorted into what the live box shows."""
    def test_classify(self):
        import presence
        c = presence.classify
        self.assertEqual(c('Custom Game: Slayer on Live Fire')['kind'], 'custom')
        self.assertEqual(c('Ranked Arena: CTF on Aquarius')['kind'], 'ranked')
        self.assertEqual(c('Quick Play: Slayer')['kind'], 'matchmaking')
        self.assertEqual(c('Main Menu')['kind'], 'menu')
        self.assertEqual(c('Firefight: King of the Hill')['kind'], 'firefight')
        self.assertIsNone(c(''))
    def test_parse_needs_halo_active(self):
        import presence
        e = {'devices': [{'titles': [{'name': 'Home', 'state': 'Active'}, {'name': 'Halo Infinite', 'state': 'Active', 'activity': {'richPresence': 'Custom Game'}}]}]}
        self.assertEqual(presence._parse(e)['kind'], 'custom')
        self.assertIsNone(presence._parse({'devices': [{'titles': [{'name': 'Online', 'state': 'Active'}]}]}))
