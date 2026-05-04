"""
Test suite untuk StructureChecker.

Cara jalankan:
    python3 -m unittest tests.test_structure_checker -v
"""

import unittest
from pathlib import Path

from app.services.docx_parser import DocxParser
from app.services.schema_rules import (
    SchemaRules,
    SectionRule,
    get_pkm_kc_proposal_rules,
)
from app.services.structure_checker import (
    StructureChecker,
    _heading_matches_rule,
    _normalize,
)

SAMPLE_DIR = Path(__file__).parent / "sample_docs"
DUMMY_FILE = SAMPLE_DIR / "dummy_pkm_kc.docx"
REAL_FILE = SAMPLE_DIR / "A410170082.docx"


# ============================================================================
# Test: helper normalisasi & matching
# ============================================================================


class TestNormalize(unittest.TestCase):
    def test_uppercase_and_strip(self):
        self.assertEqual(_normalize("  Bab 1. Pendahuluan  "), "BAB 1. PENDAHULUAN")

    def test_strips_toc_dot_leader(self):
        """Entri ToC 'BAB 1. PENDAHULUAN ............... 1' → 'BAB 1. PENDAHULUAN'."""
        self.assertEqual(
            _normalize("BAB 1. PENDAHULUAN ............... 1"),
            "BAB 1. PENDAHULUAN",
        )

    def test_collapses_multiple_spaces(self):
        self.assertEqual(_normalize("BAB    1.   PENDAHULUAN"), "BAB 1. PENDAHULUAN")


class TestHeadingMatching(unittest.TestCase):
    def test_canonical_match(self):
        rule = SectionRule(name="DAFTAR ISI", required=True, order=1)
        self.assertTrue(_heading_matches_rule("DAFTAR ISI", rule))
        self.assertTrue(_heading_matches_rule("Daftar Isi", rule))

    def test_alias_match(self):
        rule = SectionRule(
            name="BAB 1. PENDAHULUAN",
            aliases=["BAB I. PENDAHULUAN"],
            required=True, order=5,
        )
        self.assertTrue(_heading_matches_rule("BAB I. PENDAHULUAN", rule))

    def test_no_match(self):
        rule = SectionRule(name="DAFTAR ISI", required=True, order=1)
        self.assertFalse(_heading_matches_rule("BAB 1. PENDAHULUAN", rule))


# ============================================================================
# Test: PKM-KC rules construction
# ============================================================================


class TestPkmKcRules(unittest.TestCase):
    def test_rules_loaded(self):
        rules = get_pkm_kc_proposal_rules()
        self.assertEqual(rules.competition_code, "PKM")
        self.assertEqual(rules.schema_code, "KC")
        self.assertEqual(rules.report_type_code, "PROPOSAL")

    def test_required_sections_present(self):
        rules = get_pkm_kc_proposal_rules()
        names = {r.name for r in rules.required_sections()}
        # Section wajib menurut blueprint §8.1
        for expected in [
            "DAFTAR ISI", "DAFTAR LAMPIRAN",
            "BAB 1. PENDAHULUAN", "BAB 2. TINJAUAN PUSTAKA",
            "BAB 3. TAHAP PELAKSANAAN", "BAB 4. BIAYA DAN JADWAL KEGIATAN",
            "DAFTAR PUSTAKA", "LAMPIRAN",
        ]:
            self.assertIn(expected, names, f"{expected!r} hilang dari required")

    def test_forbidden_sections_present(self):
        rules = get_pkm_kc_proposal_rules()
        names = {r.name for r in rules.forbidden_sections()}
        for expected in ["HALAMAN SAMPUL", "HALAMAN PENGESAHAN", "RINGKASAN"]:
            self.assertIn(expected, names, f"{expected!r} hilang dari forbidden")

    def test_core_sections(self):
        rules = get_pkm_kc_proposal_rules()
        core_names = {r.name for r in rules.core_sections()}
        # BAB 1-4 + Daftar Pustaka harus core (untuk PhysicalSheetCounter)
        for expected in [
            "BAB 1. PENDAHULUAN", "BAB 2. TINJAUAN PUSTAKA",
            "BAB 3. TAHAP PELAKSANAAN", "BAB 4. BIAYA DAN JADWAL KEGIATAN",
            "DAFTAR PUSTAKA",
        ]:
            self.assertIn(expected, core_names)

    def test_rule_invariant_required_xor_forbidden(self):
        """SectionRule tidak boleh required=True dan forbidden=True sekaligus."""
        with self.assertRaises(ValueError):
            SectionRule(name="X", required=True, forbidden=True, order=1)

    def test_rule_required_must_have_order(self):
        with self.assertRaises(ValueError):
            SectionRule(name="X", required=True)


# ============================================================================
# Test: StructureChecker pada DUMMY (yang struktur-wise valid)
# ============================================================================


