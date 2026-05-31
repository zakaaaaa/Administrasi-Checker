"""
SimilarityChecker — validasi persentase hasil uji similaritas (Turnitin) PKM-KC.

Persentase "Overall Similarity" pada Lampiran "Hasil Uji Periksa Similaritas"
tidak boleh > 25% (25% masih lolos).

Persentasenya ada DI DALAM GAMBAR (screenshot overview Turnitin) yang ter-embed
di .docx — bukan teks — jadi butuh OCR. Agar cepat:
- hanya beberapa gambar PERTAMA lampiran similaritas yang di-OCR (gambar 1-2),
- gambar di-crop ke bagian atas (tempat "XX% Overall Similarity"),
- berhenti begitu angka ditemukan.

Angka diekstrak dengan regex yang DI-ANCHOR ke "Overall Similarity"/"Similarity
Index" supaya tidak tertukar dengan persentase Top Sources (mis. 17%, 3%, 12%).
"""

from __future__ import annotations

import io
import re
import zipfile
from dataclasses import dataclass, field
from typing import Optional
from xml.etree import ElementTree as ET

from app.services.docx_parser import DocxParser
from app.services.similarity_rules import (
    SimilarityRules,
    get_pkm_kc_similarity_rules,
    get_pkm_vgk_similarity_rules,
    get_pkm_re_similarity_rules,
    get_pkm_rsh_similarity_rules,
    get_pkm_k_similarity_rules,
    get_pkm_ki_similarity_rules,
    get_pkm_pi_similarity_rules,
    get_pkm_pm_similarity_rules,
    get_pkm_ai_similarity_rules,
    get_pkm_gft_similarity_rules,
)
from app.services.biodata_date_checker import (
    _load_image_rels,
    _run_ocr,
    _W_NS,
    _R_NS,
    _A_NS,
)


@dataclass
class CheckMessage:
    level: str
    text: str


@dataclass
class SimilarityCheckResult:
    status: str
    messages: list[CheckMessage] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "messages": [{"level": m.level, "text": m.text} for m in self.messages],
        }


# Regex di-anchor ke "Overall Similarity" / "Similarity Index" / "Originality Report"
# (bukan persen sembarang). Mendukung dua layout Turnitin yang umum:
#   A. "Overall Similarity: 25%" — label DULU lalu angka, single-line.
#   B. Layout overview Turnitin baru:
#          ORIGINALITY REPORT
#          X%    Y%    Z%    W%
#          SIMILARITY INDEX   INTERNET   PUBLICATIONS   STUDENT PAPERS
#      → Vision OCR membaca dengan urutan tergantung crop:
#         - Column-by-column: "X% Y% Z% W% SIMILARITY INDEX ..." (X = overall)
#         - Row-by-row:       "X% SIMILARITY INDEX Y% INTERNET ..." (X = overall)
#      Kedua kasus: X% adalah angka PERTAMA setelah "ORIGINALITY REPORT".
#
# Priority: anchor "Originality Report" PALING DULU karena paling reliable.
_SIM_PATTERNS = [
    # Paling reliable: angka pertama setelah "Originality Report".
    re.compile(r"originality\s+report[\s\S]{0,30}?(\d{1,3})\s*%", re.IGNORECASE),
    # Layout A: "XX% Overall Similarity" / "Overall Similarity: XX%"
    re.compile(r"(\d{1,3})\s*%\s*overall\s+similarit", re.IGNORECASE),
    re.compile(r"overall\s+similarit\w*\s*[:\-]?\s*(\d{1,3})\s*%", re.IGNORECASE),
    # Layout B fallback: angka mendahului "SIMILARITY INDEX" (column order).
    re.compile(r"(\d{1,3})\s*%[\s\S]{0,15}?similarity\s+index", re.IGNORECASE),
    # Layout A fallback: "Similarity Index: XX%" (kasus lama).
    re.compile(r"similarity\s+index\s*[:\-]?\s*(\d{1,3})\s*%", re.IGNORECASE),
]

_LAMPIRAN_N_RE = re.compile(r"\blampiran\s+(?:\d+|[ivxlc]+)", re.IGNORECASE)
_SIM_HEADING_RE = re.compile(r"(similarit|uji\s+periksa|turnitin|plagiar)", re.IGNORECASE)

