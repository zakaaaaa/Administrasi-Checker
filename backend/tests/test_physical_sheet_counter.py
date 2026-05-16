"""
Test suite untuk PhysicalSheetCounter.

Cara jalankan:
    python3 -m unittest tests.test_physical_sheet_counter -v

Catatan: test ini butuh LibreOffice terinstal di system. Kalau tidak ada,
test yang butuh konversi akan di-skip (bukan fail).
"""

import shutil
import unittest
from pathlib import Path

from app.services.checkers.physical_sheet_counter import (
    PhysicalSheetCounter,
    SheetPageNumber,
    PageNumberAnomaly,
    _extract_page_number_from_text,
    _roman_to_int,
    get_sheet_count_rule,
)
from app.services.core.base_rules import SchemaRules
from app.services.core.docx_parser import DocxParser
from app.services.core.pdf_converter import PdfConverter, PdfConversionError
from app.services.schemas.pkm_kc.rules import get_pkm_kc_proposal_rules

SAMPLE_DIR = Path(__file__).parent / "sample_docs"
DUMMY_FILE = SAMPLE_DIR / "dummy_pkm_kc.docx"
REAL_FILE = SAMPLE_DIR / "A410170082.docx"


def _libreoffice_available() -> bool:
    try:
        PdfConverter()
        return True
    except PdfConversionError:
        return False


# ============================================================================
# Test: helper extract_page_number_from_text
# ============================================================================


class TestExtractPageNumber(unittest.TestCase):
    def test_arabic_at_start(self):
        raw, val, roman, arabic = _extract_page_number_from_text("5\nBAB 3. ...")
        self.assertEqual(raw, "5")
        self.assertEqual(val, 5)
        self.assertTrue(arabic)
        self.assertFalse(roman)

    def test_roman_at_start(self):
        raw, val, roman, arabic = _extract_page_number_from_text("iii\nDAFTAR ISI")
        self.assertEqual(raw, "iii")
        self.assertEqual(val, 3)
        self.assertTrue(roman)
        self.assertFalse(arabic)

    def test_arabic_at_end(self):
        raw, val, _, arabic = _extract_page_number_from_text("text body...\n7")
        self.assertEqual(val, 7)
        self.assertTrue(arabic)

    def test_no_page_number(self):
        raw, val, _, _ = _extract_page_number_from_text("text body without number")
        self.assertIsNone(raw)
        self.assertIsNone(val)

    def test_empty(self):
        raw, val, _, _ = _extract_page_number_from_text("")
        self.assertIsNone(raw)
        self.assertIsNone(val)

    def test_long_token_not_misread_as_roman(self):
        """'document' bukan romawi, harus None."""
        raw, val, _, _ = _extract_page_number_from_text("document")
        self.assertIsNone(val)


class TestRomanToInt(unittest.TestCase):
    def test_basic(self):
        self.assertEqual(_roman_to_int("i"), 1)
        self.assertEqual(_roman_to_int("ii"), 2)
        self.assertEqual(_roman_to_int("iv"), 4)
        self.assertEqual(_roman_to_int("ix"), 9)
        self.assertEqual(_roman_to_int("xiv"), 14)

    def test_invalid(self):
        self.assertIsNone(_roman_to_int("xyz"))
        self.assertIsNone(_roman_to_int(""))


# ============================================================================
# Test: schema rule lookup
# ============================================================================


class TestSheetCountRule(unittest.TestCase):
    def test_pkm_kc_max_10(self):
        rules = get_pkm_kc_proposal_rules()
        min_s, max_s = get_sheet_count_rule(rules)
        self.assertIsNone(min_s)
        self.assertEqual(max_s, 10)

    def test_pkm_gft_8_to_15(self):
        gft = SchemaRules(
            competition_code="PKM", schema_code="GFT",
            report_type_code="PROPOSAL", schema_name="GFT",
        )
        min_s, max_s = get_sheet_count_rule(gft)
        self.assertEqual(min_s, 8)
        self.assertEqual(max_s, 15)

    def test_unknown_schema_default(self):
        unknown = SchemaRules(
            competition_code="P2MW", schema_code="X",
            report_type_code="X", schema_name="X",
        )
        min_s, max_s = get_sheet_count_rule(unknown)
        self.assertIsNone(min_s)
        self.assertEqual(max_s, 10)


