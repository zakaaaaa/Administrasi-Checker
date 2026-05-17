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

from app.services.docx_parser import DocxParser, dxa_to_cm
from app.services.schema_rules import SchemaRules
from app.services.style_resolver import StyleResolver


# ============================================================================
# Aturan format default (mengikuti blueprint §3.3 untuk PKM)
# ============================================================================
#
# Nantinya ini akan di-pull dari kolom `competition_schemas` di Supabase.
# Untuk Phase 1, kita pakai default PKM yang sama untuk semua skema PKM.


@dataclass
class FormatRules:
    font_name: str = "Times New Roman"
    font_size_pt: float = 12.0
    font_size_tolerance_pt: float = 0.3   # 11.7–12.3 diterima
    margin_left_cm: float = 4.0
    margin_right_cm: float = 3.0
    margin_top_cm: float = 3.0
    margin_bottom_cm: float = 3.0
    margin_tolerance_cm: float = 0.05
    paper_width_cm: float = 21.0      # A4
    paper_height_cm: float = 29.7
    paper_tolerance_cm: float = 0.1
    line_spacing: float = 1.15
    line_spacing_tolerance: float = 0.05
    caption_line_spacing: float = 1.0
    caption_line_spacing_tolerance: float = 0.05
    check_caption_line_spacing: bool = False
    caption_font_size_pt: float = 11.0
    caption_font_size_tolerance_pt: float = 0.3
    check_caption_font_size: bool = False
    require_justify: bool = True


def get_pkm_format_rules() -> FormatRules:
    """Default rules untuk semua skema PKM (sama untuk KC, K, GFT, dll)."""
    return FormatRules()


def get_pkm_ai_format_rules() -> FormatRules:
    """Rules format khusus PKM-AI — line spacing dan font size keterangan gambar/tabel."""
    return FormatRules(check_caption_line_spacing=True, check_caption_font_size=True)


# ============================================================================
# Foreign words dictionary (untuk deteksi italic violation)
# ============================================================================
#
# Daftar kata/frasa asing umum dalam konteks akademik PKM.
# Kalau kata-kata ini muncul di teks dan TIDAK italic → flag warning.


