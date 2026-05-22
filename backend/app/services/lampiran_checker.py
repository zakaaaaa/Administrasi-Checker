"""
LampiranChecker — validasi kelengkapan lampiran wajib PKM-KC.

Lampiran wajib PKM-KC:
    1. Format Jadwal Kegiatan
    2. Biodata Ketua dan Anggota
    3. Biodata Dosen Pendamping
    4. Format Justifikasi Anggaran Kegiatan
    5. Susunan Tim Pengusul dan Pembagian Tugas
    6. Surat Pernyataan Ketua Tim Pengusul

Strategi deteksi:
    1. Cari teks heading "Lampiran N" di paragraf dokumen (cepat)
    2. Untuk lampiran yang tidak terdeteksi via teks → OCR gambar embedded
       yang muncul setelah heading LAMPIRAN di dokumen
    3. Cocokkan kata kunci judul lampiran dari teks + hasil OCR
"""

from __future__ import annotations

import io
import re
import zipfile
from dataclasses import dataclass, field
from typing import Optional
from xml.etree import ElementTree as ET

from app.services.docx_parser import DocxParser, ParagraphInfo


# =============================================================================
# Konfigurasi lampiran wajib PKM-KC
# =============================================================================

# (nomor, kata_kunci_judul, label_tampil)
_REQUIRED_LAMPIRAN: list[tuple[int, list[str], str]] = [
    (1, ["jadwal", "kegiatan"],                          "Format Jadwal Kegiatan"),
    (2, ["biodata", "ketua", "anggota"],                 "Biodata Ketua dan Anggota"),
    (3, ["biodata", "dosen", "pendamping"],              "Biodata Dosen Pendamping"),
    (4, ["justifikasi", "anggaran"],                     "Format Justifikasi Anggaran Kegiatan"),
    (5, ["susunan", "tim", "pengusul", "pembagian"],     "Susunan Tim Pengusul dan Pembagian Tugas"),
    (6, ["pernyataan", "ketua"],                         "Surat Pernyataan Ketua Tim Pengusul"),
]

# Heading LAMPIRAN (batas awal section lampiran di dokumen)
_LAMPIRAN_SECTION_RE = re.compile(r"^\s*LAMPIRAN\s*$", re.IGNORECASE)

# Pattern "Lampiran N" — N bisa angka atau romawi
_LAMPIRAN_N_RE = re.compile(r"\blampiran\s+(\d+|[IVXLC]+)\b", re.IGNORECASE)

# OOXML namespaces
_W_NS  = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
_R_NS  = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
_A_NS  = "http://schemas.openxmlformats.org/drawingml/2006/main"
_REL_TYPE_IMAGE = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/image"

