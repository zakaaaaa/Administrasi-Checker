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
    get_pkm_laporan_kemajuan_rules,
)
from app.services.structure_checker import (
    StructureChecker,
    _heading_matches_rule,
    _normalize,
)

SAMPLE_DIR = Path(__file__).parent / "sample_docs"
DUMMY_FILE = SAMPLE_DIR / "dummy_pkm_kc.docx"
REAL_FILE = SAMPLE_DIR / "A410170082.docx"
LAPKEM_FILE = SAMPLE_DIR / "lapkem_pkm_kc.docx"


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


# ============================================================================
# Test: scope "front_matter" untuk section terlarang
# ============================================================================
#
# Sampul, pengesahan dan ringkasan didefinisikan oleh LETAK (lembar depan),
# bukan sekadar kata kuncinya. Sebelum scope ini ada, pencocokan berbasis
# prefix membuat sub-bab sah "Ringkasan Hasil yang Dicapai" di BAB 4 ter-flag
# sebagai RINGKASAN terlarang — dan di UI terbaca sebagai "dokumen ada
# covernya" karena label ringkasannya digabung.
# ============================================================================


def _fake_parser(headings: list[tuple[int, str]]):
    """Parser palsu dari daftar (paragraph_index, teks heading)."""
    from app.services.docx_parser import ParagraphInfo

    class _FakeParser:
        paragraphs = [
            ParagraphInfo(index=i, text=t, is_heading=True) for i, t in headings
        ]

    return _FakeParser()


# Kerangka laporan kemajuan yang lengkap & valid, dipakai sebagai basis skenario.
_LAPKEM_SKELETON = [
    (0, "DAFTAR ISI"),
    (1, "DAFTAR LAMPIRAN"),
    (10, "BAB 1. PENDAHULUAN"),
    (20, "BAB 2. TARGET LUARAN"),
    (30, "BAB 3. TAHAP PELAKSANAAN"),
    (40, "BAB 4. HASIL YANG DICAPAI"),
    (50, "BAB 5. POTENSI HASIL"),
    (60, "BAB 6. RENCANA TAHAPAN BERIKUTNYA"),
    (70, "DAFTAR PUSTAKA"),
    (80, "LAMPIRAN"),
]


class TestForbiddenFrontMatterScope(unittest.TestCase):
    RULES = get_pkm_laporan_kemajuan_rules("KC")

    def _check(self, headings):
        return StructureChecker(_fake_parser(sorted(headings)), self.RULES).check()

    def test_skeleton_is_clean(self):
        """Sanity: kerangka dasar tanpa tambahan apa pun harus pass."""
        result = self._check(_LAPKEM_SKELETON)
        self.assertEqual(result.status, "pass")
        self.assertEqual(result.forbidden_found, [])

    def test_ringkasan_subheading_after_bab1_not_flagged(self):
        """REGRESI: sub-bab "Ringkasan Hasil yang Dicapai" di BAB 4 bukan pelanggaran.

        Ini bug yang ditemukan di lapangan: heading sah di dalam bagian inti
        ter-flag sebagai section RINGKASAN terlarang.
        """
        result = self._check(
            _LAPKEM_SKELETON + [(45, "Ringkasan Hasil yang Dicapai")]
        )
        self.assertEqual([f.rule_name for f in result.forbidden_found], [])
        self.assertEqual(result.status, "pass")

    def test_ringkasan_before_bab1_still_flagged(self):
        """Ringkasan di lembar depan (sebelum BAB 1) tetap red flag."""
        result = self._check(_LAPKEM_SKELETON + [(5, "RINGKASAN")])
        self.assertEqual([f.rule_name for f in result.forbidden_found], ["RINGKASAN"])
        self.assertEqual(result.forbidden_found[0].severity, "fail")
        self.assertEqual(result.status, "fail")

    def test_cover_before_daftar_isi_still_flagged(self):
        """Halaman sampul asli di paling depan tetap terdeteksi."""
        result = self._check(
            [(0, "LAPORAN KEMAJUAN PKM-KC")]
            + [(i + 1, t) for i, t in _LAPKEM_SKELETON]
        )
        self.assertIn("HALAMAN SAMPUL", [f.rule_name for f in result.forbidden_found])
        self.assertEqual(result.status, "fail")

    def test_pengesahan_before_bab1_still_flagged(self):
        result = self._check(_LAPKEM_SKELETON + [(5, "LEMBAR PENGESAHAN")])
        self.assertIn(
            "HALAMAN PENGESAHAN", [f.rule_name for f in result.forbidden_found]
        )

    def test_abstrak_inside_lampiran_not_flagged(self):
        """Salinan artikel ber-ABSTRAK di LAMPIRAN bukan pelanggaran struktur."""
        result = self._check(_LAPKEM_SKELETON + [(85, "ABSTRAK")])
        self.assertEqual([f.rule_name for f in result.forbidden_found], [])

    def test_not_reported_when_core_anchor_missing(self):
        """Tanpa BAB mana pun, zona depan tidak bisa ditegakkan.

        Sampul/pengesahan/ringkasan didefinisikan oleh LETAK. Kalau letaknya
        tidak bisa diverifikasi, buktinya tidak cukup untuk memvonis — dan
        karena vonisnya biner, temuan itu tidak dilaporkan.
        """
        result = self._check(
            [(0, "DAFTAR ISI"), (1, "DAFTAR LAMPIRAN"), (5, "RINGKASAN"),
             (70, "DAFTAR PUSTAKA"), (80, "LAMPIRAN")]
        )
        self.assertEqual([f.rule_name for f in result.forbidden_found], [])

    def test_unverifiable_zone_yields_pass_not_a_verdict(self):
        """Zona tidak terverifikasi → status tetap pass, bukan vonis salah.

        Ini konsekuensi yang disengaja dari vonis biner: pelanggaran yang tidak
        bisa dibuktikan letaknya akan terlewat, dan itu lebih baik daripada
        memvonis dokumen yang benar.
        """
        rules = SchemaRules(
            competition_code="TEST", schema_code="X",
            report_type_code="DRAFT", schema_name="Test",
            sections=[
                SectionRule(name="DAFTAR ISI", required=True, order=1),
                SectionRule(
                    name="RINGKASAN", forbidden=True, forbidden_scope="front_matter"
                ),
            ],
        )
        parser = _fake_parser([(0, "DAFTAR ISI"), (5, "RINGKASAN")])
        result = StructureChecker(parser, rules).check()
        self.assertEqual(result.status, "pass")
        self.assertNotIn("warning", {m.level for m in result.messages})

    def test_ai_bab_forbidden_stays_whole_document(self):
        """Forbidden tanpa scope (mis. "BAB" di PKM-AI) tetap dicek di seluruh dokumen."""
        from app.services.schema_rules import get_pkm_ai_proposal_rules

        parser = _fake_parser([
            (0, "Pendahuluan"), (10, "Metode"), (20, "Hasil dan Pembahasan"),
            (30, "Kesimpulan"), (40, "Ucapan Terimakasih"), (50, "Kontribusi Penulis"),
            (60, "Daftar Pustaka"), (70, "LAMPIRAN"), (25, "BAB 3"),
        ])
        result = StructureChecker(parser, get_pkm_ai_proposal_rules()).check()
        forbidden = [f for f in result.forbidden_found if f.rule_name == "BAB 1"]
        self.assertEqual(len(forbidden), 1)
        self.assertEqual(forbidden[0].severity, "fail")


