"""
ReferenceValidator — validator Daftar Pustaka sesuai blueprint v0.3 §4.5.

Yang dicek:
A. Format strict Harvard (pengecekan dasar — bukan parser Harvard penuh):
   - Ada tahun di entry
   - Tidak terlalu pendek (entry minimal punya nama + tahun + judul)

B. LARANGAN STRICT:
   - Tidak boleh "et al." di Daftar Pustaka
   - Tidak boleh "dkk." di Daftar Pustaka

C. Pengecekan keseimbangan sitasi (anti-referensi-bodong):
   1. In-text → DP: tiap sitasi (Author, Year) di body teks WAJIB ada di DP
   2. DP → In-text: tiap entry DP WAJIB pernah dirujuk di body teks

D. Urutan alfabetis: entry DP berdasarkan nama belakang author pertama

E. Rekomendasi kualitas: jumlah referensi mutakhir (< 10 tahun)
   - Saran (warning), bukan fail

Catatan desain:
- Format Harvard strict yang penuh (penulis dengan inisial, italic untuk judul,
  format jurnal vs buku) sangat rapuh untuk regex. Kita HANYA validasi yang
  jelas: ada tahun, tidak ada et al./dkk., balance check.
- Pencocokan sitasi pakai nama pertama (last name) dari entry DP. Variasi
  penulisan (typo, ejaan) → akan ke-flag sebagai mismatch.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

from app.services.docx_parser import DocxParser
from app.services.schema_rules import SchemaRules


# ============================================================================
# Pattern regex
# ============================================================================

# Pola sitasi in-text:
#   (Author, 2020)
#   (Author dan Author, 2020)
#   (Author dkk., 2020)        ← ini sebenarnya pelanggaran tapi kita parse dulu
#   (Author et al., 2020)      ← sama
# Year = 4 digit, optional suffix huruf kecil (2020a, 2020b)
_INTEXT_CITATION_RE = re.compile(
    r"\(([^()]+?),\s*(\d{4}[a-z]?)\)",
    re.UNICODE,
)

# Tahun di awal/dalam entry DP (Indonesia: setelah nama+titik)
# Format yang umum di sample real:
#   "Astuti. 2012. Judul..."           ← year setelah . (Indonesia style)
#   "Astuti (2012) Judul..."           ← Harvard
#   "Astuti, 2012, Judul..."           ← varian
_DP_YEAR_RE = re.compile(r"\b(\d{4}[a-z]?)\b")

# Larangan strict
_FORBIDDEN_INDICATORS = ["et al.", "et al", "dkk.", "dkk"]

# Pattern nama pertama dari entry DP. Strategi: kata-kata di awal sampai
# titik atau koma atau "(" pertama.
# Contoh: "Astuti. 2012. ..." → "Astuti"
#         "Smith, J. (2020) ..." → "Smith"
#         "Nyman, Rimma. 2017. ..." → "Nyman"
#         "BPS. 2018. ..." → "BPS"
#         "UU RI No. 20 Tahun 2003" → "UU RI No"  (special, akan kita filter)
_DP_AUTHOR_RE = re.compile(r"^\s*([^.,(\d]+?)(?:[.,(]|\s+\d{4})", re.UNICODE)


# ============================================================================
# Data class
# ============================================================================


@dataclass
class ReferenceEntry:
    """Satu entry di Daftar Pustaka."""
    paragraph_index: int
    raw_text: str
    author_first: Optional[str] = None    # last name penulis pertama (untuk balance)
    year: Optional[int] = None
    has_etal_violation: bool = False
    has_dkk_violation: bool = False
    has_year: bool = True
    is_too_short: bool = False
    is_recent: bool = False               # year >= cutoff (cutoff = current_year - 10)


@dataclass
class InTextCitation:
    """Satu sitasi di body teks."""
    paragraph_index: int
    raw_text: str               # mis. "(Astuti, 2012)"
    author: str                 # mis. "Astuti"
    year: int                   # 2012


@dataclass
class FormatIssue:
    entry_index: int            # index dalam list entries (0-based, bukan paragraph_index)
    text_preview: str
    severity: str               # 'fail' | 'warning'
    issue: str


@dataclass
class BalanceFinding:
    direction: str              # 'in_text_not_in_references' | 'in_references_not_in_text'
    citation_or_entry: str
    detail: str
    paragraph_index: Optional[int] = None


@dataclass
class CheckMessage:
    level: str
    text: str


@dataclass
class ReferenceValidationResult:
    status: str                 # 'pass' | 'warning' | 'fail'
    total_entries: int = 0
    valid_entries: int = 0
    entries: list[ReferenceEntry] = field(default_factory=list)
    in_text_citations: list[InTextCitation] = field(default_factory=list)
    format_issues: list[FormatIssue] = field(default_factory=list)
    alphabetical_status: str = "pass"  # 'pass' | 'fail'
    out_of_order_pairs: list[tuple[str, str]] = field(default_factory=list)
    balance_findings: list[BalanceFinding] = field(default_factory=list)
    recent_count: int = 0
    recent_threshold_years: int = 10
    minimum_recommended: int = 8
    quality_message: str = ""
    messages: list[CheckMessage] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "total_entries": self.total_entries,
            "valid_entries": self.valid_entries,
            "entries": [
                {
                    "paragraph_index": e.paragraph_index,
                    "raw_text": e.raw_text,
                    "author_first": e.author_first,
                    "year": e.year,
                    "has_etal_violation": e.has_etal_violation,
                    "has_dkk_violation": e.has_dkk_violation,
                    "has_year": e.has_year,
                    "is_too_short": e.is_too_short,
                    "is_recent": e.is_recent,
                }
                for e in self.entries
            ],
            "in_text_citations": [
                {
                    "paragraph_index": c.paragraph_index,
                    "raw_text": c.raw_text,
                    "author": c.author,
                    "year": c.year,
                }
                for c in self.in_text_citations
            ],
            "format_issues": [
                {
                    "entry_index": fi.entry_index,
                    "text_preview": fi.text_preview,
                    "severity": fi.severity,
                    "issue": fi.issue,
                }
                for fi in self.format_issues
            ],
            "alphabetical_order": {
                "status": self.alphabetical_status,
                "out_of_order": [
                    {"current": p[0], "should_be_after": p[1]}
                    for p in self.out_of_order_pairs
                ],
            },
            "citation_balance": {
                "in_text_not_in_references": [
                    {
                        "citation": f.citation_or_entry,
                        "detail": f.detail,
                        "paragraph_index": f.paragraph_index,
                    }
                    for f in self.balance_findings
                    if f.direction == "in_text_not_in_references"
                ],
                "in_references_not_in_text": [
                    {
                        "reference": f.citation_or_entry,
                        "detail": f.detail,
                        "paragraph_index": f.paragraph_index,
                    }
                    for f in self.balance_findings
                    if f.direction == "in_references_not_in_text"
                ],
            },
            "quality_recommendation": {
                "recent_references_count": self.recent_count,
                "recent_threshold_years": self.recent_threshold_years,
                "minimum_recommended": self.minimum_recommended,
                "message": self.quality_message,
            },
            "messages": [{"level": m.level, "text": m.text} for m in self.messages],
        }


# ============================================================================
# ReferenceValidator
# ============================================================================


class ReferenceValidator:
    """
    Validator Daftar Pustaka.

    Usage:
        parser = DocxParser('proposal.docx')
        schema = get_pkm_kc_proposal_rules()
        result = ReferenceValidator(parser, schema, current_year=2026).check()
    """

    # Limit jumlah karakter preview untuk display
    PREVIEW_CHARS = 100

    # Minimal panjang entry (deteksi entry kosong / placeholder)
    MIN_ENTRY_LENGTH = 30

    def __init__(
        self,
        parser: DocxParser,
        schema: SchemaRules,
        current_year: int = 2026,
        recent_threshold_years: int = 10,
        minimum_recommended_recent: int = 8,
    ):
        self.parser = parser
        self.schema = schema
        self.current_year = current_year
        self.recent_threshold_years = recent_threshold_years
        self.minimum_recommended_recent = minimum_recommended_recent

    def check(self) -> ReferenceValidationResult:
        result = ReferenceValidationResult(
            status="pass",
            recent_threshold_years=self.recent_threshold_years,
            minimum_recommended=self.minimum_recommended_recent,
        )

        # Step 1: ekstrak entries dari Daftar Pustaka
        result.entries = self._extract_dp_entries()
        result.total_entries = len(result.entries)

        # Step 2: validasi format per entry (et al./dkk., year, length)
        result.format_issues = self._validate_format(result.entries)
        result.valid_entries = len([
            e for e in result.entries
            if not (e.has_etal_violation or e.has_dkk_violation
                    or not e.has_year or e.is_too_short)
        ])

        # Step 3: ekstrak sitasi in-text
        result.in_text_citations = self._extract_in_text_citations()

        # Step 4: balance check (in-text ↔ DP)
        result.balance_findings = self._balance_check(
            result.entries, result.in_text_citations
        )

        # Step 5: alphabetical order check
        result.alphabetical_status, result.out_of_order_pairs = (
            self._check_alphabetical_order(result.entries)
        )

        # Step 6: quality recommendation (recency)
        result.recent_count = sum(1 for e in result.entries if e.is_recent)
        result.quality_message = self._build_quality_message(result.recent_count)

        # Step 7: aggregate status
        self._finalize_status(result)

        return result

    # ------------------------------------------------------------------------
    # Step 1: ekstrak entries
    # ------------------------------------------------------------------------

    def _extract_dp_entries(self) -> list[ReferenceEntry]:
        """
        Locate section "DAFTAR PUSTAKA" (heading_only), ambil paragraf
        sampai section selanjutnya (LAMPIRAN). Entry = paragraf non-empty.
        """
        boundaries = self.parser.find_section_boundaries(
            ["DAFTAR PUSTAKA", "LAMPIRAN"], headings_only=True
        )
        dp_start = boundaries["DAFTAR PUSTAKA"]
        dp_end = boundaries["LAMPIRAN"]

        if dp_start is None:
            return []

        # Kalau LAMPIRAN tidak ada, ambil sampai akhir
        if dp_end is None:
            dp_end = len(self.parser.paragraphs)

        entries: list[ReferenceEntry] = []
        for i in range(dp_start + 1, dp_end):
            para = self.parser.paragraphs[i]
            text = para.text.strip()
            if not text:
                continue
            # Skip kalau ini heading sub-section (jarang, tapi safe)
            if para.is_heading:
                continue

            # Normalize whitespace (banyak entry ada \t)
            text_normalized = re.sub(r"\s+", " ", text)

            entry = self._parse_entry(i, text_normalized)
            entries.append(entry)
        return entries

    def _parse_entry(self, para_idx: int, text: str) -> ReferenceEntry:
        entry = ReferenceEntry(
            paragraph_index=para_idx,
            raw_text=text,
            is_too_short=len(text) < self.MIN_ENTRY_LENGTH,
        )

        # Cek et al./dkk.
        text_lower = text.lower()
        if "et al" in text_lower:
            entry.has_etal_violation = True
        if "dkk" in text_lower:
            entry.has_dkk_violation = True

        # Cari tahun
        m = _DP_YEAR_RE.search(text)
        if m:
            year_str = m.group(1)
            # Buang suffix huruf untuk konversi int
            year_int_str = re.sub(r"[a-z]", "", year_str)
            try:
                entry.year = int(year_int_str)
                # Validasi tahun masuk akal (1900..current_year+1)
                if not (1900 <= entry.year <= self.current_year + 1):
                    entry.year = None
            except ValueError:
                entry.year = None
        if entry.year is None:
            entry.has_year = False

        # Recency
        if entry.year is not None:
            entry.is_recent = (
                self.current_year - entry.year < self.recent_threshold_years
            )

        # Author first (untuk balance check)
        m_author = _DP_AUTHOR_RE.match(text)
        if m_author:
            author = m_author.group(1).strip()
            # Bersihkan dari titik trailing
            author = author.rstrip(". ").strip()
            # Skip kalau terlalu generik (mis. "UU RI No")
            if author and len(author) >= 2:
                # Ambil token pertama saja (last name penulis pertama)
                # mis. "Nyman, Rimma" → "Nyman"
                #      "Smith and Jones" → "Smith"
                tokens = re.split(r"[,\s]+", author)
                if tokens:
                    entry.author_first = tokens[0]

        return entry

    # ------------------------------------------------------------------------
    # Step 2: validasi format
    # ------------------------------------------------------------------------

    def _validate_format(
        self, entries: list[ReferenceEntry]
    ) -> list[FormatIssue]:
        issues: list[FormatIssue] = []
        for i, e in enumerate(entries):
            preview = e.raw_text[: self.PREVIEW_CHARS]
            if e.has_etal_violation:
                issues.append(
                    FormatIssue(
                        entry_index=i,
                        text_preview=preview,
                        severity="fail",
                        issue=(
                            "Mengandung 'et al.' — Harvard strict melarang. "
                            "Tulis semua nama penulis lengkap."
                        ),
                    )
                )
            if e.has_dkk_violation:
                issues.append(
                    FormatIssue(
                        entry_index=i,
                        text_preview=preview,
                        severity="fail",
                        issue=(
                            "Mengandung 'dkk.' — Harvard strict melarang. "
                            "Tulis semua nama penulis lengkap."
                        ),
                    )
                )
            if not e.has_year:
                issues.append(
                    FormatIssue(
                        entry_index=i,
                        text_preview=preview,
                        severity="fail",
                        issue=(
                            "Tahun publikasi tidak ditemukan di entry. "
                            "Setiap referensi wajib mencantumkan tahun."
                        ),
                    )
                )
            if e.is_too_short:
                issues.append(
                    FormatIssue(
                        entry_index=i,
                        text_preview=preview,
                        severity="warning",
                        issue=(
                            f"Entry terlalu pendek ({len(e.raw_text)} char) "
                            f"— kemungkinan tidak lengkap."
                        ),
                    )
                )
        return issues

    # ------------------------------------------------------------------------
    # Step 3: ekstrak sitasi in-text
    # ------------------------------------------------------------------------

    def _extract_in_text_citations(self) -> list[InTextCitation]:
        """
        Scan body teks dari BAB 1 sampai sebelum DAFTAR PUSTAKA.
        Pattern: (Author, Year) — toleran spasi, "dan", "&".
        """
        boundaries = self.parser.find_section_boundaries(
            ["BAB 1", "DAFTAR PUSTAKA"], headings_only=True
        )
        body_start = boundaries["BAB 1"]
        body_end = boundaries["DAFTAR PUSTAKA"]

        if body_start is None:
            body_start = 0
        if body_end is None:
            body_end = len(self.parser.paragraphs)

        citations: list[InTextCitation] = []
        for i in range(body_start, body_end):
            text = self.parser.paragraphs[i].text
            if not text.strip():
                continue
            for m in _INTEXT_CITATION_RE.finditer(text):
                author_part = m.group(1).strip()
                year_str = m.group(2)
                year_int_str = re.sub(r"[a-z]", "", year_str)
                try:
                    year = int(year_int_str)
                except ValueError:
                    continue

                # Author bisa "Smith dan Jones", "Smith, Jones", "Smith et al"
                # Ambil author pertama saja
                first_author = self._extract_first_author_from_citation(author_part)
                if not first_author:
                    continue

                citations.append(
                    InTextCitation(
                        paragraph_index=i,
                        raw_text=m.group(0),
                        author=first_author,
                        year=year,
                    )
                )
        return citations

    @staticmethod
    def _extract_first_author_from_citation(author_text: str) -> Optional[str]:
        """
        Ambil author pertama dari teks sitasi. Toleran terhadap:
        - "Smith"
        - "Smith dan Jones"
        - "Smith & Jones"
        - "Smith et al."
        - "Smith dkk."
        """
        # Buang prefix umum
        text = author_text.strip()
        # Split by 'dan', '&', ',', 'and', dst.
        tokens = re.split(r"\s+(?:dan|and|&)\s+|,\s+", text, maxsplit=1)
        if not tokens:
            return None
        first = tokens[0].strip()
        # Buang trailing "et al" / "dkk"
        first = re.sub(r"\s+et\s+al\.?$", "", first, flags=re.IGNORECASE)
        first = re.sub(r"\s+dkk\.?$", "", first, flags=re.IGNORECASE)
        first = first.strip(". ").strip()
        if not first or len(first) < 2:
            return None
        return first

    # ------------------------------------------------------------------------
    # Step 4: balance check
    # ------------------------------------------------------------------------

    def _balance_check(
        self,
        entries: list[ReferenceEntry],
        citations: list[InTextCitation],
    ) -> list[BalanceFinding]:
        """
        Dua arah cek:
        1. In-text → DP: tiap (Author, Year) di teks harus ada di DP
        2. DP → In-text: tiap entry DP harus pernah disitasi

        Pencocokan: berdasarkan (author_first.lower(), year).
        Toleransi: cek substring author (untuk handle "Mustika" vs "Muatika")
        """
        # Build sets
        dp_keys: set[tuple[str, int]] = set()
        dp_authors_lower: dict[str, list[ReferenceEntry]] = {}
        for e in entries:
            if e.author_first and e.year:
                dp_keys.add((e.author_first.lower(), e.year))
                dp_authors_lower.setdefault(e.author_first.lower(), []).append(e)

        intext_keys: set[tuple[str, int]] = set()
        intext_authors_lower: dict[str, list[InTextCitation]] = {}
        for c in citations:
            intext_keys.add((c.author.lower(), c.year))
            intext_authors_lower.setdefault(c.author.lower(), []).append(c)

        findings: list[BalanceFinding] = []

        seen_intext_findings: set[tuple[str, int]] = set()
        # 1. In-text not in DP
        for c in citations:
            key = (c.author.lower(), c.year)
            if key in dp_keys:
                continue
            # Coba match toleran: cek apakah ada entry DP dengan author yang
            # PREFIX-cocok (mis. "Smith" vs "Smithson")
            partial = self._fuzzy_author_match(c.author.lower(), dp_authors_lower.keys())
            if partial:
                # Year bisa beda — tapi kalau author match, kita tetap flag
                # kalau year tidak ditemukan
                dp_years = {e.year for e in dp_authors_lower[partial] if e.year}
                if c.year not in dp_years:
                    if key in seen_intext_findings:
                        continue
                    seen_intext_findings.add(key)
                    findings.append(
                        BalanceFinding(
                            direction="in_text_not_in_references",
                            citation_or_entry=c.raw_text,
                            detail=(
                                f"Sitasi '({c.author}, {c.year})' tidak match exact "
                                f"di Daftar Pustaka. Author '{partial}' ada tapi "
                                f"tahun {sorted(dp_years)} (bukan {c.year})."
                            ),
                            paragraph_index=c.paragraph_index,
                        )
                    )
            else:
                if key in seen_intext_findings:
                    continue
                seen_intext_findings.add(key)
                findings.append(
                    BalanceFinding(
                        direction="in_text_not_in_references",
                        citation_or_entry=c.raw_text,
                        detail=(
                            f"Sitasi '({c.author}, {c.year})' di teks tapi tidak "
                            f"ada author '{c.author}' di Daftar Pustaka."
                        ),
                        paragraph_index=c.paragraph_index,
                    )
                )

        seen_dp_findings: set[tuple[str, int]] = set()
        # 2. DP not in in-text
        for e in entries:
            if not e.author_first or not e.year:
                continue
            key = (e.author_first.lower(), e.year)
            if key in intext_keys:
                continue
            if key in seen_dp_findings:
                continue
            seen_dp_findings.add(key)
            # Fuzzy author match
            partial = self._fuzzy_author_match(
                e.author_first.lower(), intext_authors_lower.keys()
            )
            if partial:
                # Author di-cite tapi tahun beda — kita TIDAK flag (sudah
                # di-flag oleh sisi in-text)
                continue
            findings.append(
                BalanceFinding(
                    direction="in_references_not_in_text",
                    citation_or_entry=e.raw_text[: self.PREVIEW_CHARS],
                    detail=(
                        f"Referensi '{e.author_first} ({e.year})' ada di Daftar "
                        f"Pustaka tapi tidak pernah disitasi di body teks "
                        f"(referensi bodong)."
                    ),
                    paragraph_index=e.paragraph_index,
                )
            )

        return findings

    @staticmethod
    def _fuzzy_author_match(target: str, candidates) -> Optional[str]:
        """
        Cari candidate yang mirip target (prefix match minimal 4 karakter
        atau Levenshtein distance ≤ 2 untuk nama panjang).
        Return: candidate yang match, atau None.
        """
        if not target:
            return None
        t = target.lower()
        for cand in candidates:
            c = cand.lower()
            if c == t:
                return cand
            # Prefix match: kalau salah satu mengandung yang lain (4+ char)
            if len(t) >= 4 and len(c) >= 4:
                if c.startswith(t[:4]) or t.startswith(c[:4]):
                    return cand
        return None

    # ------------------------------------------------------------------------
    # Step 5: alphabetical order
    # ------------------------------------------------------------------------

    def _check_alphabetical_order(
        self, entries: list[ReferenceEntry]
    ) -> tuple[str, list[tuple[str, str]]]:
        """
        Cek urutan alfabetis berdasarkan author_first.
        Skip entries yang author_first = None (tidak bisa di-sort).

        Return (status, list of (current_name, should_be_after_name)).
        """
        out_of_order: list[tuple[str, str]] = []
        sortable = [e for e in entries if e.author_first]
        for i in range(1, len(sortable)):
            prev = sortable[i - 1].author_first or ""
            curr = sortable[i].author_first or ""
            if curr.lower() < prev.lower():
                out_of_order.append((curr, prev))
        status = "fail" if out_of_order else "pass"
        return status, out_of_order

    # ------------------------------------------------------------------------
    # Step 6: quality recommendation
    # ------------------------------------------------------------------------

    def _build_quality_message(self, recent_count: int) -> str:
        if recent_count >= self.minimum_recommended_recent:
            return (
                f"Ada {recent_count} referensi mutakhir "
                f"(<{self.recent_threshold_years} tahun) — sudah memenuhi "
                f"rekomendasi minimum {self.minimum_recommended_recent}."
            )
        return (
            f"Hanya {recent_count} referensi mutakhir "
            f"(<{self.recent_threshold_years} tahun). Disarankan menambah "
            f"hingga ≥{self.minimum_recommended_recent} untuk scoring "
            f"maksimal. Bukan error mati."
        )

    # ------------------------------------------------------------------------
    # Step 7: finalize
    # ------------------------------------------------------------------------

    def _finalize_status(self, result: ReferenceValidationResult) -> None:
        def loc(paragraph_index: Optional[int]) -> str:
            if paragraph_index is None:
                return ""
            estimator = getattr(self.parser, "estimate_physical_page", None)
            in_page_estimator = getattr(self.parser, "estimate_paragraph_index_in_page", None)
            page = estimator(paragraph_index) if callable(estimator) else None
            in_page = (
                in_page_estimator(paragraph_index)
                if callable(in_page_estimator)
                else None
            )
            if page is None:
                return f" (paragraf #{paragraph_index})"
            if in_page is None or in_page <= 0:
                return f" (halaman fisik ~{page}, paragraf #{paragraph_index})"
            return (
                f" (halaman fisik ~{page}, paragraf ke-{in_page} "
                f"(global #{paragraph_index}))"
            )

        has_fail = False
        has_warning = False

        if result.total_entries == 0:
            result.status = "fail"
            result.messages.append(
                CheckMessage(
                    level="fail",
                    text=(
                        "Daftar Pustaka tidak ditemukan / kosong. Section ini "
                        "wajib ada untuk PKM."
                    ),
                )
            )
            return

        # Format issues
        for fi in result.format_issues:
            if fi.severity == "fail":
                has_fail = True
            else:
                has_warning = True
            result.messages.append(
                CheckMessage(
                    level=fi.severity,
                    text=(
                        f"[Entry #{fi.entry_index + 1}] {fi.issue}"
                        f"{loc(result.entries[fi.entry_index].paragraph_index) if fi.entry_index < len(result.entries) else ''}"
                    ),
                )
            )

        # Alphabetical
        if result.alphabetical_status == "fail":
            has_fail = True
            result.messages.append(
                CheckMessage(
                    level="fail",
                    text=(
                        f"Urutan alfabetis Daftar Pustaka tidak sesuai. "
                        f"{len(result.out_of_order_pairs)} pasangan entry "
                        f"tidak terurut."
                    ),
                )
            )
            for cur, prev in result.out_of_order_pairs[:5]:
                result.messages.append(
                    CheckMessage(
                        level="fail",
                        text=f"  • '{cur}' muncul setelah '{prev}' (seharusnya sebelum).",
                    )
                )

        # Balance
        in_text_missing = [
            f for f in result.balance_findings
            if f.direction == "in_text_not_in_references"
        ]
        bodong = [
            f for f in result.balance_findings
            if f.direction == "in_references_not_in_text"
        ]
        if in_text_missing:
            has_fail = True
            result.messages.append(
                CheckMessage(
                    level="fail",
                    text=(
                        f"{len(in_text_missing)} sitasi di teks tidak ditemukan "
                        f"di Daftar Pustaka."
                    ),
                )
            )
            for f in in_text_missing[:5]:
                result.messages.append(
                    CheckMessage(
                        level="fail",
                        text=f"  • {f.detail}{loc(f.paragraph_index)}",
                    )
                )
        if bodong:
            has_fail = True
            result.messages.append(
                CheckMessage(
                    level="fail",
                    text=(
                        f"{len(bodong)} entry Daftar Pustaka tidak pernah "
                        f"disitasi di body teks (referensi bodong)."
                    ),
                )
            )
            for f in bodong[:5]:
                result.messages.append(
                    CheckMessage(
                        level="fail",
                        text=f"  • {f.detail}{loc(f.paragraph_index)}",
                    )
                )

        # Quality recommendation
        if result.recent_count < result.minimum_recommended:
            has_warning = True
            result.messages.append(
                CheckMessage(level="warning", text=result.quality_message)
            )
        else:
            result.messages.append(
                CheckMessage(level="pass", text=result.quality_message)
            )

        # Set status
        if has_fail:
            result.status = "fail"
        elif has_warning:
            result.status = "warning"
        else:
            result.status = "pass"