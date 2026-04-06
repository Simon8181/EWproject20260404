from __future__ import annotations

import unittest

from app.note_def_extract import parse_def_notes


class NoteDefExtractTest(unittest.TestCase):
    def test_labels_broker_rate_mc(self) -> None:
        d = "Broker: ACME 物流"
        e = "Rate: $1,250"
        f = "MC: 884422"
        r = parse_def_notes(d, e, f)
        self.assertEqual(r["broker"], "ACME 物流")
        self.assertEqual(r["actual_driver_rate_raw"], "$1,250")
        self.assertEqual(r["carriers"], "884422")

    def test_labels_chinese_newlines(self) -> None:
        d = "经纪：顺丰跨境\n价格：3200\nMC：123456"
        r = parse_def_notes(d, "", "")
        self.assertIn("顺丰", r["broker"])
        self.assertIn("3200", r["actual_driver_rate_raw"])
        self.assertEqual(r["carriers"], "123456")

    def test_broker_3pl_rate(self) -> None:
        d = "Broker: XYZ"
        e = "3PL单号：WH-99201-A"
        f = "Rate: 900 USD"
        r = parse_def_notes(d, e, f)
        self.assertEqual(r["broker"], "XYZ")
        self.assertIn("900", r["actual_driver_rate_raw"])
        self.assertTrue(r["carriers"])

    def test_fallback_three_columns(self) -> None:
        r = parse_def_notes("BestBroker LLC", "1850", "MC 776655")
        self.assertEqual(r["broker"], "BestBroker LLC")
        self.assertEqual(r["actual_driver_rate_raw"], "1850")
        self.assertEqual(r["carriers"], "776655")

    def test_empty_notes(self) -> None:
        r = parse_def_notes("", "", "")
        self.assertEqual(r, {"broker": "", "actual_driver_rate_raw": "", "carriers": ""})


if __name__ == "__main__":
    unittest.main()