_NSMAP = {
    "w": _W_NS,
    "r": _R_NS,
    "a": _A_NS,
    "wp": "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing",
}


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
    """
    Validasi kelengkapan lampiran wajib PKM-KC.

    Cara pakai:
        result = LampiranChecker.for_pkm_kc(parser).check()
    """

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
        return cls(parser, _REQUIRED_LAMPIRAN, "PKM-KC")

    # -------------------------------------------------------------------------
    # Public
    # -------------------------------------------------------------------------

    def check(self) -> LampiranCheckResult:
        result = LampiranCheckResult(status="pass")

        # 1. Kumpulkan teks dari section Lampiran
        lampiran_section_idx = self._find_lampiran_section_start()
        text_corpus = self._collect_text_from_lampiran(lampiran_section_idx)

        # 2. Cek tiap lampiran wajib via teks
        missing_via_text: list[tuple[int, list[str], str]] = []
        for num, keywords, label in self.required:
            if not self._lampiran_found_in_text(num, keywords, text_corpus):
                missing_via_text.append((num, keywords, label))

        # 3. Jika ada yang tidak ketemu via teks → coba OCR gambar di section Lampiran
        if missing_via_text:
            ocr_text = self._ocr_lampiran_images(lampiran_section_idx)
            still_missing: list[tuple[int, list[str], str]] = []
            for num, keywords, label in missing_via_text:
                if not self._lampiran_found_in_text(num, keywords, ocr_text):
                    still_missing.append((num, keywords, label))
        else:
            still_missing = []

        # 4. Bangun messages
        if still_missing:
            result.status = "fail"
            for num, keywords, label in still_missing:
                result.messages.append(CheckMessage(
                    level="fail",
                    text=(
                        f"Lampiran {num} ({label}) tidak ditemukan di dokumen {self.schema_label}. "
                        f"Pastikan heading 'Lampiran {num}. {label}' ada di bagian Lampiran."
                    ),
                ))
        else:
            result.messages.append(CheckMessage(
                level="pass",
                text=(
                    f"Kelengkapan lampiran {self.schema_label} sesuai: "
                    f"semua {len(self.required)} lampiran wajib ditemukan."
                ),
            ))

        return result

    # -------------------------------------------------------------------------
    # Step 1 & 2: Deteksi teks
    # -------------------------------------------------------------------------

    def _find_lampiran_section_start(self) -> Optional[int]:
        """Return paragraph index heading 'LAMPIRAN' (batas awal section lampiran)."""
        for para in self.parser.paragraphs:
            t = para.text.strip()
            if _LAMPIRAN_SECTION_RE.match(t) and para.is_heading:
                return para.index
        return None

    def _collect_text_from_lampiran(self, start_idx: Optional[int]) -> str:
        """Kumpulkan semua teks paragraf mulai dari section Lampiran."""
        parts: list[str] = []
        for para in self.parser.paragraphs:
            if start_idx is not None and para.index < start_idx:
                continue
            if para.text.strip():
                parts.append(para.text)
        return " ".join(parts)

    def _lampiran_found_in_text(
        self, num: int, keywords: list[str], corpus: str
    ) -> bool:
        """
        Cek apakah ada heading "Lampiran X" (nomor berapapun) yang diikuti
        oleh semua kata kunci dalam 200 karakter berikutnya.
        Tidak mengecek nomor karena dokumen lapangan sering memakai
        penomoran berbeda dari standar.
        """
        corpus_lower = corpus.lower()
        for m in _LAMPIRAN_N_RE.finditer(corpus_lower):
            window = corpus_lower[m.start(): m.start() + 200]
            if all(kw in window for kw in keywords):
                return True
        return False

    # -------------------------------------------------------------------------
    # Step 3: OCR gambar di section Lampiran
    # -------------------------------------------------------------------------

    def _ocr_lampiran_images(self, lampiran_section_idx: Optional[int]) -> str:
        """
        Ekstrak gambar embedded dari section Lampiran di docx, lalu OCR.
        Return teks gabungan hasil OCR.
        """
        import logging
        log = logging.getLogger(__name__)

        try:
            from PIL import Image
        except ImportError as e:
            log.warning(f"[lampiran] PIL not available: {e}")
            return ""

        docx_path = str(self.parser.file_path)
        ocr_parts: list[str] = []

        try:
            with zipfile.ZipFile(docx_path, "r") as zf:
                # Muat relationship map: rId → image path
                rel_map = _load_image_rels(zf)
                if not rel_map:
                    return ""

                # Muat XML dokumen
                with zf.open("word/document.xml") as f:
                    doc_xml = ET.parse(f).getroot()

                # Cari paragraph elemen di section Lampiran
                body = doc_xml.find(f"{{{_W_NS}}}body")
                if body is None:
                    return ""

                # Kumpulkan rId gambar dari paragraf setelah section Lampiran
                image_rids = _collect_image_rids_after(
                    body, lampiran_section_idx, self.parser.paragraphs
                )
                log.info(f"[lampiran] Found {len(image_rids)} images in lampiran section")
                print(f"[lampiran] Found {len(image_rids)} images in lampiran section", flush=True)
                if not image_rids:
                    return ""

                images: list = []
                for rid in image_rids:
                    img_path = rel_map.get(rid)
                    if not img_path:
                        continue
                    full_img_path = f"word/{img_path}" if not img_path.startswith("word/") else img_path
                    try:
                        img_bytes = zf.read(full_img_path)
                        images.append(Image.open(io.BytesIO(img_bytes)))
                    except Exception as e:
                        log.warning(f"[lampiran] Failed to open image {full_img_path}: {e}")
                        continue

                if not images:
                    return ""

                # Pakai EasyOCR yang sama dengan BiodataDateChecker, sehingga
                # model yang sudah di-preload saat startup benar-benar terpakai.
                from app.services.biodata_date_checker import _run_ocr
                log.info(f"[lampiran] Loaded {len(images)} images, running OCR...")
                print(f"[lampiran] Loaded {len(images)} images, running OCR...", flush=True)
                ocr_parts = _run_ocr(images)
                log.info(f"[lampiran] OCR done, total chars: {sum(len(t) for t in ocr_parts)}")
                print(f"[lampiran] OCR done, total chars: {sum(len(t) for t in ocr_parts)}", flush=True)

        except Exception as e:
            log.error(f"[lampiran] OCR failed: {e}", exc_info=True)
            return ""

        return " ".join(ocr_parts)


# =============================================================================
# Helpers OOXML
# =============================================================================


def _load_image_rels(zf: zipfile.ZipFile) -> dict[str, str]:
    """Load rId → target path dari word/_rels/document.xml.rels."""
    rel_map: dict[str, str] = {}
    try:
        with zf.open("word/_rels/document.xml.rels") as f:
            root = ET.parse(f).getroot()
        ns = "http://schemas.openxmlformats.org/package/2006/relationships"
        for rel in root.findall(f"{{{ns}}}Relationship"):
            if rel.get("Type") == _REL_TYPE_IMAGE:
                rid = rel.get("Id", "")
                target = rel.get("Target", "")
                # Target bisa "media/image1.png" atau "../media/image1.png"
                target = target.lstrip("./").lstrip("/")
                if target.startswith("media/"):
                    rel_map[rid] = target
    except Exception:
        pass
    return rel_map


def _collect_image_rids_after(
    body: ET.Element,
    lampiran_section_idx: Optional[int],
    paragraphs: list[ParagraphInfo],
) -> list[str]:
    """
    Kumpulkan relationship ID gambar dari paragraf-paragraf setelah
    section Lampiran di XML body.
    """
    rids: list[str] = []

    # Bangun set paragraph index yang ada di section Lampiran
    if lampiran_section_idx is not None:
        valid_para_indices = {p.index for p in paragraphs if p.index >= lampiran_section_idx}
    else:
        valid_para_indices = {p.index for p in paragraphs}

    # Iterate XML body — para counter untuk track index
    para_counter = 0
    for child in body:
        tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
        if tag == "p":
            if para_counter in valid_para_indices:
                # Cari semua blip (gambar) di dalam paragraf ini
                for blip in child.iter(f"{{{_A_NS}}}blip"):
                    rid = blip.get(f"{{{_R_NS}}}embed")
                    if rid:
                        rids.append(rid)
                # Juga cari di <v:imagedata> (format lama)
                _V_NS = "urn:schemas-microsoft-com:vml"
                for imgdata in child.iter(f"{{{_V_NS}}}imagedata"):
                    rid = imgdata.get(f"{{{_R_NS}}}id")
                    if rid:
                        rids.append(rid)
            para_counter += 1

    return rids


