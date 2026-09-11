"""
Test suite untuk PageNumberingChecker.

Cara jalankan:
    python3 -m unittest tests.test_page_numbering_checker -v
"""

import unittest
from pathlib import Path

from app.services.docx_parser import DocxParser, SectionInfo
from app.services.page_numbering_checker import (
    PageNumberingChecker,
    PageNumberingRules,
    ZoneRule,
    HeaderFooterAnalysis,
    SectionPageNumberingAnalysis,
    ZoneFinding,
    get_pkm_page_numbering_rules,
)
from app.services.schema_rules import (
    get_pkm_kc_proposal_rules,
    get_pkm_laporan_kemajuan_rules,
)

SAMPLE_DIR = Path(__file__).parent / "sample_docs"
DUMMY_FILE = SAMPLE_DIR / "dummy_pkm_kc.docx"
REAL_FILE = SAMPLE_DIR / "A410170082.docx"
LAPKEM_RE_FILE = SAMPLE_DIR / "lapkem_pkm_re.docx"
LAPKEM_PM_FILE = SAMPLE_DIR / "lapkem_pkm_pm.docx"
LAPKEM_RSH_NUM_FILE = SAMPLE_DIR / "lapkem_pkm_rsh_numbering.docx"


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


# ============================================================================
# Test: header/footer "first" & "even" yang tidak aktif harus diabaikan
# ============================================================================
#
# ECMA-376: part ber-type "first" hanya dirender kalau section punya
# <w:titlePg/>; part ber-type "even" hanya kalau dokumen punya
# <w:evenAndOddHeaders/>. Part yang syaratnya tidak terpenuhi adalah sisa mati
# — lazim tertinggal dari editan lama. Sebelum perbaikan, part mati itu ikut
# dibaca sehingga posisi nomor halaman divonis 'top' padahal yang benar-benar
# dirender adalah footer 'default' di 'bottom'.
# ============================================================================


class _FakeSection:
    """SectionInfo minimal untuk menguji _ordered_refs."""

    def __init__(self, header_refs=None, footer_refs=None, title_pg=False):
        self.index = 0
        self.header_refs = header_refs or {}
        self.footer_refs = footer_refs or {}
        self.title_pg = title_pg


class _FakeParser:
    def __init__(self, even_and_odd=False):
        self.even_and_odd_headers = even_and_odd
        self.sections = []
        self.paragraphs = []


class TestInactiveHeaderRefsIgnored(unittest.TestCase):
    def _checker(self, even_and_odd=False):
        checker = PageNumberingChecker.__new__(PageNumberingChecker)
        checker.parser = _FakeParser(even_and_odd)
        return checker

    def test_first_ref_dropped_without_titlepg(self):
        """REGRESI: headerReference type='first' tanpa <w:titlePg/> = mati."""
        c = self._checker()
        sec = _FakeSection(header_refs={"first": "rId9"}, title_pg=False)
        self.assertEqual(c._ordered_refs(sec.header_refs, sec), [])

    def test_first_ref_kept_with_titlepg(self):
        c = self._checker()
        sec = _FakeSection(header_refs={"first": "rId9"}, title_pg=True)
        self.assertEqual(c._ordered_refs(sec.header_refs, sec), [("first", "rId9")])

    def test_even_ref_dropped_without_setting(self):
        c = self._checker(even_and_odd=False)
        sec = _FakeSection(header_refs={"even": "rId5"}, title_pg=True)
        self.assertEqual(c._ordered_refs(sec.header_refs, sec), [])

    def test_even_ref_kept_with_setting(self):
        c = self._checker(even_and_odd=True)
        sec = _FakeSection(header_refs={"even": "rId5"}, title_pg=True)
        self.assertEqual(c._ordered_refs(sec.header_refs, sec), [("even", "rId5")])

    def test_default_ref_always_kept_and_ordered_first(self):
        c = self._checker(even_and_odd=True)
        sec = _FakeSection(
            header_refs={"even": "rId5", "first": "rId9", "default": "rId4"},
            title_pg=True,
        )
        self.assertEqual(
            c._ordered_refs(sec.header_refs, sec),
            [("default", "rId4"), ("first", "rId9"), ("even", "rId5")],
        )

    def test_sec_none_keeps_legacy_behaviour(self):
        """Tanpa konteks section, semua ref dipakai (perilaku lama)."""
        c = self._checker()
        refs = {"first": "rId9", "default": "rId4"}
        self.assertEqual(
            c._ordered_refs(refs), [("default", "rId4"), ("first", "rId9")]
        )


