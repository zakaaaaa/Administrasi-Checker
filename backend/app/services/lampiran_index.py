"""
LampiranOcrIndex — satu sumber kebenaran untuk section Lampiran + cache OCR per-gambar.

Tujuan (Fase 1 optimasi OCR): lampiran_checker, biodata_date_checker, dan
similarity_checker tidak lagi meng-OCR gambar yang sama berkali-kali. Tiap rId
gambar di-OCR **maksimal sekali**, hasilnya disimpan di cache dan dipakai bersama.

Index ini dibuat SEKALI di orchestrator lalu diteruskan ke checker-checker.

Konsep:
    - `para_image_rids`   : dict[para_index -> list rId gambar] (blip + vml).
    - `rids_in_range`     : rId gambar pada rentang paragraf [start, end).
    - `segments`          : potong section Lampiran jadi sub-lampiran per heading
                            "Lampiran N ...".
    - `ocr_text_for_rids` : OCR tiap rId (cache), gabung teks non-kosong urut rId.
                            Ini mekanisme dedup-nya — pemanggilan berikutnya untuk
                            rId yang sama langsung pakai cache.

Konsistensi dengan kode lama dijaga ketat: pengumpulan rId & transform OCR
memakai helper yang sama persis (`_collect_image_rids_after` / `_run_ocr`),
sehingga teks yang dihasilkan identik dengan sebelum optimasi.
"""

from __future__ import annotations

import io
import re
import zipfile
from dataclasses import dataclass, field
from typing import Optional
from xml.etree import ElementTree as ET

from app.services.docx_parser import DocxParser
from app.services.biodata_date_checker import (
    _load_image_rels,
    _run_ocr,
    _W_NS,
    _R_NS,
    _A_NS,
)

_V_NS = "urn:schemas-microsoft-com:vml"

# Heading "LAMPIRAN" (batas awal section) — sama dengan checker.
_LAMPIRAN_SECTION_RE = re.compile(r"^\s*LAMPIRAN\s*$", re.IGNORECASE)
# "Lampiran N" (angka atau romawi) — batas tiap sub-lampiran.
_LAMPIRAN_N_RE = re.compile(r"\blampiran\s+(\d+|[IVXLC]+)\b", re.IGNORECASE)
# Heading lampiran similaritas (untuk berhenti sebelum segment similaritas).
_SIM_HEADING_RE = re.compile(r"(similarit|uji\s+periksa|turnitin|plagiar)", re.IGNORECASE)


@dataclass
class LampiranSegment:
    """Satu sub-lampiran: dari heading 'Lampiran N' sampai sebelum heading berikutnya."""
    heading_text: str
    start_para_idx: int
    end_para_idx: int                 # eksklusif (None-equivalent = sangat besar)
    image_rids: list[str] = field(default_factory=list)
    seg_text: str = ""                # teks gabungan paragraf dalam segment


