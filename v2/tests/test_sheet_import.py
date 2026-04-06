from __future__ import annotations

import unittest

from app.sheet_import import _higher_priority_status


class SheetImportLogicTest(unittest.TestCase):
    def test_status_priority(self) -> None:
        self.assertEqual(_higher_priority_status("quote", "ordered"), "ordered")
        self.assertEqual(_higher_priority_status("picked", "ordered"), "picked")
        self.assertEqual(_higher_priority_status("complete", "cancel"), "cancel")

    def test_carrier_assigned_between_ready_to_pick_and_picked(self) -> None:
        self.assertEqual(
            _higher_priority_status("ready_to_pick", "carrier_assigned"),
            "carrier_assigned",
        )
        self.assertEqual(
            _higher_priority_status("carrier_assigned", "picked"),
            "picked",
        )
        self.assertEqual(
            _higher_priority_status("picked", "carrier_assigned"),
            "picked",
        )


if __name__ == "__main__":
    unittest.main()

