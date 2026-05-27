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

import io
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

    def _ocr_lampiran_images(self, lampiran_section_idx: Optional[int]) -> str:
        import logging
        log = logging.getLogger(__name__)

        try:
            from PIL import Image
        except ImportError as e:
            log.warning(f"[biodata_date] PIL not available: {e}")
            return ""

        docx_path = str(self.parser.file_path)
        ocr_parts: list[str] = []

        try:
            with zipfile.ZipFile(docx_path, "r") as zf:
                rel_map = _load_image_rels(zf)
                if not rel_map:
                    log.warning("[biodata_date] No image rels found in docx")
                    return ""

                with zf.open("word/document.xml") as f:
                    doc_xml = ET.parse(f).getroot()

                body = doc_xml.find(f"{{{_W_NS}}}body")
                if body is None:
                    return ""

                rids = _collect_image_rids_after(body, lampiran_section_idx, self.parser.paragraphs)
                log.info(f"[biodata_date] Found {len(rids)} images in lampiran section")
                if not rids:
                    return ""

                images: list = []
                for rid in rids:
                    img_path = rel_map.get(rid)
                    if not img_path:
                        continue
                    full_path = f"word/{img_path}" if not img_path.startswith("word/") else img_path
                    try:
                        img_bytes = zf.read(full_path)
                        images.append(Image.open(io.BytesIO(img_bytes)))
                    except Exception as e:
                        log.warning(f"[biodata_date] Failed to open image {full_path}: {e}")
                        continue

                log.info(f"[biodata_date] Loaded {len(images)} images, running OCR...")
                if not images:
                    return ""

                ocr_parts = _run_ocr(images)
                log.info(f"[biodata_date] OCR done, total chars: {sum(len(t) for t in ocr_parts)}")

        except Exception as e:
            log.error(f"[biodata_date] OCR failed: {e}", exc_info=True)
            return ""

        return " ".join(ocr_parts)


# =============================================================================
# OCR engine (pytesseract → easyocr fallback)
# =============================================================================

_easyocr_reader = None  # lazy singleton


def preload_ocr_model() -> None:
    """Inisialisasi easyocr reader di awal agar request pertama tidak lelet."""
    global _easyocr_reader
    if _easyocr_reader is not None:
        return
    try:
        import easyocr
        _easyocr_reader = easyocr.Reader(["id", "en"], gpu=False, verbose=False)
    except Exception:
        pass


_OCR_MONTH_FIXES: dict[str, str] = {
    "mci": "Mei", "meil": "Mei", "mel": "Mei",
    "apri": "April", "apnl": "April",
    "marct": "Maret", "maret": "Maret",
    "januari": "Januari", "januan": "Januari",
    "februari": "Februari", "pebruari": "Februari",
    "junl": "Juni", "junh": "Juni",
    "agustus": "Agustus", "agustua": "Agustus",
    "septembcr": "September", "septembér": "September",
    "oktobcr": "Oktober",
    "novembcr": "November",
    "desembcr": "Desember", "desember": "Desember",
}

_MONTH_FIX_RE = re.compile(
    r"\b(" + "|".join(re.escape(k) for k in _OCR_MONTH_FIXES) + r")\b",
    re.IGNORECASE,
)


def _fix_ocr_months(text: str) -> str:
    def _replace(m: re.Match) -> str:
        return _OCR_MONTH_FIXES.get(m.group(0).lower(), m.group(0))
    return _MONTH_FIX_RE.sub(_replace, text)


_ROTATION_SCORE_THRESHOLD = 15  # skor tinggi → orientasi pasti benar, stop
_ROTATION_FAST_ACCEPT = 3       # skor minimal di 0° untuk terima tanpa coba rotasi lain
_OCR_MAX_DIM = 1500             # downscale sisi terpanjang sebelum OCR (waktu easyocr ∝ piksel)

# "Sudah ada tanggal / persen" → jika 0° memuat ini, orientasi sudah benar, tak perlu rotasi.
_ANY_DATE_RE = re.compile(
    r"\d{1,2}\s+(?:Januari|Februari|Maret|April|Mei|Juni|Juli|Agustus"
    r"|September|Oktober|November|Desember)\s+\d{4}",
    re.IGNORECASE,
)
_ANY_PERCENT_RE = re.compile(r"\d{1,3}\s*%")


def _downscale_for_ocr(img):
    """Kecilkan gambar besar (jaga rasio) agar OCR lebih cepat. No-op jika sudah kecil."""
    w, h = img.size
    longest = max(w, h)
    if longest <= _OCR_MAX_DIM:
        return img
    scale = _OCR_MAX_DIM / float(longest)
    return img.resize((max(1, int(w * scale)), max(1, int(h * scale))))


