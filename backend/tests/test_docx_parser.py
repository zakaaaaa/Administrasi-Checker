"""
Test suite untuk DocxParser — versi unittest (stdlib).

Bisa dijalankan dengan:
    python3 -m unittest tests.test_docx_parser -v
atau (jika pytest tersedia):
    python3 -m pytest tests/test_docx_parser.py -v
"""

import unittest
import tempfile
from pathlib import Path

from app.services.docx_parser import (
    DocxParser,
    ParagraphInfo,
    TableInfo,
    SectionInfo,
    dxa_to_cm,
    half_points_to_pt,
)

SAMPLE_DIR = Path(__file__).parent / "sample_docs"
DUMMY_FILE = SAMPLE_DIR / "A410170082.docx"


class DocxParserTestBase(unittest.TestCase):
    """Base class — load parser sekali untuk efisiensi."""

    @classmethod
    def setUpClass(cls):
        if not DUMMY_FILE.exists():
            raise unittest.SkipTest(
                "Dummy belum di-generate. "
                "Jalankan: python3 tests/build_dummy_docx.py"
            )
        cls.parser = DocxParser(DUMMY_FILE)


# ============================================================================
# Test: konstruktor & validasi input
# ============================================================================


class TestConstructor(unittest.TestCase):
    def test_file_not_found_raises(self):
        with self.assertRaises(FileNotFoundError):
            DocxParser("/path/yang/tidak/ada.docx")

    def test_non_docx_extension_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            fake = Path(tmp) / "bukan.pdf"
            fake.write_bytes(b"hello")
            with self.assertRaises(ValueError):
                DocxParser(fake)


# ============================================================================
# Test: property dasar
# ============================================================================


class TestBasicProperties(DocxParserTestBase):
    def test_paragraphs_extracted(self):
        paras = self.parser.paragraphs
        self.assertIsInstance(paras, list)
        self.assertGreater(len(paras), 0)
        for p in paras:
            self.assertIsInstance(p, ParagraphInfo)
        self.assertTrue(any(p.text.strip() for p in paras))

    def test_paragraph_has_index_text_runs(self):
        for p in self.parser.paragraphs:
            self.assertIsInstance(p.index, int)
            self.assertIsInstance(p.text, str)
            self.assertIsInstance(p.runs, list)

    def test_heading_detection(self):
        bab1 = [p for p in self.parser.paragraphs if "BAB 1" in p.text.upper()]
        self.assertGreaterEqual(len(bab1), 1, "BAB 1 tidak ditemukan")
        heading_paras = [p for p in bab1 if p.is_heading]
        self.assertGreaterEqual(
            len(heading_paras), 1,
            "BAB 1 ada tapi tidak terdeteksi sebagai heading"
        )

    def test_tables_extracted(self):
        tables = self.parser.tables
        self.assertIsInstance(tables, list)
        self.assertGreaterEqual(len(tables), 2, "Dummy punya 2 tabel")
        for t in tables:
            self.assertIsInstance(t, TableInfo)
            self.assertGreater(t.rows, 0)
            self.assertGreater(t.cols, 0)
            self.assertEqual(len(t.cells), t.rows * t.cols)

    def test_table_header_texts(self):
        rab_tables = [
            t for t in self.parser.tables
            if any("Jenis Pengeluaran" in h for h in t.header_texts)
        ]
        self.assertGreaterEqual(len(rab_tables), 1, "Tabel RAB tidak terdeteksi")

    def test_sections_extracted(self):
        sections = self.parser.sections
        self.assertIsInstance(sections, list)
        self.assertGreaterEqual(len(sections), 1)
        for s in sections:
            self.assertIsInstance(s, SectionInfo)

    def test_section_margins_match_pkm_rules(self):
        s0 = self.parser.sections[0]
        left_cm = dxa_to_cm(s0.margin_left_dxa)
        right_cm = dxa_to_cm(s0.margin_right_dxa)
        top_cm = dxa_to_cm(s0.margin_top_dxa)
        bottom_cm = dxa_to_cm(s0.margin_bottom_dxa)
        self.assertAlmostEqual(left_cm, 4.0, delta=0.05)
        self.assertAlmostEqual(right_cm, 3.0, delta=0.05)
        self.assertAlmostEqual(top_cm, 3.0, delta=0.05)
        self.assertAlmostEqual(bottom_cm, 3.0, delta=0.05)


# ============================================================================
# Test: header/footer XML
# ============================================================================


class TestRawXMLAccess(DocxParserTestBase):
    def test_header_footer_xmls_accessible(self):
        self.assertIsInstance(self.parser.header_xmls, dict)
        self.assertIsInstance(self.parser.footer_xmls, dict)

    def test_document_xml_loads(self):
        root = self.parser.document_xml
        self.assertIsNotNone(root)
        self.assertTrue(root.tag.endswith("}document"))


# ============================================================================
# Test: find_section_boundaries
# ============================================================================


