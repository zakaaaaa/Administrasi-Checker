"""
BiodataDateChecker — validasi tanggal tanda tangan di lampiran biodata PKM-KC.

Tanggal di atas tanda tangan (format: "Kota, DD Bulan YYYY") harus
berada dalam rentang 9 Maret 2026 s.d. 9 April 2026 (inklusif).

Strategi:
    1. Cari teks lampiran (heading + isi) di section Lampiran
    2. OCR semua gambar embedded di section Lampiran
    3. Gabungkan teks + OCR, ekstrak semua pola "Kota, DD Bulan YYYY"
    4. Validasi tiap tanggal terhadap rentang valid
"""

from __future__ import annotations

import re
import zipfile
from dataclasses import dataclass, field
from datetime import date
from typing import Optional
from xml.etree import ElementTree as ET

from app.services.docx_parser import DocxParser


# =============================================================================
# Konstanta
# =============================================================================

_VALID_FROM = date(2026, 3, 9)
_VALID_TO   = date(2026, 4, 9)

_INDONESIAN_MONTHS: dict[str, int] = {
    "januari": 1, "februari": 2, "maret": 3, "april": 4,
    "mei": 5, "juni": 6, "juli": 7, "agustus": 8,
    "september": 9, "oktober": 10, "november": 11, "desember": 12,
}

# "Kota, DD Bulan YYYY" — kota harus proper-case (Awalan Kapital + huruf kecil)
# (?-i:...) menonaktifkan IGNORECASE untuk bagian kota saja agar "AI" / "dengan" tidak ikut match
_DATE_RE = re.compile(
    r"(?<!\w)"
    r"(?-i:[A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})"   # Kota: proper noun, case-sensitive
    r"\s*[,;]\s*"
    r"(\d{1,2})\s+"
    r"(Januari|Februari|Maret|April|Mei|Juni|Juli|Agustus"
    r"|September|Oktober|November|Desember)\s+"
    r"(\d{4})",
    re.IGNORECASE,
)

_LAMPIRAN_SECTION_RE = re.compile(r"^\s*LAMPIRAN\s*$", re.IGNORECASE)

# Sub-lampiran yang MUNGKIN memuat tanggal tanda tangan (positive include):
# biodata (ketua/anggota/dosen) + surat pernyataan ketua.
_DATE_SEGMENT_KEYWORDS: list[list[str]] = [
    ["biodata"],
    ["pernyataan", "ketua"],
]

# Sub-lampiran yang JELAS tidak memuat tanggal tanda tangan (dipakai hanya di
# fallback aman bila tak ada segment biodata/surat terdeteksi via teks).
# (similaritas ditangani terpisah via is_similarity_segment)
_NON_DATE_LAMPIRAN_KEYWORDS: list[list[str]] = [
    ["jadwal", "kegiatan"],
    ["justifikasi", "anggaran"],
    ["susunan", "tim", "pengusul"],
]

# OOXML namespaces
_W_NS  = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
_R_NS  = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
_A_NS  = "http://schemas.openxmlformats.org/drawingml/2006/main"
_REL_TYPE_IMAGE = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/image"


# =============================================================================
# Data classes
# =============================================================================


@dataclass
class CheckMessage:
    level: str
    text: str


@dataclass
class BiodataDateResult:
    status: str
    messages: list[CheckMessage] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "messages": [{"level": m.level, "text": m.text} for m in self.messages],
        }


# =============================================================================
# BiodataDateChecker
# =============================================================================