class TestCheckerOnDummy(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not DUMMY_FILE.exists():
            raise unittest.SkipTest(
                "Dummy belum di-generate. "
                "Jalankan: python3 tests/build_dummy_docx.py"
            )
        cls.parser = DocxParser(DUMMY_FILE)
        cls.rules = get_pkm_kc_proposal_rules()
        cls.result = StructureChecker(cls.parser, cls.rules).check()

    def test_status_is_pass(self):
        """
        Dummy dirancang struktur-wise sesuai PKM-KC: DAFTAR ISI, DAFTAR LAMPIRAN,
        BAB 1-4, DAFTAR PUSTAKA, LAMPIRAN. Tidak ada cover/pengesahan/abstrak.
        """
        if self.result.status != "pass":
            print("\nDEBUG missing:", [m.rule_name for m in self.result.missing_required])
            print("DEBUG forbidden:", [f.rule_name for f in self.result.forbidden_found])
            print("DEBUG out_of_order:", [o.message for o in self.result.out_of_order])
        self.assertEqual(self.result.status, "pass")

    def test_no_missing_required(self):
        self.assertEqual(len(self.result.missing_required), 0)

    def test_no_forbidden(self):
        self.assertEqual(len(self.result.forbidden_found), 0)

    def test_no_out_of_order(self):
        self.assertEqual(len(self.result.out_of_order), 0)

    def test_found_sections_include_all_required(self):
        found_required = {
            f.rule_name for f in self.result.found_sections if f.is_required
        }
        expected_required = {r.name for r in self.rules.required_sections()}
        self.assertEqual(found_required, expected_required)

    def test_to_dict_serializable(self):
        d = self.result.to_dict()
        self.assertEqual(d["status"], "pass")
        self.assertEqual(d["schema"]["competition"], "PKM")
        self.assertEqual(d["schema"]["code"], "KC")
        self.assertIsInstance(d["found_sections"], list)
        self.assertIsInstance(d["messages"], list)


# ============================================================================
# Test: StructureChecker pada DOKUMEN REAL (yang punya red flag)
# ============================================================================


class TestCheckerOnRealDoc(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not REAL_FILE.exists():
            raise unittest.SkipTest(
                f"Sampel real {REAL_FILE.name} tidak tersedia di sandbox."
            )
        cls.parser = DocxParser(REAL_FILE)
        cls.rules = get_pkm_kc_proposal_rules()
        cls.result = StructureChecker(cls.parser, cls.rules).check()

    def test_status_is_fail(self):
        """
        Dokumen real punya halaman sampul ('PROPOSAL PKM-KC') dan tidak punya
        DAFTAR LAMPIRAN sebagai section terpisah. Harus FAIL.
        """
        self.assertEqual(self.result.status, "fail")

    def test_detects_cover_page_red_flag(self):
        """Halaman sampul 'PROPOSAL PKM-KC' harus ter-detect sebagai forbidden."""
        forbidden_names = {f.rule_name for f in self.result.forbidden_found}
        self.assertIn("HALAMAN SAMPUL", forbidden_names)

    def test_detects_missing_daftar_lampiran(self):
        """Dokumen real tidak punya heading 'DAFTAR LAMPIRAN'."""
        missing_names = {m.rule_name for m in self.result.missing_required}
        self.assertIn("DAFTAR LAMPIRAN", missing_names)

    def test_finds_bab_1_to_4(self):
        """BAB 1-4 harus ter-detect dengan benar (heading_only filter bekerja)."""
        found_names = {f.rule_name for f in self.result.found_sections if f.is_required}
        for bab in [
            "BAB 1. PENDAHULUAN", "BAB 2. TINJAUAN PUSTAKA",
            "BAB 3. TAHAP PELAKSANAAN", "BAB 4. BIAYA DAN JADWAL KEGIATAN",
        ]:
            self.assertIn(bab, found_names)


# ============================================================================
# Test: skenario buatan — section out of order
# ============================================================================


class TestOutOfOrderDetection(unittest.TestCase):
    """
    Test logika out-of-order pakai SchemaRules buatan + parser palsu.
    Tidak perlu .docx asli karena kita test internal logic.
    """

    def test_simple_swap_detected(self):
        from app.services.docx_parser import ParagraphInfo
        from app.services.structure_checker import (
            FoundSection, StructureCheckResult,
        )

        # Skenario: di dokumen, "BAB 2" muncul SEBELUM "BAB 1"
        rules = SchemaRules(
            competition_code="TEST", schema_code="X",
            report_type_code="DRAFT", schema_name="Test",
            sections=[
                SectionRule(name="BAB 1", required=True, order=1),
                SectionRule(name="BAB 2", required=True, order=2),
            ],
        )

        # Mock parser: paragraph index 5 = BAB 2, paragraph index 10 = BAB 1
        class _FakeParser:
            paragraphs = [
                ParagraphInfo(index=0, text="title", is_heading=False),
                ParagraphInfo(index=5, text="BAB 2", is_heading=True),
                ParagraphInfo(index=10, text="BAB 1", is_heading=True),
            ]

        result = StructureChecker(_FakeParser(), rules).check()
        self.assertEqual(result.status, "fail")
        self.assertEqual(len(result.out_of_order), 1)
        v = result.out_of_order[0]
        self.assertEqual(v.earlier_should_be, "BAB 1")
        self.assertEqual(v.later_should_be, "BAB 2")


if __name__ == "__main__":
    unittest.main(verbosity=2)