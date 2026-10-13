"""Capacity regressions use an isolated database; no Halo/Twitch traffic."""
import sqlite3
import unittest
from unittest.mock import patch, AsyncMock
import db
import worker
import web


class SyncScaling(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(':memory:', isolation_level=None, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.db_patch = patch.object(db, 'conn', return_value=self.conn)
        self.db_patch.start()
        db.init()
        self.addCleanup(self.conn.close)
        self.addCleanup(self.db_patch.stop)
        self.now = 2000000
        self.clock = patch.object(worker.time, 'time', return_value=self.now)
        self.clock.start()
        self.addCleanup(self.clock.stop)
        self.follow = patch.object(worker, '_followed_names', return_value=(set(), set()))
        self.follow.start()
        self.addCleanup(self.follow.stop)
        self.clear_queue()
        self.addCleanup(self.clear_queue)

    def clear_queue(self):
        while not worker._q.empty():
            worker._q.get_nowait()
        worker._queued.clear()
        worker._film_pending.clear()
        worker._film_rest.clear()

    def player(self, pid, state='ready', viewed=None, synced=0):
        db.run("INSERT INTO players(id,xuid,gamertag,slug,created_at,sync_state,last_view,last_synced) VALUES(?,?,?,?,?,?,?,?)",
               pid, str(pid), 'Load Test '+str(pid), 'load-test-'+str(pid), self.now, state, viewed, synced)

    def test_500_imports_drain_once_with_bounded_memory_and_restart(self):
        for pid in range(1, 501):
            self.player(pid, state='queued')
        worker.schedule()
        self.assertLessEqual(len(worker._queued), worker.MAX_PENDING//2)
        self.assertEqual(worker.position(500), 500)
        # Losing the in-memory queue does not lose accepted jobs.
        self.clear_queue()
        seen = []
        while len(seen) < 500:
            worker.schedule()
            self.assertLessEqual(len(worker._queued), worker.MAX_PENDING//2)
            self.assertFalse(worker._q.empty(), 'durable work must not get stranded')
            pid = worker._q.get_nowait()[2]
            seen.append(pid)
            worker._queued.discard(pid)
            db.run("UPDATE players SET sync_state='ready',last_synced=? WHERE id=?", self.now, pid)
        self.assertEqual(seen, list(range(1, 501)))

    def test_500_idle_players_back_off_and_expire(self):
        for pid in range(1, 501):
            self.player(pid, viewed=self.now-2*86400, synced=self.now-3600)
        self.assertEqual(worker.refresh_due(), [])
        db.run("UPDATE players SET last_synced=?", self.now-86401)
        self.assertEqual(len(worker.refresh_due()), 500)
        db.run("UPDATE players SET last_view=?", self.now-8*86400)
        self.assertEqual(worker.refresh_due(), [])

    def test_500_viewed_players_share_budget_and_oldest_goes_first(self):
        for pid in range(1, 501):
            self.player(pid, viewed=self.now, synced=self.now-60)
        self.assertEqual(worker.viewing_interval(), 1000)
        self.assertEqual(worker.refresh_due(), [])
        db.run("UPDATE players SET last_synced=? WHERE id=500", self.now-2000)
        db.run("UPDATE players SET last_synced=? WHERE id=1", self.now-1500)
        self.assertEqual(worker.refresh_due(), [500, 1])

    def test_same_player_500_viewers_only_one_job(self):
        self.player(1, viewed=self.now)
        self.assertEqual(sum(worker.enqueue(1) for _ in range(500)), 1)
        self.assertEqual(worker.backlog(), 1)

    def test_foreground_capacity_reserved_and_priority(self):
        for pid in range(1, 501):
            self.player(pid, state='queued')
        worker.schedule()
        self.assertTrue(worker.enqueue(900))
        self.assertEqual(worker._q.get_nowait()[2], 900)

    def test_viewer_promotes_existing_background_job_without_duplicate(self):
        worker.enqueue(1, background=True)
        worker.enqueue(2, background=True)
        self.assertFalse(worker.enqueue(2))
        self.assertEqual(worker.backlog(), 2)
        self.assertEqual(worker._q.get_nowait()[2], 2)

    def test_refresh_and_import_both_get_service(self):
        for pid in range(1, 31):
            self.player(pid, state='queued')
        self.player(100, viewed=self.now, synced=0)
        worker.schedule()
        self.assertIn(100, worker._queued)
        self.assertIn(1, worker._queued)

    def test_resolved_player_accepted_when_memory_queue_is_full(self):
        with patch.object(worker, '_queued', set(range(worker.MAX_PENDING))), \
             patch.object(web.ingest, 'resolve_gamertag', new=AsyncMock(return_value=('1000', 'Capacity Example'))), \
             patch.object(web, '_blocked', return_value=False):
            slug, _, error = web._resolve_new('Capacity Example', '')
        self.assertIsNone(error)
        p = db.q1("SELECT * FROM players WHERE slug=?", slug)
        self.assertEqual(p['sync_state'], 'queued')
        self.assertGreater(worker.position(p['id']), 0)

    def test_live_poll_renews_viewing_lease_without_duplicate_work(self):
        self.player(1, viewed=self.now-86400, synced=self.now)
        p = db.q1("SELECT * FROM players WHERE id=1")
        self.assertFalse(worker.stale(p, active=True))
        self.assertEqual(db.q1("SELECT last_view FROM players WHERE id=1")['last_view'], self.now)

    def test_followed_players_continue_hourly_without_viewer(self):
        self.player(1, synced=self.now-3601)
        with patch.object(worker, '_followed_names', return_value=({'load test 1'}, set())):
            self.assertEqual(worker.refresh_due(), [1])


if __name__ == '__main__':
    unittest.main()
