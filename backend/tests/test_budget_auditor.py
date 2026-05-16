"""
Test suite untuk BudgetAuditor & budget_table_parser.

Cara jalankan:
    python3 -m unittest tests.test_budget_auditor -v
"""

import unittest
from pathlib import Path

from app.services.core.docx_parser import DocxParser
from app.services.schemas.pkm_kc.budget_auditor import (
    BudgetAuditResult,
    BudgetAuditor,
    FundingInput,
)
from app.services.schemas.pkm_kc.budget_rules import (
    BudgetRules,
    FundingSourceRule,
    BudgetCategory,
    get_pkm_kc_budget_rules,
)
from app.services.schemas.pkm_kc.budget_table_parser import (
    BudgetItem,
    Lampiran2ParseResult,
    parse_indonesian_number,
    is_bab4_rab_table,
    is_lampiran2_table,
    parse_bab4_table,
    parse_lampiran2_table,
    match_category_to_canonical,
)

SAMPLE_DIR = Path(__file__).parent / "sample_docs"
DUMMY_FILE = SAMPLE_DIR / "dummy_pkm_kc.docx"
REAL_FILE = SAMPLE_DIR / "A410170082.docx"


# ============================================================================
# Test: parse_indonesian_number
# ============================================================================


class TestParseIndonesianNumber(unittest.TestCase):
    def test_indonesian_format(self):
        self.assertEqual(parse_indonesian_number("4.400.000,00"), 4400000)
        self.assertEqual(parse_indonesian_number("11.320.000"), 11320000)
        self.assertEqual(parse_indonesian_number("Rp 750.000,00"), 750000)
        self.assertEqual(parse_indonesian_number("Rp1.000.000"), 1000000)

    def test_us_format_fallback(self):
        self.assertEqual(parse_indonesian_number("1,500,000.00"), 1500000)
        self.assertEqual(parse_indonesian_number("100,000"), 100000)

    def test_simple_number(self):
        self.assertEqual(parse_indonesian_number("100"), 100)
        self.assertEqual(parse_indonesian_number("12345"), 12345)

    def test_invalid(self):
        self.assertIsNone(parse_indonesian_number("invalid"))
        self.assertIsNone(parse_indonesian_number(""))
        self.assertIsNone(parse_indonesian_number("abc"))


# ============================================================================
# Test: identifikasi tabel
# ============================================================================


