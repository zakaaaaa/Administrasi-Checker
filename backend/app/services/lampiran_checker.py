"""
LampiranChecker — validasi kelengkapan lampiran wajib (PKM-KC & PKM-VGK).

Strategi 3-stage:
    Stage 1. Cek heading "DAFTAR LAMPIRAN" ada di dokumen.
             - Tidak ada → return fail dengan SATU pesan "DAFTAR LAMPIRAN
               tidak ditemukan". Stop, tidak enumerasi lampiran.
    Stage 2. Untuk tiap lampiran wajib, cek body section Lampiran (setelah
             heading "LAMPIRAN" body):
             a) Scan teks paragraf — heading "Lampiran N ..." + kata kunci.
             b) Kalau (a) gagal, fallback OCR (Google Vision via LampiranOcrIndex)
                pada gambar di body Lampiran — sering pakai kalau biodata/surat
                pernyataan di-scan jadi image.
    Stage 3. Untuk lampiran yang ADA di body tapi TIDAK terdaftar di blok
             "Daftar Lampiran" depan → flag mismatch.

Pesan output (tiga jenis):
    (a) "DAFTAR LAMPIRAN tidak ditemukan"
    (b) 'Tidak ditemukan Lampiran N "<label>" pada halaman lampiran'
    (c) 'Kesalahan kelengkapan Daftar Lampiran, tidak ditemukan "<label>"'

Aturan kombinasi:
    - Kalau Daftar Lampiran tidak ada → hanya (a). Tidak enumerasi (b)/(c).
    - Kalau lampiran X missing di body → hanya (b). Skip (c) walau di daftar
      juga missing (akar masalah di body, bukan kelengkapan daftar).
    - Kalau lampiran X ada di body tapi tidak di daftar → (c).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

from app.services.docx_parser import DocxParser


# =============================================================================
# Konfigurasi lampiran wajib per skema
# =============================================================================

# Tuple format: (nomor, kata_kunci_judul, label_tampil)
# Kata kunci = daftar substring lower-case yang HARUS muncul di window 200 char
# setelah anchor "Lampiran N" (untuk body text) / di blok daftar.

_REQUIRED_LAMPIRAN_KC: list[tuple[int, list[str], str]] = [
    (1, ["jadwal", "kegiatan"],                          "Format Jadwal Kegiatan"),
    (2, ["biodata", "ketua", "anggota"],                 "Biodata Ketua dan Anggota"),
    (3, ["biodata", "dosen", "pendamping"],              "Biodata Dosen Pendamping"),
    (4, ["justifikasi", "anggaran"],                     "Format Justifikasi Anggaran Kegiatan"),
    (5, ["susunan", "tim", "pengusul", "pembagian"],     "Susunan Tim Pengusul dan Pembagian Tugas"),
    (6, ["pernyataan", "ketua"],                         "Surat Pernyataan Ketua Tim Pengusul"),
    (7, ["uji", "similar"],                              "Hasil Uji Periksa Similaritas Proposal"),
]

_REQUIRED_LAMPIRAN_VGK: list[tuple[int, list[str], str]] = [
    (1, ["biodata", "ketua", "dosen"],                   "Biodata Ketua dan Anggota, serta Dosen Pendamping"),
    (2, ["justifikasi", "anggaran"],                     "Justifikasi Anggaran Kegiatan"),
    (3, ["susunan", "tim", "pengusul", "pembagian"],     "Susunan Tim Pengusul dan Pembagian Tugas"),
    (4, ["pernyataan", "ketua"],                         "Surat Pernyataan Ketua Tim Pengusul"),
    (5, ["uji", "similar"],                              "Hasil Uji Periksa Similaritas Proposal"),
]


# =============================================================================
# Regex
# =============================================================================

# Heading LAMPIRAN (batas awal section lampiran di body)
_LAMPIRAN_SECTION_RE = re.compile(r"^\s*LAMPIRAN\s*$", re.IGNORECASE)
# Heading "DAFTAR LAMPIRAN" / "DAFTAR LAMPIRAN-LAMPIRAN" di depan dokumen
_DAFTAR_LAMPIRAN_RE = re.compile(r"^\s*daftar\s+lampiran(?:-lampiran)?\s*$", re.IGNORECASE)
# Pattern "Lampiran N" — N angka atau romawi
_LAMPIRAN_N_RE = re.compile(r"\blampiran\s+(\d+|[IVXLC]+)\b", re.IGNORECASE)


# =============================================================================
# Data classes
# =============================================================================


@dataclass
class CheckMessage:
    level: str
    text: str


@dataclass
class LampiranCheckResult:
    status: str
    messages: list[CheckMessage] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "messages": [{"level": m.level, "text": m.text} for m in self.messages],
        }


# =============================================================================
# LampiranChecker
# =============================================================================


class LampiranChecker:
    def __init__(
        self,
        parser: DocxParser,
        required: list[tuple[int, list[str], str]],
        schema_label: str,
    ):
        self.parser = parser
        self.required = required
        self.schema_label = schema_label

    @classmethod
    def for_pkm_kc(cls, parser: DocxParser) -> "LampiranChecker":
        return cls(parser, _REQUIRED_LAMPIRAN_KC, "PKM-KC")

    @classmethod
    def for_pkm_vgk(cls, parser: DocxParser) -> "LampiranChecker":
        return cls(parser, _REQUIRED_LAMPIRAN_VGK, "PKM-VGK")

    @classmethod
    def for_pkm_re(cls, parser: DocxParser) -> "LampiranChecker":
        # PKM-RE pakai daftar lampiran wajib yang SAMA dengan PKM-KC.
        return cls(parser, _REQUIRED_LAMPIRAN_KC, "PKM-RE")

    @classmethod
    def for_pkm_rsh(cls, parser: DocxParser) -> "LampiranChecker":
        # PKM-RSH pakai daftar lampiran wajib yang SAMA dengan PKM-KC.
        return cls(parser, _REQUIRED_LAMPIRAN_KC, "PKM-RSH")

    # -------------------------------------------------------------------------
    # Public
    # -------------------------------------------------------------------------

    def check(self, index=None) -> LampiranCheckResult:
        result = LampiranCheckResult(status="pass")

        # Stage 1: DAFTAR LAMPIRAN ada?
        daftar_start = self._find_daftar_lampiran_idx()
        if daftar_start is None:
            result.status = "fail"
            result.messages.append(CheckMessage(
                level="fail",
                text="DAFTAR LAMPIRAN tidak ditemukan",
            ))
            return result

        # Stage 2: korpus untuk pengecekan
        daftar_corpus = self._collect_daftar_lampiran_text(daftar_start)
        body_start = self._find_lampiran_section_start()
        body_text_corpus = self._collect_text_from_lampiran(body_start)

        # OCR body section hanya dipanggil kalau perlu (lazy)
        ocr_corpus_cache: Optional[str] = None

        def body_ocr_text() -> str:
            nonlocal ocr_corpus_cache, index
            if ocr_corpus_cache is not None:
                return ocr_corpus_cache
            if body_start is None:
                ocr_corpus_cache = ""
                return ocr_corpus_cache
            if index is None:
                from app.services.lampiran_index import LampiranOcrIndex
                index = LampiranOcrIndex(self.parser)
            rids = index.rids_in_range(body_start)
            ocr_corpus_cache = index.ocr_text_for_rids(rids) if rids else ""
            return ocr_corpus_cache

        missing_in_body: list[tuple[int, str]] = []
        missing_in_daftar_only: list[tuple[int, str]] = []

        for num, keywords, label in self.required:
            in_body_text = _anchored_keywords_match(keywords, body_text_corpus)
            in_body = in_body_text
            if not in_body:
                ocr_text = body_ocr_text()
                if ocr_text:
                    # OCR fallback: terima anchored ATAU keyword-anywhere
                    # (heading "Lampiran N" di gambar tak selalu ter-OCR jelas).
                    in_body = (
                        _anchored_keywords_match(keywords, ocr_text)
                        or _keywords_in_text(keywords, ocr_text)
                    )

            in_daftar = _anchored_keywords_match(keywords, daftar_corpus)

            if not in_body:
                missing_in_body.append((num, label))
            elif not in_daftar:
                missing_in_daftar_only.append((num, label))

        # Stage 3: susun pesan
        for num, label in missing_in_body:
            result.messages.append(CheckMessage(
                level="fail",
                text=f'Tidak ditemukan Lampiran {num} "{label}" pada halaman lampiran',
            ))
        for num, label in missing_in_daftar_only:
            result.messages.append(CheckMessage(
                level="fail",
                text=f'Kesalahan kelengkapan Daftar Lampiran, tidak ditemukan "{label}"',
            ))

        if result.messages:
            result.status = "fail"
        else:
            result.messages.append(CheckMessage(
                level="pass",
                text=(
                    f"Kelengkapan lampiran {self.schema_label} sesuai: semua "
                    f"{len(self.required)} lampiran wajib ditemukan di Daftar "
                    f"Lampiran dan halaman Lampiran."
                ),
            ))
        return result

    # -------------------------------------------------------------------------
    # Helpers: lokasi section
    # -------------------------------------------------------------------------

    def _find_daftar_lampiran_idx(self) -> Optional[int]:
        for p in self.parser.paragraphs:
            if _DAFTAR_LAMPIRAN_RE.match(p.text.strip()):
                return p.index
        return None

    def _find_lampiran_section_start(self) -> Optional[int]:
        for p in self.parser.paragraphs:
            t = p.text.strip()
            if _LAMPIRAN_SECTION_RE.match(t) and p.is_heading:
                return p.index
        return None

    # -------------------------------------------------------------------------
    # Helpers: korpus teks
    # -------------------------------------------------------------------------

    def _collect_daftar_lampiran_text(self, daftar_idx: int) -> str:
        """
        Teks entri di blok Daftar Lampiran — sampai heading section lain.

        Pendekatan ganda:
        1. Coba dari parser.paragraphs (cepat, lazim).
        2. Kalau hasil kosong/sangat pendek (kasus TOC field code yang berada di
           dalam <w:sdt> dan TIDAK dienumerasi sebagai paragraf python-docx),
           jatuh ke ekstraksi XML body langsung — termasuk konten SDT.
        """
        parts: list[str] = []
        next_heading_idx: Optional[int] = None
        for p in self.parser.paragraphs:
            if p.index <= daftar_idx:
                continue
            t = p.text.strip()
            if p.is_heading and t and not _LAMPIRAN_N_RE.search(t):
                next_heading_idx = p.index
                break
            if t:
                parts.append(p.text)
        result = " ".join(parts)

        # Fallback XML kalau kosong (TOC field di <w:sdt>) — extract dari body XML.
        if not result.strip():
            result = self._collect_daftar_lampiran_text_xml(daftar_idx, next_heading_idx)
        return result

    def _collect_daftar_lampiran_text_xml(
        self, daftar_idx: int, next_heading_idx: Optional[int]
    ) -> str:
        """Extract teks dari semua node setelah paragraf DAFTAR LAMPIRAN sampai
        paragraf heading berikutnya (eksklusif). Iterasi anak-langsung <w:body>,
        ambil semua <w:t> dalam <w:p> dan <w:sdt> (TOC field)."""
        from docx.oxml.ns import qn
        try:
            body = self.parser.doc.element.body
        except Exception:
            return ""
        para_counter = -1
        parts: list[str] = []

        def _extract_text(el) -> str:
            # Pisah dengan spasi: hindari "Pendamping11Lampiran" yang menghilangkan
            # word-boundary di regex _LAMPIRAN_N_RE.
            return " ".join(
                (t.text or "").strip()
                for t in el.iter(qn("w:t"))
                if (t.text or "").strip()
            )

        for child in body:
            tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
            if tag == "p":
                para_counter += 1
                if para_counter <= daftar_idx:
                    continue
                if next_heading_idx is not None and para_counter >= next_heading_idx:
                    break
                text = _extract_text(child)
                if text:
                    parts.append(text)
            elif tag == "sdt":
                # SDT (TOC field) berada di antara paragraf — counter paragraf tidak
                # bergerak. Hanya ambil setelah daftar_idx sudah lewat.
                if para_counter < daftar_idx:
                    continue
                if next_heading_idx is not None and para_counter >= next_heading_idx:
                    break
                text = _extract_text(child)
                if text:
                    parts.append(text)
        return " ".join(parts)

    def _collect_text_from_lampiran(self, start_idx: Optional[int]) -> str:
        """Kumpulkan teks paragraf mulai dari heading 'LAMPIRAN' body s.d. akhir."""
        if start_idx is None:
            return ""
        parts: list[str] = []
        for p in self.parser.paragraphs:
            if p.index < start_idx:
                continue
            if p.text.strip():
                parts.append(p.text)
        return " ".join(parts)


# =============================================================================
# Helpers: matching kata kunci
# =============================================================================


def _anchored_keywords_match(keywords: list[str], corpus: str) -> bool:
    """
    Tiap "Lampiran N" di corpus → window 200 char setelahnya; match kalau
    SEMUA keyword muncul di window. Tidak tergantung nomor N — agar variasi
    penomoran lapangan tidak menggagalkan match.
    """
    if not corpus or not keywords:
        return False
    cl = corpus.lower()
    for m in _LAMPIRAN_N_RE.finditer(cl):
        window = cl[m.start(): m.start() + 200]
        if all(kw in window for kw in keywords):
            return True
    return False


def _keywords_in_text(keywords: list[str], corpus: str) -> bool:
    """
    Fallback longgar untuk OCR: cukup semua keyword muncul di corpus, tanpa
    anchor "Lampiran N" (kadang heading di gambar tak ter-OCR jelas, tapi isi
    form-nya jelas terbaca dan memuat kata kunci judul lampiran).
    """
    if not corpus or not keywords:
        return False
    cl = corpus.lower()
    return all(kw in cl for kw in keywords)