# Heading lampiran similaritas: "Lampiran N ..." DI AWAL baris. Di-anchor ke awal
# supaya paragraf body yang kebetulan menyebut "similaritas" tidak ikut ter-match,
# sehingga batas panjang boleh longgar — heading asli sering >90 char karena memuat
# embel-embel, mis. "Lampiran 6. Hasil Uji Periksa Similaritas Proposal (Turnitin)
# dengan indeks similaritas maksimum 25%".
_LAMPIRAN_HEAD_RE = re.compile(r"^\s*lampiran\s+(?:\d+|[ivxlc]+)\b", re.IGNORECASE)
_MAX_SIM_HEADING_LEN = 160


def _extract_similarity_percent(text: str) -> Optional[int]:
    """Ambil angka 'Overall Similarity' dari teks OCR, atau None."""
    for pat in _SIM_PATTERNS:
        m = pat.search(text or "")
        if m:
            try:
                v = int(m.group(1))
            except ValueError:
                continue
            if 0 <= v <= 100:
                return v
    return None


class SimilarityChecker:
    """
    Validasi persentase hasil uji similaritas.

    Cara pakai:
        result = SimilarityChecker.for_pkm_kc(parser).check()
    """

    def __init__(self, parser: DocxParser, rules: SimilarityRules):
        self.parser = parser
        self.rules = rules

    @classmethod
    def for_pkm_kc(cls, parser: DocxParser) -> "SimilarityChecker":
        return cls(parser, get_pkm_kc_similarity_rules())

    @classmethod
    def for_pkm_vgk(cls, parser: DocxParser) -> "SimilarityChecker":
        return cls(parser, get_pkm_vgk_similarity_rules())

    @classmethod
    def for_pkm_re(cls, parser: DocxParser) -> "SimilarityChecker":
        return cls(parser, get_pkm_re_similarity_rules())

    @classmethod
    def for_pkm_rsh(cls, parser: DocxParser) -> "SimilarityChecker":
        return cls(parser, get_pkm_rsh_similarity_rules())

    @classmethod
    def for_pkm_k(cls, parser: DocxParser) -> "SimilarityChecker":
        return cls(parser, get_pkm_k_similarity_rules())

    @classmethod
    def for_pkm_ki(cls, parser: DocxParser) -> "SimilarityChecker":
        return cls(parser, get_pkm_ki_similarity_rules())

    @classmethod
    def for_pkm_pi(cls, parser: DocxParser) -> "SimilarityChecker":
        return cls(parser, get_pkm_pi_similarity_rules())

    @classmethod
    def for_pkm_pm(cls, parser: DocxParser) -> "SimilarityChecker":
        return cls(parser, get_pkm_pm_similarity_rules())

    @classmethod
    def for_pkm_ai(cls, parser: DocxParser) -> "SimilarityChecker":
        return cls(parser, get_pkm_ai_similarity_rules())

    @classmethod
    def for_pkm_gft(cls, parser: DocxParser) -> "SimilarityChecker":
        return cls(parser, get_pkm_gft_similarity_rules())

    # ------------------------------------------------------------------ public

    def check(self) -> SimilarityCheckResult:
        result = SimilarityCheckResult(status="pass")
        label = self.rules.schema_label
        maxp = self.rules.max_percent

        # Bedakan dua kasus yang sebelumnya digabung:
        #   1. Lampiran similaritas MISSING dari body → fail merah dengan pesan jelas.
        #   2. Lampiran ADA tapi OCR gagal baca % (gambar Turnitin rusak / OCR
        #      credentials hilang) → warning kuning "periksa manual".
        if not self._lampiran_similarity_exists():
            result.status = "fail"
            result.messages.append(CheckMessage(
                level="fail",
                text="Kesalahan tidak terdapat Lampiran hasil uji similaritas",
            ))
            return result

        pct = self._detect_percent()

        if pct is None:
            result.status = "warning"
            result.messages.append(CheckMessage(
                level="warning",
                text=(
                    f"Persentase hasil uji similaritas {label} tidak terdeteksi — "
                    f"periksa manual (maksimal {maxp}%)."
                ),
            ))
        elif pct > maxp:
            result.status = "fail"
            result.messages.append(CheckMessage(
                level="fail",
                text=f"Hasil uji similaritas {pct}% melebihi batas maksimum {maxp}%.",
            ))
        else:
            result.messages.append(CheckMessage(
                level="pass",
                text=f"Hasil uji similaritas {pct}% sesuai (≤{maxp}%).",
            ))
        return result

    # ----------------------------------------------------------------- helpers

    def _lampiran_similarity_exists(self) -> bool:
        """True jika heading 'Lampiran N ... similaritas' ditemukan di body."""
        start, _ = self._find_similarity_range()
        return start is not None

    def _detect_percent(self) -> Optional[int]:
        start, end = self._find_similarity_range()
        if start is None:
            return None
        rids = self._collect_image_rids_in_range(start, end)
        if not rids:
            return None
        return self._ocr_extract(rids)

    def _find_similarity_range(self) -> tuple[Optional[int], Optional[int]]:
        """
        Lokasi heading lampiran similaritas di BODY (kemunculan TERAKHIR, bukan
        entri Daftar Lampiran/TOC di depan). Return (start_idx, end_idx).
        end = heading 'Lampiran N' berikutnya, atau None (sampai akhir dokumen).
        """
        paras = self.parser.paragraphs
        start: Optional[int] = None
        for p in paras:
            t = p.text.strip()
            if not t or len(t) > _MAX_SIM_HEADING_LEN:
                continue
            if _LAMPIRAN_HEAD_RE.match(t) and _SIM_HEADING_RE.search(t):
                start = p.index   # ambil yang TERAKHIR
        if start is None:
            # fallback: paragraf pendek apa pun yang menyebut similaritas/turnitin
            for p in paras:
                t = p.text.strip()
                if t and len(t) <= 90 and _SIM_HEADING_RE.search(t):
                    start = p.index
        if start is None:
            return None, None

        end: Optional[int] = None
        for p in paras:
            t = p.text.strip()
            if p.index > start and len(t) <= _MAX_SIM_HEADING_LEN and _LAMPIRAN_HEAD_RE.match(t):
                end = p.index
                break
        return start, end

    def _collect_image_rids_in_range(self, start: int, end: Optional[int]) -> list[str]:
        try:
            with zipfile.ZipFile(str(self.parser.file_path)) as zf:
                with zf.open("word/document.xml") as fh:
                    body = ET.parse(fh).getroot().find(f"{{{_W_NS}}}body")
        except Exception:
            return []
        if body is None:
            return []

        _V_NS = "urn:schemas-microsoft-com:vml"

        rids: list[str] = []
        pc = 0
        for child in body:
            if child.tag.split("}")[-1] == "p":
                if pc >= start and (end is None or pc < end):
                    for blip in child.iter(f"{{{_A_NS}}}blip"):
                        rid = blip.get(f"{{{_R_NS}}}embed")
                        if rid:
                            rids.append(rid)
                    for imgdata in child.iter(f"{{{_V_NS}}}imagedata"):
                        rid = imgdata.get(f"{{{_R_NS}}}id")
                        if rid:
                            rids.append(rid)
                pc += 1
        return rids

    def _ocr_extract(self, rids: list[str]) -> Optional[int]:
        """
        OCR gambar lampiran similaritas untuk ekstrak persentase Overall.

        Strategi:
        1. Step 1 — crop atas: OCR bagian top crop_top_ratio (mis. 35%) untuk
           semua gambar. Cepat, cocok kalau angka di header overview.
        2. Step 2 — full image fallback: kalau Step 1 tak ketemu, OCR gambar
           PENUH untuk semua. Gambar overview Turnitin tidak selalu di pertama
           (kadang last page), jadi scan banyak gambar.

        OCR jalan paralel via ThreadPoolExecutor di GoogleVisionEngine.
        """
        try:
            from PIL import Image
        except ImportError:
            return None

        try:
            with zipfile.ZipFile(str(self.parser.file_path)) as zf:
                rel_map = _load_image_rels(zf)
                images: list = []
                for rid in rids[: self.rules.max_images_to_scan]:
                    path = rel_map.get(rid)
                    if not path:
                        continue
                    full = path if path.startswith("word/") else f"word/{path}"
                    try:
                        images.append(Image.open(io.BytesIO(zf.read(full))))
                    except Exception:
                        continue

                if not images:
                    return None

                # Step 1: top-crop semua gambar (cepat).
                crops = []
                for img in images:
                    w, h = img.size
                    crops.append(
                        img.crop((0, 0, w, max(1, int(h * self.rules.crop_top_ratio))))
                    )
                for text in _run_ocr(crops):
                    pct = _extract_similarity_percent(text)
                    if pct is not None:
                        return pct

                # Step 2: full image fallback (slower tapi paralel).
                for text in _run_ocr(images):
                    pct = _extract_similarity_percent(text)
                    if pct is not None:
                        return pct
        except Exception:
            return None
        return None