class TestSectionBoundaries(DocxParserTestBase):
    def test_default_matches_first_occurrence(self):
        """
        Default (headings_only=False): match kemunculan pertama, yang BISA berupa
        baris di Daftar Isi. Ini adalah perilaku lama yang dipertahankan.
        """
        b = self.parser.find_section_boundaries(
            ["DAFTAR ISI", "BAB 1", "DAFTAR PUSTAKA", "LAMPIRAN"]
        )
        self.assertIsNotNone(b["DAFTAR ISI"])
        self.assertIsNotNone(b["BAB 1"])
        self.assertIsNotNone(b["DAFTAR PUSTAKA"])
        self.assertIsNotNone(b["LAMPIRAN"])
        # Note: di dummy, "BAB 1" di-match ke baris ToC (paragraf #1),
        # bukan ke heading BAB 1 asli. Itu memang perilaku default.

    def test_headings_only_skips_toc_entries(self):
        """
        headings_only=True: hanya match paragraf yang is_heading.
        Baris di Daftar Isi (yang bukan heading) di-skip, sehingga
        "BAB 1" akan ketemu di heading aslinya, bukan di entri ToC.
        """
        b_default = self.parser.find_section_boundaries(["BAB 1"])
        b_headings = self.parser.find_section_boundaries(
            ["BAB 1"], headings_only=True
        )
        self.assertIsNotNone(b_default["BAB 1"])
        self.assertIsNotNone(b_headings["BAB 1"])
        # Heading asli pasti BELAKANG (lebih besar indeksnya) daripada entri ToC.
        self.assertGreater(
            b_headings["BAB 1"], b_default["BAB 1"],
            "Heading asli BAB 1 seharusnya muncul setelah baris BAB 1 di ToC"
        )
        # Verifikasi yang ketemu memang heading
        bab1_para = self.parser.paragraphs[b_headings["BAB 1"]]
        self.assertTrue(bab1_para.is_heading)
        self.assertIn("PENDAHULUAN", bab1_para.text.upper())

    def test_headings_only_full_proposal_order(self):
        """
        Dengan headings_only=True, urutan section dalam proposal harus benar:
        DAFTAR ISI < BAB 1 < BAB 2 < BAB 3 < BAB 4 < DAFTAR PUSTAKA < LAMPIRAN.
        """
        b = self.parser.find_section_boundaries(
            ["DAFTAR ISI", "BAB 1", "BAB 2", "BAB 3", "BAB 4",
             "DAFTAR PUSTAKA", "LAMPIRAN"],
            headings_only=True,
        )
        # Semua harus ditemukan
        for name, idx in b.items():
            self.assertIsNotNone(idx, f"Section {name!r} tidak ditemukan")
        # Urutan strictly ascending
        order = ["DAFTAR ISI", "BAB 1", "BAB 2", "BAB 3", "BAB 4",
                 "DAFTAR PUSTAKA", "LAMPIRAN"]
        for prev, nxt in zip(order, order[1:]):
            self.assertLess(
                b[prev], b[nxt],
                f"Urutan salah: {prev}({b[prev]}) seharusnya sebelum {nxt}({b[nxt]})"
            )

    def test_missing_returns_none(self):
        b = self.parser.find_section_boundaries(["BAGIAN_FIKTIF_TIDAK_ADA"])
        self.assertIsNone(b["BAGIAN_FIKTIF_TIDAK_ADA"])

    def test_missing_with_headings_only(self):
        """Section yang tidak ada → None, baik dengan flag maupun tanpa."""
        b = self.parser.find_section_boundaries(
            ["BAGIAN_FIKTIF"], headings_only=True
        )
        self.assertIsNone(b["BAGIAN_FIKTIF"])


# ============================================================================
# Test: iter_runs
# ============================================================================


class TestIterRuns(DocxParserTestBase):
    def test_iter_runs_yields_data(self):
        count = 0
        found_tnr = False
        for _, run in self.parser.iter_runs():
            count += 1
            if run.font_name and "Times New Roman" in run.font_name:
                found_tnr = True
        self.assertGreater(count, 0)
        self.assertTrue(found_tnr, "Run dengan TNR tidak ditemukan")


# ============================================================================
# Test: images
# ============================================================================


class TestImages(DocxParserTestBase):
    def test_images_property(self):
        images = self.parser.images
        self.assertIsInstance(images, list)
        # Dummy tidak ada gambar — kosong wajar


# ============================================================================
# Test: konversi unit
# ============================================================================


class TestUnitConversion(unittest.TestCase):
    def test_dxa_to_cm(self):
        self.assertAlmostEqual(dxa_to_cm(11906), 21.0, delta=0.01)
        self.assertIsNone(dxa_to_cm(None))
        self.assertAlmostEqual(dxa_to_cm(1440), 2.54, delta=0.001)

    def test_half_points_to_pt(self):
        self.assertEqual(half_points_to_pt(24), 12.0)
        self.assertEqual(half_points_to_pt("24"), 12.0)
        self.assertIsNone(half_points_to_pt(None))
        self.assertIsNone(half_points_to_pt("invalid"))


# ============================================================================
# Test: summary
# ============================================================================


class TestSummary(DocxParserTestBase):
    def test_summary_returns_dict(self):
        s = self.parser.summary()
        self.assertIsInstance(s, dict)
        expected_keys = {
            "file", "paragraph_count", "table_count", "section_count",
            "header_part_count", "footer_part_count", "image_count", "warnings",
        }
        self.assertTrue(expected_keys.issubset(set(s.keys())))
        self.assertGreater(s["paragraph_count"], 0)
        self.assertGreaterEqual(s["table_count"], 2)


# ============================================================================
# Test: invalid zip
# ============================================================================


class TestCorruptedFile(unittest.TestCase):
    def test_corrupted_docx_collects_warning(self):
        with tempfile.TemporaryDirectory() as tmp:
            fake = Path(tmp) / "rusak.docx"
            fake.write_bytes(b"ini bukan zip valid")
            parser = DocxParser(fake)
            raw = parser.read_raw_part("word/document.xml")
            self.assertIsNone(raw)
            self.assertGreater(len(parser.warnings), 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)