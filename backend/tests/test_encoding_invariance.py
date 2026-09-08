"""
Uji invariansi penyandian — jaring pengaman untuk dokumen yang BELUM PERNAH ada.

Masalah yang diserang
---------------------
Korpus dokumen nyata menjaga bug yang sudah diperbaiki tidak kambuh (regresi),
tapi tidak bisa mencegah false positive pada dokumen baru yang menulis hal yang
sama dengan cara berbeda. Itu sumber keluhan "dokumen baru selalu saja ada
false positive": checker ditala per dokumen yang pernah dilihat, lalu patah
pada penyandian yang belum pernah dilihat.

Cara kerjanya
-------------
`build_variant_docx` menghasilkan 27 dokumen dari SATU isi logis yang sama —
3 gaya Daftar Isi x 3 gaya heading x 3 gaya nomor halaman. Isinya identik:
section, urutan, dan penempatan nomor halaman sama persis. Yang berbeda cuma
cara Word menuliskannya di dalam file.

Invariannya satu kalimat: **vonis harus sama untuk ke-27 varian.** Vonis yang
berubah padahal isi tidak berubah adalah bug — dan ketemu tanpa perlu menunggu
dokumen mahasiswa datang.

Tiga varian menyandikan jebakan yang pernah lolos ke produksi:
- toc 'tab_leader'   : bug "melebihi 10 halaman" (entri Daftar Isi bertab
                       dikira awal BAB 1)
- pagenum 'first_dead': bug "letak nomor halaman" (headerReference type='first'
                       tanpa <w:titlePg/> — part mati yang tetap terbaca)
- heading 'outline_level': heading ber-style kustom, hanya ditandai outlineLvl

Cara jalankan:
    python3 -m unittest tests.test_encoding_invariance -v
"""

from __future__ import annotations

import shutil
import tempfile
import unittest
from collections import defaultdict
from pathlib import Path

from app.services.docx_parser import DocxParser
from app.services.page_numbering_checker import PageNumberingChecker
from app.services.physical_sheet_counter import PhysicalSheetCounter
from app.services.schema_rules import get_pkm_laporan_kemajuan_rules
from app.services.structure_checker import StructureChecker

from tests.build_variant_docx import (
    HEADING_STYLES,
    PAGENUM_STYLES,
    TOC_STYLES,
    build_all_variants,
)


def _verdict(path: Path, rules) -> tuple:
    """Vonis yang harus invarian terhadap cara penyandian."""
    parser = DocxParser(path)
    structure = StructureChecker(parser, rules).check()
    sheets = PhysicalSheetCounter(parser, rules).check()
    numbering = PageNumberingChecker(parser, rules).check()
    return (
        structure.status,
        tuple(sorted(f.rule_name for f in structure.forbidden_found)),
        tuple(sorted(m.rule_name for m in structure.missing_required)),
        tuple(sorted(o.earlier_should_be for o in structure.out_of_order)),
        sheets.status,
        numbering.status,
        tuple(sorted(f.aspect for f in numbering.findings)),
    )


