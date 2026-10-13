import sqlite3
import unittest
from unittest.mock import patch
import db
import activity_notify as notify


class ActivityNotifications(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(':memory:', isolation_level=None)
        self.conn.row_factory = sqlite3.Row
        p = patch.object(db, 'conn', return_value=self.conn)
        p.start();self.addCleanup(self.conn.close);self.addCleanup(p.stop)
        db.init()
        self.now = 10000
        p = patch.object(notify.time, 'time', side_effect=lambda: self.now)
        p.start();self.addCleanup(p.stop)
        p = patch.object(notify, 'settings', return_value={'enabled': True, 'url': 'http://notify.test/topic'})
        p.start();self.addCleanup(p.stop)
        p = patch.object(notify, 'deliver')
        self.send = p.start();self.addCleanup(p.stop)

    def add(self, pid):
        db.run("INSERT INTO players(id,xuid,gamertag,slug,created_at) VALUES(?,?,?,?,?)",
               pid, str(pid), 'Example '+str(pid), 'example-'+str(pid), self.now)

    def test_baseline_excludes_existing_and_repeat_views(self):
        self.add(1);notify.poll()
        self.now += 600
        db.run("UPDATE players SET views=views+1,last_view=?", self.now)
        notify.poll();self.send.assert_not_called()

    def test_batches_and_persists_without_repeat_notifications(self):
        notify.poll();self.now += 60
        self.add(1);self.add(2);notify.poll();self.send.assert_not_called()
        self.now += 241;notify.poll()
        self.send.assert_called_once_with('http://notify.test/topic', 2)
        self.now += 400;notify.poll();self.send.assert_called_once()
        self.add(3);notify.poll()
        self.assertEqual(self.send.call_count, 2)

    def test_delivery_failure_retries_later_without_losing_activity(self):
        notify.poll();self.now += 301;self.add(1)
        self.send.side_effect = RuntimeError('offline')
        with self.assertRaises(RuntimeError):notify.poll()
        self.now += 60;notify.poll();self.send.assert_called_once()
        self.now += 241;self.send.side_effect = None;notify.poll()
        self.assertEqual(self.send.call_count, 2)

    def test_disabled_does_nothing(self):
        with patch.object(notify, 'settings', return_value={}):
            notify.poll()
        self.assertIsNone(db.kv_get(notify.STATE_KEY));self.send.assert_not_called()
