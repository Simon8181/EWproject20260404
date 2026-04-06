from __future__ import annotations

import unittest
from unittest.mock import patch

from app.party_ai import AiPartyResult, extract_parties_with_gemini, resolve_party_info


class PartyAiResolveTest(unittest.TestCase):
    def test_resolve_uses_ai_when_ok(self) -> None:
        def fake(
            _sf_raw: str,
            _st_raw: str,
            _sf_out: str,
            _st_out: str,
            _cc: str,
        ) -> AiPartyResult:
            return AiPartyResult(
                True,
                "Ship Name | 5551112222",
                "Recv Co | Jane",
                0.88,
                "",
                None,
            )

        with patch("app.party_ai.extract_parties_with_gemini", fake):
            s, c = resolve_party_info(
                ship_from_raw="x",
                ship_to_raw="y",
                ship_from_out="o1",
                ship_to_out="o2",
                consignee_contact="",
            )
        self.assertEqual(s, "Ship Name | 5551112222")
        self.assertEqual(c, "Recv Co | Jane")

    def test_resolve_falls_back_when_ai_not_ok(self) -> None:
        def fake(
            _a: str,
            _b: str,
            _c: str,
            _d: str,
            _e: str,
        ) -> AiPartyResult:
            return AiPartyResult(False, "", "", 0.0, "", "PARTY_AI_BAD_JSON")

        raw = "David R,+1-6312522866, suite 10 545 Johnson ave,Bohemia,New York,11716"
        with patch("app.party_ai.extract_parties_with_gemini", fake):
            s, c = resolve_party_info(
                ship_from_raw=raw,
                ship_to_raw=raw,
                ship_from_out=raw,
                ship_to_out=raw,
                consignee_contact="",
            )
        self.assertIn("David", s)
        self.assertTrue(
            "6312522866" in s.replace("-", "").replace(" ", "") or "631" in s
        )
        self.assertIn("David", c)


class PartyAiGeminiParseTest(unittest.TestCase):
    def test_extract_disabled_short_circuits(self) -> None:
        with patch.dict("os.environ", {"AI_PARTY_EXTRACT_ENABLED": "0"}, clear=False):
            r = extract_parties_with_gemini("a", "b", "c", "d", "e")
        self.assertFalse(r.ok)
        self.assertEqual(r.error_message, "PARTY_AI_DISABLED")


if __name__ == "__main__":
    unittest.main()