class TestTableIdentificationRealDoc(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not REAL_FILE.exists():
            raise unittest.SkipTest(f"{REAL_FILE.name} tidak ada")
        cls.parser = DocxParser(REAL_FILE)

    def test_finds_bab4_table(self):
        bab4_tables = [t for t in self.parser.tables if is_bab4_rab_table(t)]
        self.assertEqual(len(bab4_tables), 1, "Harus tepat 1 tabel RAB Bab 4")
        self.assertEqual(bab4_tables[0].index, 0)

    def test_finds_lampiran2_table(self):
        lamp2_tables = [t for t in self.parser.tables if is_lampiran2_table(t)]
        # Mungkin lebih dari 1 kalau ada sub-table di biodata, tapi minimal 1
        self.assertGreaterEqual(len(lamp2_tables), 1)

    def test_doesnt_misidentify_biodata_table(self):
        """Tabel biodata (3 kolom) tidak boleh ke-detect sebagai RAB Bab 4."""
        # Tabel biodata di doc real punya 3 kolom dan header 'Nama Lengkap'
        biodata_tables = [
            t for t in self.parser.tables
            if any("Nama Lengkap" in h for h in t.header_texts)
        ]
        for bt in biodata_tables:
            self.assertFalse(is_bab4_rab_table(bt),
                f"Biodata table #{bt.index} salah dikira RAB Bab 4")


# ============================================================================
# Test: parse tabel pada dokumen real
# ============================================================================


class TestParseTablesRealDoc(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not REAL_FILE.exists():
            raise unittest.SkipTest(f"{REAL_FILE.name} tidak ada")
        cls.parser = DocxParser(REAL_FILE)

    def test_bab4_grand_total(self):
        bab4_tables = [t for t in self.parser.tables if is_bab4_rab_table(t)]
        result = parse_bab4_table(bab4_tables[0])
        self.assertEqual(result.grand_total_rp, 11_320_000)

    def test_bab4_categories_count(self):
        bab4_tables = [t for t in self.parser.tables if is_bab4_rab_table(t)]
        result = parse_bab4_table(bab4_tables[0])
        self.assertEqual(len(result.categories), 4)

    def test_lampiran2_grand_total(self):
        lamp2_tables = [t for t in self.parser.tables if is_lampiran2_table(t)]
        result = parse_lampiran2_table(lamp2_tables[0])
        self.assertEqual(result.grand_total_rp, 11_320_000)

    def test_lampiran2_has_items(self):
        lamp2_tables = [t for t in self.parser.tables if is_lampiran2_table(t)]
        result = parse_lampiran2_table(lamp2_tables[0])
        self.assertGreater(len(result.items), 10)

    def test_lampiran2_items_have_categories(self):
        lamp2_tables = [t for t in self.parser.tables if is_lampiran2_table(t)]
        result = parse_lampiran2_table(lamp2_tables[0])
        # Minimal beberapa item punya kategori
        with_cat = [i for i in result.items if i.category]
        self.assertGreater(len(with_cat), 0)


# ============================================================================
# Test: match_category_to_canonical (alias matching)
# ============================================================================


class TestCategoryMatching(unittest.TestCase):
    def setUp(self):
        self.cats = get_pkm_kc_budget_rules().categories

    def test_canonical_match(self):
        self.assertEqual(
            match_category_to_canonical("Bahan habis pakai", self.cats),
            "Bahan habis pakai",
        )

    def test_alias_perlengkapan_to_sewa_jasa(self):
        """'Perlengkapan yang diperlukan' harus map ke 'Sewa dan jasa'."""
        self.assertEqual(
            match_category_to_canonical("Perlengkapan yang diperlukan", self.cats),
            "Sewa dan jasa",
        )

    def test_alias_perjalanan_to_transportasi(self):
        """'Perjalanan' harus map ke 'Transportasi lokal'."""
        self.assertEqual(
            match_category_to_canonical("Perjalanan", self.cats),
            "Transportasi lokal",
        )

    def test_alias_lain_lain_with_endash(self):
        """'Lain – lain' (en-dash) harus map ke 'Lain-lain'."""
        self.assertEqual(
            match_category_to_canonical("Lain – lain", self.cats),
            "Lain-lain",
        )

    def test_no_match(self):
        self.assertIsNone(
            match_category_to_canonical("Kategori Asing", self.cats),
        )


# ============================================================================
# Test: Funding validation (Lapis 1)
# ============================================================================


class TestFundingValidation(unittest.TestCase):
    """Test Lapis 1 dengan parser stub — tidak butuh .docx."""

    def _make_auditor(self, funding: FundingInput) -> BudgetAuditor:
        # Stub parser dengan tables kosong supaya tidak crash
        class _StubParser:
            tables = []
        return BudgetAuditor(
            parser=_StubParser(),
            rules=get_pkm_kc_budget_rules(),
            funding=funding,
        )

    def test_pt_zero_fails(self):
        """Dana PT = Rp0 harus FAIL (zero_value_is_error)."""
        result = self._make_auditor(
            FundingInput(belmawa=7_000_000, university=0, external=0)
        ).check()
        pt_results = [fv for fv in result.funding_validation if fv.name == "university"]
        self.assertEqual(len(pt_results), 1)
        self.assertEqual(pt_results[0].status, "fail")
        self.assertIn("Rp0", pt_results[0].message)

    def test_pt_500_passes(self):
        """Dana PT = Rp500 (minimum) harus PASS."""
        result = self._make_auditor(
            FundingInput(belmawa=7_000_000, university=500, external=0)
        ).check()
        pt = next(fv for fv in result.funding_validation if fv.name == "university")
        self.assertEqual(pt.status, "pass")

    def test_pt_above_max_fails(self):
        result = self._make_auditor(
            FundingInput(belmawa=7_000_000, university=2_500_000, external=0)
        ).check()
        pt = next(fv for fv in result.funding_validation if fv.name == "university")
        self.assertEqual(pt.status, "fail")

    def test_belmawa_below_range_fails(self):
        result = self._make_auditor(
            FundingInput(belmawa=5_000_000, university=1_000_000, external=0)
        ).check()
        belmawa = next(fv for fv in result.funding_validation if fv.name == "belmawa")
        self.assertEqual(belmawa.status, "fail")

    def test_belmawa_above_range_fails(self):
        result = self._make_auditor(
            FundingInput(belmawa=10_000_000, university=1_000_000, external=0)
        ).check()
        belmawa = next(fv for fv in result.funding_validation if fv.name == "belmawa")
        self.assertEqual(belmawa.status, "fail")

    def test_external_zero_passes(self):
        """Dana eksternal = Rp0 harus PASS (opsional)."""
        result = self._make_auditor(
            FundingInput(belmawa=7_000_000, university=1_000_000, external=0)
        ).check()
        ext = next(fv for fv in result.funding_validation if fv.name == "external")
        self.assertEqual(ext.status, "pass")

    def test_all_valid_passes(self):
        result = self._make_auditor(
            FundingInput(belmawa=7_000_000, university=1_000_000, external=500_000)
        ).check()
        for fv in result.funding_validation:
            self.assertEqual(fv.status, "pass", f"{fv.name} should pass: {fv.message}")


# ============================================================================
# Test: BudgetAuditor end-to-end pada dokumen real
# ============================================================================


class TestBudgetAuditorRealDoc(unittest.TestCase):
    """
    Dokumen `A410170082.docx`:
    - Total RAB: 11.320.000 (jauh di atas Belmawa range 6-8jt)
    - Kategori: 'Perlengkapan' (35.5%) - over 15% limit
    - Cross-check: ada mismatch Bab4 vs Lamp2 di kategori 'Bahan habis pakai'
    - Banyak prohibited items (Hard Disk, Sewa Komputer, Biaya Seminar, dll)
    """

    @classmethod
    def setUpClass(cls):
        if not REAL_FILE.exists():
            raise unittest.SkipTest(f"{REAL_FILE.name} tidak ada")
        cls.parser = DocxParser(REAL_FILE)
        cls.rules = get_pkm_kc_budget_rules()
        cls.result = BudgetAuditor(cls.parser, cls.rules).check()

    def test_overall_status_fail(self):
        self.assertEqual(self.result.status, "fail")

    def test_finds_bab4_grand_total(self):
        self.assertEqual(self.result.bab4_grand_total_rp, 11_320_000)

    def test_finds_lampiran2_grand_total(self):
        self.assertEqual(self.result.lampiran2_grand_total_rp, 11_320_000)

    def test_table_integrity_pass(self):
        """Semua 4 kategori PKM-KC ada (via alias matching)."""
        self.assertEqual(self.result.table_integrity_status, "pass",
            f"Missing: {self.result.table_integrity_missing}")

    def test_cross_check_finds_discrepancy(self):
        """Bab 4 'Bahan habis pakai' = 2.470.000, Lamp 2 = 3.120.000 → mismatch."""
        self.assertEqual(self.result.cross_check_status, "fail")
        self.assertGreater(len(self.result.cross_check_discrepancies), 0)

    def test_finds_prohibited_items(self):
        """Dokumen ada Hard Disk, Sewa Komputer, Biaya Seminar, dll."""
        self.assertGreater(len(self.result.prohibited_items), 0)
        # Cek beberapa item terlarang spesifik
        descs = [p.description for p in self.result.prohibited_items]
        self.assertTrue(
            any("Hard Disk" in d or "hard disk" in d.lower() for d in descs),
            f"Hard Disk not found in: {descs}"
        )

    def test_finds_relocation_warnings_when_unit_price_high(self):
        """Saran relokasi memakai patokan harga satuan > Rp1jt (bukan total baris)."""
        self.assertGreater(len(self.result.relocation_items), 0)
        for ri in self.result.relocation_items:
            self.assertGreater(ri.amount_rp, 1_000_000)

    def test_perlengkapan_category_over_limit(self):
        """Kategori 'Sewa dan jasa' (alias 'Perlengkapan') = 4.4jt / 11.32jt = 38.9% > 15%."""
        sewa_results = [
            c for c in self.result.categories
            if c.canonical_name == "Sewa dan jasa"
        ]
        self.assertEqual(len(sewa_results), 1)
        self.assertEqual(sewa_results[0].status, "fail")
        self.assertGreater(sewa_results[0].actual_pct or 0, 15.0)


# ============================================================================
# Test: relokasi = patokan harga satuan
# ============================================================================


class TestRelocationUnitPriceThreshold(unittest.TestCase):
    """_scan_relocation: bandingkan unit_price, bukan total_rp."""

    def test_only_high_unit_price_flagged(self):
        class _P:
            def estimate_page_for_table_cell(self, *a, **k):
                return 12

        auditor = BudgetAuditor.__new__(BudgetAuditor)
        auditor.rules = get_pkm_kc_budget_rules()
        auditor.parser = _P()
        result = BudgetAuditResult(status="pass")
        lamp2 = Lampiran2ParseResult(
            found=True,
            table_index=0,
            items=[
                BudgetItem(
                    description="Vol besar OK",
                    unit_price=200_000,
                    total_rp=10_000_000,
                    volume="50",
                    row_index=1,
                    table_index=0,
                ),
                BudgetItem(
                    description="Satuan mahal",
                    unit_price=1_200_000,
                    total_rp=1_200_000,
                    volume="1",
                    row_index=2,
                    table_index=0,
                ),
                BudgetItem(
                    description="Tanpa satuan",
                    unit_price=None,
                    total_rp=5_000_000,
                    row_index=3,
                    table_index=0,
                ),
            ],
        )
        BudgetAuditor._scan_relocation(auditor, result, lamp2)
        self.assertEqual(len(result.relocation_items), 1)
        self.assertEqual(result.relocation_items[0].description, "Satuan mahal")
        self.assertEqual(result.relocation_items[0].approx_page, 12)

    def test_no_unit_price_no_relocation_flag(self):
        class _P:
            def estimate_page_for_table_cell(self, *a, **k):
                return None

        auditor = BudgetAuditor.__new__(BudgetAuditor)
        auditor.rules = get_pkm_kc_budget_rules()
        auditor.parser = _P()
        result = BudgetAuditResult(status="pass")
        lamp2 = Lampiran2ParseResult(
            found=True,
            table_index=0,
            items=[
                BudgetItem(
                    description="Hanya total",
                    unit_price=None,
                    total_rp=5_000_000,
                    row_index=1,
                    table_index=0,
                ),
            ],
        )
        BudgetAuditor._scan_relocation(auditor, result, lamp2)
        self.assertEqual(len(result.relocation_items), 0)


# ============================================================================
# Test: edge case — tabel tidak ada
# ============================================================================


class TestNoTablesEdgeCase(unittest.TestCase):
    def test_no_tables_in_doc(self):
        """Stub parser tanpa tabel → table_integrity FAIL semua kategori."""
        class _StubParser:
            tables = []
        result = BudgetAuditor(
            parser=_StubParser(),
            rules=get_pkm_kc_budget_rules(),
        ).check()
        self.assertEqual(result.table_integrity_status, "fail")
        # Semua kategori PKM-KC harus dilaporkan missing
        self.assertEqual(len(result.table_integrity_missing), 4)


if __name__ == "__main__":
    unittest.main(verbosity=2)