class TestLapkemReRealDoc(unittest.TestCase):
    """Laporan Kemajuan PKM-RE asli yang salah divonis letak nomor halaman.

    Section #0 punya footerReference 'default' (footer1.xml, kanan bawah) DAN
    headerReference 'first' (header1.xml) tanpa <w:titlePg/>. Yang benar-benar
    dirender Word cuma footernya, jadi zona awal sudah benar: roman di bawah.
    """

    @classmethod
    def setUpClass(cls):
        if not LAPKEM_RE_FILE.exists():
            raise unittest.SkipTest(
                f"Sampel {LAPKEM_RE_FILE.name} tidak tersedia di sandbox."
            )
        cls.parser = DocxParser(LAPKEM_RE_FILE)
        cls.result = PageNumberingChecker(
            cls.parser, get_pkm_laporan_kemajuan_rules("RE")
        ).check()

    def test_section0_has_first_header_without_titlepg(self):
        """Prasyarat dokumen: kondisi yang memicu bug memang ada."""
        sec0 = self.parser.sections[0]
        self.assertFalse(sec0.title_pg)
        self.assertIn("first", sec0.header_refs)
        self.assertIn("default", sec0.footer_refs)

    def test_front_matter_position_read_from_footer(self):
        sec0 = next(
            s for s in self.result.sections_analysis if s.section_index == 0
        )
        self.assertEqual(sec0.actual_position, "bottom")
        self.assertFalse(sec0.has_header_with_page)

    def test_status_is_pass(self):
        self.assertEqual(self.result.status, "pass")



# ============================================================================
# Petak section harus selaras dengan enumerasi parser
# ============================================================================
#
# _compute_section_paragraph_ranges() dan DocxParser._iter_sect_pr() harus
# melihat urutan sectPr yang SAMA. Kalau salah satu melewatkan section break
# yang bersarang di <w:sdt>, indeksnya bergeser dan zona tiap section salah
# petak — nomor halaman bagian inti dibaca dari header bagian depan.
# ============================================================================


class TestSectionRangesAlignWithParser(unittest.TestCase):
    """Jumlah petak tidak boleh melebihi jumlah section yang dikenal parser."""

    SAMPLES = [
        ("dummy", DUMMY_FILE),
        ("real", REAL_FILE),
        ("lapkem_re", LAPKEM_RE_FILE),
    ]

    def test_ranges_indices_are_valid_sections(self):
        for label, path in self.SAMPLES:
            if not path.exists():
                continue
            with self.subTest(sample=label):
                parser = DocxParser(path)
                checker = PageNumberingChecker(
                    parser, get_pkm_laporan_kemajuan_rules("KC")
                )
                ranges = checker._compute_section_paragraph_ranges()
                n = len(parser.sections)
                self.assertTrue(
                    all(0 <= idx < n for idx in ranges),
                    f"indeks petak di luar jangkauan section: "
                    f"petak={sorted(ranges)} jumlah_section={n}",
                )

    def test_every_section_analysed(self):
        """Tiap section parser wajib punya baris analisis."""
        for label, path in self.SAMPLES:
            if not path.exists():
                continue
            with self.subTest(sample=label):
                parser = DocxParser(path)
                result = PageNumberingChecker(
                    parser, get_pkm_laporan_kemajuan_rules("KC")
                ).check()
                self.assertEqual(
                    [a.section_index for a in result.sections_analysis],
                    [s.index for s in parser.sections],
                )



# ============================================================================
# Nomor halaman dobel (header DAN footer sama-sama mencetak)
# ============================================================================
#
# Aturan PKM menentukan SATU posisi per zona. Kalau header dan footer
# sama-sama memuat nomor, satu halaman mencetak nomornya dua kali — lazim
# terjadi saat penulis menambah header bernomor untuk bagian inti sementara
# footer bagian depan ikut terwarisi.
#
# Dulu lolos tanpa temuan: checker memilih salah satu sumber (header lebih
# diprioritaskan), melihat posisinya cocok aturan, lalu menyatakan pass.
# ============================================================================