# ============================================================================
# Test: PdfConverter (butuh LibreOffice)
# ============================================================================


@unittest.skipUnless(_libreoffice_available(), "LibreOffice tidak terinstal")
class TestPdfConverter(unittest.TestCase):
    def test_convert_dummy(self):
        conv = PdfConverter()
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            pdf = conv.convert(DUMMY_FILE, output_dir=tmp)
            self.assertTrue(pdf.exists())
            self.assertEqual(pdf.suffix, ".pdf")
            self.assertGreater(pdf.stat().st_size, 0)

    def test_file_not_found(self):
        conv = PdfConverter()
        with self.assertRaises(FileNotFoundError):
            conv.convert("/path/yang/tidak/ada.docx")


class TestPdfConverterWithoutLibreOffice(unittest.TestCase):
    """Test fallback path tanpa LibreOffice."""

    def test_explicit_invalid_soffice_raises(self):
        """Kalau soffice_path eksplisit invalid, harus error informatif."""
        conv = PdfConverter(soffice_path="/path/yang/tidak/ada/soffice")
        with self.assertRaises(PdfConversionError):
            conv.convert(DUMMY_FILE, output_dir="/tmp")


# ============================================================================
# Test: PhysicalSheetCounter pada DUMMY (compliant: <10 lembar inti)
# ============================================================================


