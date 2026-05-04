"""
Test suite untuk PageNumberingChecker.

Cara jalankan:
    python3 -m unittest tests.test_page_numbering_checker -v
"""

import unittest
from pathlib import Path

from app.services.docx_parser import DocxParser
from app.services.page_numbering_checker import (
    PageNumberingChecker,
    PageNumberingRules,
    ZoneRule,
    HeaderFooterAnalysis,
    SectionPageNumberingAnalysis,
    ZoneFinding,
    get_pkm_page_numbering_rules,
)
from app.services.schema_rules import get_pkm_kc_proposal_rules

SAMPLE_DIR = Path(__file__).parent / "sample_docs"
DUMMY_FILE = SAMPLE_DIR / "dummy_pkm_kc.docx"
REAL_FILE = SAMPLE_DIR / "A410170082.docx"


# ============================================================================
# Test: rule construction
# ============================================================================


class TestPageNumberingRules(unittest.TestCase):
    def test_default_rules(self):
        r = get_pkm_page_numbering_rules()
        self.assertEqual(r.front_matter.numeral_type, "roman_lower")
        self.assertEqual(r.front_matter.position, "bottom")
        self.assertEqual(r.front_matter.alignment, "right")
        self.assertEqual(r.front_matter.font_name, "Times New Roman")
        self.assertEqual(r.front_matter.font_size_pt, 12.0)
        self.assertEqual(r.core_matter.numeral_type, "arabic")
        self.assertEqual(r.core_matter.position, "top")


# ============================================================================
# Test: PageNumberingChecker pada DUMMY
# ============================================================================


class TestCheckerOnDummy(unittest.TestCase):
    """
    Dummy yang kita generate TIDAK punya header/footer dengan PAGE field.
    Itu sebabnya kita expect status FAIL dengan finding 'missing' di kedua zona.
    """

    @classmethod
    def setUpClass(cls):
        if not DUMMY_FILE.exists():
            raise unittest.SkipTest("Dummy belum di-generate")
        cls.parser = DocxParser(DUMMY_FILE)
        cls.schema = get_pkm_kc_proposal_rules()
        cls.result = PageNumberingChecker(cls.parser, cls.schema).check()

    def test_returns_result(self):
        self.assertIsNotNone(self.result)
        self.assertIn(self.result.status, ["pass", "warning", "fail"])

    def test_section_analysis_populated(self):
        """Analyses untuk semua section harus ada."""
        self.assertEqual(
            len(self.result.sections_analysis),
            len(self.parser.sections),
        )

    def test_dummy_no_page_numbers_fails(self):
        """
        Dummy tidak punya nomor halaman → harus FAIL dengan finding 'missing'.
        """
        self.assertEqual(self.result.status, "fail")
        missing = [f for f in self.result.findings if f.aspect == "missing"]
        self.assertGreater(len(missing), 0)

    def test_to_dict_serializable(self):
        d = self.result.to_dict()
        self.assertIn("status", d)
        self.assertIn("front_matter", d)
        self.assertIn("core_matter", d)
        self.assertIn("sections_analysis", d)
        self.assertIn("findings", d)


# ============================================================================
# Test: PageNumberingChecker pada DOKUMEN REAL
# ============================================================================