class BiodataDateChecker:
    """
    Validasi tanggal tanda tangan di lampiran biodata PKM-KC.

    Cara pakai:
        result = BiodataDateChecker.for_pkm_kc(parser).check()
    """

    def __init__(self, parser: DocxParser, schema_label: str = "PKM-KC"):
        self.parser = parser
        self.schema_label = schema_label

    @classmethod
    def for_pkm_kc(cls, parser: DocxParser) -> "BiodataDateChecker":
        return cls(parser, "PKM-KC")

    @classmethod
    def for_pkm_re(cls, parser: DocxParser) -> "BiodataDateChecker":
        return cls(parser, "PKM-RE")

    @classmethod
    def for_pkm_rsh(cls, parser: DocxParser) -> "BiodataDateChecker":
        return cls(parser, "PKM-RSH")

    @classmethod
    def for_pkm_k(cls, parser: DocxParser) -> "BiodataDateChecker":
        return cls(parser, "PKM-K")

    @classmethod
    def for_pkm_ki(cls, parser: DocxParser) -> "BiodataDateChecker":
        return cls(parser, "PKM-KI")

    @classmethod
    def for_pkm_pi(cls, parser: DocxParser) -> "BiodataDateChecker":
        return cls(parser, "PKM-PI")

    @classmethod
    def for_pkm_pm(cls, parser: DocxParser) -> "BiodataDateChecker":
        return cls(parser, "PKM-PM")

    # -------------------------------------------------------------------------
    # Public
    # -------------------------------------------------------------------------

    def check(self, index=None) -> BiodataDateResult:
        """`index` = LampiranOcrIndex bersama (opsional). Jika None, dibuat sendiri."""
        result = BiodataDateResult(status="pass")

        lamp_start = self._find_lampiran_section_start()

        # 1. Teks dari section Lampiran (tetap penuh — gratis, tak ubah hasil)
        text_corpus = self._collect_lampiran_text(lamp_start)

        # 2. OCR — hanya segment yang relevan untuk tanggal tanda tangan
        #    (biodata + surat pernyataan), lewati jadwal/justifikasi/susunan/similaritas.
        #    Pakai cache bersama agar gambar yang sudah di-OCR lampiran tak diulang.
        ocr_text = self._ocr_date_segments(lamp_start, index)

        combined = text_corpus + " " + ocr_text

        # 3. Ekstrak semua tanggal
        found_dates = _extract_dates(combined)

        if not found_dates:
            result.status = "warning"
            result.messages.append(CheckMessage(
                level="warning",
                text=(
                    "Tanggal tanda tangan di lampiran biodata tidak dapat terdeteksi. "
                    "Periksa secara manual — tanggal harus antara 9 Maret s.d. 9 April 2026."
                ),
            ))
            return result

        # 4. Validasi tiap tanggal
        invalid: list[tuple[date, str]] = [
            (d, raw) for d, raw in found_dates
            if not (_VALID_FROM <= d <= _VALID_TO)
        ]

        if invalid:
            result.status = "fail"
            for d, raw in invalid:
                result.messages.append(CheckMessage(
                    level="fail",
                    text=(
                        f"Tanggal '{raw.strip()}' di lampiran biodata tidak valid. "
                        f"Harus antara 9 Maret 2026 s.d. 9 April 2026."
                    ),
                ))
        else:
            result.messages.append(CheckMessage(
                level="pass",
                text=(
                    f"Tanggal di lampiran biodata {self.schema_label} sesuai "
                    f"({len(found_dates)} tanggal terdeteksi, semua dalam rentang "
                    f"9 Maret s.d. 9 April 2026)."
                ),
            ))

        return result

    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------

    def _find_lampiran_section_start(self) -> Optional[int]:
        for p in self.parser.paragraphs:
            if _LAMPIRAN_SECTION_RE.match(p.text.strip()):
                return p.index
        return None

    def _collect_lampiran_text(self, start_idx: Optional[int]) -> str:
        parts: list[str] = []
        for p in self.parser.paragraphs:
            if start_idx is not None and p.index < start_idx:
                continue
            if p.text.strip():
                parts.append(p.text)
        return " ".join(parts)

    def _ocr_date_segments(self, lamp_start: Optional[int], index=None) -> str:
        """
        OCR gambar HANYA pada sub-lampiran biodata + surat pernyataan (positive
        include) — di situlah tanggal tanda tangan berada. Sub-lampiran lain
        (jadwal/justifikasi/susunan/gambaran teknologi/similaritas dll) dilewati.
        Pakai cache OCR bersama (index) agar gambar tak di-OCR ulang antar checker.

        Safety fallback: kalau tak ada segment biodata/surat yang terdeteksi via
        teks (mis. heading-nya berupa gambar), pakai cakupan lama (semua kecuali
        yang jelas bukan-tanggal) supaya tanggal tidak terlewat.
        """
        from app.services.lampiran_index import LampiranOcrIndex

        if index is None:
            index = LampiranOcrIndex(self.parser)

        seg_start = index.find_section_start()
        if seg_start is None:
            seg_start = lamp_start

        segs = index.segments(seg_start)
        if not segs:
            # Tak ada segment terdeteksi → perilaku lama: OCR semua gambar dari lamp_start.
            return index.ocr_text_for_rids(index.rids_in_range(lamp_start))

        # Positive include: segment yang teksnya cocok biodata / surat pernyataan.
        included_rids: list[str] = []
        for seg in segs:
            if index.is_similarity_segment(seg):
                continue
            sl = (seg.seg_text or "").lower()
            if any(all(k in sl for k in kws) for kws in _DATE_SEGMENT_KEYWORDS):
                included_rids.extend(seg.image_rids)

        if included_rids:
            return index.ocr_text_for_rids(included_rids)

        # Fallback aman: tak ada segment biodata/surat via teks → cakupan lama.
        fallback_rids: list[str] = []
        for seg in segs:
            if index.is_similarity_segment(seg):
                continue
            sl = (seg.seg_text or "").lower()
            if any(all(k in sl for k in kws) for kws in _NON_DATE_LAMPIRAN_KEYWORDS):
                continue
            fallback_rids.extend(seg.image_rids)
        return index.ocr_text_for_rids(fallback_rids)