def _rotation_score(text: str) -> int:
    return sum(1 for w in text.split() if w.isalpha() and len(w) > 3)


def _ocr_arr(arr, reader) -> str:
    return " ".join(reader.readtext(arr, detail=0, paragraph=True))


def _best_rotation_text(img, reader) -> str:
    """
    OCR satu gambar dengan auto-rotate hemat:
      - downscale dulu (waktu ∝ piksel),
      - OCR 0° dulu; terima langsung jika skor cukup (≥3) ATAU sudah memuat
        pola tanggal/persen — gambar tegak (mayoritas) cukup 1× OCR,
      - hanya jika 0° nyaris kosong baru coba 90/180/270° dan pilih terbaik
        (early-stop bila skor sangat tinggi).
    """
    import numpy as np
    img = _downscale_for_ocr(img)

    try:
        text0 = _ocr_arr(np.array(img.convert("RGB")), reader)
    except Exception:
        text0 = ""
    score0 = _rotation_score(text0)
    if (
        score0 >= _ROTATION_FAST_ACCEPT
        or _ANY_DATE_RE.search(text0)
        or _ANY_PERCENT_RE.search(text0)
    ):
        return text0

    # 0° nyaris kosong → kemungkinan gambar miring; coba orientasi lain.
    best_text, best_score = text0, score0
    for angle in (90, 180, 270):
        try:
            arr = np.array(img.rotate(angle, expand=True).convert("RGB"))
            text = _ocr_arr(arr, reader)
        except Exception:
            continue
        score = _rotation_score(text)
        if score > best_score:
            best_score, best_text = score, text
        if score >= _ROTATION_SCORE_THRESHOLD:
            break
    return best_text


def _run_ocr(images: list) -> list[str]:
    """Pakai easyocr dengan auto-rotate dan normalisasi bulan. Return list teks per gambar."""
    import logging
    log = logging.getLogger(__name__)

    # --- pytesseract (opsional, jika tersedia) ---
    try:
        import pytesseract
        results = []
        for img in images:
            try:
                text = pytesseract.image_to_string(img, lang="ind+eng", config="--psm 6")
                if text.strip():
                    results.append(_fix_ocr_months(text))
            except Exception as e:
                log.warning(f"[biodata_date] pytesseract per-image error: {e}")
        if results:
            log.info(f"[biodata_date] pytesseract OK: {len(results)} images with text")
            return results
        log.info("[biodata_date] pytesseract returned no text, trying easyocr...")
    except Exception as e:
        log.warning(f"[biodata_date] pytesseract unavailable: {e}")

    # --- easyocr dengan auto-rotate ---
    try:
        import easyocr
        global _easyocr_reader
        if _easyocr_reader is None:
            log.info("[biodata_date] Initializing easyocr reader...")
            _easyocr_reader = easyocr.Reader(["id", "en"], gpu=False, verbose=False)
        results = []
        for img in images:
            try:
                text = _best_rotation_text(img, _easyocr_reader)
                if text.strip():
                    results.append(_fix_ocr_months(text))
            except Exception as e:
                log.warning(f"[biodata_date] easyocr per-image error: {e}")
        log.info(f"[biodata_date] easyocr OK: {len(results)} images with text")
        return results
    except Exception as e:
        log.error(f"[biodata_date] easyocr failed: {e}", exc_info=True)

    return []


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


def _collect_image_rids_after(
    body: ET.Element,
    lampiran_section_idx: Optional[int],
    paragraphs,
) -> list[str]:
    rids: list[str] = []
    if lampiran_section_idx is not None:
        valid_indices = {p.index for p in paragraphs if p.index >= lampiran_section_idx}
    else:
        valid_indices = {p.index for p in paragraphs}

    para_counter = 0
    for child in body:
        tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
        if tag == "p":
            if para_counter in valid_indices:
                for blip in child.iter(f"{{{_A_NS}}}blip"):
                    rid = blip.get(f"{{{_R_NS}}}embed")
                    if rid:
                        rids.append(rid)
                _V_NS = "urn:schemas-microsoft-com:vml"
                for imgdata in child.iter(f"{{{_V_NS}}}imagedata"):
                    rid = imgdata.get(f"{{{_R_NS}}}id")
                    if rid:
                        rids.append(rid)
            para_counter += 1

    return rids


# =============================================================================
# Date helpers
# =============================================================================


# Strip tanggal lahir: "Tempat dan Tanggal [Lahir] ... DD Bulan YYYY"
# Menangani OCR misread "Tempat"→"Tcmpat" dan format tanpa kata "Lahir"
_TTL_RE = re.compile(
    r"(?:t[ce]?mpat\s+dan\s+tanggal(?:\s+lahir)?|t\.?\s*t\.?\s*l\.?)"
    r"[^\d]*\d{1,2}\s+"
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