class TestLapkemRealDoc(unittest.TestCase):
    """Dokumen laporan kemajuan PKM-KC asli yang memicu false positive RINGKASAN."""

    @classmethod
    def setUpClass(cls):
        if not LAPKEM_FILE.exists():
            raise unittest.SkipTest(
                f"Sampel {LAPKEM_FILE.name} tidak tersedia di sandbox."
            )
        cls.parser = DocxParser(LAPKEM_FILE)
        cls.result = StructureChecker(
            cls.parser, get_pkm_laporan_kemajuan_rules("KC")
        ).check()

    def test_no_forbidden_section(self):
        """Dokumen tidak punya cover/pengesahan/ringkasan di lembar depan."""
        self.assertEqual(
            [(f.rule_name, f.matched_text) for f in self.result.forbidden_found], []
        )

    def test_first_heading_is_daftar_isi(self):
        """Ground truth: heading pertama dokumen = DAFTAR ISI, jadi tidak ada cover."""
        first = next(p for p in self.parser.paragraphs if p.text.strip())
        self.assertEqual(first.text.strip().upper(), "DAFTAR ISI")

    def test_status_is_pass(self):
        self.assertEqual(self.result.status, "pass")



# ============================================================================
# Test: vonis biner — hanya divonis kalau bisa dibuktikan
# ============================================================================
#
# Sistem ini TIDAK punya tingkat 'warning'. Hasilnya cuma salah atau benar.
# Konsekuensinya, temuan yang buktinya tidak cukup kuat TIDAK DILAPORKAN sama
# sekali — lebih baik terlewat daripada memvonis salah.
#
# Bukti dianggap cukup kalau salah satu terpenuhi:
#   - Word menandai paragrafnya heading (style Heading N / Title / outlineLvl), ATAU
#   - teks paragrafnya PERSIS nama section.
# Yang tidak punya keduanya (dikenali cuma dari bentuk teks DAN cocok sebagai
# awalan saja) bisa jadi paragraf biasa yang kebetulan berawalan sama.
#
# Tujuannya menekan false positive pada dokumen yang belum pernah dilihat.
# ============================================================================


def _para(index, text, *, is_heading=False):
    from app.services.docx_parser import ParagraphInfo

    return ParagraphInfo(index=index, text=text, is_heading=is_heading)


