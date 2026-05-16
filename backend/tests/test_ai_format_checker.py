"""
Test suite untuk AiFormatChecker — fokus pada body block (Fase 1 refactor).

Setelah Opsi 2, AiFormatChecker pemilik penuh format teks PKM-AI termasuk
body (TNR 12 justify 1.15) dan foreign words wajib italic. FormatChecker
untuk PKM-AI cuma paper_size + margin.

Cara jalankan:
    python3 -m pytest tests/test_ai_format_checker.py -v
"""
from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.services.core.docx_parser import ParagraphInfo, RunInfo
from app.services.schemas.pkm_ai import ai_format_checker as afc
from app.services.schemas.pkm_ai.ai_format_checker import (
    AiFormatChecker,
    BODY_FONT_SIZE,
    BODY_LINE_SPACING,
)
from app.services.schemas.pkm_ai.rules import get_pkm_ai_article_rules


def _run(text: str, size: float = 12.0, italic: bool = False,
         bold: bool = False) -> RunInfo:
    return RunInfo(text=text, font_name="Times New Roman",
                   font_size_pt=size, italic=italic, bold=bold)


def _para(idx: int, text: str, *, size: float = 12.0,
          alignment: str = "justify", line_spacing: float = 1.15,
          is_heading: bool = False, italic: bool = False,
          bold: bool = False) -> ParagraphInfo:
    return ParagraphInfo(
        index=idx,
        text=text,
        alignment=alignment,
        line_spacing=line_spacing,
        runs=[_run(text, size=size, italic=italic, bold=bold)] if text.strip() else [],
        is_heading=is_heading,
    )


def _make_checker(paragraphs, alignment_map=None):
    """Buat AiFormatChecker dgn parser mock + resolver yang return alignment per-paragraf dari paragraf itu sendiri (atau alignment_map)."""
    parser = SimpleNamespace(
        paragraphs=paragraphs,
        estimate_physical_page=lambda i: 1,
    )
    with patch.object(afc, "StyleResolver") as mock_cls:
        resolver = mock_cls.return_value
        def resolve_align(i):
            if alignment_map is not None and i in alignment_map:
                return alignment_map[i]
            for p in paragraphs:
                if p.index == i:
                    return p.alignment
            return None
        resolver.resolve_paragraph_alignment = resolve_align
        checker = AiFormatChecker(parser, get_pkm_ai_article_rules())
    return checker


# Front-matter standar PKM-AI: judul → penulis → ABSTRAK → isi abstrak ID
# → Kata kunci → ABSTRACT → isi abstract EN → Keywords → PENDAHULUAN → body
_FRONTMATTER = [
    _para(0, "Judul Artikel Ilmiah Mahasiswa PKM-AI", size=12.0, alignment="center", line_spacing=1.0, bold=True),
    _para(1, "Nama Penulis Pertama, Nama Kedua", size=10.0, alignment="center", line_spacing=1.0),
    _para(2, "ABSTRAK", size=12.0, alignment="left", line_spacing=1.0, is_heading=True),
    _para(3, "Isi abstrak ID dengan ukuran 11pt dan justify.", size=11.0, alignment="justify", line_spacing=1.0),
    _para(4, "Kata kunci: kata, kata, kata", size=11.0, alignment="justify", line_spacing=1.0),
    _para(5, "ABSTRACT", size=12.0, alignment="left", line_spacing=1.0, is_heading=True),
    _para(6, "Abstract content in English, justify 11pt.", size=11.0, alignment="justify", line_spacing=1.0),
    _para(7, "Keywords: foo, bar, baz", size=11.0, alignment="justify", line_spacing=1.0),
    _para(8, "PENDAHULUAN", size=12.0, alignment="left", line_spacing=1.15, is_heading=True),
]