FOREIGN_WORDS = {
    # ----------------------------------------------------------------
    # AI / Machine Learning (PKM-KC, RE)
    # ----------------------------------------------------------------
    "artificial intelligence", "machine learning", "deep learning",
    "natural language processing", "computer vision",
    "neural network", "convolutional neural network",
    "recurrent neural network", "long short-term memory",
    "generative adversarial network", "transformer",
    "transfer learning", "reinforcement learning",
    "support vector machine", "random forest", "gradient boosting",
    "naive bayes", "decision tree", "k-nearest neighbor",
    "principal component analysis", "autoencoder",
    "object detection", "image segmentation", "speech recognition",
    "sentiment analysis", "text mining", "data mining",
    "named entity recognition", "topic modeling",
    "recommendation system", "collaborative filtering",
    "knowledge graph", "fuzzy logic", "genetic algorithm",
    # ----------------------------------------------------------------
    # Teknologi / Sistem / IoT (PKM-KC)
    # ----------------------------------------------------------------
    "internet of things", "edge computing", "cloud computing",
    "blockchain", "big data",
    "augmented reality", "virtual reality", "mixed reality",
    "smart city", "smart farming", "smart agriculture",
    "embedded system", "microcontroller", "printed circuit board",
    "3d printing", "additive manufacturing", "nanotechnology",
    "image processing", "signal processing", "remote sensing",
    "geographic information system", "finite element analysis",
    "renewable energy",
    # ----------------------------------------------------------------
    # Software / Web / Sistem Informasi (PKM-KC, K)
    # ----------------------------------------------------------------
    "software", "hardware", "framework", "open source",
    "website", "web application", "mobile application",
    "user interface", "user experience", "dashboard", "prototype",
    "database", "server", "client", "input", "output",
    "real time", "real-time", "chatbot",
    "online", "offline", "e-commerce", "marketplace",
    "supply chain", "microservices", "devops", "agile", "scrum",
    "usability testing", "user testing", "a/b testing",
    "search engine optimization", "application programming interface",
    # ----------------------------------------------------------------
    # Metodologi Penelitian (PKM-RE, RSH)
    # ----------------------------------------------------------------
    "literature review", "systematic review", "case study",
    "focus group discussion", "action research", "grounded theory",
    "thematic analysis", "content analysis", "discourse analysis",
    "triangulation", "mixed method",
    "purposive sampling", "random sampling", "snowball sampling",
    "cluster sampling", "stratified sampling", "convenience sampling",
    "simple random sampling", "quota sampling",
    "cross-sectional study", "longitudinal study", "cohort study",
    "randomized controlled trial", "double blind",
    "pilot study", "baseline study", "observational study",
    "open access", "peer review",
    # ----------------------------------------------------------------
    # Statistik (PKM-RE, RSH)
    # ----------------------------------------------------------------
    "p-value", "t-test", "chi-square", "one-way anova", "two-way anova",
    "goodness of fit", "effect size", "confidence interval",
    "standard deviation", "mean square error", "root mean square error",
    "regression analysis", "logistic regression", "multiple regression",
    "factor analysis", "structural equation modeling", "path analysis",
    "pearson correlation", "spearman correlation",
    "inter-rater reliability", "cronbach alpha",
    # ----------------------------------------------------------------
    # Kesehatan / Biologi / Lingkungan (PKM-RE, PM, PI)
    # ----------------------------------------------------------------
    "in vivo", "in vitro", "in situ", "ex situ",
    "clinical trial", "randomized controlled trial",
    "placebo", "biomarker", "screening", "follow-up",
    "body mass index", "informed consent", "ethical clearance",
    "point of care", "telemedicine", "wearable",
    "carbon footprint", "sustainability", "biodiversity",
    "ecosystem services", "food security",
    "water treatment", "wastewater treatment",
    "biomass", "biofuel", "biogas",
    "hydroponics", "aquaponics", "vertical farming",
    "precision agriculture",
    # ----------------------------------------------------------------
    # Bisnis / Kewirausahaan (PKM-K)
    # ----------------------------------------------------------------
    "marketing", "branding", "startup", "stakeholder",
    "feedback", "endorsement", "ads",
    "business model", "value proposition",
    "cost benefit analysis", "return on investment",
    "market research", "customer satisfaction",
    "competitive advantage", "product development",
    "supply chain management", "total quality management",
    "key performance indicator", "break even point",
    "cash flow", "business plan", "market share",
    "brand awareness", "target market",
    "digital marketing", "content marketing", "social media marketing",
    "influencer", "copywriting",
    "crowdfunding", "minimum viable product",
    "business-to-business", "business-to-consumer",
    "customer journey", "net promoter score",
    "conversion rate", "click-through rate",
    "outsourcing", "franchising", "dropship", "reseller",
    "launching", "rebranding", "packaging",
    "loyalty program", "omnichannel",
    # ----------------------------------------------------------------
    # Pendidikan (PKM-PM, RSH)
    # ----------------------------------------------------------------
    "blended learning", "e-learning",
    "problem-based learning", "project-based learning",
    "flipped classroom", "learning management system",
    "student-centered learning", "collaborative learning",
    "active learning", "critical thinking",
    "higher order thinking", "self-regulated learning",
    "peer learning",
    # ----------------------------------------------------------------
    # Sosial (PKM-RSH, PM)
    # ----------------------------------------------------------------
    "empowerment", "capacity building", "community development",
    "social capital", "gender mainstreaming",
    # ----------------------------------------------------------------
    # Latin / Akademik
    # ----------------------------------------------------------------
    "et cetera", "id est", "exempli gratia", "circa", "versus",
    "a priori", "a posteriori", "ad hoc", "de facto", "de jure",
    "status quo", "vice versa", "per se", "ipso facto",
    "et al", "nota bene", "ibid", "op cit",
    "bona fide", "prima facie", "caveat", "addendum",
    "curriculum vitae", "ex officio", "pro rata",
    "mutatis mutandis",
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
_KETERANGAN_RE = re.compile(r"^\s*Keterangan\s*:", re.IGNORECASE)


def _is_figure_table_caption_paragraph(text: str) -> bool:
    """True jika paragraf adalah caption gambar/tabel atau keterangan tabel."""
    stripped = text.strip()
    if not stripped or len(stripped) > _MAX_CAPTION_PARAGRAPH_CHARS:
        return False
    return bool(_CAPTION_HEAD_RE.match(stripped)) or bool(_KETERANGAN_RE.match(stripped))


# ============================================================================
# Data classes hasil
# ============================================================================


@dataclass
class FormatIssue:
    """Satu pelanggaran format."""
    check_name: str   # 'font' | 'margin' | 'paper_size' | 'line_spacing' | ...
    severity: str     # 'fail' | 'warning'
    location: str     # mis. "Section #0", "Paragraf #42 run #2"
    issue: str
    found: Optional[str] = None
    expected: Optional[str] = None


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
        pdf_sheet_texts: Optional[list[str]] = None,
    ):
        self.parser = parser
        self.rules = rules or get_pkm_format_rules()
        self.schema = schema  # opsional, untuk skip pengecekan tertentu nanti
        self.resolver = StyleResolver(parser)
        self._pdf_sheet_texts = pdf_sheet_texts  # teks PDF per lembar untuk lokasi akurat

    _LAMPIRAN_RE = re.compile(r"^\s*LAMPIRAN\b", re.IGNORECASE)

    def _find_lampiran_para_index(self, after_idx: Optional[int] = None) -> Optional[int]:
        """Return index paragraf pertama yang merupakan heading LAMPIRAN, atau None.

        Hanya mencari SETELAH after_idx (biasanya Bab 1) sehingga entri
        "Lampiran 1. ..." di Daftar Lampiran (halaman 2-3) tidak di-false-positive.

        Tiga kriteria diterima sebagai heading LAMPIRAN:
        (a) pakai Heading style
        (b) teks pendek (≤60 char) all-caps  — mis. "LAMPIRAN 1"
        (c) teks pendek (≤80 char) + semua run bold — heading non-style umum PKM
        """
        for para in self.parser.paragraphs:
            if after_idx is not None and para.index < after_idx:
                continue
            text = para.text.strip()
            if not text or not self._LAMPIRAN_RE.match(text):
                continue
            if para.is_heading:
                return para.index
            if len(text) <= 60 and text == text.upper():
                return para.index
            text_runs = [r for r in para.runs if r.text.strip()]
            if text_runs and all(r.bold is True for r in text_runs) and len(text) <= 80:
                return para.index
        return None

    def _pdf_page_for_text(self, text: str, last_occurrence: bool = False) -> Optional[int]:
        """Cari teks di PDF sheets, return nomor halaman fisik (1-based), atau None.

        last_occurrence=True: kembalikan kemunculan terakhir. Berguna untuk heading
        yang juga muncul di TOC (halaman awal) — kemunculan terakhir = lokasi asli.
        """
        if not self._pdf_sheet_texts or not text or len(text) < 20:
            return None
        search = text[:60].strip()
        if last_occurrence:
            found = None
            for i, sheet_text in enumerate(self._pdf_sheet_texts):
                if search in sheet_text:
                    found = i + 1
            return found
        for i, sheet_text in enumerate(self._pdf_sheet_texts):
            if search in sheet_text:
                return i + 1
        return None

    def _format_para_location(self, paragraph_index: int) -> str:
        # Coba PDF text search dulu (akurat)
        if self._pdf_sheet_texts and 0 <= paragraph_index < len(self.parser.paragraphs):
            para_text = self.parser.paragraphs[paragraph_index].text.strip()
            pdf_page = self._pdf_page_for_text(para_text)
            if pdf_page is not None:
                return f"Halaman {pdf_page}"
        # Fallback: DOCX estimator (perkiraan)
        estimator = getattr(self.parser, "estimate_physical_page", None)
        page: Optional[int] = None
        if callable(estimator):
            raw = estimator(paragraph_index)
            if isinstance(raw, int):
                page = raw
        if page is None:
            return f"Paragraf #{paragraph_index}"
        return f"Halaman ~{page}"

    def _section_location(self, section_index: int) -> str:
        """Return nomor halaman fisik pertama dari section. Pakai PDF text search jika tersedia."""
        W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
        try:
            body = self.parser.document_xml.find(f"{{{W}}}body")
        except Exception:
            return f"Section #{section_index}"
        if body is None:
            return f"Section #{section_index}"

        estimator = getattr(self.parser, "estimate_physical_page", None)

        def resolve(first_para_idx: int) -> str:
            if self._pdf_sheet_texts:
                paras = self.parser.paragraphs
                limit = min(first_para_idx + 30, len(paras))
                # Prioritas 1: heading pertama di section → pakai last_occurrence
                # agar tidak tersangkut TOC di halaman awal.
                for pi in range(first_para_idx, limit):
                    p = paras[pi]
                    txt = p.text.strip()
                    if not txt:
                        continue
                    if p.is_heading and len(txt) >= 10:
                        pg = self._pdf_page_for_text(txt, last_occurrence=True)
                        if pg is not None:
                            return f"Halaman {pg}"
                        break  # heading tidak ditemukan di PDF, coba body text
                # Prioritas 2: body paragraph pertama (first occurrence)
                for pi in range(first_para_idx, limit):
                    p = paras[pi]
                    txt = p.text.strip()
                    if not txt or p.is_heading or len(txt) < 30:
                        continue
                    pg = self._pdf_page_for_text(txt)
                    if pg is not None:
                        return f"Halaman {pg}"
            # Fallback: DOCX estimator
            if callable(estimator):
                page = estimator(first_para_idx)
                if page is not None:
                    return f"Halaman ~{page}"
            return f"Section #{section_index}"

        para_idx = -1
        cur_sec = 0
        sec_first_para = 0

        for child in body:
            if child.tag == f"{{{W}}}p":
                para_idx += 1
                ppr = child.find(f"{{{W}}}pPr")
                if ppr is not None and ppr.find(f"{{{W}}}sectPr") is not None:
                    if cur_sec == section_index:
                        return resolve(sec_first_para)
                    cur_sec += 1
                    sec_first_para = para_idx + 1
            elif child.tag == f"{{{W}}}sectPr":
                if cur_sec == section_index:
                    return resolve(sec_first_para)

        if cur_sec == section_index:
            return resolve(sec_first_para)

        return f"Section #{section_index}"

    def check(self, start_para_idx: Optional[int] = None) -> FormatCheckResult:
        result = FormatCheckResult(status="pass")

        # Batas paragraf: skip front matter (start_para_idx) dan stop sebelum LAMPIRAN.
        # Cari LAMPIRAN hanya setelah start_para_idx agar entri Daftar Lampiran
        # di halaman awal tidak di-false-positive sebagai batas akhir.
        lampiran_idx = self._find_lampiran_para_index(after_idx=start_para_idx)

        # Jalankan tiap sub-check
        result.checks["paper_size"] = self._check_paper_size()
        result.checks["margin"] = self._check_margin()
        result.checks["paragraph_indent"] = self._check_paragraph_indent(lampiran_idx, start_para_idx)
        result.checks["font_body"] = self._check_font_body(lampiran_idx, start_para_idx)
        result.checks["line_spacing"] = self._check_line_spacing(lampiran_idx, start_para_idx)
        if self.rules.require_justify:
            result.checks["alignment"] = self._check_alignment(lampiran_idx, start_para_idx)
        result.checks["foreign_words_italic"] = self._check_foreign_words_italic(lampiran_idx, start_para_idx)

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
                # Append summary, lalu detail issue (limit)
                count = len(sec.issues)
                shown = sec.issues[: self.MAX_ISSUES_PER_CATEGORY]
                more = count - len(shown)
                summary = f"{name}: {count} pelanggaran terdeteksi"
                if more > 0:
                    summary += f" (menampilkan {len(shown)} dari {count})"
                result.messages.append(
                    CheckMessage(level=sec.status, text=summary)
                )
                for issue in shown:
                    result.messages.append(
                        CheckMessage(
                            level=issue.severity,
                            text=f"  • [{issue.location}] {issue.issue}",
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
                        location=f"Section #{s.index}",
                        issue=(
                            f"Ukuran kertas bukan A4. "
                            f"Diharapkan {self.rules.paper_width_cm}×{self.rules.paper_height_cm} cm."
                        ),
                        found=f"{w_cm}×{h_cm} cm",
                        expected=f"{self.rules.paper_width_cm}×{self.rules.paper_height_cm} cm",
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
                            location=self._section_location(s.index),
                            issue=f"Margin {side} tidak sesuai aturan PKM.",
                            found=f"{act} cm",
                            expected=f"{exp} cm (toleransi ±{tol} cm)",
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
    # Sub-check: paragraph indentation
    # ------------------------------------------------------------------------

    # Threshold: 1134 dxa ≈ 2.0 cm — flag indentasi kiri yang jelas berlebihan
    # (normal list ≤ 720 dxa; first-line indent tidak dicek karena bukan ind.left)
    _IND_LEFT_THRESHOLD_DXA: int = 1134

    def _check_paragraph_indent(
        self, lampiran_idx: Optional[int] = None, start_para_idx: Optional[int] = None
    ) -> FormatCheckSection:
        """
        Cek apakah ada paragraf di bagian inti yang punya indentasi kiri berlebihan.
        Indentasi kiri paragraph-level (pPr/ind@w:left) berbeda dari margin halaman
        dan bisa dipakai (secara keliru) untuk mempersempit lebar teks.
        """
        sec = FormatCheckSection(name="paragraph_indent", status="pass")
        for para in self.parser.paragraphs:
            if start_para_idx is not None and para.index < start_para_idx:
                continue
            if lampiran_idx is not None and para.index >= lampiran_idx:
                break
            if not para.text.strip():
                continue
            if para.is_heading:
                continue
            if para.ind_left_dxa is None or para.ind_left_dxa <= self._IND_LEFT_THRESHOLD_DXA:
                continue
            ind_cm = round(para.ind_left_dxa / 1440 * 2.54, 2)
            loc = self._format_para_location(para.index)
            sec.issues.append(
                FormatIssue(
                    check_name="paragraph_indent",
                    severity="fail",
                    location=loc,
                    issue=(
                        f"Indentasi kiri paragraf berlebihan ({ind_cm} cm) — "
                        f"seharusnya 0 cm (tanpa indent tambahan)."
                    ),
                    found=f"{ind_cm} cm",
                    expected="0 cm",
                )
            )
        if sec.issues:
            sec.status = "fail"
        sec.detail = {
            "threshold_dxa": self._IND_LEFT_THRESHOLD_DXA,
            "violations_count": len(sec.issues),
        }
        return sec

    # ------------------------------------------------------------------------
    # Sub-check: font body
    # ------------------------------------------------------------------------

    def _check_font_body(self, lampiran_idx: Optional[int] = None, start_para_idx: Optional[int] = None) -> FormatCheckSection:
        """
        Cek font body (dari start_para_idx sampai sebelum LAMPIRAN). Skip:
        - Heading, paragraf kosong
        """
        sec = FormatCheckSection(name="font_body", status="pass")
        font_distribution: dict[str, int] = {}
        size_distribution: dict[float, int] = {}

        for para in self.parser.paragraphs:
            if start_para_idx is not None and para.index < start_para_idx:
                continue
            if lampiran_idx is not None and para.index >= lampiran_idx:
                break
            if not para.text.strip():
                continue
            if para.is_heading:
                continue
            if _is_figure_table_caption_paragraph(para.text):
                if self.rules.check_caption_font_size:
                    cap_font = self.resolver.resolve_paragraph_font(para.index)
                    cap_tol = self.rules.caption_font_size_tolerance_pt
                    # Cek per run; inherit dari cap_font jika run tidak set size explicit
                    bad_cap_size: Optional[float] = None
                    bad_cap_snippet: str = para.text.strip()[:60]
                    if para.runs:
                        for run in para.runs:
                            if not run.text.strip():
                                continue
                            eff_size = run.font_size_pt if run.font_size_pt is not None else cap_font.size_pt
                            if eff_size is not None and abs(eff_size - self.rules.caption_font_size_pt) > cap_tol:
                                bad_cap_size = eff_size
                                run_raw = run.text.strip()
                                bad_cap_snippet = run_raw[:60] + ("…" if len(run_raw) > 60 else "")
                                break
                    elif cap_font.size_pt is not None and abs(cap_font.size_pt - self.rules.caption_font_size_pt) > cap_tol:
                        bad_cap_size = cap_font.size_pt
                    if bad_cap_size is not None:
                        sec.issues.append(
                            FormatIssue(
                                check_name="caption_font_size",
                                severity="fail",
                                location=self._format_para_location(para.index),
                                issue=f"Ukuran font keterangan gambar/tabel bukan {self.rules.caption_font_size_pt}pt — \"{bad_cap_snippet}\"",
                                found=f"{bad_cap_size}pt",
                                expected=f"{self.rules.caption_font_size_pt}pt",
                            )
                        )
                continue

            # Resolve font default paragraf (dari style chain, untuk run yang inherit)
            para_font = self.resolver.resolve_paragraph_font(para.index)

            # Track distribusi berdasarkan paragraph-level font (informatif)
            if para_font.name:
                font_distribution[para_font.name] = font_distribution.get(para_font.name, 0) + 1
            if para_font.size_pt is not None:
                size_distribution[para_font.size_pt] = size_distribution.get(para_font.size_pt, 0) + 1

            raw = para.text.strip()
            para_snippet = raw[:60] + ("…" if len(raw) > 60 else "")

            # Cek font name: gunakan effective font per run.
            # Run yang tidak set font explicit → inherit dari para_font.
            # Ini mencegah false positive pada dokumen di mana mahasiswa set TNR
            # secara manual (run-level) tapi paragraph style masih "Calibri" dari docDefaults.
            bad_font: Optional[str] = None
            bad_font_snippet: str = para_snippet
            if para.runs:
                for run in para.runs:
                    if not run.text.strip():
                        continue
                    # Lewati run yang mengandung karakter non-ASCII (simbol kimia, matematika,
                    # karakter Unicode, dsb) — font non-TNR pada run semacam ini sering muncul
                    # akibat substitusi font otomatis Word dan tidak bisa diandalkan sebagai
                    # indikator kesalahan format.
                    if any(ord(c) > 127 for c in run.text):
                        continue
                    effective_name = run.font_name if run.font_name else para_font.name
                    if effective_name and effective_name != self.rules.font_name:
                        bad_font = effective_name
                        run_raw = run.text.strip()
                        bad_font_snippet = run_raw[:60] + ("…" if len(run_raw) > 60 else "")
                        break
            elif para_font.name and para_font.name != self.rules.font_name:
                bad_font = para_font.name

            if bad_font:
                sec.issues.append(
                    FormatIssue(
                        check_name="font_name",
                        severity="fail",
                        location=self._format_para_location(para.index),
                        issue=f"Font bukan {self.rules.font_name} — \"{bad_font_snippet}\"",
                        found=bad_font,
                        expected=self.rules.font_name,
                    )
                )

            # Cek size: gunakan effective size per run (sama seperti font name).
            bad_size: Optional[float] = None
            bad_size_snippet: str = para_snippet
            if para.runs:
                for run in para.runs:
                    if not run.text.strip():
                        continue
                    effective_size = run.font_size_pt if run.font_size_pt is not None else para_font.size_pt
                    if effective_size is not None and abs(effective_size - self.rules.font_size_pt) > self.rules.font_size_tolerance_pt:
                        bad_size = effective_size
                        run_raw = run.text.strip()
                        bad_size_snippet = run_raw[:60] + ("…" if len(run_raw) > 60 else "")
                        break
            elif para_font.size_pt is not None and abs(para_font.size_pt - self.rules.font_size_pt) > self.rules.font_size_tolerance_pt:
                bad_size = para_font.size_pt

            if bad_size is not None:
                sec.issues.append(
                    FormatIssue(
                        check_name="font_size",
                        severity="fail",
                        location=self._format_para_location(para.index),
                        issue=f"Ukuran Font bukan 12 — \"{bad_size_snippet}\"",
                        found=f"{bad_size}pt",
                        expected=f"{self.rules.font_size_pt}pt",
                    )
                )

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

    def _check_line_spacing(self, lampiran_idx: Optional[int] = None, start_para_idx: Optional[int] = None) -> FormatCheckSection:
        sec = FormatCheckSection(name="line_spacing", status="pass")
        tol = self.rules.line_spacing_tolerance
        cap_tol = self.rules.caption_line_spacing_tolerance
        spacing_distribution: dict[float, int] = {}
        for para in self.parser.paragraphs:
            if start_para_idx is not None and para.index < start_para_idx:
                continue
            if lampiran_idx is not None and para.index >= lampiran_idx:
                break
            if not para.text.strip():
                continue
            if para.is_heading:
                continue
            ls = para.line_spacing
            if ls is None:
                continue
            spacing_distribution[ls] = spacing_distribution.get(ls, 0) + 1
            if _is_figure_table_caption_paragraph(para.text):
                # Caption wajib spasi 1 — hanya cek jika skema mengaktifkan rule ini
                if self.rules.check_caption_line_spacing and abs(ls - self.rules.caption_line_spacing) > cap_tol:
                    raw = para.text.strip()
                    snippet = raw[:60] + ("…" if len(raw) > 60 else "")
                    sec.issues.append(
                        FormatIssue(
                            check_name="caption_line_spacing",
                            severity="warning",
                            location=self._format_para_location(para.index),
                            issue=f"Line spacing keterangan gambar/tabel bukan 1 — \"{snippet}\"",
                            found=str(ls),
                            expected=str(self.rules.caption_line_spacing),
                        )
                    )
            elif abs(ls - self.rules.line_spacing) > tol:
                sec.issues.append(
                    FormatIssue(
                        check_name="line_spacing",
                        severity="warning",
                        location=self._format_para_location(para.index),
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
            "caption_expected": self.rules.caption_line_spacing,
            "caption_tolerance": cap_tol,
            "spacing_distribution": dict(
                sorted(spacing_distribution.items(), key=lambda x: -x[1])
            ),
            "violations_count": len(sec.issues),
        }
        return sec

    # ------------------------------------------------------------------------
    # Sub-check: alignment (justify)
    # ------------------------------------------------------------------------

    def _check_alignment(self, lampiran_idx: Optional[int] = None, start_para_idx: Optional[int] = None) -> FormatCheckSection:
        """
        Body teks PKM wajib justify (dari start_para_idx sampai sebelum LAMPIRAN). Skip:
        - Heading, paragraf pendek <30 char, caption gambar/tabel
        """
        sec = FormatCheckSection(name="alignment", status="pass")
        for para in self.parser.paragraphs:
            if start_para_idx is not None and para.index < start_para_idx:
                continue
            if lampiran_idx is not None and para.index >= lampiran_idx:
                break
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

    def _check_foreign_words_italic(self, lampiran_idx: Optional[int] = None, start_para_idx: Optional[int] = None) -> FormatCheckSection:
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
            if start_para_idx is not None and para.index < start_para_idx:
                continue
            if lampiran_idx is not None and para.index >= lampiran_idx:
                break
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

            # Cek apakah ada run italic
            has_italic_run = any(r.italic for r in para.runs)
            # Heuristik kasar: kalau seluruh paragraf tidak ada run italic
            # padahal mengandung kata asing → flag warning.
            if not has_italic_run:
                sec.issues.append(
                    FormatIssue(
                        check_name="foreign_words_italic",
                        severity="fail",
                        location=self._format_para_location(para.index),
                        issue=(
                            f"Paragraf memuat kata/frasa asing "
                            f"({', '.join(matched_words[:3])}) tapi tidak ada run italic. "
                            f"Bahasa asing wajib italic."
                        ),
                        found="tidak italic",
                        expected="italic",
                    )
                )

        if sec.issues:
            sec.status = "fail"
        sec.detail = {"violations_count": len(sec.issues)}
        return sec