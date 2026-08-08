# =====================================================
# tests/test_position_tracker.py
# Unit/Integration tests for PositionTracker
# =====================================================

import sys
import unittest
from datetime import datetime

from mt5_client.position_tracker.models import (
    TrackedPosition,
    PositionOrigin,
    PositionSnapshot,
    ClosedManualSummary,
)
from mt5_client.position_tracker.tracker import PositionTracker


class TestPositionTracker(unittest.TestCase):

    def setUp(self):
        self.tracker = PositionTracker()
        self.tracker._system_tickets.clear()
        self.tracker._prev_snapshot.clear()
        self.tracker._closed_manual.clear()

    def test_singleton(self):
        t1 = PositionTracker()
        t2 = PositionTracker()
        self.assertIs(t1, t2)

    def test_register_system_ticket(self):
        self.tracker.register_system_ticket(
            symbol="XAUUSD",
            ticket=12345,
            strategy="RCS",
            magic=901001,
            direction="BUY",
            volume=0.01,
            open_price=2000.0,
        )
        self.assertIn(12345, self.tracker._system_tickets)
        self.assertIn(901001, self.tracker._known_magics)
        tracked = self.tracker._system_tickets[12345]
        self.assertEqual(tracked.origin, PositionOrigin.SYSTEM)
        self.assertEqual(tracked.strategy, "RCS")

    def test_classify_manual_vs_system(self):
        # Setup mock MT5 position object
        class MockPosition:
            def __init__(self, ticket, symbol, magic, ptype, volume, price_open, profit, swap, comment=""):
                self.ticket = ticket
                self.symbol = symbol
                self.magic = magic
                self.type = ptype
                self.volume = volume
                self.price_open = price_open
                self.profit = profit
                self.swap = swap
                self.time = int(datetime.now().timestamp())
                self.comment = comment

        # Registered system position
        self.tracker.register_system_ticket("XAUUSD", 100, "RCS", 901001)
        pos_sys = MockPosition(100, "XAUUSD", 901001, 0, 0.01, 2000.0, 10.0, 0.0)

        # Manual position (magic 0)
        pos_man = MockPosition(200, "XAUUSD", 0, 1, 0.05, 2005.0, -5.0, -0.5)

        t_sys = self.tracker._classify_position(pos_sys)
        t_man = self.tracker._classify_position(pos_man)

        self.assertEqual(t_sys.origin, PositionOrigin.SYSTEM)
        self.assertEqual(t_man.origin, PositionOrigin.MANUAL)
        self.assertEqual(t_man.strategy, "UNKNOWN")
        self.assertEqual(t_man.direction, "SELL")

    def test_net_profit_calculation(self):
        pos = TrackedPosition(
            ticket=1,
            symbol="XAUUSD",
            direction="BUY",
            volume=0.01,
            open_price=2000.0,
            open_time=datetime.now(),
            magic_number=0,
            comment="",
            origin=PositionOrigin.MANUAL,
            strategy="UNKNOWN",
            current_profit=15.0,
            current_swap=-1.5,
            current_commission=-0.5,
        )
        self.assertAlmostEqual(pos.net_profit, 13.0)

        pos.is_closed = True
        pos.close_profit = 20.0
        pos.close_swap = -1.5
        pos.close_commission = -0.5
        self.assertAlmostEqual(pos.net_profit, 18.0)


if __name__ == "__main__":
    unittest.main()
