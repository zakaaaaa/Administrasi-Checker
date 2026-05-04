"""
PhysicalSheetCounter — modul pengecek jumlah lembar fisik & validitas penomoran halaman.

Sumber blueprint: v0.3 §4.2

Tugas:
1. Konversi DOCX → PDF (via PdfConverter)
2. Hitung total lembar fisik (pakai pypdf)
3. Identifikasi rentang lembar bagian inti (BAB 1 sampai akhir Lampiran)
4. Validasi jumlah lembar inti vs aturan skema:
     - GFT/AI: 8–15 lembar
     - 8 bidang lain (KC, K, RE, RSH, PM, PI, KI, VGK): maks 10 lembar
5. Ekstrak nomor halaman per lembar, deteksi anomali:
     - duplicate_numbers (mis. dua lembar bernomor "5")
     - skipped_numbers (gap dalam urutan, mis. ...5, 7,...)
     - out_of_order (nomor mundur)
     - missing_numbers (lembar yang seharusnya bernomor tapi kosong)

Catatan teknis:
- Strategi ekstraksi nomor halaman: parse teks pypdf per lembar, ambil token
  pertama yang berupa angka arab atau romawi kecil di awal/akhir teks.
- Toleransi PDF kosong / teks tidak ter-extract dengan baik (mis. lembar gambar):
  flag sebagai "missing" tapi tidak crash.

Input:
    - DocxParser (sudah parse, dipakai untuk locate range BAB 1..akhir lampiran via teks)
    - SchemaRules (untuk min/max sheet count)
    - PdfConverter (atau hasil PDF yang sudah ada — bisa di-inject untuk testing)

Output:
    - PhysicalSheetResult dengan to_dict() siap simpan ke check_results.page_count_result
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from pypdf import PdfReader

from app.services.docx_parser import DocxParser
from app.services.pdf_converter import PdfConverter
from app.services.schema_rules import SchemaRules


# ============================================================================
# Schema-level rule untuk sheet count
# ============================================================================
#
# Blueprint v0.3 §8.7:
# - PKM-GFT, PKM-AI: 8–15 lembar fisik (inti)
# - PKM-KC, K, RE, RSH, PM, PI, KI, VGK: maks 10 lembar (tanpa min)
#
# Nantinya rule ini akan jadi field di SchemaRules. Untuk sekarang, kita
# tentukan via lookup table di sini.
# ============================================================================


SHEET_COUNT_RULES = {
    # (competition, schema): (min_sheets_or_None, max_sheets)
    ("PKM", "KC"):  (None, 10),
    ("PKM", "K"):   (None, 10),
    ("PKM", "RE"):  (None, 10),
    ("PKM", "RSH"): (None, 10),
    ("PKM", "PM"):  (None, 10),
    ("PKM", "PI"):  (None, 10),
    ("PKM", "KI"):  (None, 10),
    ("PKM", "VGK"): (None, 10),
    ("PKM", "GFT"): (8,    15),
    ("PKM", "AI"):  (8,    15),
}


def get_sheet_count_rule(rules: SchemaRules) -> tuple[Optional[int], int]:
    """
    Return (min_sheets, max_sheets) untuk skema. Default ke (None, 10) untuk
    skema PKM yang belum di-listing eksplisit.
    """
    key = (rules.competition_code, rules.schema_code)
    if key in SHEET_COUNT_RULES:
        return SHEET_COUNT_RULES[key]
    # Default fallback
    return (None, 10)


# ============================================================================
# Data classes hasil
# ============================================================================


@dataclass
class SheetPageNumber:
    """Nomor halaman yang terdeteksi di satu lembar fisik."""
    sheet_index: int               # index lembar fisik (1-based)
    page_num_text: Optional[str]   # raw text yang di-detect, mis. "5", "iii", atau None
    page_num_value: Optional[int]  # nilai numerik (1, 2, 3, untuk romawi: 1, 2, 3 → i, ii, iii)
    is_roman: bool = False
    is_arabic: bool = False
    extraction_source: str = "auto"  # 'auto' | 'header_top' | 'footer_bottom' | 'fallback'


@dataclass
class PageNumberAnomaly:
    """Anomali penomoran yang ditemukan."""
    type: str          # 'duplicate' | 'skipped' | 'out_of_order' | 'missing'
    severity: str      # 'fail' | 'warning'
    detail: dict
    message: str


@dataclass
class CheckMessage:
    level: str   # 'pass' | 'warning' | 'fail'
    text: str


@dataclass
class PhysicalSheetResult:
    status: str                                # 'pass' | 'warning' | 'fail'
    method: str = "pdf_physical_sheet_count"
    total_physical_sheets: int = 0
    core_physical_sheets: int = 0
    core_first_sheet: Optional[int] = None     # 1-based index lembar fisik tempat BAB 1 mulai
    core_last_sheet: Optional[int] = None      # 1-based index lembar fisik akhir Lampiran
    rule: dict = field(default_factory=dict)   # {schema, min_sheets, max_sheets}
    page_numbers: list[SheetPageNumber] = field(default_factory=list)
    anomalies: list[PageNumberAnomaly] = field(default_factory=list)
    messages: list[CheckMessage] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "method": self.method,
            "total_physical_sheets": self.total_physical_sheets,
            "core_physical_sheets": self.core_physical_sheets,
            "core_first_sheet": self.core_first_sheet,
            "core_last_sheet": self.core_last_sheet,
            "rule": self.rule,
            "page_numbering_issues": {
                "duplicate_numbers": [
                    a.detail for a in self.anomalies if a.type == "duplicate"
                ],
                "skipped_numbers": [
                    a.detail for a in self.anomalies if a.type == "skipped"
                ],
                "out_of_order": [
                    a.detail for a in self.anomalies if a.type == "out_of_order"
                ],
                "missing_numbers": [
                    a.detail for a in self.anomalies if a.type == "missing"
                ],
            },
            "page_numbers_per_sheet": [
                {
                    "sheet": p.sheet_index,
                    "page_num_text": p.page_num_text,
                    "page_num_value": p.page_num_value,
                    "is_roman": p.is_roman,
                    "is_arabic": p.is_arabic,
                }
                for p in self.page_numbers
            ],
            "messages": [{"level": m.level, "text": m.text} for m in self.messages],
        }


# ============================================================================
# Helpers ekstraksi
# ============================================================================


_ROMAN_RE = re.compile(r"^\s*([ivxlcdm]+)\s*$", re.IGNORECASE)
_ARABIC_RE = re.compile(r"^\s*(\d{1,4})\s*$")


def _roman_to_int(s: str) -> Optional[int]:
    """Konversi romawi → int. Return None jika invalid."""
    s = s.upper().strip()
    if not s:
        return None
    values = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100, "D": 500, "M": 1000}
    total = 0
    prev = 0
    for ch in reversed(s):
        if ch not in values:
            return None
        v = values[ch]
        if v < prev:
            total -= v
        else:
            total += v
        prev = v
    return total if total > 0 else None


def _extract_page_number_from_text(
    text: str, max_reasonable: int = 999
) -> tuple[Optional[str], Optional[int], bool, bool]:
    """
    Ekstrak nomor halaman dari teks satu lembar PDF.

    Strategi:
    1. Cari token tunggal di awal atau akhir teks yang berupa angka arab
       (1, 2, 3, ...) atau romawi kecil (i, ii, iii, ...).
    2. Awal teks lebih prioritas (sesuai aturan PKM: pojok kanan ATAS untuk
       zona inti).
    3. Filter false positive: angka > max_reasonable (default 999) tidak
       mungkin nomor halaman — kemungkinan tahun (2018, 2021) atau nomor
       NIM (A410180106) yang muncul standalone di baris.

    Args:
        text: teks lembar PDF
        max_reasonable: batas atas nilai yang masuk akal sebagai nomor halaman.
            Default 999 cukup untuk dokumen sampai ratusan halaman; sesuaikan
            kalau dokumen punya struktur khusus.

    Return: (raw_text, value, is_roman, is_arabic)
    Kalau tidak ada → (None, None, False, False)
    """
    if not text:
        return (None, None, False, False)

    # Ambil baris pertama dan terakhir non-empty
    lines = [ln.strip() for ln in text.split("\n") if ln.strip()]
    if not lines:
        return (None, None, False, False)

    # Coba: baris pertama (header/atas), lalu baris terakhir (footer/bawah)
    candidates = []
    if lines:
        candidates.append(lines[0])
    if len(lines) > 1:
        candidates.append(lines[-1])

    for cand in candidates:
        # Arabic
        m = _ARABIC_RE.match(cand)
        if m:
            val = int(m.group(1))
            # Filter false positive (tahun, NIM, dll)
            if val > max_reasonable:
                continue
            return (m.group(1), val, False, True)
        # Roman lowercase
        m = _ROMAN_RE.match(cand)
        if m:
            roman = m.group(1)
            if len(roman) <= 5:
                v = _roman_to_int(roman)
                if v and v <= max_reasonable:
                    return (roman, v, True, False)
    return (None, None, False, False)


# ============================================================================
# PhysicalSheetCounter
# ============================================================================


class PhysicalSheetCounter:
    """
    Hitung lembar fisik & validasi penomoran halaman.

    Usage:
        parser = DocxParser('proposal.docx')
        rules = get_pkm_kc_proposal_rules()
        counter = PhysicalSheetCounter(parser, rules)
        result = counter.check()
        # atau dengan PDF yang sudah ada (skip konversi):
        result = counter.check(pdf_path='/path/cached.pdf')
    """

    # Heuristik teks untuk locate awal & akhir bagian inti di PDF.
    # "BAB 1" atau "BAB I" muncul di awal halaman bagian inti.
    #
    # Tantangan: Daftar Isi juga memuat baris "BAB 1 PENDAHULUAN....X" yang
    # bisa false-match. Untuk avoid ini, kita pakai dua heuristik:
    # 1. "BAB 1" muncul di AWAL baris (^... atau setelah newline) tanpa
    #    dot leader sebelumnya
    # 2. Tidak ada titik berturut (".....") atau angka halaman setelahnya
    #    dalam jarak dekat — ciri khas entri ToC
    CORE_START_PATTERNS = [
        # "BAB 1." / "BAB 1 " / "BAB I." / "BAB I " di awal baris,
        # diikuti judul (huruf), bukan dot leader
        re.compile(r"(?:^|\n)\s*BAB\s*1\.?\s+[A-Z]", re.IGNORECASE),
        re.compile(r"(?:^|\n)\s*BAB\s*I\.?\s+(?!I)[A-Z]", re.IGNORECASE),
    ]
    # Akhir bagian inti = lembar terakhir dokumen yang masih bagian dari
    # Lampiran. Untuk PKM, akhir bagian inti = lembar terakhir PDF.
    # (asumsi: tidak ada appendix di luar LAMPIRAN)

    # Pattern tambahan untuk mendeteksi konteks ToC: kalau dalam window 80 char
    # setelah "BAB 1 PENDAHULUAN" ada dot leader (3+ titik) atau
    # nomor halaman → kemungkinan baris ToC, skip lembar ini.
    _TOC_CONTEXT_RE = re.compile(r"\.{3,}|\s+\d+\s*$", re.MULTILINE)

    def __init__(
        self,
        parser: DocxParser,
        rules: SchemaRules,
        pdf_converter: Optional[PdfConverter] = None,
    ):
        self.parser = parser
        self.rules = rules
        self.pdf_converter = pdf_converter or PdfConverter()

    def check(self, pdf_path: Optional[str | Path] = None) -> PhysicalSheetResult:
        """
        Args:
            pdf_path: kalau di-supply, skip konversi DOCX→PDF (untuk testing/cache).
                     Kalau None, otomatis konversi.
        """
        # 1. Dapatkan PDF
        if pdf_path is None:
            pdf_path = self.pdf_converter.convert(self.parser.file_path)
        else:
            pdf_path = Path(pdf_path)

        # 2. Buat result skeleton dengan rule info
        min_sheets, max_sheets = get_sheet_count_rule(self.rules)
        result = PhysicalSheetResult(
            status="pass",
            rule={
                "schema": f"{self.rules.competition_code}-{self.rules.schema_code}",
                "min_sheets": min_sheets,
                "max_sheets": max_sheets,
            },
        )

        # 3. Baca PDF, hitung lembar
        reader = PdfReader(str(pdf_path))
        result.total_physical_sheets = len(reader.pages)

        # 4. Ekstrak teks per lembar (sekali, dipakai banyak step)
        sheet_texts: list[str] = []
        for page in reader.pages:
            try:
                sheet_texts.append(page.extract_text() or "")
            except Exception:
                sheet_texts.append("")

        # 5. Identifikasi rentang bagian inti
        core_first, core_last = self._locate_core_range(sheet_texts)
        result.core_first_sheet = core_first
        result.core_last_sheet = core_last
        if core_first is not None and core_last is not None:
            result.core_physical_sheets = core_last - core_first + 1

        # 6. Ekstrak nomor halaman per lembar
        result.page_numbers = self._extract_page_numbers(sheet_texts)

        # 7. Deteksi anomali penomoran (hanya di rentang bagian inti)
        if core_first is not None and core_last is not None:
            result.anomalies = self._detect_anomalies(
                result.page_numbers, core_first, core_last
            )

        # 8. Validasi jumlah lembar inti vs aturan skema
        sheet_count_msgs = self._validate_sheet_count(result, min_sheets, max_sheets)
        result.messages.extend(sheet_count_msgs)

        # 9. Tambah message untuk anomali
        for a in result.anomalies:
            result.messages.append(CheckMessage(level=a.severity, text=a.message))

        # 10. Tentukan status overall
        has_fail = any(m.level == "fail" for m in result.messages)
        has_warn = any(m.level == "warning" for m in result.messages)
        if has_fail:
            result.status = "fail"
        elif has_warn:
            result.status = "warning"
        else:
            result.status = "pass"
            result.messages.insert(
                0,
                CheckMessage(
                    level="pass",
                    text=(
                        f"Bagian inti {result.core_physical_sheets} lembar fisik — "
                        f"sesuai batas ({min_sheets or '-'}–{max_sheets} lembar) untuk "
                        f"{self.rules.competition_code}-{self.rules.schema_code}. "
                        f"Tidak ada anomali penomoran terdeteksi."
                    ),
                ),
            )

        return result

    # ------------------------------------------------------------------------
    # Step: locate rentang bagian inti
    # ------------------------------------------------------------------------

    def _locate_core_range(
        self, sheet_texts: list[str]
    ) -> tuple[Optional[int], Optional[int]]:
        """
        Cari lembar fisik (1-based) awal & akhir bagian inti.

        - core_first: lembar pertama yang mengandung heading "BAB 1"
          (bukan entri Daftar Isi). Kita filter dengan dua heuristik:
            (1) match pattern CORE_START_PATTERNS (BAB 1 di awal baris,
                diikuti huruf judul)
            (2) lembar TIDAK didominasi dot leader / nomor halaman
                (ciri khas Daftar Isi)
        - core_last: lembar terakhir PDF.
        """
        core_first: Optional[int] = None
        for i, text in enumerate(sheet_texts):
            # Skip lembar yang jelas Daftar Isi: banyak dot leader
            dot_leader_count = len(self._TOC_CONTEXT_RE.findall(text))
            if dot_leader_count >= 3:
                # ≥3 baris dot leader → lembar ini ToC, skip
                continue

            for pat in self.CORE_START_PATTERNS:
                if pat.search(text):
                    core_first = i + 1
                    break
            if core_first is not None:
                break

        if core_first is None:
            return (None, None)

        core_last = len(sheet_texts)
        return (core_first, core_last)

    # ------------------------------------------------------------------------
    # Step: ekstrak nomor halaman per lembar
    # ------------------------------------------------------------------------

    def _extract_page_numbers(self, sheet_texts: list[str]) -> list[SheetPageNumber]:
        # Nomor halaman tidak mungkin > total lembar × buffer 5x
        # (5x supaya tetap akomodir dokumen yang nomor halamannya di-restart
        # di tengah dokumen, mis. start=19 di section akhir).
        # Minimal 999 untuk safety.
        max_reasonable = max(len(sheet_texts) * 5, 999)
        result: list[SheetPageNumber] = []
        for i, text in enumerate(sheet_texts):
            raw, value, is_roman, is_arabic = _extract_page_number_from_text(
                text, max_reasonable=max_reasonable
            )
            result.append(
                SheetPageNumber(
                    sheet_index=i + 1,
                    page_num_text=raw,
                    page_num_value=value,
                    is_roman=is_roman,
                    is_arabic=is_arabic,
                )
            )
        return result

    # ------------------------------------------------------------------------
    # Step: deteksi anomali
    # ------------------------------------------------------------------------

    def _detect_anomalies(
        self,
        page_numbers: list[SheetPageNumber],
        core_first: int,
        core_last: int,
    ) -> list[PageNumberAnomaly]:
        """
        Hanya analisa rentang [core_first..core_last] (1-based).
        Hanya cek nomor ARAB di zona inti — romawi tidak diharapkan ada di sini
        (kalau ada, nanti PageNumberingChecker yang flag).
        """
        anomalies: list[PageNumberAnomaly] = []

        # Filter ke nomor halaman di zona inti, yang berupa angka arab
        core_pages = [
            p for p in page_numbers
            if core_first <= p.sheet_index <= core_last
        ]

        # 1. Missing: lembar di zona inti tanpa nomor halaman
        for p in core_pages:
            if p.page_num_value is None:
                anomalies.append(
                    PageNumberAnomaly(
                        type="missing",
                        severity="warning",  # tidak fail mati — bisa jadi lembar gambar
                        detail={"sheet_index": p.sheet_index},
                        message=(
                            f"Lembar fisik #{p.sheet_index} tidak terdeteksi nomor halaman. "
                            f"Mungkin lembar gambar atau format nomor non-standar."
                        ),
                    )
                )

        # Untuk analisa duplicate/skipped/out_of_order, hanya pakai yang ada nomor
        numbered = [p for p in core_pages if p.page_num_value is not None and p.is_arabic]

        # 2. Duplicate: nomor sama muncul di >1 lembar
        seen: dict[int, list[int]] = {}
        for p in numbered:
            seen.setdefault(p.page_num_value, []).append(p.sheet_index)
        for num, sheets in seen.items():
            if len(sheets) > 1:
                anomalies.append(
                    PageNumberAnomaly(
                        type="duplicate",
                        severity="fail",
                        detail={"number": str(num), "found_on_sheets": sheets},
                        message=(
                            f"Nomor halaman '{num}' duplikat — muncul di lembar fisik: "
                            f"{', '.join(str(s) for s in sheets)}"
                        ),
                    )
                )

        # 3. Out-of-order & skipped: scan numbered berurutan
        for i in range(1, len(numbered)):
            prev = numbered[i - 1]
            curr = numbered[i]
            diff = curr.page_num_value - prev.page_num_value
            if diff < 0:
                anomalies.append(
                    PageNumberAnomaly(
                        type="out_of_order",
                        severity="fail",
                        detail={
                            "previous": prev.page_num_value,
                            "current": curr.page_num_value,
                            "previous_sheet": prev.sheet_index,
                            "current_sheet": curr.sheet_index,
                        },
                        message=(
                            f"Nomor halaman mundur: dari '{prev.page_num_value}' "
                            f"(lembar #{prev.sheet_index}) ke '{curr.page_num_value}' "
                            f"(lembar #{curr.sheet_index})."
                        ),
                    )
                )
            elif diff > 1:
                # Skipped: ada gap. Tapi diff = 2 dengan 1 lembar di antara yang
                # 'missing' (mis. lembar gambar) bisa wajar; kita tetap flag untuk
                # transparansi, tapi level warning, bukan fail.
                # Kalau gap >= 3 dianggap fail.
                severity = "fail" if diff >= 3 else "warning"
                anomalies.append(
                    PageNumberAnomaly(
                        type="skipped",
                        severity=severity,
                        detail={
                            "after": prev.page_num_value,
                            "next": curr.page_num_value,
                            "gap": diff - 1,
                            "after_sheet": prev.sheet_index,
                            "next_sheet": curr.sheet_index,
                        },
                        message=(
                            f"Nomor halaman meloncat: dari '{prev.page_num_value}' langsung ke "
                            f"'{curr.page_num_value}' (gap {diff - 1} nomor)."
                        ),
                    )
                )

        return anomalies

    # ------------------------------------------------------------------------
    # Step: validasi jumlah lembar inti
    # ------------------------------------------------------------------------

    def _validate_sheet_count(
        self,
        result: PhysicalSheetResult,
        min_sheets: Optional[int],
        max_sheets: int,
    ) -> list[CheckMessage]:
        msgs: list[CheckMessage] = []
        if result.core_first_sheet is None:
            msgs.append(
                CheckMessage(
                    level="fail",
                    text=(
                        "Bagian inti dokumen tidak teridentifikasi: 'BAB 1' tidak "
                        "ditemukan di teks PDF. Mungkin dokumen scan / OCR diperlukan."
                    ),
                )
            )
            return msgs

        count = result.core_physical_sheets
        if count > max_sheets:
            msgs.append(
                CheckMessage(
                    level="fail",
                    text=(
                        f"Bagian inti {count} lembar fisik — melebihi batas {max_sheets} "
                        f"lembar untuk {self.rules.competition_code}-{self.rules.schema_code}."
                    ),
                )
            )
        if min_sheets is not None and count < min_sheets:
            msgs.append(
                CheckMessage(
                    level="fail",
                    text=(
                        f"Bagian inti {count} lembar fisik — kurang dari batas minimum "
                        f"{min_sheets} lembar untuk {self.rules.competition_code}-"
                        f"{self.rules.schema_code}."
                    ),
                )
            )
        return msgs