class TestBodyBlockValidator(unittest.TestCase):
    """_validate_body_block: TNR 12 justify 1.15 sesuai §2 MIGRATION_PER_SCHEMA."""

    def test_compliant_body_no_finding(self):
        body = [
            _para(9, "Paragraf body pertama dengan isi yang cukup panjang.",
                  size=12.0, alignment="justify", line_spacing=1.15),
            _para(10, "Paragraf body kedua, juga compliant TNR 12 justify 1.15.",
                  size=12.0, alignment="justify", line_spacing=1.15),
        ]
        checker = _make_checker(_FRONTMATTER + body)
        result = checker.check()
        body_findings = [f for f in result.findings if f.zone == "body"]
        self.assertEqual(body_findings, [],
            f"Body compliant tapi muncul finding: {[f.message for f in body_findings]}")

    def test_body_wrong_font_size_fails(self):
        body = [
            _para(9, "Paragraf body pakai 11pt, harusnya 12pt.",
                  size=11.0, alignment="justify", line_spacing=1.15),
            _para(10, "Paragraf body kedua juga 11pt.",
                  size=11.0, alignment="justify", line_spacing=1.15),
        ]
        checker = _make_checker(_FRONTMATTER + body)
        result = checker.check()
        findings = [f for f in result.findings
                    if f.zone == "body" and f.aspect == "font_size"]
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].severity, "fail")
        self.assertEqual(findings[0].expected, f"{BODY_FONT_SIZE}pt")
        self.assertIn("pakai ukuran 11", findings[0].message)

    def test_body_wrong_alignment_fails(self):
        body = [
            _para(9, "Paragraf body left, harusnya justify.",
                  size=12.0, alignment="left", line_spacing=1.15),
            _para(10, "Paragraf body kedua juga left.",
                  size=12.0, alignment="left", line_spacing=1.15),
        ]
        checker = _make_checker(_FRONTMATTER + body)
        result = checker.check()
        findings = [f for f in result.findings
                    if f.zone == "body" and f.aspect == "alignment"]
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].severity, "fail")
        self.assertIn("bukan justify", findings[0].message)

    def test_body_wrong_line_spacing_fails(self):
        body = [
            _para(9, "Paragraf body spasi 1.0, harusnya 1.15.",
                  size=12.0, alignment="justify", line_spacing=1.0),
            _para(10, "Paragraf body kedua spasi 1.0.",
                  size=12.0, alignment="justify", line_spacing=1.0),
        ]
        checker = _make_checker(_FRONTMATTER + body)
        result = checker.check()
        findings = [f for f in result.findings
                    if f.zone == "body" and f.aspect == "line_spacing"]
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].severity, "fail")
        self.assertIn(f"{BODY_LINE_SPACING}", findings[0].expected)

    def test_caption_inside_body_not_revalidated(self):
        """Caption Gambar/Tabel di area body harus di-skip oleh body validator
        (sudah punya validator caption tersendiri)."""
        body = [
            _para(9, "Paragraf body compliant.",
                  size=12.0, alignment="justify", line_spacing=1.15),
            _para(10, "Gambar 1. Caption pendek TNR 11 center.",
                  size=11.0, alignment="center", line_spacing=1.0),
            _para(11, "Paragraf body lain compliant.",
                  size=12.0, alignment="justify", line_spacing=1.15),
        ]
        checker = _make_checker(_FRONTMATTER + body)
        result = checker.check()
        # Caption ditangani _validate_captions (severity warning) — bukan body
        body_size_findings = [f for f in result.findings
                              if f.zone == "body" and f.aspect == "font_size"]
        self.assertEqual(body_size_findings, [])
        caption_findings = [f for f in result.findings if f.zone == "caption"]
        # Caption compliant → tidak ada finding caption juga
        self.assertEqual(caption_findings, [])

    def test_heading_inside_body_not_revalidated(self):
        """Heading di area body (mis. 'METODE') di-skip oleh body validator."""
        body = [
            _para(9, "Paragraf body compliant.",
                  size=12.0, alignment="justify", line_spacing=1.15),
            _para(10, "METODE PENELITIAN",
                  size=14.0, alignment="left", line_spacing=1.0, is_heading=True),
            _para(11, "Paragraf body lain compliant.",
                  size=12.0, alignment="justify", line_spacing=1.15),
        ]
        checker = _make_checker(_FRONTMATTER + body)
        result = checker.check()
        body_findings = [f for f in result.findings if f.zone == "body"]
        self.assertEqual(body_findings, [])

    def test_no_landmarks_skips_body_validation(self):
        """Tanpa landmark abstract/keywords/pendahuluan → body tidak bisa
        ditentukan → validator skip diam-diam (no finding, no crash)."""
        paras = [
            _para(0, "Judul saja", size=12.0, alignment="center"),
            _para(1, "Isi bebas", size=11.0, alignment="left", line_spacing=1.0),
        ]
        checker = _make_checker(paras)
        result = checker.check()
        body_findings = [f for f in result.findings if f.zone == "body"]
        self.assertEqual(body_findings, [])