class TestCheckerOnRealDoc(unittest.TestCase):
    """
    Dokumen real `A410170082.docx`:
    - Header XMLs: 6 buah, 2 punya PAGE field (header1, header6) di section #5 dan #27
    - Footer: TIDAK ADA → zona awal (front_matter) wajib pakai footer-bottom,
      tapi dokumen ini tidak punya footer → FAIL 'missing' untuk front_matter
    - Header punya page field tapi:
      * Size 10pt (sz=20 half-points), seharusnya 12pt → FAIL font
      * Tidak ada <w:jc>, default left → FAIL alignment (seharusnya right)
    """

    @classmethod
    def setUpClass(cls):
        if not REAL_FILE.exists():
            raise unittest.SkipTest(f"{REAL_FILE.name} tidak ada")
        cls.parser = DocxParser(REAL_FILE)
        cls.schema = get_pkm_kc_proposal_rules()
        cls.result = PageNumberingChecker(cls.parser, cls.schema).check()

    def test_overall_fail(self):
        self.assertEqual(self.result.status, "fail")

    def test_front_matter_missing(self):
        """
        Dokumen real TIDAK punya footer sama sekali → zona awal (yang
        seharusnya pakai footer untuk romawi pojok kanan bawah) = missing.
        """
        front_findings = [
            f for f in self.result.findings if f.zone == "front_matter"
        ]
        # Minimal ada 1 finding 'missing' untuk front_matter
        missing = [f for f in front_findings if f.aspect == "missing"]
        self.assertGreater(len(missing), 0,
            f"Front matter findings: {[(f.aspect, f.message) for f in front_findings]}")

    def test_core_matter_font_size_wrong(self):
        """
        Header dokumen real pakai sz=20 (= 10pt), seharusnya 12pt.
        Harus terdeteksi di zona core.
        """
        core_findings = [
            f for f in self.result.findings if f.zone == "core_matter"
        ]
        font_findings = [f for f in core_findings if f.aspect == "font"]
        self.assertGreater(len(font_findings), 0,
            f"Tidak ada finding font di core. All core findings: "
            f"{[(f.aspect, f.message) for f in core_findings]}")
        # Salah satu finding font harus tentang ukuran 10pt vs 12pt
        size_complaints = [f for f in font_findings if f.found and "10" in str(f.found)]
        self.assertGreater(len(size_complaints), 0,
            f"Tidak ada finding tentang size 10pt. Font findings: "
            f"{[(f.expected, f.found) for f in font_findings]}")

    def test_core_matter_alignment_wrong(self):
        """
        Header dokumen real tidak ada <w:jc> → default 'left'.
        Seharusnya 'right'. Harus terdeteksi.
        """
        core_findings = [
            f for f in self.result.findings if f.zone == "core_matter"
        ]
        align_findings = [f for f in core_findings if f.aspect == "alignment"]
        self.assertGreater(len(align_findings), 0,
            f"Tidak ada finding alignment di core. All findings: "
            f"{[(f.aspect, f.message) for f in core_findings]}")

    def test_some_section_detected_as_core(self):
        """Minimal 1 section harus diidentifikasi sebagai core_matter."""
        core_secs = [
            a for a in self.result.sections_analysis if a.zone == "core_matter"
        ]
        self.assertGreater(len(core_secs), 0)


# ============================================================================
# Test: synthetic — validasi logic _validate_section_against_zone
# ============================================================================


class TestValidationLogic(unittest.TestCase):
    """Test logic validasi pakai analysis buatan (tidak butuh .docx)."""

    def _make_checker(self):
        # Bypass __init__: kita tidak butuh parser asli untuk test logic ini
        c = PageNumberingChecker.__new__(PageNumberingChecker)
        c.rules = get_pkm_page_numbering_rules()
        return c

    def test_perfect_core_section_passes(self):
        c = self._make_checker()
        analysis = SectionPageNumberingAnalysis(
            section_index=5,
            zone="core_matter",
            has_header_with_page=True,
            actual_position="top",
            actual_numeral_type="arabic",
            actual_alignment="right",
            actual_font_name="Times New Roman",
            actual_font_size_pt=12.0,
        )
        findings = c._validate_section_against_zone(analysis, c.rules.core_matter)
        self.assertEqual(len(findings), 0)

    def test_wrong_numeral_flagged(self):
        c = self._make_checker()
        analysis = SectionPageNumberingAnalysis(
            section_index=5,
            zone="core_matter",
            has_header_with_page=True,
            actual_position="top",
            actual_numeral_type="roman_lower",  # SALAH — seharusnya arabic
            actual_alignment="right",
            actual_font_name="Times New Roman",
            actual_font_size_pt=12.0,
        )
        findings = c._validate_section_against_zone(analysis, c.rules.core_matter)
        numeral_findings = [f for f in findings if f.aspect == "numeral"]
        self.assertEqual(len(numeral_findings), 1)
        self.assertEqual(numeral_findings[0].severity, "fail")

    def test_wrong_position_flagged(self):
        c = self._make_checker()
        analysis = SectionPageNumberingAnalysis(
            section_index=2,
            zone="front_matter",
            has_header_with_page=True,
            actual_position="top",  # SALAH — front matter seharusnya bottom
            actual_numeral_type="roman_lower",
            actual_alignment="right",
            actual_font_name="Times New Roman",
            actual_font_size_pt=12.0,
        )
        findings = c._validate_section_against_zone(analysis, c.rules.front_matter)
        pos_findings = [f for f in findings if f.aspect == "position"]
        self.assertEqual(len(pos_findings), 1)

    def test_wrong_font_size_flagged(self):
        c = self._make_checker()
        analysis = SectionPageNumberingAnalysis(
            section_index=5,
            zone="core_matter",
            has_header_with_page=True,
            actual_position="top",
            actual_numeral_type="arabic",
            actual_alignment="right",
            actual_font_name="Times New Roman",
            actual_font_size_pt=10.0,  # SALAH — seharusnya 12
        )
        findings = c._validate_section_against_zone(analysis, c.rules.core_matter)
        font_findings = [f for f in findings if f.aspect == "font"]
        self.assertEqual(len(font_findings), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)