@unittest.skipUnless(_libreoffice_available(), "LibreOffice tidak terinstal")
class TestCounterOnDummy(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not DUMMY_FILE.exists():
            raise unittest.SkipTest("Dummy belum di-generate")
        cls.parser = DocxParser(DUMMY_FILE)
        cls.rules = get_pkm_kc_proposal_rules()
        cls.counter = PhysicalSheetCounter(cls.parser, cls.rules)
        cls.result = cls.counter.check()

    def test_pdf_conversion_succeeded(self):
        """Total lembar > 0 berarti konversi sukses."""
        self.assertGreater(self.result.total_physical_sheets, 0)

    def test_core_range_identified(self):
        """BAB 1 harus ke-detect di teks PDF."""
        self.assertIsNotNone(self.result.core_first_sheet)
        self.assertIsNotNone(self.result.core_last_sheet)
        self.assertGreaterEqual(self.result.core_physical_sheets, 1)

    def test_dummy_under_10_sheets_inti(self):
        """Dummy kecil — bagian inti pasti < 10 lembar (max PKM-KC)."""
        self.assertLessEqual(self.result.core_physical_sheets, 10)

    def test_to_dict_serializable(self):
        d = self.result.to_dict()
        self.assertIn("status", d)
        self.assertIn("total_physical_sheets", d)
        self.assertIn("page_numbering_issues", d)
        self.assertIn("messages", d)


# ============================================================================
# Test: PhysicalSheetCounter pada DOKUMEN REAL
# ============================================================================


@unittest.skipUnless(_libreoffice_available(), "LibreOffice tidak terinstal")
class TestCounterOnRealDoc(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not REAL_FILE.exists():
            raise unittest.SkipTest(f"Sampel real {REAL_FILE.name} tidak ada")
        cls.parser = DocxParser(REAL_FILE)
        cls.rules = get_pkm_kc_proposal_rules()
        cls.counter = PhysicalSheetCounter(cls.parser, cls.rules)
        cls.result = cls.counter.check()

    def test_total_sheets_27(self):
        """Berdasarkan inspeksi sebelumnya, dokumen real = 27 lembar."""
        self.assertEqual(self.result.total_physical_sheets, 27)

    def test_core_starts_at_sheet_6(self):
        """BAB 1 mulai di sheet #6 berdasarkan inspeksi."""
        self.assertEqual(self.result.core_first_sheet, 6)

    def test_core_count_exceeds_pkm_kc_limit(self):
        """
        Bagian inti (#6 sampai #27) = 22 lembar — jauh di atas batas 10
        untuk PKM-KC. Harus FAIL.
        """
        self.assertGreater(self.result.core_physical_sheets, 10)
        self.assertEqual(self.result.status, "fail")

    def test_detects_skipped_page_number(self):
        """
        Berdasarkan inspeksi: nomor halaman 5 → langsung ke 7 (skip 6).
        Harus terdeteksi sebagai 'skipped'.
        """
        skipped = [a for a in self.result.anomalies if a.type == "skipped"]
        # Minimal 1 skip terdeteksi (5→7 di sheet #11)
        self.assertGreater(len(skipped), 0,
            f"Tidak ada skipped detected. Anomalies: {self.result.anomalies}"
        )

    def test_detects_big_jump_page_14_to_19(self):
        """
        Nomor halaman 14 → langsung ke 19 (gap 5) — harus terdeteksi sebagai
        skipped dengan severity='fail' (gap >= 3).
        """
        big_skips = [
            a for a in self.result.anomalies
            if a.type == "skipped" and a.detail.get("gap", 0) >= 3
        ]
        self.assertGreater(len(big_skips), 0)


# ============================================================================
# Test: deteksi anomali pakai input synthetic (tidak butuh LibreOffice)
# ============================================================================


class TestAnomalyDetectionSynthetic(unittest.TestCase):
    """
    Test logic _detect_anomalies dengan input synthetic — tidak butuh PDF.
    Kita panggil method privat lewat instance dummy.
    """

    def _make_counter(self):
        # Bypass __init__ yang butuh PdfConverter
        c = PhysicalSheetCounter.__new__(PhysicalSheetCounter)
        c.rules = get_pkm_kc_proposal_rules()
        return c

    def _make_pages(self, page_values: list) -> list:
        """Helper: page_values = [1, 2, None, 5] → list of SheetPageNumber."""
        result = []
        for i, v in enumerate(page_values):
            result.append(
                SheetPageNumber(
                    sheet_index=i + 1,
                    page_num_text=str(v) if v is not None else None,
                    page_num_value=v,
                    is_arabic=v is not None,
                )
            )
        return result

    def test_no_anomaly_consecutive(self):
        c = self._make_counter()
        pages = self._make_pages([1, 2, 3, 4, 5])
        anomalies = c._detect_anomalies(pages, core_first=1, core_last=5)
        self.assertEqual(len(anomalies), 0)

    def test_duplicate_detected(self):
        c = self._make_counter()
        pages = self._make_pages([1, 2, 2, 3])
        anomalies = c._detect_anomalies(pages, core_first=1, core_last=4)
        dups = [a for a in anomalies if a.type == "duplicate"]
        self.assertEqual(len(dups), 1)
        self.assertEqual(dups[0].detail["number"], "2")
        self.assertEqual(dups[0].detail["found_on_sheets"], [2, 3])

    def test_skipped_small_gap_warning(self):
        c = self._make_counter()
        pages = self._make_pages([1, 2, 4, 5])  # skip 3 (gap=1) → warning
        anomalies = c._detect_anomalies(pages, core_first=1, core_last=4)
        skipped = [a for a in anomalies if a.type == "skipped"]
        self.assertEqual(len(skipped), 1)
        self.assertEqual(skipped[0].severity, "warning")

    def test_skipped_big_gap_fail(self):
        c = self._make_counter()
        pages = self._make_pages([1, 2, 8, 9])  # skip 5 nomor → fail
        anomalies = c._detect_anomalies(pages, core_first=1, core_last=4)
        skipped = [a for a in anomalies if a.type == "skipped"]
        self.assertEqual(len(skipped), 1)
        self.assertEqual(skipped[0].severity, "fail")

    def test_out_of_order_detected(self):
        c = self._make_counter()
        pages = self._make_pages([1, 2, 5, 3, 4])  # 5 → 3 = mundur
        anomalies = c._detect_anomalies(pages, core_first=1, core_last=5)
        ooo = [a for a in anomalies if a.type == "out_of_order"]
        self.assertEqual(len(ooo), 1)

    def test_missing_detected(self):
        c = self._make_counter()
        pages = self._make_pages([1, 2, None, 4])
        anomalies = c._detect_anomalies(pages, core_first=1, core_last=4)
        missing = [a for a in anomalies if a.type == "missing"]
        self.assertEqual(len(missing), 1)
        self.assertEqual(missing[0].detail["sheet_index"], 3)


if __name__ == "__main__":
    unittest.main(verbosity=2)