class TestForeignItalicBody(unittest.TestCase):
    """_validate_foreign_italic_body: warning bila kata asing di body tidak italic."""

    def test_foreign_word_without_italic_flagged(self):
        body = [
            _para(9, "Penelitian ini menggunakan machine learning untuk analisis.",
                  size=12.0, alignment="justify", line_spacing=1.15, italic=False),
        ]
        checker = _make_checker(_FRONTMATTER + body)
        result = checker.check()
        findings = [f for f in result.findings
                    if f.zone == "body" and f.aspect == "foreign_italic"]
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].severity, "warning")
        self.assertIn("machine learning", findings[0].message)

    def test_foreign_word_with_italic_not_flagged(self):
        body = [
            _para(9, "Penelitian ini menggunakan machine learning.",
                  size=12.0, alignment="justify", line_spacing=1.15, italic=True),
        ]
        checker = _make_checker(_FRONTMATTER + body)
        result = checker.check()
        findings = [f for f in result.findings
                    if f.zone == "body" and f.aspect == "foreign_italic"]
        self.assertEqual(findings, [])


class TestMessageFormatNoForbiddenStrings(unittest.TestCase):
    """§2 MIGRATION_PER_SCHEMA: tidak boleh ada 'paragraf #N', 'global #N',
    'Section #N', 'halaman fisik ~N' di pesan apa pun."""

    FORBIDDEN = ("paragraf #", "global #", "Section #", "halaman fisik ~")

    def test_body_findings_no_forbidden_strings(self):
        body = [
            _para(9, "Body 11pt left 1.0, salah di tiga aspek.",
                  size=11.0, alignment="left", line_spacing=1.0),
            _para(10, "Body 11pt left 1.0 lagi.",
                  size=11.0, alignment="left", line_spacing=1.0),
        ]
        checker = _make_checker(_FRONTMATTER + body)
        result = checker.check()
        for msg in result.messages:
            for needle in self.FORBIDDEN:
                self.assertNotIn(needle, msg.text,
                    f"Pesan terlarang '{needle}' muncul: {msg.text!r}")
        # Pesan harus pakai format "Halaman X — kesalahan — Perbaiki: …"
        non_pass = [m for m in result.messages if m.level != "pass"]
        self.assertTrue(non_pass, "Harus ada minimal 1 finding")
        for m in non_pass:
            self.assertTrue(m.text.startswith("Halaman "),
                f"Pesan tidak mulai 'Halaman': {m.text!r}")
            self.assertIn(" — Perbaiki: ", m.text,
                f"Pesan tidak mengandung ' — Perbaiki: ': {m.text!r}")


class TestPassMessageMentionsBody(unittest.TestCase):
    """Pesan 'pass' _finalize harus menyebut body TNR 12 justify 1,15."""

    def test_pass_message_mentions_body(self):
        body = [
            _para(9, "Body compliant pertama.",
                  size=12.0, alignment="justify", line_spacing=1.15),
            _para(10, "Body compliant kedua.",
                  size=12.0, alignment="justify", line_spacing=1.15),
        ]
        checker = _make_checker(_FRONTMATTER + body)
        result = checker.check()
        self.assertEqual(result.status, "pass")
        pass_msgs = [m.text for m in result.messages if m.level == "pass"]
        self.assertTrue(pass_msgs)
        combined = " ".join(pass_msgs).lower()
        self.assertIn("body", combined)
        self.assertIn("1,15", combined)


if __name__ == "__main__":
    unittest.main(verbosity=2)
