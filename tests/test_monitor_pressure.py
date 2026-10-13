import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('ops_monitor', Path(__file__).resolve().parents[1]/'ops'/'monitor.py')
monitor = importlib.util.module_from_spec(spec)
spec.loader.exec_module(monitor)


class QueuePressureTests(unittest.TestCase):
    def test_flapping_never_alerts(self):
        p=monitor.QueuePressure()
        for n in range(10):
            self.assertFalse(p.due(True,n*300))
            self.assertFalse(p.due(True,n*300+120))
            self.assertFalse(p.due(False,n*300+180))

    def test_sustained_pressure_and_hourly_cooldown(self):
        p=monitor.QueuePressure()
        self.assertFalse(p.due(True,0))
        self.assertFalse(p.due(True,599))
        self.assertTrue(p.due(True,600))
        p.sent_at=600
        self.assertFalse(p.due(True,4199))
        self.assertTrue(p.due(True,4200))

    def test_recurrence_does_not_reset_cooldown(self):
        p=monitor.QueuePressure()
        p.due(True,0);p.sent_at=600
        self.assertFalse(p.due(False,700))
        self.assertFalse(p.due(True,800))
        self.assertFalse(p.due(True,1400))

    def test_failed_delivery_remains_retryable(self):
        p=monitor.QueuePressure()
        p.due(True,0)
        self.assertTrue(p.due(True,600))
        self.assertTrue(p.due(True,630))
