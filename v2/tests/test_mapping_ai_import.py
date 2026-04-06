from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.mapping import load_mapping


class MappingAiImportParseTest(unittest.TestCase):
    def test_rules_file_merged_next_to_yaml(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "rules").mkdir()
            (root / "rules" / "q.md").write_text("From file rule.", encoding="utf-8")
            yml = root / "m.yaml"
            yml.write_text(
                """
spreadsheet_id: "abc123"
tabs:
  - key: quote
    worksheet: "W"
    data_start_row: 2
    key_column_letter: "C"
    use_color_status: false
    color_status_map: {}
    status:
      mode: fixed
      value: pending_quote
      default: pending_quote
    trouble_case:
      column_letter: ""
      truthy: ["1"]
    ai_import_parse:
      enabled: true
      rules_text: "Inline."
      rules_file: rules/q.md
      scope: aggregated
""",
                encoding="utf-8",
            )
            m = load_mapping(yml)
            cfg = m.tabs[0].ai_import_parse
            self.assertIsNotNone(cfg)
            assert cfg is not None
            self.assertTrue(cfg.enabled)
            self.assertIn("Inline.", cfg.rules_resolved)
            self.assertIn("From file rule.", cfg.rules_resolved)


if __name__ == "__main__":
    unittest.main()
