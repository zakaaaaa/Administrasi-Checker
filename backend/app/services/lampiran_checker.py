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

# Heading "DAFTAR LAMPIRAN" (daftar di depan dokumen)
_DAFTAR_LAMPIRAN_RE = re.compile(r"^\s*daftar\s+lampiran\s*$", re.IGNORECASE)

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

    def check(self, index=None) -> LampiranCheckResult:
        """
        Deteksi kelengkapan lampiran MURNI dari teks: gabungan **Daftar Lampiran**
        (depan) + heading **bagian Lampiran** (body). TIDAK ada OCR — pada proposal
        rapi heading lampiran selalu diketik, dan Daftar Lampiran adalah deklarasi
        penulis sendiri. Lampiran wajib yang tak tercantum → dilaporkan + diarahkan
        cek manual (tanpa membuang waktu OCR semua gambar).

        `index` diterima demi kompatibilitas pemanggilan orchestrator, tidak dipakai.
        """
        result = LampiranCheckResult(status="pass")

        text_corpus = self._collect_lampiran_text_corpus()

        missing: list[tuple[int, list[str], str]] = []
        for num, keywords, label in self.required:
            if not self._lampiran_found_in_text(num, keywords, text_corpus):
                missing.append((num, keywords, label))

        if missing:
            result.status = "fail"
            labels = [label for _, _, label in missing]
            daftar = "\n".join(f"{i}. {lbl}" for i, lbl in enumerate(labels, 1))
            acuan = "lampiran tersebut" if len(labels) == 1 else "lampiran-lampiran tersebut"
            result.messages.append(CheckMessage(
                level="fail",
                text=(
                    f"{len(labels)} lampiran wajib tidak terdapat di Daftar Lampiran "
                    f"dokumen {self.schema_label}:\n{daftar}\n"
                    f"Cek juga halaman Lampiran secara manual untuk memastikan {acuan} "
                    f"benar-benar ada."
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

    def _collect_lampiran_text_corpus(self) -> str:
        """
        Korpus teks untuk deteksi: blok 'DAFTAR LAMPIRAN' (depan) + bagian Lampiran
        di body. Sengaja TIDAK menyertakan prosa Bab 1–5 supaya 'Lampiran N' yang
        disebut sambil lalu di teks utama tidak memicu false-positive.
        """
        paras = self.parser.paragraphs
        parts: list[str] = []

        # (a) Blok Daftar Lampiran di depan: heading + entri sampai heading section lain.
        daftar_idx = next(
            (p.index for p in paras if _DAFTAR_LAMPIRAN_RE.match(p.text.strip())),
            None,
        )
        if daftar_idx is not None:
            for p in paras:
                if p.index <= daftar_idx:
                    continue
                t = p.text.strip()
                if not t:
                    continue
                if p.is_heading and not _LAMPIRAN_N_RE.search(t):
                    break  # sudah keluar dari blok Daftar Lampiran
                parts.append(p.text)

        # (b) Bagian Lampiran di body (heading 'LAMPIRAN' → akhir dokumen).
        body_start = self._find_lampiran_section_start()
        if body_start is not None:
            for p in paras:
                if p.index >= body_start and p.text.strip():
                    parts.append(p.text)

        return " ".join(parts)

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

# =============================================================================
# Helpers OOXML (tidak lagi dipakai lampiran — disisakan untuk util internal)
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


