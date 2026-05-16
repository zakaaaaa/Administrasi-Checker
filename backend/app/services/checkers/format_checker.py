"""
FormatChecker — modul pengecek format penulisan sesuai blueprint v0.3 §4.3.

Yang dicek:
1. Font: Times New Roman 12pt (di body teks)
2. Margin: kiri 4cm, kanan/atas/bawah 3cm (toleransi ±0.05cm)
3. Paper size: A4 (21.0 × 29.7 cm)
4. Line spacing: 1.15
5. Alignment: justify untuk paragraf body (kecuali heading, paragraf pendek,
   dan caption Gambar/Tabel yang umumnya rata tengah)
6. (tambahan) Deteksi bahasa asing umum yang tidak italic

Catatan:
- Validasi nomor halaman (TNR 12pt, posisi pojok kanan atas/bawah, romawi vs
  arab per zona) ada di MODUL TERPISAH PageNumberingChecker (modul 5),
  karena butuh parsing header/footer XML yang berbeda. FormatChecker hanya
  cek format BODY teks.
- StructureChecker sudah cek heading; FormatChecker tidak duplikasi itu.

Input:
    - DocxParser
    - SchemaRules (untuk aturan format spesifik skema)

Output:
    - FormatCheckResult dengan to_dict() siap simpan ke check_results.format_result
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

from app.services.core.base_rules import FormatRules, SchemaRules, get_pkm_format_rules
from app.services.core.docx_parser import DocxParser, dxa_to_cm
from app.services.core.message_format import format_finding
from app.services.core.style_resolver import StyleResolver


# ============================================================================
# Foreign words dictionary (untuk deteksi italic violation)
# ============================================================================
#
# Daftar kata/frasa asing umum dalam konteks akademik PKM.
# Kalau kata-kata ini muncul di teks dan TIDAK italic → flag warning.


FOREIGN_WORDS = {
    # Tech / IoT
    "internet of things", "machine learning", "deep learning", "artificial intelligence",
    "smart farming", "smart city", "big data", "cloud computing", "open source",
    "real time", "real-time", "user interface", "user experience",
    # Penelitian / metode
    "literature review", "case study", "purposive sampling", "random sampling",
    "in vivo", "in vitro", "in situ", "ex situ",
    # Bahasa Latin / akademik
    "et cetera", "id est", "exempli gratia", "circa", "versus",
    "a priori", "a posteriori", "ad hoc", "de facto", "de jure",
    "status quo", "vice versa", "per se", "ipso facto",
    # Statistik / publikasi
    "p-value", "open access",
    # Bisnis (untuk PKM-K)
    "marketing", "branding", "startup", "stakeholder",
    "feedback", "endorsement", "ads", "online", "offline",
}

# Caption gambar/tabel (sering center / bukan justify). Hanya pola awal baris
# + batas panjang supaya paragraf body yang kebetulan diawali "Tabel 1 ..."
# tidak terkecualikan seluruhnya.
_MAX_CAPTION_PARAGRAPH_CHARS = 280
_CAPTION_HEAD_RE = re.compile(
    r"^\s*(?:"
    r"Gambar|Gbr\.?"
    r"|Figure|Fig\.?"
    r"|Tabel|Table"
    r"|Diagram|Foto|Chart|Grafik"
    r")\s*"
    r"(?:\d{1,3}[a-z]?|[IVXLCDM]{1,8})\b"
    r"\s*[.:)\-–—]?\s*",
    re.IGNORECASE | re.UNICODE,
)


def _is_figure_table_caption_paragraph(text: str) -> bool:
    """True jika paragraf tampak seperti satu baris caption gambar/tabel."""
    stripped = text.strip()
    if not stripped or len(stripped) > _MAX_CAPTION_PARAGRAPH_CHARS:
        return False
    return bool(_CAPTION_HEAD_RE.match(stripped))


# ============================================================================
# Data classes hasil
# ============================================================================


@dataclass
class FormatIssue:
    """Satu pelanggaran format."""
    check_name: str   # 'font' | 'margin' | 'paper_size' | 'line_spacing' | ...
    severity: str     # 'fail' | 'warning'
    location: str     # legacy: dipertahankan di payload untuk back-compat
    issue: str
    found: Optional[str] = None
    expected: Optional[str] = None
    page: Optional[int] = None     # halaman fisik (1-based) untuk format pesan baru


@dataclass
class FormatCheckSection:
    """Hasil pengecekan satu sub-area (font, margin, dll)."""
    name: str
    status: str        # 'pass' | 'warning' | 'fail'
    issues: list[FormatIssue] = field(default_factory=list)
    detail: dict = field(default_factory=dict)


@dataclass
class CheckMessage:
    level: str
    text: str


@dataclass
class FormatCheckResult:
    status: str
    checks: dict[str, FormatCheckSection] = field(default_factory=dict)
    messages: list[CheckMessage] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "checks": {
                name: {
                    "status": sec.status,
                    "issues": [
                        {
                            "check_name": i.check_name,
                            "severity": i.severity,
                            "location": i.location,
                            "issue": i.issue,
                            "found": i.found,
                            "expected": i.expected,
                        }
                        for i in sec.issues
                    ],
                    "detail": sec.detail,
                }
                for name, sec in self.checks.items()
            },
            "messages": [{"level": m.level, "text": m.text} for m in self.messages],
        }


# ============================================================================
# FormatChecker
# ============================================================================


class FormatChecker:
    """
    Checker format dokumen.

    Usage:
        parser = DocxParser('proposal.docx')
        rules = get_pkm_format_rules()
        result = FormatChecker(parser, rules).check()
    """

    # Limit: berapa banyak issue per kategori yang di-report (avoid spam)
    MAX_ISSUES_PER_CATEGORY = 10

    def __init__(
        self,
        parser: DocxParser,
        rules: Optional[FormatRules] = None,
        schema: Optional[SchemaRules] = None,
        enabled_checks: Optional[set[str]] = None,
    ):
        self.parser = parser
        self.rules = rules or get_pkm_format_rules()
        self.schema = schema  # opsional, untuk skip pengecekan tertentu nanti
        self.resolver = StyleResolver(parser)
        # None = jalankan semua sub-check (default, PKM-KC). Set = whitelist
        # sub-check yang aktif (mis. PKM-AI: hanya {"paper_size","margin"}
        # karena sisanya divalidasi AiFormatChecker dengan aturan per-zona).
        self.enabled_checks = enabled_checks

    def _enabled(self, name: str) -> bool:
        return self.enabled_checks is None or name in self.enabled_checks

    def _page_of(self, paragraph_index: int) -> Optional[int]:
        """Estimasi halaman fisik (1-based) dari paragraph index. None kalau tak bisa."""
        estimator = getattr(self.parser, "estimate_physical_page", None)
        if not callable(estimator):
            return None
        try:
            raw = estimator(paragraph_index)
        except Exception:
            return None
        return raw if isinstance(raw, int) else None

    def _format_para_location(self, paragraph_index: int) -> str:
        """Legacy string location — dipakai di FormatIssue.location untuk back-compat payload."""
        page = self._page_of(paragraph_index)
        return f"Halaman {page}" if page is not None else "Halaman -"

    def check(self) -> FormatCheckResult:
        result = FormatCheckResult(status="pass")

        # Jalankan tiap sub-check (skip kalau enabled_checks membatasi)
        if self._enabled("paper_size"):
            result.checks["paper_size"] = self._check_paper_size()
        if self._enabled("margin"):
            result.checks["margin"] = self._check_margin()
        if self._enabled("font_body"):
            result.checks["font_body"] = self._check_font_body()
        if self._enabled("line_spacing"):
            result.checks["line_spacing"] = self._check_line_spacing()
        if self.rules.require_justify and self._enabled("alignment"):
            result.checks["alignment"] = self._check_alignment()
        if self._enabled("foreign_words_italic"):
            result.checks["foreign_words_italic"] = self._check_foreign_words_italic()

        # Aggregate status
        statuses = [s.status for s in result.checks.values()]
        if "fail" in statuses:
            result.status = "fail"
        elif "warning" in statuses:
            result.status = "warning"
        else:
            result.status = "pass"

        # Bangun summary messages
        for name, sec in result.checks.items():
            if sec.status == "pass":
                result.messages.append(
                    CheckMessage(level="pass", text=f"{name}: OK")
                )
            else:
                # Detail per issue dalam format 3-bagian.
                # Summary count tidak ditambahkan agar pesan tidak duplikatif
                # — frontend bisa hitung sendiri dari jumlah message.
                shown = sec.issues[: self.MAX_ISSUES_PER_CATEGORY]
                more = len(sec.issues) - len(shown)
                for issue in shown:
                    perbaikan = issue.expected or "perbaiki sesuai aturan"
                    result.messages.append(
                        CheckMessage(
                            level=issue.severity,
                            text=format_finding(issue.page, issue.issue, perbaikan),
                        )
                    )
                if more > 0:
                    result.messages.append(
                        CheckMessage(
                            level=sec.status,
                            text=format_finding(
                                None,
                                f"{name}: masih ada {more} pelanggaran serupa yang tidak ditampilkan",
                                f"perbaiki semua pelanggaran {name} agar lulus",
                            ),
                        )
                    )

        return result

    # ------------------------------------------------------------------------
    # Sub-check: paper size
    # ------------------------------------------------------------------------

    def _check_paper_size(self) -> FormatCheckSection:
        sec = FormatCheckSection(name="paper_size", status="pass")
        tol = self.rules.paper_tolerance_cm
        for s in self.parser.sections:
            w_cm = dxa_to_cm(s.page_width_dxa)
            h_cm = dxa_to_cm(s.page_height_dxa)
            if w_cm is None or h_cm is None:
                continue
            ok = (
                abs(w_cm - self.rules.paper_width_cm) <= tol
                and abs(h_cm - self.rules.paper_height_cm) <= tol
            )
            if not ok:
                sec.issues.append(
                    FormatIssue(
                        check_name="paper_size",
                        severity="fail",
                        location="Halaman -",
                        issue=f"ukuran kertas {w_cm}×{h_cm} cm, bukan A4",
                        found=f"{w_cm}×{h_cm} cm",
                        expected=f"ubah ukuran kertas ke A4 ({self.rules.paper_width_cm}×{self.rules.paper_height_cm} cm)",
                        page=None,
                    )
                )
        if sec.issues:
            sec.status = "fail"
        sec.detail = {
            "expected_w_cm": self.rules.paper_width_cm,
            "expected_h_cm": self.rules.paper_height_cm,
            "section_count": len(self.parser.sections),
            "violations_count": len(sec.issues),
        }
        return sec

    # ------------------------------------------------------------------------
    # Sub-check: margin
    # ------------------------------------------------------------------------

    def _check_margin(self) -> FormatCheckSection:
        sec = FormatCheckSection(name="margin", status="pass")
        tol = self.rules.margin_tolerance_cm
        expected = {
            "left": self.rules.margin_left_cm,
            "right": self.rules.margin_right_cm,
            "top": self.rules.margin_top_cm,
            "bottom": self.rules.margin_bottom_cm,
        }
        for s in self.parser.sections:
            actual = {
                "left": dxa_to_cm(s.margin_left_dxa),
                "right": dxa_to_cm(s.margin_right_dxa),
                "top": dxa_to_cm(s.margin_top_dxa),
                "bottom": dxa_to_cm(s.margin_bottom_dxa),
            }
            for side, exp in expected.items():
                act = actual[side]
                if act is None:
                    continue
                if abs(act - exp) > tol:
                    sec.issues.append(
                        FormatIssue(
                            check_name="margin",
                            severity="fail",
                            location="Halaman -",
                            issue=f"margin {side} {act} cm, tidak sesuai aturan PKM",
                            found=f"{act} cm",
                            expected=f"ubah margin {side} ke {exp} cm (toleransi ±{tol} cm)",
                            page=None,
                        )
                    )
        if sec.issues:
            sec.status = "fail"
        sec.detail = {
            "expected": expected,
            "tolerance_cm": tol,
            "violations_count": len(sec.issues),
        }
        return sec

    # ------------------------------------------------------------------------
    # Sub-check: font body
    # ------------------------------------------------------------------------

    def _check_font_body(self) -> FormatCheckSection:
        """
        Cek font seluruh body. Skip:
        - Paragraf di dalam tabel (bisa ada penyesuaian formatting wajar)
        - Heading (style bisa pakai font berbeda by design)
        - Paragraf kosong
        """
        sec = FormatCheckSection(name="font_body", status="pass")
        font_distribution: dict[str, int] = {}
        size_distribution: dict[float, int] = {}

        for para in self.parser.paragraphs:
            if not para.text.strip():
                continue
            if para.is_heading:
                continue
            if _is_figure_table_caption_paragraph(para.text.strip()):
                continue

            checked_any_run = False
            reported_font_name = False
            reported_font_size = False
            for run_index, run in enumerate(para.runs):
                if not run.text.strip():
                    continue

                checked_any_run = True
                font = self.resolver.resolve_run_font(para.index, run_index)

                if font.name:
                    font_distribution[font.name] = font_distribution.get(font.name, 0) + 1
                if font.size_pt is not None:
                    size_distribution[font.size_pt] = size_distribution.get(font.size_pt, 0) + 1

                if (
                    font.name
                    and font.name != self.rules.font_name
                    and not reported_font_name
                ):
                    sec.issues.append(
                        FormatIssue(
                            check_name="font_name",
                            severity="fail",
                            location=self._format_para_location(para.index),
                            page=self._page_of(para.index),
                            issue=f"Font bukan {self.rules.font_name}.",
                            found=font.name,
                            expected=self.rules.font_name,
                        )
                    )
                    reported_font_name = True

                if (
                    font.size_pt is not None
                    and abs(font.size_pt - self.rules.font_size_pt)
                    > self.rules.font_size_tolerance_pt
                    and not reported_font_size
                ):
                    tol = self.rules.font_size_tolerance_pt
                    lo = round(self.rules.font_size_pt - tol, 2)
                    hi = round(self.rules.font_size_pt + tol, 2)
                    sec.issues.append(
                        FormatIssue(
                            check_name="font_size",
                            severity="fail",
                            location=self._format_para_location(para.index),
                            page=self._page_of(para.index),
                            issue=f"Ukuran font di luar rentang {lo}-{hi}pt.",
                            found=f"{font.size_pt}pt",
                            expected=f"{self.rules.font_size_pt}pt (toleransi +/-{tol}pt, rentang {lo}-{hi}pt)",
                        )
                    )
                    reported_font_size = True
            if not checked_any_run:
                font = self.resolver.resolve_paragraph_font(para.index)
                if font.name:
                    font_distribution[font.name] = font_distribution.get(font.name, 0) + 1
                if font.size_pt is not None:
                    size_distribution[font.size_pt] = size_distribution.get(font.size_pt, 0) + 1

        if sec.issues:
            sec.status = "fail"
        tol = self.rules.font_size_tolerance_pt
        sec.detail = {
            "font_distribution": dict(sorted(font_distribution.items(), key=lambda x: -x[1])),
            "size_distribution": dict(sorted(size_distribution.items(), key=lambda x: -x[1])),
            "violations_count": len(sec.issues),
            "expected_font": self.rules.font_name,
            "expected_size_pt": self.rules.font_size_pt,
            "font_size_tolerance_pt": tol,
            "acceptable_size_range": f"{round(self.rules.font_size_pt - tol, 2)}–{round(self.rules.font_size_pt + tol, 2)}pt",
        }
        return sec

    # ------------------------------------------------------------------------
    # Sub-check: line spacing
    # ------------------------------------------------------------------------

    def _check_line_spacing(self) -> FormatCheckSection:
        sec = FormatCheckSection(name="line_spacing", status="pass")
        tol = self.rules.line_spacing_tolerance
        spacing_distribution: dict[float, int] = {}
        for para in self.parser.paragraphs:
            if not para.text.strip():
                continue
            if para.is_heading:
                continue
            if _is_figure_table_caption_paragraph(para.text.strip()):
                continue
            ls = para.line_spacing
            if ls is None:
                continue
            spacing_distribution[ls] = spacing_distribution.get(ls, 0) + 1
            if abs(ls - self.rules.line_spacing) > tol:
                sec.issues.append(
                    FormatIssue(
                        check_name="line_spacing",
                        severity="warning",  # warning karena banyak dokumen pakai 1.5 / 2.0
                        location=self._format_para_location(para.index),
                        page=self._page_of(para.index),
                        issue=f"Line spacing bukan {self.rules.line_spacing}.",
                        found=str(ls),
                        expected=str(self.rules.line_spacing),
                    )
                )
        if sec.issues:
            sec.status = "warning"
        sec.detail = {
            "expected": self.rules.line_spacing,
            "tolerance": tol,
            "spacing_distribution": dict(
                sorted(spacing_distribution.items(), key=lambda x: -x[1])
            ),
            "violations_count": len(sec.issues),
        }
        return sec

    # ------------------------------------------------------------------------
    # Sub-check: alignment (justify)
    # ------------------------------------------------------------------------

    def _check_alignment(self) -> FormatCheckSection:
        """
        Body teks PKM wajib justify. Skip:
        - Heading (biasanya center)
        - Paragraf pendek <30 char (judul tabel/gambar, dll)
        - Satu baris caption Gambar/Figure/Tabel/… (umumnya center, bukan justify)
        """
        sec = FormatCheckSection(name="alignment", status="pass")
        for para in self.parser.paragraphs:
            text = para.text.strip()
            if len(text) < 30:
                continue
            if para.is_heading:
                continue
            if _is_figure_table_caption_paragraph(text):
                continue
            align = para.alignment
            # python-docx return 'left'/'right'/'center'/'justify' atau None
            # None = inherit dari style (biasanya left untuk Normal)
            if align is None:
                # Nilai None = inherit style; tanpa resolver alignment style, ini ambigu.
                # Supaya tidak false-positive ("halu"), skip dari pelanggaran.
                continue
            elif align != "justify":
                sec.issues.append(
                    FormatIssue(
                        check_name="alignment",
                        severity="fail",
                        location=self._format_para_location(para.index),
                        page=self._page_of(para.index),
                        issue="Paragraf body bukan justify.",
                        found=align,
                        expected="justify",
                    )
                )
        if sec.issues:
            # Status warning kalau hanya inherit; fail kalau ada yang explicit non-justify
            has_fail = any(i.severity == "fail" for i in sec.issues)
            sec.status = "fail" if has_fail else "warning"
        sec.detail = {
            "violations_count": len(sec.issues),
        }
        return sec

    # ------------------------------------------------------------------------
    # Sub-check: foreign words italic
    # ------------------------------------------------------------------------

    def _check_foreign_words_italic(self) -> FormatCheckSection:
        """
        Untuk tiap kata/frasa asing di FOREIGN_WORDS yang muncul di body teks,
        cek apakah run yang memuatnya italic. Kalau tidak → warning.

        Pendekatan sederhana (Phase 1):
        - Gabung text run dalam satu paragraf
        - Cari pola foreign word (case-insensitive, word boundary)
        - Cek run yang overlap dengan posisi match: harus italic minimal salah satu

        Catatan: cara yang lebih rigorous butuh map char-to-run; untuk Phase 1
        cukup cek apakah ADA run italic di paragraf yang memuat kata asing.
        """
        sec = FormatCheckSection(name="foreign_words_italic", status="pass")
        # Compile regex untuk semua kata asing sekaligus
        patterns = [
            (word, re.compile(r"\b" + re.escape(word) + r"\b", re.IGNORECASE))
            for word in FOREIGN_WORDS
        ]

        for para in self.parser.paragraphs:
            text = para.text
            if not text.strip():
                continue
            # Skip heading & ToC entries
            if para.is_heading:
                continue
            # Cari kata asing
            matched_words = []
            for word, pat in patterns:
                if pat.search(text):
                    matched_words.append(word)
            if not matched_words:
                continue

            pattern_map = dict(patterns)
            spans = self._run_text_spans(para)
            bad_words = [
                word
                for word in matched_words
                if not any(
                    self._match_is_fully_italic(
                        para.index, match.start(), match.end(), spans
                    )
                    for match in pattern_map[word].finditer(text)
                )
            ]
            if bad_words:
                sec.issues.append(
                    FormatIssue(
                        check_name="foreign_words_italic",
                        severity="warning",
                        location=self._format_para_location(para.index),
                        page=self._page_of(para.index),
                        issue=(
                            f"Paragraf memuat kata/frasa asing "
                            f"({', '.join(bad_words[:3])}) tapi tidak ditulis italic. "
                            f"Bahasa asing wajib italic."
                        ),
                        found="tidak italic",
                        expected="italic",
                    )
                )

        if sec.issues:
            sec.status = "warning"
        sec.detail = {"violations_count": len(sec.issues)}
        return sec

    @staticmethod
    def _run_text_spans(para) -> list[tuple[int, int, int, str]]:
        """Return (start, end, run_index, text) untuk memetakan match ke run."""
        spans: list[tuple[int, int, int, str]] = []
        cursor = 0
        for run_index, run in enumerate(para.runs):
            text = run.text or ""
            start = cursor
            cursor += len(text)
            spans.append((start, cursor, run_index, text))
        return spans

    def _match_is_fully_italic(
        self,
        paragraph_index: int,
        start: int,
        end: int,
        spans: list[tuple[int, int, int, str]],
    ) -> bool:
        """
        True jika semua run yang memuat karakter non-spasi dalam match sudah
        italic efektif. Frasa yang split antar-run tetap dicek dengan benar.
        """
        touched = False
        for run_start, run_end, run_index, run_text in spans:
            if run_end <= start or run_start >= end:
                continue
            local_start = max(start, run_start) - run_start
            local_end = min(end, run_end) - run_start
            if not run_text[local_start:local_end].strip():
                continue
            touched = True
            font = self.resolver.resolve_run_font(paragraph_index, run_index)
            if font.italic is not True:
                return False
        return touched