# =============================================================================
# OCR — delegasi ke Google Vision (lihat ocr_engine.py)
# =============================================================================


def preload_ocr_model() -> None:
    """Preload Vision client di startup biar request pertama tak nunggu init."""
    from app.services.ocr_engine import preload_ocr_engine
    preload_ocr_engine()


def _run_ocr(images: list) -> list[str]:
    """
    Entry point OCR semua checker. Delegasi ke Google Vision.
    Output: list teks per gambar, urutan dipertahankan. Konsumen (similarity,
    lampiran_index) import dari sini — signature & semantic dijaga.
    """
    from app.services.ocr_engine import get_ocr_engine
    return get_ocr_engine().run(images)


# =============================================================================
# Helpers OOXML
# =============================================================================


def _load_image_rels(zf: zipfile.ZipFile) -> dict[str, str]:
    rel_map: dict[str, str] = {}
    try:
        with zf.open("word/_rels/document.xml.rels") as f:
            root = ET.parse(f).getroot()
        ns = "http://schemas.openxmlformats.org/package/2006/relationships"
        for rel in root.findall(f"{{{ns}}}Relationship"):
            if rel.get("Type") == _REL_TYPE_IMAGE:
                rid = rel.get("Id", "")
                target = rel.get("Target", "").lstrip("./").lstrip("/")
                if target.startswith("media/"):
                    rel_map[rid] = target
    except Exception:
        pass
    return rel_map


# =============================================================================
# Date helpers
# =============================================================================


# Strip tanggal lahir: "Tempat dan Tanggal [Lahir] ... DD Bulan YYYY"
# Menangani OCR misread "Tempat"→"Tcmpat" dan format tanpa kata "Lahir".
# Gap pakai [\s\S]{0,300}? (lazy, lintas newline) agar match ke layout tabel Vision
# yang taruh label kolom dulu (mengandung digit) baru value-nya.
_TTL_RE = re.compile(
    r"(?:t[ce]?mpat\s+dan\s+tanggal(?:\s+lahir)?|tanggal\s+lahir|t\.?\s*t\.?\s*l\.?)"
    r"[\s\S]{0,300}?\d{1,2}\s+"
    r"(?:Januari|Februari|Maret|April|Mei|Juni|Juli|Agustus"
    r"|September|Oktober|November|Desember)\s+\d{4}",
    re.IGNORECASE,
)


def _strip_birthdate_lines(text: str) -> str:
    """Hapus baris 'Tempat dan Tanggal Lahir ...' agar tanggal lahir tidak ikut terdeteksi."""
    return _TTL_RE.sub("", text)


def _extract_dates(text: str) -> list[tuple[date, str]]:
    """Ekstrak semua tanggal format 'Kota, DD Bulan YYYY' dari teks (tanggal lahir dikecualikan).
    Setiap kemunculan dihitung terpisah sehingga bisa mendeteksi tanggal per orang.
    """
    clean = _strip_birthdate_lines(text)
    results: list[tuple[date, str]] = []

    for m in _DATE_RE.finditer(clean):
        day_str   = m.group(1)
        month_str = m.group(2).lower()
        year_str  = m.group(3)

        month = _INDONESIAN_MONTHS.get(month_str)
        if month is None:
            continue
        try:
            d = date(int(year_str), month, int(day_str))
        except ValueError:
            continue

        # Simpan hanya bagian tanggalnya (tanpa prefix kota/tempat) untuk pesan.
        date_only = f"{m.group(1)} {m.group(2)} {year_str}"
        results.append((d, date_only))

    return results
