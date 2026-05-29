"""
PkmAiFormatChecker — checker format front matter PKM-AI.

Yang dicek (sistematika halaman pertama PKM-AI):
1. Judul      : TNR 12pt, tebal, huruf kapital semua, maks 20 kata
2. Penulis    : TNR 10pt, tegak
3. Abstrak ID : TNR 11pt, justified, maks 250 kata
4. Abstract EN: TNR 11pt, miring, justified, maks 250 kata
5. Spasi baris front matter: 1.0

Deteksi batas front matter: paragraf sebelum BAB 1.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Iterator, Optional

from app.services.docx_parser import DocxParser, ParagraphInfo
from app.services.schema_rules import SchemaRules
from app.services.style_resolver import StyleResolver
from app.services.format_checker import (
    CheckMessage,
    FormatCheckResult,
    FormatCheckSection,
    FormatIssue,
)


class PkmAiFormatChecker:
    """
    Checker format sistematika awal PKM-AI (front matter).

    Usage:
        result = PkmAiFormatChecker(parser, rules).check()
        # result.checks berisi: title_format, author_font,
        #   abstract_id_format, abstract_en_format, front_matter_spacing
    """

    # Heading pertama sesudah front matter = "Pendahuluan"
    _CORE_START_RE = re.compile(r"^\s*(?:Pendahuluan|PENDAHULUAN)\s*$", re.IGNORECASE)
    _ABSTRAK_ID_RE = re.compile(r"^\s*Abstrak\s*$", re.IGNORECASE)
    _ABSTRACT_EN_RE = re.compile(r"^\s*Abstract\s*$", re.IGNORECASE)
    _KATA_KUNCI_RE = re.compile(r"^\s*(?:Kata\s*[Kk]unci|Keywords?)\s*:", re.IGNORECASE)

    # 7 heading section yang wajib TNR 12 cetak tebal (PDF panduan halaman 7–10).
    _SECTION_HEADING_PATTERNS: list[tuple[str, re.Pattern]] = [
        ("Pendahuluan",         re.compile(r"pendahuluan", re.IGNORECASE)),
        ("Metode",              re.compile(r"metode(?:\s+(?:pelaksanaan|penelitian))?", re.IGNORECASE)),
        ("Hasil dan Pembahasan", re.compile(r"hasil\s+dan\s+(?:pembahasan|diskusi)", re.IGNORECASE)),
        ("Kesimpulan",          re.compile(r"(?:kesimpulan|simpulan)", re.IGNORECASE)),
        ("Ucapan Terima Kasih", re.compile(r"ucapan\s+terima\s*kasih", re.IGNORECASE)),
        ("Kontribusi Penulis",  re.compile(r"kontribusi\s+penulis", re.IGNORECASE)),
        ("Daftar Pustaka",      re.compile(r"daftar\s+pustaka", re.IGNORECASE)),
    ]
    # Strip prefix nomor heading umum (mis. "1. Pendahuluan", "1) Metode")
    _HEADING_NUM_PREFIX_RE = re.compile(r"^\s*\d+\s*[.)]\s*")

    # Caption "Tabel N." dan "Gambar N." di awal paragraf (untuk cek posisi).
    _TBL_CAPTION_RE = re.compile(r"^\s*Tabel\s+\d+[.:]?\s+", re.IGNORECASE)
    _FIG_CAPTION_RE = re.compile(r"^\s*Gambar\s+\d+[.:]?\s+", re.IGNORECASE)
    # Namespace WordprocessingML (untuk traversal body order)
    _W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"

    MAX_ISSUES = 5  # per sub-check

    def __init__(self, parser: DocxParser, rules: SchemaRules):
        self.parser = parser
        self.rules = rules
        self.resolver = StyleResolver(parser)

    # ----------------------------------------------------------------
    # Public
    # ----------------------------------------------------------------

    def check(self) -> FormatCheckResult:
        result = FormatCheckResult(status="pass")
        bab1_idx = self._find_core_start_para_index()

        result.checks["title_format"] = self._check_title(bab1_idx)
        result.checks["author_font"] = self._check_author_font(bab1_idx)
        result.checks["abstract_id_format"] = self._check_abstract("id", bab1_idx)
        result.checks["abstract_en_format"] = self._check_abstract("en", bab1_idx)
        result.checks["front_matter_spacing"] = self._check_front_matter_spacing(bab1_idx)
        result.checks["section_headings"] = self._check_section_headings(bab1_idx)
        result.checks["caption_positions"] = self._check_caption_positions(bab1_idx)

        statuses = [s.status for s in result.checks.values()]
        if "fail" in statuses:
            result.status = "fail"
        elif "warning" in statuses:
            result.status = "warning"
        else:
            result.status = "pass"

        for name, sec in result.checks.items():
            if sec.status == "pass":
                result.messages.append(CheckMessage(level="pass", text=f"{name}: OK"))
            else:
                n = len(sec.issues)
                result.messages.append(CheckMessage(level=sec.status, text=f"{name}: {n} pelanggaran"))
                for issue in sec.issues[: self.MAX_ISSUES]:
                    result.messages.append(
                        CheckMessage(level=issue.severity, text=f"  • {issue.issue}")
                    )

        return result

    # ----------------------------------------------------------------
    # Helpers
    # ----------------------------------------------------------------

    def _find_core_start_para_index(self) -> Optional[int]:
        """Return index paragraf 'Pendahuluan' (awal isi artikel, sesudah front matter)."""
        for para in self.parser.paragraphs:
            if self._CORE_START_RE.match(para.text.strip()):
                return para.index
        return None

    def _front_matter(self, bab1_idx: Optional[int]) -> Iterator[ParagraphInfo]:
        for para in self.parser.paragraphs:
            if bab1_idx is not None and para.index >= bab1_idx:
                break
            yield para

    # ----------------------------------------------------------------
    # Sub-check: judul
    # ----------------------------------------------------------------

    def _check_title(self, bab1_idx: Optional[int]) -> FormatCheckSection:
        """
        Paragraf non-empty pertama = judul.
        Aturan: ALL CAPS, maks 20 kata, TNR 12pt, bold.
        """
        sec = FormatCheckSection(name="title_format", status="pass")

        title_para: Optional[ParagraphInfo] = None
        for para in self._front_matter(bab1_idx):
            if para.text.strip():
                title_para = para
                break

        if title_para is None:
            sec.issues.append(FormatIssue(
                check_name="title_missing",
                severity="fail",
                location="Front matter",
                issue="Judul artikel tidak ditemukan di front matter.",
            ))
            sec.status = "fail"
            return sec

        text = title_para.text.strip()

        # ALL CAPS
        if text != text.upper():
            non_caps = [w for w in text.split() if w != w.upper() and w.isalpha()]
            sec.issues.append(FormatIssue(
                check_name="title_caps",
                severity="fail",
                location="Judul",
                issue=f"Judul harus huruf kapital semua (ALL CAPS). Contoh kata tidak kapital: {', '.join(non_caps[:3])}",
                found=text[:80],
                expected="Semua huruf kapital",
            ))

        # Maks 20 kata
        word_count = len(text.split())
        if word_count > 20:
            sec.issues.append(FormatIssue(
                check_name="title_word_count",
                severity="fail",
                location="Judul",
                issue=f"Judul melebihi batas 20 kata ({word_count} kata).",
                found=str(word_count),
                expected="Maksimal 20 kata",
            ))

        # Font name
        font = self.resolver.resolve_paragraph_font(title_para.index)
        if font.name and font.name != "Times New Roman":
            sec.issues.append(FormatIssue(
                check_name="title_font_name",
                severity="fail",
                location="Judul",
                issue="Font judul bukan Times New Roman.",
                found=font.name,
                expected="Times New Roman",
            ))

        # Font size 12pt
        if font.size_pt is not None and abs(font.size_pt - 12.0) > 0.3:
            sec.issues.append(FormatIssue(
                check_name="title_font_size",
                severity="fail",
                location="Judul",
                issue=f"Ukuran font judul bukan 12pt.",
                found=f"{font.size_pt}pt",
                expected="12pt",
            ))

        # Bold — cek via run; None = inherit (tidak di-flag)
        explicitly_not_bold = any(
            r.bold is False for r in title_para.runs if r.text.strip()
        )
        if explicitly_not_bold:
            sec.issues.append(FormatIssue(
                check_name="title_bold",
                severity="fail",
                location="Judul",
                issue="Judul harus dicetak tebal (bold).",
                found="tidak bold",
                expected="bold",
            ))

        if sec.issues:
            sec.status = "fail"
        sec.detail = {"word_count": word_count, "title_text": text[:120]}
        return sec

    # ----------------------------------------------------------------
    # Sub-check: nama penulis & institusi (TNR 10pt)
    # ----------------------------------------------------------------

    def _check_author_font(self, bab1_idx: Optional[int]) -> FormatCheckSection:
        """
        Zona penulis: paragraf setelah judul sampai sebelum heading Abstrak/Abstract.
        Aturan PKM-AI: TNR 10pt, cetak normal (tidak bold, tidak italic).
        """
        sec = FormatCheckSection(name="author_font", status="pass")

        title_passed = False
        for para in self._front_matter(bab1_idx):
            text = para.text.strip()
            if not text:
                continue

            if not title_passed:
                title_passed = True
                continue  # skip judul

            if self._ABSTRAK_ID_RE.match(text) or self._ABSTRACT_EN_RE.match(text):
                break

            snippet = text[:60] + ("…" if len(text) > 60 else "")
            para_font = self.resolver.resolve_paragraph_font(para.index)

            # Cek font name dan size per run (run override > paragraph default)
            for run in para.runs:
                if not run.text.strip():
                    continue
                if any(ord(c) > 127 for c in run.text):
                    continue  # skip run dengan karakter non-ASCII

                eff_name = run.font_name if run.font_name else para_font.name
                eff_size = run.font_size_pt if run.font_size_pt is not None else para_font.size_pt

                if eff_name and eff_name != "Times New Roman":
                    sec.issues.append(FormatIssue(
                        check_name="author_font_name",
                        severity="fail",
                        location=f"Penulis/Institusi",
                        issue=f"Font nama penulis/institusi bukan Times New Roman — \"{snippet}\"",
                        found=eff_name,
                        expected="Times New Roman",
                    ))
                    break

                if eff_size is not None and abs(eff_size - 10.0) > 0.3:
                    sec.issues.append(FormatIssue(
                        check_name="author_font_size",
                        severity="fail",
                        location=f"Penulis/Institusi",
                        issue=f"Ukuran font nama penulis/institusi bukan 10pt — \"{snippet}\"",
                        found=f"{eff_size}pt",
                        expected="10pt",
                    ))
                    break

            # Cek cetak normal: tidak bold, tidak italic
            bold_runs = [r for r in para.runs if r.text.strip() and r.bold is True]
            italic_runs = [r for r in para.runs if r.text.strip() and r.italic is True]

            if bold_runs:
                sec.issues.append(FormatIssue(
                    check_name="author_bold",
                    severity="fail",
                    location="Penulis/Institusi",
                    issue=f"Nama penulis/institusi harus cetak normal, bukan tebal (bold) — \"{snippet}\"",
                    found="bold",
                    expected="normal",
                ))

            if italic_runs:
                sec.issues.append(FormatIssue(
                    check_name="author_italic",
                    severity="fail",
                    location="Penulis/Institusi",
                    issue=f"Nama penulis/institusi harus cetak normal, bukan miring (italic) — \"{snippet}\"",
                    found="italic",
                    expected="normal",
                ))

            if len(sec.issues) >= self.MAX_ISSUES:
                break

        if sec.issues:
            sec.status = "fail"
        return sec

    # ----------------------------------------------------------------
    # Sub-check: abstrak ID dan abstract EN
    # ----------------------------------------------------------------

    def _check_abstract(self, lang: str, bab1_idx: Optional[int]) -> FormatCheckSection:
        """
        lang='id': Abstrak Indonesia — TNR 11pt, ≤250 kata.
        lang='en': Abstract English  — TNR 11pt, miring (italic), ≤250 kata.
        Kata-kata kunci juga wajib TNR 11pt (dicek terpisah dari word count).
        """
        is_id = lang == "id"
        label = "Abstrak (Indonesia)" if is_id else "Abstract (English)"
        kw_label = "Kata-kata kunci" if is_id else "Keywords"
        sec = FormatCheckSection(name=f"abstract_{lang}_format", status="pass")

        start_re = self._ABSTRAK_ID_RE if is_id else self._ABSTRACT_EN_RE
        stop_re = self._ABSTRACT_EN_RE if is_id else None

        in_abstract = False
        content_paras: list[ParagraphInfo] = []
        keyword_paras: list[ParagraphInfo] = []

        for para in self._front_matter(bab1_idx):
            text = para.text.strip()
            if not text:
                continue
            if not in_abstract:
                if start_re.match(text):
                    in_abstract = True
                continue
            if stop_re and stop_re.match(text):
                break
            if self._KATA_KUNCI_RE.match(text):
                keyword_paras.append(para)
                continue
            content_paras.append(para)

        if not content_paras:
            sev = "fail" if is_id else "warning"
            sec.issues.append(FormatIssue(
                check_name=f"abstract_{lang}_missing",
                severity=sev,
                location="Front matter",
                issue=f"{label} tidak ditemukan. Heading '{('Abstrak' if is_id else 'Abstract')}' diperlukan.",
            ))
            sec.status = sev
            return sec

        # Word count (tidak termasuk baris kata kunci)
        full_text = " ".join(p.text for p in content_paras)
        word_count = len(full_text.split())
        sec.detail = {"word_count": word_count}
        if word_count > 250:
            sec.issues.append(FormatIssue(
                check_name=f"abstract_{lang}_word_count",
                severity="fail",
                location=label,
                issue=f"{label} melebihi 250 kata ({word_count} kata).",
                found=str(word_count),
                expected="Maksimal 250 kata",
            ))

        # Justify: paragraf konten abstrak wajib rata kiri-kanan (PDF panduan §C.4).
        # alignment None = inherit dari style — skip (tidak bisa pasti).
        non_justify_align: Optional[str] = None
        for para in content_paras:
            if para.alignment is None:
                continue
            if para.alignment != "justify":
                non_justify_align = para.alignment
                break
        if non_justify_align is not None:
            sec.issues.append(FormatIssue(
                check_name=f"abstract_{lang}_alignment",
                severity="fail",
                location=label,
                issue=f"{label} harus rata kiri-kanan (justify).",
                found=non_justify_align,
                expected="justify",
            ))

        # Font & italic — cek per run (run override > paragraph default)
        for para in content_paras:
            para_font = self.resolver.resolve_paragraph_font(para.index)
            snippet = para.text.strip()[:60]

            bad_name: Optional[str] = None
            bad_size: Optional[float] = None
            for run in para.runs:
                if not run.text.strip():
                    continue
                if any(ord(c) > 127 for c in run.text):
                    continue
                eff_name = run.font_name if run.font_name else para_font.name
                eff_size = run.font_size_pt if run.font_size_pt is not None else para_font.size_pt
                if eff_name and eff_name != "Times New Roman" and bad_name is None:
                    bad_name = eff_name
                if eff_size is not None and abs(eff_size - 11.0) > 0.3 and bad_size is None:
                    bad_size = eff_size

            if bad_name:
                sec.issues.append(FormatIssue(
                    check_name=f"abstract_{lang}_font_name",
                    severity="fail",
                    location=label,
                    issue=f"Font {label} bukan Times New Roman — \"{snippet}\"",
                    found=bad_name,
                    expected="Times New Roman",
                ))
                break
            if bad_size is not None:
                sec.issues.append(FormatIssue(
                    check_name=f"abstract_{lang}_font_size",
                    severity="fail",
                    location=label,
                    issue=f"Ukuran font {label} bukan 11pt — \"{snippet}\"",
                    found=f"{bad_size}pt",
                    expected="11pt",
                ))
                break

        # Abstract EN wajib FULL italic: setiap run terlihat harus italic.
        # Pakai italic ter-resolve dari style chain (tanpa pPr/rPr penanda paragraf)
        # agar italic via style juga terbaca, bukan hanya per run.
        if not is_id:
            for para in content_paras:
                non_italic_snippet: Optional[str] = None
                for ri, run in enumerate(para.runs):
                    if not run.text.strip():
                        continue
                    if self.resolver.resolve_run_italic(para.index, ri) is not True:
                        non_italic_snippet = run.text.strip()[:60]
                        break
                if non_italic_snippet is not None:
                    sec.issues.append(FormatIssue(
                        check_name="abstract_en_italic",
                        severity="fail",
                        location=label,
                        issue=f"Abstract (English) harus dicetak miring (italic) sepenuhnya — \"{non_italic_snippet}\"",
                        found="ada teks tidak italic",
                        expected="italic penuh",
                    ))
                    break

        # Font kata-kata kunci / keywords — wajib TNR 11pt
        for para in keyword_paras:
            para_font = self.resolver.resolve_paragraph_font(para.index)
            snippet = para.text.strip()[:60]

            bad_name = None
            bad_size = None
            for run in para.runs:
                if not run.text.strip():
                    continue
                if any(ord(c) > 127 for c in run.text):
                    continue
                eff_name = run.font_name if run.font_name else para_font.name
                eff_size = run.font_size_pt if run.font_size_pt is not None else para_font.size_pt
                if eff_name and eff_name != "Times New Roman" and bad_name is None:
                    bad_name = eff_name
                if eff_size is not None and abs(eff_size - 11.0) > 0.3 and bad_size is None:
                    bad_size = eff_size

            if bad_name:
                sec.issues.append(FormatIssue(
                    check_name=f"keywords_{lang}_font_name",
                    severity="fail",
                    location=kw_label,
                    issue=f"Font {kw_label} bukan Times New Roman — \"{snippet}\"",
                    found=bad_name,
                    expected="Times New Roman",
                ))
            if bad_size is not None:
                sec.issues.append(FormatIssue(
                    check_name=f"keywords_{lang}_font_size",
                    severity="fail",
                    location=kw_label,
                    issue=f"Ukuran font {kw_label} bukan 11pt — \"{snippet}\"",
                    found=f"{bad_size}pt",
                    expected="11pt",
                ))

        if sec.issues:
            sec.status = "fail"
        return sec

    # ----------------------------------------------------------------
    # Sub-check: spasi baris front matter (1.0)
    # ----------------------------------------------------------------

    def _check_front_matter_spacing(self, bab1_idx: Optional[int]) -> FormatCheckSection:
        sec = FormatCheckSection(name="front_matter_spacing", status="pass")
        tol = 0.05
        bad_values: list[float] = []

        for para in self._front_matter(bab1_idx):
            if not para.text.strip():
                continue
            ls = para.line_spacing
            if ls is None:
                continue
            if abs(ls - 1.0) > tol:
                bad_values.append(ls)

        if bad_values:
            sample = bad_values[0]
            sec.issues.append(FormatIssue(
                check_name="front_matter_spacing",
                severity="fail",
                location="Front matter",
                issue=f"Spasi baris front matter harus 1.0 (ditemukan {sample}).",
                found=str(sample),
                expected="1.0",
            ))
            sec.status = "fail"

        return sec

    # ----------------------------------------------------------------
    # Sub-check: heading 7 section wajib TNR 12 cetak tebal
    # ----------------------------------------------------------------

    def _check_section_headings(self, bab1_idx: Optional[int]) -> FormatCheckSection:
        """
        Aturan PKM-AI: heading Pendahuluan, Metode, Hasil dan Pembahasan,
        Kesimpulan, Ucapan Terima Kasih, Kontribusi Penulis, Daftar Pustaka
        wajib ditulis dengan Times New Roman 12 cetak tebal.

        Strategi pencarian heading: fullmatch teks paragraf (setelah strip nomor
        prefix opsional dan whitespace) ke pola — heading section selalu berdiri
        sendiri, tidak akan match paragraf body yang berisi kalimat panjang.
        """
        sec = FormatCheckSection(name="section_headings", status="pass")
        if bab1_idx is None:
            return sec

        found: dict[str, ParagraphInfo] = {}
        for para in self.parser.paragraphs:
            if para.index < bab1_idx:
                continue
            text = self._HEADING_NUM_PREFIX_RE.sub("", para.text.strip()).strip()
            if not text or len(text) > 60:
                continue
            for canon, pat in self._SECTION_HEADING_PATTERNS:
                if canon in found:
                    continue
                if pat.fullmatch(text):
                    found[canon] = para
                    break

        for canon, para in found.items():
            bad_bold = False
            bad_font: Optional[str] = None
            bad_size: Optional[float] = None
            for ri, run in enumerate(para.runs):
                if not run.text.strip():
                    continue
                if self.resolver.resolve_run_bold(para.index, ri) is not True:
                    bad_bold = True
                # Font/size lewat resolver lengkap (boleh inherit dari style)
                rf = self.resolver.resolve_run_font(para.index, ri)
                # Lewati run dengan karakter non-ASCII (substitusi font Word).
                if any(ord(c) > 127 for c in run.text):
                    continue
                if rf.name and rf.name != "Times New Roman" and bad_font is None:
                    bad_font = rf.name
                if (
                    rf.size_pt is not None
                    and abs(rf.size_pt - 12.0) > 0.3
                    and bad_size is None
                ):
                    bad_size = rf.size_pt

            if bad_bold:
                sec.issues.append(FormatIssue(
                    check_name="heading_bold",
                    severity="fail",
                    location=f"Heading {canon}",
                    issue=f"Heading '{canon}' wajib dicetak tebal (bold).",
                    found="tidak bold",
                    expected="bold",
                ))
            if bad_font:
                sec.issues.append(FormatIssue(
                    check_name="heading_font_name",
                    severity="fail",
                    location=f"Heading {canon}",
                    issue=f"Font heading '{canon}' bukan Times New Roman.",
                    found=bad_font,
                    expected="Times New Roman",
                ))
            if bad_size is not None:
                sec.issues.append(FormatIssue(
                    check_name="heading_font_size",
                    severity="fail",
                    location=f"Heading {canon}",
                    issue=f"Ukuran font heading '{canon}' bukan 12pt.",
                    found=f"{bad_size}pt",
                    expected="12pt",
                ))
            if len(sec.issues) >= self.MAX_ISSUES:
                break

        if sec.issues:
            sec.status = "fail"
        sec.detail = {"headings_found": list(found.keys())}
        return sec

    # ----------------------------------------------------------------
    # Sub-check: posisi caption (Tabel di atas, Gambar di bawah)
    # ----------------------------------------------------------------

    def _check_caption_positions(self, bab1_idx: Optional[int]) -> FormatCheckSection:
        """
        PDF panduan §3 PKM-AI: keterangan tabel diletakkan di ATAS tabel,
        keterangan gambar diletakkan di BAWAH gambar. Validasi berdasarkan
        urutan blok body (<w:p> dan <w:tbl>), serta deteksi <w:drawing>/<w:pict>
        di dalam paragraf gambar.
        """
        sec = FormatCheckSection(name="caption_positions", status="pass")
        if bab1_idx is None:
            return sec

        blocks = self._iter_body_blocks()
        if not blocks:
            return sec

        def is_meaningful(b: dict) -> bool:
            if b["kind"] == "tbl":
                return True
            if b["kind"] == "p":
                return bool(b["text"].strip()) or b["has_image"]
            return False

        def next_meaningful(i: int) -> Optional[int]:
            for j in range(i + 1, min(len(blocks), i + 6)):
                if is_meaningful(blocks[j]):
                    return j
            return None

        def prev_meaningful(i: int) -> Optional[int]:
            for j in range(i - 1, max(-1, i - 6), -1):
                if is_meaningful(blocks[j]):
                    return j
            return None

        for i, b in enumerate(blocks):
            if b["kind"] != "p" or b["para_idx"] is None or b["para_idx"] < bab1_idx:
                continue
            text = b["text"].strip()
            if not text:
                continue
            snippet = text[:60] + ("…" if len(text) > 60 else "")
            if self._TBL_CAPTION_RE.match(text):
                # Keterangan tabel WAJIB di atas tabel.
                nxt = next_meaningful(i)
                prv = prev_meaningful(i)
                next_is_tbl = nxt is not None and blocks[nxt]["kind"] == "tbl"
                prev_is_tbl = prv is not None and blocks[prv]["kind"] == "tbl"
                if not next_is_tbl and prev_is_tbl:
                    sec.issues.append(FormatIssue(
                        check_name="caption_table_position",
                        severity="fail",
                        location=f"paragraf #{b['para_idx']}",
                        issue=f"Keterangan tabel berada di bawah tabel — \"{snippet}\". Wajib di ATAS tabel.",
                        found="di bawah tabel",
                        expected="di atas tabel",
                    ))
            elif self._FIG_CAPTION_RE.match(text):
                # Keterangan gambar WAJIB di bawah gambar.
                nxt = next_meaningful(i)
                prv = prev_meaningful(i)
                prev_has_image = (
                    prv is not None
                    and blocks[prv]["kind"] == "p"
                    and blocks[prv]["has_image"]
                )
                next_has_image = (
                    nxt is not None
                    and blocks[nxt]["kind"] == "p"
                    and blocks[nxt]["has_image"]
                )
                if not prev_has_image and next_has_image:
                    sec.issues.append(FormatIssue(
                        check_name="caption_figure_position",
                        severity="fail",
                        location=f"paragraf #{b['para_idx']}",
                        issue=f"Keterangan gambar berada di atas gambar — \"{snippet}\". Wajib di BAWAH gambar.",
                        found="di atas gambar",
                        expected="di bawah gambar",
                    ))
            if len(sec.issues) >= self.MAX_ISSUES:
                break

        if sec.issues:
            sec.status = "fail"
        return sec

    def _iter_body_blocks(self) -> list[dict]:
        """Walk anak-langsung <w:body> sesuai urutan dokumen. Sinkron dengan
        konvensi indexing parser: paragraph_index hanya naik untuk <w:p>
        anak-langsung body (tidak masuk paragraf dalam tabel)."""
        body = self.parser.doc.element.body

        def q(tag: str) -> str:
            return f"{{{self._W_NS}}}{tag}"

        blocks: list[dict] = []
        para_counter = -1
        tbl_counter = -1
        for child in body:
            tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
            if tag == "p":
                para_counter += 1
                text = "".join((t.text or "") for t in child.iter(q("t")))
                has_image = (
                    child.find(".//" + q("drawing")) is not None
                    or child.find(".//" + q("pict")) is not None
                )
                blocks.append({
                    "kind": "p", "para_idx": para_counter, "tbl_idx": None,
                    "text": text, "has_image": has_image,
                })
            elif tag == "tbl":
                tbl_counter += 1
                blocks.append({
                    "kind": "tbl", "para_idx": None, "tbl_idx": tbl_counter,
                    "text": "", "has_image": False,
                })
            else:
                # sdt, sectPr, lainnya — tetap masuk daftar agar urutan tidak hilang,
                # tapi ditandai not meaningful untuk neighbor logic.
                blocks.append({
                    "kind": tag, "para_idx": None, "tbl_idx": None,
                    "text": "", "has_image": False,
                })
        return blocks
