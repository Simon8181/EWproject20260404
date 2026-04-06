from __future__ import annotations

import unittest

from app.debug_web import _normalize_order_load_state, _order_load_state_status_filter


class DebugWebOrderFilterTest(unittest.TestCase):
    def test_filter_all_none(self) -> None:
        self.assertIsNone(_order_load_state_status_filter(None))
        self.assertIsNone(_order_load_state_status_filter(""))
        self.assertIsNone(_order_load_state_status_filter("all"))
        self.assertIsNone(_order_load_state_status_filter(" ALL "))

    def test_filter_waiting(self) -> None:
        frag = _order_load_state_status_filter("waiting")
        self.assertEqual(frag, ("status = ?", ("ordered",)))

    def test_filter_found(self) -> None:
        frag = _order_load_state_status_filter("found")
        self.assertEqual(frag, ("status = ?", ("carrier_assigned",)))

    def test_filter_transit(self) -> None:
        frag = _order_load_state_status_filter("transit")
        self.assertEqual(frag, ("status = ?", ("picked",)))

    def test_filter_unknown_none(self) -> None:
        self.assertIsNone(_order_load_state_status_filter("unknown"))


class DebugWebNormalizeLoadStateTest(unittest.TestCase):
    def test_normalize(self) -> None:
        self.assertIsNone(_normalize_order_load_state(None))
        self.assertIsNone(_normalize_order_load_state(""))
        self.assertIsNone(_normalize_order_load_state("all"))
        self.assertEqual(_normalize_order_load_state("waiting"), "waiting")
        self.assertEqual(_normalize_order_load_state(" FOUND "), "found")
        self.assertEqual(_normalize_order_load_state("transit"), "transit")


if __name__ == "__main__":
    unittest.main()