class LampiranOcrIndex:
    def __init__(self, parser: DocxParser):
        self.parser = parser
        self._para_rids: Optional[dict[int, list[str]]] = None
        self._para_blip_rids: dict[int, list[str]] = {}
        self._rel_map: Optional[dict[str, str]] = None
        self._ocr_cache: dict[str, str] = {}

    # ------------------------------------------------------------------ rId map

    def _ensure_para_rids(self) -> None:
        """Bangun peta para_index -> list rId gambar (blip + vml), urut dokumen."""
        if self._para_rids is not None:
            return
        para_rids: dict[int, list[str]] = {}
        try:
            with zipfile.ZipFile(str(self.parser.file_path), "r") as zf:
                self._rel_map = _load_image_rels(zf)
                with zf.open("word/document.xml") as f:
                    body = ET.parse(f).getroot().find(f"{{{_W_NS}}}body")
        except Exception:
            self._para_rids = {}
            self._rel_map = self._rel_map or {}
            return
        if body is None:
            self._para_rids = {}
            return

        blip_rids: dict[int, list[str]] = {}  # a:blip only (inserted images)
        pc = 0
        for child in body:
            tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
            if tag == "p":
                rids: list[str] = []
                b_rids: list[str] = []
                for blip in child.iter(f"{{{_A_NS}}}blip"):
                    rid = blip.get(f"{{{_R_NS}}}embed")
                    if rid:
                        rids.append(rid)
                        b_rids.append(rid)
                for imgdata in child.iter(f"{{{_V_NS}}}imagedata"):
                    rid = imgdata.get(f"{{{_R_NS}}}id")
                    if rid:
                        rids.append(rid)
                if rids:
                    para_rids[pc] = rids
                if b_rids:
                    blip_rids[pc] = b_rids
                pc += 1
        self._para_rids = para_rids
        self._para_blip_rids = blip_rids

    def rids_in_range(
        self,
        start: Optional[int],
        end: Optional[int] = None,
        blip_only: bool = False,
    ) -> list[str]:
        """rId gambar pada paragraf [start, end). start None = dari awal dokumen.
        blip_only=True hanya kembalikan a:blip (bukan VML) — dipakai untuk
        _keywords_in_text agar OCR corpus tidak tercemar VML page-embed."""
        self._ensure_para_rids()
        assert self._para_rids is not None
        source = self._para_blip_rids if blip_only else self._para_rids
        lo = start if start is not None else -1
        rids: list[str] = []
        for idx in sorted(source):
            if idx < lo:
                continue
            if end is not None and idx >= end:
                break
            rids.extend(source[idx])
        return rids

    # --------------------------------------------------------------- segmentasi

    def find_section_start(self) -> Optional[int]:
        """Heading 'LAMPIRAN' (is_heading) — batas awal section lampiran."""
        for p in self.parser.paragraphs:
            if _LAMPIRAN_SECTION_RE.match(p.text.strip()) and p.is_heading:
                return p.index
        return None

    def segments(self, section_start: Optional[int]) -> list[LampiranSegment]:
        """
        Potong section Lampiran (mulai section_start) jadi sub-lampiran berdasarkan
        heading 'Lampiran N ...'. Paragraf sebelum heading 'Lampiran N' pertama
        (tapi >= section_start) jadi segment pembuka dengan heading_text="".
        """
        self._ensure_para_rids()
        paras = [p for p in self.parser.paragraphs
                 if section_start is None or p.index >= section_start]
        if not paras:
            return []

        # indeks paragraf yang merupakan heading "Lampiran N"
        boundaries = [p.index for p in paras if _LAMPIRAN_N_RE.search(p.text or "")]

        starts: list[int] = []
        if not boundaries or boundaries[0] > paras[0].index:
            starts.append(paras[0].index)   # segment pembuka (orphan)
        starts.extend(boundaries)
        starts = sorted(set(starts))

        last_idx = paras[-1].index
        text_by_idx = {p.index: (p.text or "") for p in paras}
        heading_by_idx = {b: text_by_idx.get(b, "") for b in boundaries}

        segs: list[LampiranSegment] = []
        for i, s in enumerate(starts):
            end = starts[i + 1] if i + 1 < len(starts) else last_idx + 1
            seg_text = " ".join(
                text_by_idx[idx] for idx in range(s, end)
                if text_by_idx.get(idx, "").strip()
            )
            rids: list[str] = []
            assert self._para_rids is not None
            for idx in range(s, end):
                rids.extend(self._para_rids.get(idx, []))
            segs.append(LampiranSegment(
                heading_text=heading_by_idx.get(s, ""),
                start_para_idx=s,
                end_para_idx=end,
                image_rids=rids,
                seg_text=seg_text,
            ))
        return segs

    @staticmethod
    def is_similarity_segment(seg: LampiranSegment) -> bool:
        head = seg.heading_text or seg.seg_text[:120]
        return bool(_SIM_HEADING_RE.search(head))

    # ----------------------------------------------------------------- OCR cache

    def _image_by_rid(self, rid: str):
        try:
            from PIL import Image
        except ImportError:
            return None
        self._ensure_para_rids()
        assert self._rel_map is not None
        path = self._rel_map.get(rid)
        if not path:
            return None
        full = path if path.startswith("word/") else f"word/{path}"
        try:
            with zipfile.ZipFile(str(self.parser.file_path), "r") as zf:
                return Image.open(io.BytesIO(zf.read(full)))
        except Exception:
            return None

    def ocr_text_for_rids(self, rids: list[str]) -> str:
        """
        OCR tiap rId maksimal sekali (cache), gabung teks non-kosong urut rId.

        Replikasi persis perilaku lama: `_run_ocr([img])` per gambar memberi list
        berisi 0/1 teks (sudah lewat _best_rotation_text + _fix_ocr_months,
        hanya disimpan jika non-kosong). Gabung dengan spasi seperti
        `" ".join(_run_ocr(images))` sebelumnya.
        """
        parts: list[str] = []
        for rid in rids:
            if rid not in self._ocr_cache:
                img = self._image_by_rid(rid)
                if img is None:
                    self._ocr_cache[rid] = ""
                else:
                    texts = _run_ocr([img])
                    self._ocr_cache[rid] = texts[0] if texts else ""
            t = self._ocr_cache[rid]
            if t.strip():
                parts.append(t)
        return " ".join(parts)
