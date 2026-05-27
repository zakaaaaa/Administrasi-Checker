"""
Test suite untuk SimilarityChecker (hasil uji similaritas ≤ 25%).

Cara jalankan:
    python3 -m unittest tests.test_similarity_checker -v

Catatan: test ini TIDAK menjalankan OCR (lambat/flaky). Ekstraksi angka diuji
via _extract_similarity_percent, dan logika ambang via monkeypatch _detect_percent.
"""

import unittest
from unittest.mock import MagicMock

from app.services.similarity_checker import (
    SimilarityChecker,
    _extract_similarity_percent,
)
from app.services.similarity_rules import get_pkm_kc_similarity_rules


# ============================================================================
# Ekstraksi persen dari teks OCR
# ============================================================================


class TestExtractPercent(unittest.TestCase):
    def test_turnitin_overview_format(self):
        # Persis output OCR nyata dari Picture 1.jpg
        text = ("turnitin Page 2 of 40 - Integrity Overview 20% Overall Similarity "
                "The combined total ... Top Sources 17% Internet sources 3% Publications "
                "12% Submitted works")
        self.assertEqual(_extract_similarity_percent(text), 20)

    def test_not_confused_by_top_sources(self):
        # Hanya angka Top Sources, tanpa 'Overall Similarity' → None
        text = "Top Sources 17% Internet sources 3% Publications 12% Submitted works"
        self.assertIsNone(_extract_similarity_percent(text))

    def test_overall_similarity_after_number_variant(self):
        self.assertEqual(_extract_similarity_percent("Overall Similarity: 30%"), 30)

    def test_similarity_index_variant(self):
        self.assertEqual(_extract_similarity_percent("Similarity Index 18%"), 18)

    def test_empty_or_garbage(self):
        self.assertIsNone(_extract_similarity_percent(""))
        self.assertIsNone(_extract_similarity_percent("tidak ada angka di sini"))

    def test_out_of_range_rejected(self):
        # 200% bukan angka similaritas valid
        self.assertIsNone(_extract_similarity_percent("999% Overall Similarity"))


# ============================================================================
# Logika ambang (25% lolos, 26% gagal)
# ============================================================================


def _checker_returning(percent):
    parser = MagicMock()
    chk = SimilarityChecker(parser, get_pkm_kc_similarity_rules())
    chk._detect_percent = lambda: percent
    return chk


class TestThreshold(unittest.TestCase):
    def test_24_pass(self):
        res = _checker_returning(24).check()
        self.assertEqual(res.status, "pass")

    def test_exactly_25_pass(self):
        """25% masih lolos (batas: > 25 baru gagal)."""
        res = _checker_returning(25).check()
        self.assertEqual(res.status, "pass")

    def test_26_fail(self):
        res = _checker_returning(26).check()
        self.assertEqual(res.status, "fail")
        self.assertTrue(any("melebihi" in m.text.lower() for m in res.messages))

    def test_high_fail(self):
        res = _checker_returning(80).check()
        self.assertEqual(res.status, "fail")

    def test_not_detected_warning(self):
        res = _checker_returning(None).check()
        self.assertEqual(res.status, "warning")
        self.assertTrue(any("tidak terdeteksi" in m.text.lower() for m in res.messages))

    def test_to_dict_serializable(self):
        d = _checker_returning(20).check().to_dict()
        self.assertIn("status", d)
        self.assertIn("messages", d)
        self.assertIsInstance(d["messages"], list)


# ============================================================================
# Default rules
# ============================================================================


class TestRules(unittest.TestCase):
    def test_pkm_kc_defaults(self):
        r = get_pkm_kc_similarity_rules()
        self.assertEqual(r.max_percent, 25)
        self.assertEqual(r.schema_label, "PKM-KC")


if __name__ == "__main__":
    unittest.main(verbosity=2)
