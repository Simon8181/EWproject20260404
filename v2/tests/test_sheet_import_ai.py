from __future__ import annotations

import unittest
from unittest.mock import patch

from app.mapping import (
    DEFAULT_AI_IMPORT_ALLOWLIST,
    AiImportParseConfig,
    LoadMapping,
    TabConfig,
)
from app.sheet_import import ImportStats, _apply_import_ai_to_aggregate


def _tab_quote_ai() -> TabConfig:
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
        color_status_map={"red": "ordered", "green": "carrier_assigned"},
        ai_import_parse=AiImportParseConfig(
            enabled=True,
            rules_resolved="H 列为货描",
            fields_allowlist=DEFAULT_AI_IMPORT_ALLOWLIST,
            scope="aggregated",
        ),
    )


class SheetImportAiMergeTest(unittest.TestCase):
    @patch("app.sheet_import.sheet_import_ai.parse_import_aggregated")
    @patch("app.sheet_import.gemini_api_key")
    @patch("app.sheet_import.sheet_import_ai.import_ai_globally_enabled")
    def test_fills_only_empty_allowlisted_fields(
        self, mock_glob: unittest.mock.MagicMock, mock_key: unittest.mock.MagicMock, mock_parse: unittest.mock.MagicMock
    ) -> None:
        mock_glob.return_value = True
        mock_key.return_value = "fake"
        mock_parse.return_value = (
            {
                "commodity_desc": "from AI",
                "pickup_eta": "should not apply",
            },
            None,
        )
        mapping = LoadMapping(spreadsheet_id="x", tabs=(_tab_quote_ai(),))
        aggregate = {
            "Q1": {
                "commodity_desc": "",
                "customer_name": "Acme",
                "source_tabs": {"quote"},
                "_import_ai_contexts": [
                    {"tab_key": "quote", "cells": {"H": "", "C": "Q1"}}
                ],
            }
        }
        stats = ImportStats()
        _apply_import_ai_to_aggregate(aggregate, mapping, stats)
        self.assertEqual(aggregate["Q1"]["commodity_desc"], "from AI")
        self.assertEqual(stats.ai_import_calls, 1)
        self.assertEqual(stats.ai_import_failures, 0)
        mock_parse.assert_called_once()

    @patch("app.sheet_import.sheet_import_ai.parse_import_aggregated")
    @patch("app.sheet_import.gemini_api_key")
    @patch("app.sheet_import.sheet_import_ai.import_ai_globally_enabled")
    def test_skips_when_deterministic_already_set(
        self, mock_glob: unittest.mock.MagicMock, mock_key: unittest.mock.MagicMock, mock_parse: unittest.mock.MagicMock
    ) -> None:
        mock_glob.return_value = True
        mock_key.return_value = "fake"
        mock_parse.return_value = ({"commodity_desc": "AI version"}, None)
        mapping = LoadMapping(spreadsheet_id="x", tabs=(_tab_quote_ai(),))
        aggregate = {
            "Q1": {
                "commodity_desc": "Sheet value",
                "source_tabs": {"quote"},
                "_import_ai_contexts": [{"tab_key": "quote", "cells": {}}],
            }
        }
        stats = ImportStats()
        _apply_import_ai_to_aggregate(aggregate, mapping, stats)
        self.assertEqual(aggregate["Q1"]["commodity_desc"], "Sheet value")

    @patch("app.sheet_import.sheet_import_ai.parse_import_aggregated")
    @patch("app.sheet_import.gemini_api_key")
    @patch("app.sheet_import.sheet_import_ai.import_ai_globally_enabled")
    def test_failure_increments_failures(
        self, mock_glob: unittest.mock.MagicMock, mock_key: unittest.mock.MagicMock, mock_parse: unittest.mock.MagicMock
    ) -> None:
        mock_glob.return_value = True
        mock_key.return_value = "fake"
        mock_parse.return_value = ({}, "AI_BAD_JSON")
        mapping = LoadMapping(spreadsheet_id="x", tabs=(_tab_quote_ai(),))
        aggregate = {
            "Q1": {
                "commodity_desc": "",
                "source_tabs": {"quote"},
                "_import_ai_contexts": [{"tab_key": "quote", "cells": {}}],
            }
        }
        stats = ImportStats()
        _apply_import_ai_to_aggregate(aggregate, mapping, stats)
        self.assertEqual(stats.ai_import_calls, 1)
        self.assertEqual(stats.ai_import_failures, 1)
        self.assertEqual(aggregate["Q1"]["commodity_desc"], "")


if __name__ == "__main__":
    unittest.main()