class TestVerdictRequiresDirectEvidence(unittest.TestCase):
    RULES = get_pkm_laporan_kemajuan_rules("KC")

    def _check(self, paras):
        class _FakeParser:
            paragraphs = paras

        return StructureChecker(_FakeParser(), self.RULES).check()

    def _skeleton(self, *, styled=True):
        return [
            _para(i, t, is_heading=styled)
            for i, t in _LAPKEM_SKELETON
        ]

    def test_shape_evidence_with_prefix_match_is_not_reported(self):
        """REGRESI: paragraf tak ber-style yang cuma BERAWALAN nama section.

        Ini bug yang ditemukan di lapangan ("Ringkasan Hasil yang Dicapai").
        Buktinya tidak cukup, jadi tidak divonis dan tidak dilaporkan.
        """
        paras = self._skeleton() + [
            _para(5, "RINGKASAN HASIL SEMENTARA KEGIATAN", is_heading=False)
        ]
        result = self._check(sorted(paras, key=lambda p: p.index))
        self.assertEqual(
            [f.rule_name for f in result.forbidden_found], [],
            "temuan berbukti lemah tidak boleh dilaporkan",
        )
        self.assertEqual(result.status, "pass")

    def test_shape_evidence_with_exact_match_is_fail(self):
        """Teks PERSIS nama section tetap konklusif walau style-nya Normal.

        Kasus nyata: proposal dengan paragraf bold berbunyi persis "Abstrak".
        """
        paras = self._skeleton() + [_para(5, "RINGKASAN", is_heading=False)]
        result = self._check(sorted(paras, key=lambda p: p.index))
        ringkasan = [f for f in result.forbidden_found if f.rule_name == "RINGKASAN"]
        self.assertEqual(len(ringkasan), 1)
        self.assertEqual(ringkasan[0].severity, "fail")
        self.assertEqual(result.status, "fail")

    def test_style_evidence_with_prefix_match_is_fail(self):
        """Heading ber-style tetap vonis walau judulnya ber-ekor."""
        paras = self._skeleton() + [
            _para(5, "RINGKASAN KEGIATAN", is_heading=True)
        ]
        result = self._check(sorted(paras, key=lambda p: p.index))
        ringkasan = [f for f in result.forbidden_found if f.rule_name == "RINGKASAN"]
        self.assertEqual(len(ringkasan), 1)
        self.assertEqual(ringkasan[0].severity, "fail")

    def test_missing_section_is_reported_regardless_of_style(self):
        """Section wajib yang hilang tetap divonis.

        Pencarian memakai style heading DAN heuristik bentuk, jadi "tidak ketemu
        oleh keduanya" sudah dasar yang cukup — berlaku baik dokumen memakai
        style heading maupun tidak.
        """
        for styled in (True, False):
            with self.subTest(styled=styled):
                paras = [
                    _para(i, t, is_heading=styled)
                    for i, t in _LAPKEM_SKELETON
                    if t != "DAFTAR LAMPIRAN"
                ]
                result = self._check(paras)
                missing = [
                    m for m in result.missing_required
                    if m.rule_name == "DAFTAR LAMPIRAN"
                ]
                self.assertEqual(len(missing), 1)
                self.assertEqual(result.status, "fail")

    def test_clean_document_still_passes(self):
        """Kebijakan severity tidak boleh memunculkan temuan baru."""
        result = self._check(self._skeleton())
        self.assertEqual(result.status, "pass")

    def test_no_warning_level_is_ever_emitted(self):
        """Sistem ini biner: tidak boleh ada pesan ber-level 'warning'."""
        cases = [
            self._skeleton(),
            self._skeleton() + [_para(5, "RINGKASAN", is_heading=False)],
            self._skeleton() + [_para(5, "RINGKASAN HASIL SEMENTARA", is_heading=False)],
        ]
        for paras in cases:
            result = self._check(sorted(paras, key=lambda p: p.index))
            self.assertIn(result.status, ("pass", "fail"))
            levels = {m.level for m in result.messages}
            self.assertNotIn("warning", levels)

    def test_evidence_is_serialized(self):
        """Dasar pengenalan tetap ikut disimpan untuk penelusuran."""
        d = self._check(self._skeleton()).to_dict()
        self.assertTrue(all("evidence" in s for s in d["found_sections"]))
        self.assertTrue(all("match_quality" in s for s in d["found_sections"]))


class TestHeadingMatchQuality(unittest.TestCase):
    def test_exact_beats_prefix(self):
        from app.services.structure_checker import _heading_match_quality

        rule = SectionRule(name="RINGKASAN", aliases=["ABSTRAK"], forbidden=True)
        self.assertEqual(_heading_match_quality("Ringkasan", rule), "exact")
        self.assertEqual(_heading_match_quality("ABSTRAK", rule), "exact")
        self.assertEqual(
            _heading_match_quality("Ringkasan Hasil yang Dicapai", rule), "prefix"
        )
        self.assertIsNone(_heading_match_quality("Pendahuluan", rule))

    def test_toc_dot_leader_normalised_to_exact(self):
        """Entri ToC 'BAB 1. PENDAHULUAN ..... 5' tetap dianggap cocok penuh."""
        from app.services.structure_checker import _heading_match_quality

        rule = SectionRule(name="BAB 1. PENDAHULUAN", required=True, order=1)
        self.assertEqual(
            _heading_match_quality("BAB 1. PENDAHULUAN ......... 5", rule), "exact"
        )



if __name__ == "__main__":
    unittest.main(verbosity=2)