class TestEncodingInvariance(unittest.TestCase):
    """Vonis wajib identik untuk seluruh kombinasi penyandian."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="variant_docs_"))
        cls.rules = get_pkm_laporan_kemajuan_rules("KC")
        cls.built = build_all_variants(cls.tmp)
        cls.verdicts = {
            key: _verdict(path, cls.rules) for key, path in cls.built.items()
        }

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_all_combinations_built(self):
        expected = len(TOC_STYLES) * len(HEADING_STYLES) * len(PAGENUM_STYLES)
        self.assertEqual(len(self.built), expected)

    def test_verdict_is_identical_across_all_variants(self):
        """Invarian utama: 27 penyandian, 1 vonis."""
        groups: dict[tuple, list] = defaultdict(list)
        for key, verdict in self.verdicts.items():
            groups[verdict].append(key)

        if len(groups) > 1:
            detail = "\n".join(
                f"  vonis {verdict}\n    dipicu oleh: {keys}"
                for verdict, keys in groups.items()
            )
            self.fail(
                "Vonis berubah padahal isi dokumen identik — "
                f"ada {len(groups)} vonis berbeda:\n{detail}"
            )

    def test_the_single_verdict_is_clean(self):
        """Dokumen logisnya memang valid, jadi vonisnya harus bersih.

        Kalau ini gagal sementara test invariansi lolos, artinya checker
        konsisten tapi salah — bukan masalah penyandian.
        """
        verdict = next(iter(self.verdicts.values()))
        structure_status, forbidden, missing, out_of_order = verdict[:4]
        self.assertEqual(structure_status, "pass")
        self.assertEqual(forbidden, ())
        self.assertEqual(missing, ())
        self.assertEqual(out_of_order, ())
        self.assertEqual(verdict[5], "pass", "penomoran halaman harus pass")


class TestVariantsEncodeKnownTraps(unittest.TestCase):
    """Varian harus benar-benar memuat jebakan, bukan cuma berganti nama.

    Tanpa test ini, uji invariansi bisa lolos secara palsu: kalau generator
    ternyata tidak menuliskan jebakannya, semua varian jadi identik di level
    file dan invariansinya trivial.
    """

    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="variant_traps_"))
        cls.built = build_all_variants(cls.tmp)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def _parser(self, toc, heading, pagenum):
        return DocxParser(self.built[(toc, heading, pagenum)])

    def test_toc_style_variant_detected_via_style(self):
        """Gaya 'style' harus terdeteksi lewat style Word, bukan dot/tab."""
        parser = self._parser("style", "heading_style", "plain")
        evidence = {p.toc_evidence for p in parser.paragraphs if p.is_toc_entry}
        self.assertEqual(evidence, {"style"})

    def test_toc_leader_variants_detected_via_fallback(self):
        for toc in ("dot_leader", "tab_leader"):
            with self.subTest(toc=toc):
                parser = self._parser(toc, "heading_style", "plain")
                evidence = {
                    p.toc_evidence for p in parser.paragraphs if p.is_toc_entry
                }
                self.assertEqual(evidence, {"leader"})

    def test_toc_entries_are_never_headings(self):
        """Entri Daftar Isi kerap UPPERCASE — tidak boleh lolos sebagai heading."""
        for toc in TOC_STYLES:
            with self.subTest(toc=toc):
                parser = self._parser(toc, "heading_style", "plain")
                leaked = [
                    p.text for p in parser.paragraphs if p.is_toc_entry and p.is_heading
                ]
                self.assertEqual(leaked, [])

    def test_outline_level_variant_recognised_as_heading(self):
        """Style kustom ber-outlineLvl harus terbaca heading tanpa heuristik bentuk."""
        parser = self._parser("style", "outline_level", "plain")
        headings = [p.text.strip() for p in parser.paragraphs if p.is_heading]
        self.assertIn("BAB 1. PENDAHULUAN", headings)

    def test_first_dead_variant_really_has_dead_header(self):
        """Jebakan PKM-RE: headerReference 'first' TANPA titlePg."""
        parser = self._parser("style", "heading_style", "first_dead")
        sec0 = parser.sections[0]
        self.assertIn("first", sec0.header_refs)
        self.assertFalse(sec0.title_pg)

    def test_titlepg_live_variant_really_has_titlepg(self):
        parser = self._parser("style", "heading_style", "titlepg_live")
        self.assertTrue(parser.sections[0].title_pg)

    def test_dead_header_ignored_live_header_used(self):
        """Part mati diabaikan; posisi dibaca dari part yang benar-benar dirender."""
        for pagenum in PAGENUM_STYLES:
            with self.subTest(pagenum=pagenum):
                parser = self._parser("style", "heading_style", pagenum)
                result = PageNumberingChecker(
                    parser, get_pkm_laporan_kemajuan_rules("KC")
                ).check()
                positions = {
                    a.section_index: a.actual_position for a in result.sections_analysis
                }
                self.assertEqual(positions[0], "bottom", "zona awal di footer")
                self.assertEqual(positions[1], "top", "zona inti di header")


if __name__ == "__main__":
    unittest.main(verbosity=2)
