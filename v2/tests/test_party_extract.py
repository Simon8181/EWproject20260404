from __future__ import annotations

import unittest

from app.party_extract import extract_consignee_info, extract_shipper_info


class PartyExtractTest(unittest.TestCase):
    def test_shipper_mostly_address_empty_or_minimal(self) -> None:
        self.assertEqual(extract_shipper_info("CA 90058"), "")
        self.assertEqual(
            extract_shipper_info("8 TAYLOR RD STE 1 Edison, NJ 08817"), ""
        )

    def test_consignee_chinese_labels_and_phone(self) -> None:
        raw = """公司名称 Joseph Nkrumah 收件人: Joseph Nkrumah
 派送地址：15 PRIDDAE SHIPPING WAREHOUSE
 150 PARK AVENUE
 EAST HARTFORD CT 06108 USA"""
        s = extract_consignee_info(raw, "")
        self.assertTrue("Joseph Nkrumah" in s)
        self.assertTrue("公司名称" in s or "Joseph" in s)

    def test_consignee_comma_name_phone_us(self) -> None:
        raw = "David R,+1-6312522866, suite 10 545 Johnson ave,Bohemia,New York,11716"
        s = extract_consignee_info(raw, "")
        self.assertTrue(
            "6312522866" in s.replace("-", "").replace(" ", "") or "631" in s
        )
        self.assertIn("David", s)


if __name__ == "__main__":
    unittest.main()
