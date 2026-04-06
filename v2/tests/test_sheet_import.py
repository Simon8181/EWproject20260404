from __future__ import annotations

import unittest

from app.mapping import TabConfig
from app.sheet_import import _compute_row_status, _higher_priority_status


def _quote_tab() -> TabConfig:
    return TabConfig(
        key="quote",
        worksheet="报价 quote",
        data_start_row=2,
        key_column_letter="C",
        status_mode="fixed",
        status_value="pending_quote",
        status_column_letter=None,
        status_map={},
        status_default="pending_quote",
        trouble_column_letter=None,
        trouble_truthy=("1", "true", "yes", "y"),
        use_color_status=True,
        color_status_map={
            "red": "ordered",
            "green": "carrier_assigned",
        },
        ai_import_parse=None,
    )


def _order_tab() -> TabConfig:
    return TabConfig(
        key="order",
        worksheet="order",
        data_start_row=2,
        key_column_letter="C",
        status_mode="fixed",
        status_value="ordered",
        status_column_letter=None,
        status_map={},
        status_default="ordered",
        trouble_column_letter=None,
        trouble_truthy=("1", "true", "yes", "y"),
        use_color_status=True,
        color_status_map={
            "red": "ordered",
            "green": "carrier_assigned",
        },
        ai_import_parse=None,
    )


class SheetImportLogicTest(unittest.TestCase):
    def test_status_priority(self) -> None:
        self.assertEqual(_higher_priority_status("pending_quote", "ordered"), "ordered")
        self.assertEqual(_higher_priority_status("picked", "ordered"), "picked")
        self.assertEqual(_higher_priority_status("complete", "cancel"), "cancel")

    def test_carrier_assigned_between_ready_to_pick_and_picked(self) -> None:
        self.assertEqual(
            _higher_priority_status("ready_to_pick", "carrier_assigned"),
            "ready_to_pick",
        )
        self.assertEqual(
            _higher_priority_status("carrier_assigned", "picked"),
            "picked",
        )
        self.assertEqual(
            _higher_priority_status("picked", "carrier_assigned"),
            "picked",
        )
        self.assertEqual(
            _higher_priority_status("ordered", "carrier_assigned"),
            "carrier_assigned",
        )

    def test_quote_no_color_pending_vs_quoted(self) -> None:
        t = _quote_tab()
        self.assertEqual(
            _compute_row_status(
                t, {"C": "x", "P": "", "U": "", "_A_COLOR": "", "A": ""}
            ),
            "pending_quote",
        )
        self.assertEqual(
            _compute_row_status(
                t, {"C": "x", "P": "100", "U": "", "_A_COLOR": "", "A": ""}
            ),
            "quoted",
        )
        self.assertEqual(
            _compute_row_status(
                t, {"C": "x", "P": "", "U": "200", "_A_COLOR": "", "A": ""}
            ),
            "quoted",
        )

    def test_quote_red_green_colors(self) -> None:
        t = _quote_tab()
        self.assertEqual(
            _compute_row_status(
                t, {"C": "x", "P": "", "U": "", "_A_COLOR": "red", "A": ""}
            ),
            "ordered",
        )
        self.assertEqual(
            _compute_row_status(
                t, {"C": "x", "P": "", "U": "", "_A_COLOR": "green", "A": ""}
            ),
            "carrier_assigned",
        )

    def test_order_green_carrier_assigned(self) -> None:
        t = _order_tab()
        self.assertEqual(
            _compute_row_status(
                t, {"C": "x", "P": "", "U": "", "_A_COLOR": "green", "A": ""}
            ),
            "carrier_assigned",
        )


if __name__ == "__main__":
    unittest.main()

