"""
SignatureCropChecker — deteksi tanda tangan hasil crop/paste pada lampiran.

Tanda tangan yang di-crop dari dokumen lain dan di-paste memiliki ciri khas:
background di sekitar tanda tangan berwarna abu-abu / off-white monokrom,
berbeda dari putih kertas asli.

Dua kasus yang ditangani:
  A. Tanda tangan di-crop lalu di-paste ke DALAM scan halaman penuh:
     → Background kertas di sudut putih (~255), area tanda tangan punya
       blok off-white MONOKROM yang konsisten (rectangle berbeda warna).
  B. Tanda tangan disisipkan sebagai gambar kecil terpisah ke dokumen:
     → Gambar itu sendiri punya background off-white monokrom.

False positive yang dihindari secara desain:
  - Materai tempel: punya warna-warni (saturasi tinggi) → tidak dihitung suspicious
  - Logo CamScanner / watermark: berwarna → saturasi tinggi → tidak dihitung
  - JPEG compression artifacts: terlalu kecil dan tersebar → di bawah threshold

Section yang diperiksa: Biodata, Surat Pernyataan Ketua, Surat Kerjasama Mitra.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.services.docx_parser import DocxParser
    from app.services.lampiran_index import LampiranOcrIndex, LampiranSegment

# ── keyword identifikasi segment ──────────────────────────────────────────────
_BIODATA_RE  = re.compile(r"biodata", re.IGNORECASE)
_SP_KETUA_RE = re.compile(r"pernyataan.{0,10}ketua", re.IGNORECASE)
_SP_MITRA_RE = re.compile(r"(kesediaan|kerjasama).{0,20}mitra", re.IGNORECASE)

# Case B: gambar < threshold = "gambar kecil standalone"
_SMALL_IMG_WIDTH  = 500
_SMALL_IMG_HEIGHT = 400

# Proporsi bawah halaman yang dianggap area tanda tangan
_SIG_AREA_RATIO = 0.25

# Block analysis parameters
_BLOCK_SIZE          = 20    # px
_DIFF_THRESHOLD      = 10   # selisih brightness dari paper_white → blok suspicious
_MAX_SATURATION      = 18   # blok warna-warni (materai/logo) → skip

_INK_DARK_PIXEL      = 150  # pixel < ini = tinta
_INK_FRAC_MAX        = 0.15 # blok >15% tinta = area teks → skip

# Consecutive-row detection: background crop muncul sebagai BANYAK baris berturut-turut
# (beda dari border tabel yang hanya 1-2 baris tipis).
_ROW_SUSPICIOUS_MIN  = 0.25  # baris dianggap "suspicious" jika >25% blok di baris itu suspicious
_MIN_CONSECUTIVE     = 3     # perlu ≥3 baris berturut-turut → cropped background rectangle

# Case B: paper corners < ini → off-white background → standalone crop
_SMALL_BG_THRESHOLD  = 240


@dataclass
class CheckMessage:
    level: str
    text: str


@dataclass
class SignatureCropResult:
    status: str
    messages: list[CheckMessage] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "messages": [{"level": m.level, "text": m.text} for m in self.messages],
        }


# ── helper analisis gambar ───────────────────────────────────────────────────

def _corner_brightness(img) -> float:
    """Mean brightness sudut kiri-atas dan kanan-atas (estimasi warna kertas)."""
    w, h = img.size
    sz = max(10, min(30, w // 12, h // 12))
    gray = img.convert("L")

    def mean_region(x0, y0, x1, y1) -> float:
        pixels = list(gray.crop((x0, y0, x1, y1)).getdata())
        return sum(pixels) / len(pixels) if pixels else 255.0

    return (mean_region(0, 0, sz, sz) + mean_region(w - sz, 0, w, sz)) / 2


def _block_saturation(rgb_img, x, y, bs) -> float:
    """Mean saturasi warna blok (max_channel - min_channel). Tinggi = berwarna."""
    block = rgb_img.crop((x, y, x + bs, y + bs)).convert("RGB")
    total = 0
    pixels = list(block.getdata())
    for r, g, b in pixels:
        total += max(r, g, b) - min(r, g, b)
    return total / len(pixels) if pixels else 0.0


def _row_suspicious_ratio(gray, rgb, y: int, w: int, paper_white: float) -> float:
    """Rasio blok suspicious dalam satu baris y."""
    bs = _BLOCK_SIZE
    total = suspicious = 0
    for x in range(0, w - bs, bs):
        block = gray.crop((x, y, x + bs, y + bs))
        pixels = list(block.getdata())
        mean_b = sum(pixels) / len(pixels)
        ink_frac = sum(1 for p in pixels if p < _INK_DARK_PIXEL) / len(pixels)
        if ink_frac > _INK_FRAC_MAX:
            continue
        total += 1
        diff = paper_white - mean_b
        if diff <= _DIFF_THRESHOLD:
            continue
        sat = _block_saturation(rgb, x, y, bs)
        if sat > _MAX_SATURATION:
            continue
        suspicious += 1
    return suspicious / total if total else 0.0


def _max_consecutive_suspicious_rows(img, y_start: int) -> int:
    """
    Hitung maksimum baris berturut-turut yang 'suspicious' di area [y_start, bottom].

    Cropped signature background → banyak baris berturut-turut suspicious
    (background rectangle yang solid).
    Border tabel tipis → hanya 1-2 baris suspicious lalu nol kembali.
    """
    paper_white = _corner_brightness(img)
    w, h = img.size
    gray = img.convert("L")
    rgb  = img.convert("RGB")
    bs   = _BLOCK_SIZE

    max_consec = cur_consec = 0
    for y in range(y_start, h - bs, bs):
        ratio = _row_suspicious_ratio(gray, rgb, y, w, paper_white)
        if ratio >= _ROW_SUSPICIOUS_MIN:
            cur_consec += 1
            max_consec = max(max_consec, cur_consec)
        else:
            cur_consec = 0
    return max_consec


_SIGNATURE_ONLY_WHITE_MIN = 0.70  # gambar signature-only: >70% pixel putih (>230)
_SIGNATURE_ONLY_INK_MIN   = 0.02  # gambar signature-only: >2% pixel tinta (<80)
_SIGNATURE_ONLY_INK_MAX   = 0.35  # gambar signature-only: <35% pixel tinta (bukan foto gelap)


def _looks_like_signature_only(img) -> bool:
    """
    True jika gambar berisi hanya tanda tangan (bukan halaman penuh / foto).

    Tanda tangan standalone: dominan putih (background), sedikit piksel tinta
    gelap (coretan TTD), tanpa struktur kompleks (form, foto, tabel).
    """
    gray = img.convert("L")
    pixels = list(gray.getdata())
    total = len(pixels)
    if total == 0:
        return False
    white_frac = sum(1 for p in pixels if p > 230) / total
    ink_frac   = sum(1 for p in pixels if p < 80)  / total
    return (
        white_frac >= _SIGNATURE_ONLY_WHITE_MIN
        and _SIGNATURE_ONLY_INK_MIN <= ink_frac <= _SIGNATURE_ONLY_INK_MAX
    )


def _is_cropped_signature(img) -> bool:
    """
    True jika gambar menunjukkan tanda tangan hasil crop/paste.

    Case A — gambar besar (full-page scan):
        Deteksi ≥ MIN_CONSECUTIVE baris berturut-turut yang punya background
        off-white monokrom di bottom SIG_AREA_RATIO halaman.
    Case B — gambar kecil (standalone insert):
        Gambar kecil di lampiran biodata/surat hanya valid jika berisi konten
        kompleks (foto, cap). Jika isinya hanya tanda tangan (dominan putih
        + sedikit tinta) → dipastikan TTD yang di-crop dan di-paste.
        Juga deteksi background off-white (crop dengan background abu-abu).
    """
    try:
        from PIL import Image  # noqa: F401
    except ImportError:
        return False

    w, h = img.size

    # Case B: gambar kecil
    if w < _SMALL_IMG_WIDTH and h < _SMALL_IMG_HEIGHT:
        # B1: background off-white (abu-abu) → jelas crop
        bg = _corner_brightness(img)
        if bg < _SMALL_BG_THRESHOLD:
            rgb = img.convert("RGB")
            sz = max(10, min(20, w // 12, h // 12))
            sat_tl = _block_saturation(rgb, 0, 0, sz)
            sat_tr = _block_saturation(rgb, max(0, w - sz), 0, sz)
            if (sat_tl + sat_tr) / 2 <= _MAX_SATURATION:
                return True  # background abu-abu monokrom = crop
        # B2: background putih tapi isi hanya tanda tangan (dominan putih + sedikit tinta)
        return _looks_like_signature_only(img)

    # Case A: gambar besar → cari ≥ MIN_CONSECUTIVE baris background suspicious
    sig_y_start = int(h * (1 - _SIG_AREA_RATIO))
    return _max_consecutive_suspicious_rows(img, sig_y_start) >= _MIN_CONSECUTIVE


# ── checker utama ─────────────────────────────────────────────────────────────

class SignatureCropChecker:
    """
    Periksa tanda tangan di lampiran Biodata, Surat Pernyataan Ketua,
    dan Surat Kerjasama Mitra untuk mendeteksi hasil crop/paste.
    """

    def __init__(self, parser: "DocxParser"):
        self.parser = parser

    def check(self, index: "LampiranOcrIndex") -> SignatureCropResult:
        result = SignatureCropResult(status="pass")

        try:
            from PIL import Image  # noqa: F401
        except ImportError:
            return result

        section_start = index.find_section_start()
        segments = index.segments(section_start)

        targets: list[tuple[str, "LampiranSegment"]] = []
        for seg in segments:
            head = (seg.heading_text or seg.seg_text[:100]).strip()
            if _BIODATA_RE.search(head):
                targets.append(("Biodata", seg))
            elif _SP_KETUA_RE.search(head):
                targets.append(("Surat Pernyataan Ketua", seg))
            elif _SP_MITRA_RE.search(head):
                targets.append(("Surat Pernyataan Kesediaan Mitra", seg))

        import io, zipfile
        try:
            zf_ctx = zipfile.ZipFile(str(self.parser.file_path), "r")
        except Exception:
            return result

        with zf_ctx as zf:
            index._ensure_para_rids()
            assert index._rel_map is not None
            rel_map = index._rel_map

            for label, seg in targets:
                flagged = False
                for rid in seg.image_rids:
                    path = rel_map.get(rid)
                    if not path:
                        continue
                    full = path if path.startswith("word/") else f"word/{path}"
                    try:
                        from PIL import Image
                        img = Image.open(io.BytesIO(zf.read(full)))
                    except Exception:
                        continue

                    if _is_cropped_signature(img):
                        flagged = True
                        break

                if flagged:
                    result.status = "fail"
                    result.messages.append(CheckMessage(
                        level="fail",
                        text=(
                            f"Terdeteksi tanda tangan hasil crop/paste pada {label} — "
                            f"tanda tangan harus ditulis langsung di dokumen atau "
                            f"di-scan bersama halaman, bukan di-paste dari dokumen lain."
                        ),
                    ))

        if result.status == "pass":
            result.messages.append(CheckMessage(
                level="pass",
                text="Tanda tangan pada lampiran tidak terdeteksi sebagai hasil crop.",
            ))
        return result