class TestDuplicatePageNumber(unittest.TestCase):
    def _analysis(self, *, header_renders, footer_renders):
        """Jalankan _analyze_section dengan header/footer palsu."""
        checker = PageNumberingChecker.__new__(PageNumberingChecker)
        checker.rules = get_pkm_page_numbering_rules()

        def fake_pick(part, kind):
            renders = header_renders if kind == "header" else footer_renders
            if renders is None:
                return None
            return HeaderFooterAnalysis(
                part_name=f"word/{kind}1.xml", kind=kind,
                has_page_field=True, alignment="right",
                font_name="Times New Roman", font_size_pt=12.0,
                renders_text=renders,
            )

        checker._analyze_header_footer = fake_pick
        checker._get_rid_to_part_map = lambda: {"rId1": "word/header1.xml",
                                                "rId2": "word/footer1.xml"}
        checker.parser = type("P", (), {"even_and_odd_headers": False})()
        sec = SectionInfo(index=0)
        sec.header_refs = {"default": "rId1"} if header_renders is not None else {}
        sec.footer_refs = {"default": "rId2"} if footer_renders is not None else {}
        sec.page_num_format = "decimal"
        return checker._analyze_section(sec, "core_matter")

    def test_both_rendering_is_duplicate(self):
        a = self._analysis(header_renders=True, footer_renders=True)
        self.assertTrue(a.has_duplicate_page_number)

    def test_header_only_is_not_duplicate(self):
        a = self._analysis(header_renders=True, footer_renders=None)
        self.assertFalse(a.has_duplicate_page_number)

    def test_footer_only_is_not_duplicate(self):
        a = self._analysis(header_renders=None, footer_renders=True)
        self.assertFalse(a.has_duplicate_page_number)

    def test_empty_leftover_field_is_not_duplicate(self):
        """Field kosong sisa editan bukan nomor halaman kedua."""
        a = self._analysis(header_renders=True, footer_renders=False)
        self.assertFalse(a.has_duplicate_page_number)

    def test_duplicate_produces_finding(self):
        checker = PageNumberingChecker.__new__(PageNumberingChecker)
        checker.rules = get_pkm_page_numbering_rules()
        analysis = SectionPageNumberingAnalysis(
            section_index=4, zone="core_matter",
            has_header_with_page=True, has_footer_with_page=True,
            actual_position="top", actual_numeral_type="arabic",
            actual_alignment="right", actual_font_name="Times New Roman",
            actual_font_size_pt=12.0, has_duplicate_page_number=True,
        )
        findings = checker._validate_zone(
            [analysis], "core_matter", checker.rules.core_matter
        )
        aspects = [f.aspect for f in findings]
        self.assertIn("duplicate", aspects)
        dup = next(f for f in findings if f.aspect == "duplicate")
        self.assertEqual(dup.severity, "fail")
        self.assertIn("2 nomor halaman dalam 1 halaman", dup.message)


    def test_message_carries_physical_page_range(self):
        """Rentang halaman fisik wajib ada DI DALAM kalimat, bukan cuma prefiks.

        Frontend mengelompokkan temuan per halaman dan hanya membaca angka
        PERTAMA dari prefiks lokasi ("Halaman ~5-17" → 5). Kalau rentangnya
        tidak dibawa di kalimat, reviewer tidak tahu masalahnya sampai hlm 17.
        """
        if not LAPKEM_PM_FILE.exists():
            self.skipTest(f"Sampel {LAPKEM_PM_FILE.name} tidak tersedia.")
        parser = DocxParser(LAPKEM_PM_FILE)
        result = PageNumberingChecker(
            parser, get_pkm_laporan_kemajuan_rules("PM")
        ).check()
        dup = [
            m for m in result.messages
            if "2 nomor halaman dalam 1 halaman" in m.text
        ]
        self.assertEqual(len(dup), 1)
        self.assertRegex(dup[0].text, r"pada halaman fisik \d+(-\d+)?")



# ============================================================================
# Angka ter-cache memutus header vs footer yang sama-sama bernomor
# ============================================================================
#
# Dokumen PKM-RSH: section halaman 2-4 (romawi) mendeklarasikan header
# bernomor sendiri DAN mewarisi footer bernomor. Menurut struktur file itu dua
# nomor; Word mencetak SATU, di bawah (dikonfirmasi lewat screenshot Word).
#
# Pemutusnya: angka yang Word simpan di field PAGE saat terakhir mencetak.
# header3 ber-cache "1" (arab) — tak mungkin dicetak di section romawi.
# footer2 ber-cache "iv" (romawi) — cocok. Dokumen PM sebaliknya: kedua part
# ber-cache arab di section arab, jadi dobelnya memang asli dan harus tetap
# terdeteksi.
# ============================================================================


class TestCachedNumeralTiebreak(unittest.TestCase):
    def test_rsh_front_matter_not_duplicate(self):
        """REGRESI: RSH hal. 2-4 tidak boleh divonis dobel maupun 'di atas'."""
        if not LAPKEM_RSH_NUM_FILE.exists():
            self.skipTest("sampel lapkem_pkm_rsh_numbering.docx tidak tersedia")
        result = PageNumberingChecker(
            DocxParser(LAPKEM_RSH_NUM_FILE), get_pkm_laporan_kemajuan_rules("RSH")
        ).check()
        self.assertEqual(result.status, "pass", [m.text for m in result.messages])
        sec1 = next(a for a in result.sections_analysis if a.section_index == 1)
        self.assertEqual(sec1.actual_position, "bottom")
        self.assertFalse(sec1.has_duplicate_page_number)

    def test_pm_real_duplicate_still_detected(self):
        """Tiebreak hanya melepas part yang bertentangan — dobel asli tetap kena."""
        if not LAPKEM_PM_FILE.exists():
            self.skipTest("sampel lapkem_pkm_pm.docx tidak tersedia")
        result = PageNumberingChecker(
            DocxParser(LAPKEM_PM_FILE), get_pkm_laporan_kemajuan_rules("PM")
        ).check()
        self.assertTrue(
            any(a.has_duplicate_page_number for a in result.sections_analysis)
        )

    def test_numeral_kind_helpers(self):
        from app.services.page_numbering_checker import _section_numeral_kind

        self.assertEqual(_section_numeral_kind("lowerRoman"), "roman")
        self.assertEqual(_section_numeral_kind("upperRoman"), "roman")
        self.assertEqual(_section_numeral_kind("decimal"), "arabic")
        self.assertEqual(_section_numeral_kind(None), "arabic")



if __name__ == "__main__":
    unittest.main(verbosity=2)