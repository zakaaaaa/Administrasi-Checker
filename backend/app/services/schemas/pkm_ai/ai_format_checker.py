"""
AiFormatChecker — validasi format per-zona khas PKM-AI.

Sumber aturan: PKM-AI-2026_fix.pdf hal 6-7 (poin 1-4 di "Sistematika penulisan
Judul, Nama Penulis, Alamat Institusi, Abstrak dan Abstract").

Zona yang divalidasi:
1. Halaman judul (paragraf sebelum heading ABSTRAK): jarak baris 1.0 spasi
2. Judul artikel itu sendiri: TNR 12 bold
3. Nama penulis + alamat institusi (antara judul & ABSTRAK): TNR 10
4. Abstrak & Abstract (paragraf isi): TNR 11
5. Caption Gambar/Tabel ("Gambar 1.", "Tabel 1."): TNR 11, 1 spasi

Modul ini melengkapi FormatChecker generik (yang validasi body TNR 12).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

from app.services.checkers.format_checker import FOREIGN_WORDS
from app.services.core.base_rules import SchemaRules
from app.services.core.docx_parser import DocxParser, ParagraphInfo, RunInfo
from app.services.core.message_format import format_finding
from app.services.core.style_resolver import StyleResolver


# ============================================================================
# Konstanta
# ============================================================================

FONT_NAME = "Times New Roman"
TITLE_PAGE_LINE_SPACING = 1.0
ABSTRACT_FONT_SIZE = 11.0
AUTHOR_FONT_SIZE = 10.0
CAPTION_FONT_SIZE = 11.0
TITLE_FONT_SIZE = 12.0

# Body PKM-AI (mulai dari setelah blok abstract EN selesai)
BODY_FONT_SIZE = 12.0
BODY_ALIGN = "justify"
BODY_LINE_SPACING = 1.15
BODY_LINE_SPACING_TOL = 0.05  # selaras FormatRules.line_spacing_tolerance

# Alignment wajib per-zona (PKM-AI)
TITLE_ALIGN = "center"
AUTHOR_ALIGN = "center"
ABSTRACT_ALIGN = "justify"
CAPTION_ALIGN = "center"
ABSTRACT_LINE_SPACING = 1.0

# Toleransi numerik (font size & line spacing)
SIZE_TOL = 0.5
SPACING_TOL = 0.1

# Pattern landmark
_ABSTRAK_RE = re.compile(r"^\s*ABSTRAK\s*[:.\-]?\s*$", re.IGNORECASE)
_ABSTRACT_RE = re.compile(r"^\s*ABSTRACT\s*[:.\-]?\s*$", re.IGNORECASE)
_KATA_KUNCI_RE = re.compile(r"^\s*kata[-\s]?kata\s+kunci\s*[:\-–—]", re.IGNORECASE)
_KEYWORDS_RE = re.compile(r"^\s*keywords?\s*[:\-–—]", re.IGNORECASE)
_PENDAHULUAN_RE = re.compile(
    r"^\s*(?:1\s*\.?\s*)?pendahuluan\s*$|^\s*bab\s+(?:1|i)\.?\s+pendahuluan",
    re.IGNORECASE,
)
_CAPTION_RE = re.compile(r"^\s*(Gambar|Tabel)\s+(\d+)\s*[.:]", re.IGNORECASE)


def _parse_caption_label(text: str) -> Optional[str]:
    """Ambil label rapi dari caption: 'Gambar 3' / 'Tabel 1'. None kalau bukan caption."""
    m = _CAPTION_RE.match((text or "").strip())
    if not m:
        return None
    kind = m.group(1).capitalize()  # 'Gambar' / 'Tabel'
    num = m.group(2)
    return f"{kind} {num}"


def _page_of(parser: DocxParser, paragraph_index: Optional[int]) -> Optional[int]:
    """Estimasi halaman fisik (1-based) dari paragraph index. None kalau tak bisa."""
    if paragraph_index is None:
        return None
    estimator = getattr(parser, "estimate_physical_page", None)
    if not callable(estimator):
        return None
    try:
        raw = estimator(paragraph_index)
    except Exception:
        return None
    return raw if isinstance(raw, int) else None


# ============================================================================
# Hasil
# ============================================================================


@dataclass
class CheckMessage:
    level: str   # 'pass' | 'warning' | 'fail'
    text: str


@dataclass
class ZoneFinding:
    zone: str                    # 'title_page' | 'title' | 'author' | 'abstract_id' | 'abstract_en' | 'caption'
    aspect: str                  # 'font_name' | 'font_size' | 'line_spacing' | 'italic' | 'bold'
    severity: str                # 'fail' | 'warning' | 'pass'
    expected: Optional[str]
    found: Optional[str]
    paragraph_index: Optional[int]
    message: str


@dataclass
class AiFormatResult:
    status: str = "pass"
    findings: list[ZoneFinding] = field(default_factory=list)
    messages: list[CheckMessage] = field(default_factory=list)
    # Diagnostic info per zona
    zones_detected: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "zones_detected": self.zones_detected,
            "findings": [
                {
                    "zone": f.zone,
                    "aspect": f.aspect,
                    "severity": f.severity,
                    "expected": f.expected,
                    "found": f.found,
                    "paragraph_index": f.paragraph_index,
                    "message": f.message,
                }
                for f in self.findings
            ],
            "messages": [{"level": m.level, "text": m.text} for m in self.messages],
        }


# ============================================================================
# Helper analisis paragraf
# ============================================================================


def _aggregate_font(paragraph: ParagraphInfo) -> tuple[Optional[str], Optional[float], float]:
    """
    Agregasi font name dominan + font size dominan dari semua run di paragraf.
    Return (font_name, font_size_pt, italic_ratio_by_chars).
    """
    name_chars: dict[str, int] = {}
    size_chars: dict[float, int] = {}
    italic_chars = 0
    total_chars = 0
    for run in paragraph.runs:
        text = (run.text or "")
        n = len(text)
        if n == 0:
            continue
        total_chars += n
        if run.font_name:
            name_chars[run.font_name] = name_chars.get(run.font_name, 0) + n
        if run.font_size_pt is not None:
            size_chars[run.font_size_pt] = size_chars.get(run.font_size_pt, 0) + n
        if run.italic is True:
            italic_chars += n

    dom_name = max(name_chars.items(), key=lambda kv: kv[1])[0] if name_chars else None
    dom_size = max(size_chars.items(), key=lambda kv: kv[1])[0] if size_chars else None
    italic_ratio = (italic_chars / total_chars) if total_chars else 0.0
    return dom_name, dom_size, italic_ratio


def _size_matches(actual: Optional[float], expected: float) -> bool:
    if actual is None:
        return False
    return abs(actual - expected) <= SIZE_TOL


def _spacing_matches(actual: Optional[float], expected: float) -> bool:
    if actual is None:
        return False
    return abs(actual - expected) <= SPACING_TOL


def _is_blank(para: ParagraphInfo) -> bool:
    return not (para.text or "").strip()


# ============================================================================
# Checker
# ============================================================================


class AiFormatChecker:
    """
    Validasi format per-zona PKM-AI.

    Usage:
        parser = DocxParser('artikel.docx')
        rules = get_pkm_ai_article_rules()
        result = AiFormatChecker(parser, rules).check()
    """

    def __init__(self, parser: DocxParser, schema: SchemaRules):
        self.parser = parser
        self.schema = schema
        self.resolver = StyleResolver(parser)

    def check(self) -> AiFormatResult:
        result = AiFormatResult()
        paragraphs = self.parser.paragraphs

        # Step 1: landmark indices
        landmarks = self._locate_landmarks(paragraphs)
        result.zones_detected = {k: v for k, v in landmarks.items()}

        # Step 2: title (paragraf signifikan pertama)
        title_para = self._find_title_paragraph(paragraphs, landmarks)
        if title_para is not None:
            result.zones_detected["title_paragraph_index"] = title_para.index
            self._validate_title(title_para, result)
            self._validate_title_page_spacing(paragraphs, title_para, landmarks, result)
            self._validate_author_block(paragraphs, title_para, landmarks, result)

        # Step 3: abstrak (ID) & abstract (EN)
        if landmarks["abstrak"] is not None:
            self._validate_abstract_block(
                paragraphs,
                heading_idx=landmarks["abstrak"],
                stop_idxs=[
                    landmarks["kata_kunci"],
                    landmarks["abstract"],
                    landmarks["keywords"],
                    landmarks["pendahuluan"],
                ],
                zone="abstract_id",
                result=result,
            )
        if landmarks["abstract"] is not None:
            self._validate_abstract_block(
                paragraphs,
                heading_idx=landmarks["abstract"],
                stop_idxs=[
                    landmarks["keywords"],
                    landmarks["kata_kunci"],
                    landmarks["pendahuluan"],
                ],
                zone="abstract_en",
                result=result,
            )

        # Step 4: captions (Gambar N./Tabel N.) — di seluruh dokumen
        self._validate_captions(paragraphs, result)

        # Step 5: body (Pendahuluan → akhir) TNR 12 justify 1,15
        # + kata asing wajib italic (warning)
        self._validate_body_block(paragraphs, landmarks, result)
        self._validate_foreign_italic_body(paragraphs, landmarks, result)

        # Step 6: messages + status
        self._finalize(result)
        return result

    # ------------------------------------------------------------------------
    # Landmarks
    # ------------------------------------------------------------------------

    def _locate_landmarks(self, paragraphs: list[ParagraphInfo]) -> dict[str, Optional[int]]:
        out: dict[str, Optional[int]] = {
            "abstrak": None,
            "abstract": None,
            "kata_kunci": None,
            "keywords": None,
            "pendahuluan": None,
        }
        for para in paragraphs:
            text = (para.text or "").strip()
            if not text:
                continue
            if out["abstrak"] is None and _ABSTRAK_RE.search(text):
                out["abstrak"] = para.index
            if out["abstract"] is None and _ABSTRACT_RE.search(text):
                out["abstract"] = para.index
            if out["kata_kunci"] is None and _KATA_KUNCI_RE.search(text):
                out["kata_kunci"] = para.index
            if out["keywords"] is None and _KEYWORDS_RE.search(text):
                out["keywords"] = para.index
            if out["pendahuluan"] is None and _PENDAHULUAN_RE.search(text):
                out["pendahuluan"] = para.index
        return out

    def _find_title_paragraph(
        self,
        paragraphs: list[ParagraphInfo],
        landmarks: dict[str, Optional[int]],
    ) -> Optional[ParagraphInfo]:
        """Paragraf signifikan pertama sebelum landmark paling awal."""
        upper = min(
            [v for v in landmarks.values() if v is not None],
            default=len(paragraphs),
        )
        for para in paragraphs:
            if para.index >= upper:
                break
            text = (para.text or "").strip()
            if not text:
                continue
            # min 4 kata, sama heuristik dengan AiContentChecker
            if len(text.split()) < 4:
                continue
            return para
        return None

    # ------------------------------------------------------------------------
    # Validators per-zona
    # ------------------------------------------------------------------------

    def _validate_title(self, para: ParagraphInfo, result: AiFormatResult) -> None:
        name, size, _ = _aggregate_font(para)
        if name and name != FONT_NAME:
            result.findings.append(ZoneFinding(
                zone="title", aspect="font_name", severity="fail",
                expected=FONT_NAME, found=name,
                paragraph_index=para.index,
                message=f"Judul pakai font '{name}'",
            ))
        if size is not None and not _size_matches(size, TITLE_FONT_SIZE):
            result.findings.append(ZoneFinding(
                zone="title", aspect="font_size", severity="fail",
                expected=f"{TITLE_FONT_SIZE}pt", found=f"{size}pt",
                paragraph_index=para.index,
                message=f"Judul pakai ukuran {size}pt",
            ))
        # Bold: minimal sebagian besar run bold
        total_chars = sum(len((r.text or "")) for r in para.runs)
        bold_chars = sum(
            len((r.text or "")) for r in para.runs if r.bold is True
        )
        bold_ratio = (bold_chars / total_chars) if total_chars else 0.0
        if bold_ratio < 0.8:
            result.findings.append(ZoneFinding(
                zone="title", aspect="bold", severity="fail",
                expected="cetak tebal (bold)",
                found=f"{int(bold_ratio * 100)}% bold",
                paragraph_index=para.index,
                message=(
                    f"Judul artikel hanya {int(bold_ratio * 100)}% dicetak tebal"
                ),
            ))
        # Alignment: judul harus rata tengah
        align = self.resolver.resolve_paragraph_alignment(para.index)
        if align is not None and align != TITLE_ALIGN:
            result.findings.append(ZoneFinding(
                zone="title", aspect="alignment", severity="fail",
                expected="rata tengah (center)", found=align,
                paragraph_index=para.index,
                message=f"Judul ditulis rata '{align}', bukan rata tengah",
            ))

    def _validate_title_page_spacing(
        self,
        paragraphs: list[ParagraphInfo],
        title_para: ParagraphInfo,
        landmarks: dict[str, Optional[int]],
        result: AiFormatResult,
    ) -> None:
        """
        Halaman judul = paragraf dari judul s/d sebelum ABSTRAK harus 1.0 spasi.
        Kita cek mayoritas paragraf non-blank di zona ini.
        """
        end = landmarks["abstrak"] or landmarks["pendahuluan"] or len(paragraphs)
        zone_paras = [
            p for p in paragraphs
            if title_para.index <= p.index < end and not _is_blank(p)
        ]
        if not zone_paras:
            return

        non_spec_paras = [p for p in zone_paras if p.line_spacing is not None]
        if not non_spec_paras:
            return  # Tidak bisa di-cek; bukan fail
        mismatches = [
            p for p in non_spec_paras
            if not _spacing_matches(p.line_spacing, TITLE_PAGE_LINE_SPACING)
        ]
        if len(mismatches) >= max(1, len(non_spec_paras) // 2):
            sample = mismatches[0]
            result.findings.append(ZoneFinding(
                zone="title_page", aspect="line_spacing", severity="fail",
                expected=f"{TITLE_PAGE_LINE_SPACING} (1,0 spasi)",
                found=f"{sample.line_spacing}",
                paragraph_index=sample.index,
                message=(
                    f"Halaman judul ({len(mismatches)}/{len(non_spec_paras)} "
                    f"paragraf) pakai jarak baris {sample.line_spacing}"
                ),
            ))

    def _validate_author_block(
        self,
        paragraphs: list[ParagraphInfo],
        title_para: ParagraphInfo,
        landmarks: dict[str, Optional[int]],
        result: AiFormatResult,
    ) -> None:
        """
        Block penulis = paragraf antara judul (exclusive) dan ABSTRAK
        (exclusive). Harus TNR 10pt.
        """
        abstrak_idx = landmarks["abstrak"]
        if abstrak_idx is None:
            return
        block = [
            p for p in paragraphs
            if title_para.index < p.index < abstrak_idx and not _is_blank(p)
        ]
        if not block:
            return

        # Cari paragraf yang punya size terdeteksi & flag yang ukurannya ≠ 10pt
        sized_paras = []
        for p in block:
            _, size, _ = _aggregate_font(p)
            if size is not None:
                sized_paras.append((p, size))
        if not sized_paras:
            return
        mismatches = [
            (p, s) for (p, s) in sized_paras if not _size_matches(s, AUTHOR_FONT_SIZE)
        ]
        if len(mismatches) >= max(1, len(sized_paras) // 2):
            p, s = mismatches[0]
            result.findings.append(ZoneFinding(
                zone="author", aspect="font_size", severity="fail",
                expected=f"{AUTHOR_FONT_SIZE}pt",
                found=f"{s}pt",
                paragraph_index=p.index,
                message=(
                    f"Block nama penulis & institusi ({len(mismatches)}/"
                    f"{len(sized_paras)} paragraf) pakai ukuran {s}pt"
                ),
            ))

        # Alignment: block penulis harus rata tengah
        align_mismatch = [
            (p, a) for p in block
            for a in [self.resolver.resolve_paragraph_alignment(p.index)]
            if a is not None and a != AUTHOR_ALIGN
        ]
        if len(align_mismatch) >= max(1, len(block) // 2):
            p, a = align_mismatch[0]
            result.findings.append(ZoneFinding(
                zone="author", aspect="alignment", severity="fail",
                expected="rata tengah (center)", found=a,
                paragraph_index=p.index,
                message=(
                    f"Block nama penulis & institusi ({len(align_mismatch)}/"
                    f"{len(block)} paragraf) ditulis rata '{a}', bukan rata tengah"
                ),
            ))

    def _validate_abstract_block(
        self,
        paragraphs: list[ParagraphInfo],
        heading_idx: int,
        stop_idxs: list[Optional[int]],
        zone: str,
        result: AiFormatResult,
    ) -> None:
        """Validasi font abstrak/abstract: TNR 11pt."""
        candidates = [v for v in stop_idxs if v is not None and v > heading_idx]
        end_idx = min(candidates) if candidates else len(paragraphs)
        block = [
            p for p in paragraphs
            if heading_idx < p.index < end_idx and not _is_blank(p)
        ]
        if not block:
            return

        sized_paras = []
        for p in block:
            _, size, _ = _aggregate_font(p)
            if size is not None:
                sized_paras.append((p, size))
        if not sized_paras:
            return
        mismatches = [
            (p, s) for (p, s) in sized_paras if not _size_matches(s, ABSTRACT_FONT_SIZE)
        ]
        if len(mismatches) >= max(1, len(sized_paras) // 2):
            p, s = mismatches[0]
            result.findings.append(ZoneFinding(
                zone=zone, aspect="font_size", severity="fail",
                expected=f"{ABSTRACT_FONT_SIZE}pt",
                found=f"{s}pt",
                paragraph_index=p.index,
                message=(
                    f"Isi {zone} ({len(mismatches)}/{len(sized_paras)} paragraf) "
                    f"pakai ukuran {s}pt"
                ),
            ))

        # Alignment: isi abstrak harus justify
        align_mismatch = [
            (p, a) for p in block
            for a in [self.resolver.resolve_paragraph_alignment(p.index)]
            if a is not None and a != ABSTRACT_ALIGN
        ]
        if len(align_mismatch) >= max(1, len(block) // 2):
            p, a = align_mismatch[0]
            result.findings.append(ZoneFinding(
                zone=zone, aspect="alignment", severity="fail",
                expected="rata kiri-kanan (justify)", found=a,
                paragraph_index=p.index,
                message=(
                    f"Isi {zone} ({len(align_mismatch)}/{len(block)} paragraf) "
                    f"ditulis rata '{a}', bukan justify"
                ),
            ))

        # Line spacing: isi abstrak harus 1.0
        spaced = [p for p in block if p.line_spacing is not None]
        spacing_mismatch = [
            p for p in spaced
            if not _spacing_matches(p.line_spacing, ABSTRACT_LINE_SPACING)
        ]
        if spaced and len(spacing_mismatch) >= max(1, len(spaced) // 2):
            p = spacing_mismatch[0]
            result.findings.append(ZoneFinding(
                zone=zone, aspect="line_spacing", severity="fail",
                expected=f"{ABSTRACT_LINE_SPACING} (1,0 spasi)",
                found=f"{p.line_spacing}",
                paragraph_index=p.index,
                message=(
                    f"Isi {zone} ({len(spacing_mismatch)}/{len(spaced)} paragraf) "
                    f"pakai jarak baris {p.line_spacing}"
                ),
            ))

    def _validate_captions(
        self, paragraphs: list[ParagraphInfo], result: AiFormatResult
    ) -> None:
        """
        Caption 'Gambar N.' atau 'Tabel N.' → TNR 11, 1 spasi, rata tengah.

        Emit 1 finding per caption bermasalah dengan label spesifik
        (mis. "Gambar 3", "Tabel 1") + estimasi halaman fisik, supaya
        user bisa langsung temukan di Word.
        """
        captions: list[tuple[ParagraphInfo, str]] = []
        for p in paragraphs:
            if _is_blank(p):
                continue
            label = _parse_caption_label(p.text)
            if label:
                captions.append((p, label))
        if not captions:
            return

        result.zones_detected["captions_count"] = len(captions)
        result.zones_detected["captions"] = [
            {"label": label, "paragraph_index": p.index}
            for (p, label) in captions
        ]

        for p, label in captions:
            _, size, _ = _aggregate_font(p)
            if size is not None and not _size_matches(size, CAPTION_FONT_SIZE):
                result.findings.append(ZoneFinding(
                    zone="caption", aspect="font_size", severity="warning",
                    expected=f"{CAPTION_FONT_SIZE}pt",
                    found=f"{size}pt",
                    paragraph_index=p.index,
                    message=f"Caption {label} pakai ukuran {size}pt",
                ))
            if p.line_spacing is not None and not _spacing_matches(p.line_spacing, 1.0):
                result.findings.append(ZoneFinding(
                    zone="caption", aspect="line_spacing", severity="warning",
                    expected="1.0 (1 spasi)",
                    found=f"{p.line_spacing}",
                    paragraph_index=p.index,
                    message=f"Caption {label} pakai jarak baris {p.line_spacing}",
                ))
            align = self.resolver.resolve_paragraph_alignment(p.index)
            if align is not None and align != CAPTION_ALIGN:
                result.findings.append(ZoneFinding(
                    zone="caption", aspect="alignment", severity="warning",
                    expected="rata tengah (center)",
                    found=align,
                    paragraph_index=p.index,
                    message=f"Caption {label} ditulis rata '{align}', bukan rata tengah",
                ))

    # ------------------------------------------------------------------------
    # Body block (mulai setelah blok abstract EN selesai → akhir dokumen)
    # ------------------------------------------------------------------------

    def _body_start_idx(self, landmarks: dict[str, Optional[int]]) -> Optional[int]:
        """
        Indeks paragraf awal body. Spec §2: "Body (Pendahuluan → akhir)".
        Prioritas: heading PENDAHULUAN (inklusif — heading sendiri di-skip via
        guard `is_heading`). Kalau tidak ada PENDAHULUAN, fallback ke paragraf
        SETELAH keywords/kata_kunci (akhir blok abstrak). Fallback terakhir:
        paragraf setelah heading ABSTRACT / ABSTRAK.
        """
        pendahuluan = landmarks.get("pendahuluan")
        if pendahuluan is not None:
            return pendahuluan
        kw_refs = [landmarks.get(k) for k in ("keywords", "kata_kunci")]
        kw_refs = [r for r in kw_refs if r is not None]
        if kw_refs:
            return max(kw_refs) + 1
        for key in ("abstract", "abstrak"):
            idx = landmarks.get(key)
            if idx is not None:
                return idx + 1
        return None

    def _iter_body_paragraphs(
        self,
        paragraphs: list[ParagraphInfo],
        landmarks: dict[str, Optional[int]],
    ) -> list[ParagraphInfo]:
        """Paragraf body: non-blank, bukan heading, bukan caption."""
        body_start = self._body_start_idx(landmarks)
        if body_start is None:
            return []
        out = []
        for p in paragraphs:
            if p.index < body_start:
                continue
            if _is_blank(p):
                continue
            if p.is_heading:
                continue
            if _parse_caption_label(p.text) is not None:
                continue
            out.append(p)
        return out

    def _validate_body_block(
        self,
        paragraphs: list[ParagraphInfo],
        landmarks: dict[str, Optional[int]],
        result: AiFormatResult,
    ) -> None:
        """
        Body PKM-AI: TNR 12pt, justify, line spacing 1.15.
        Pakai pola "mayoritas" (selaras `_validate_abstract_block`): emit 1
        finding per aspek bila ≥ 50% paragraf di body mismatch.
        """
        body_paras = self._iter_body_paragraphs(paragraphs, landmarks)
        if not body_paras:
            return
        result.zones_detected["body_paragraph_count"] = len(body_paras)
        result.zones_detected["body_start_paragraph_index"] = body_paras[0].index

        # Font size
        sized = []
        for p in body_paras:
            _, size, _ = _aggregate_font(p)
            if size is not None:
                sized.append((p, size))
        size_mismatches = [
            (p, s) for (p, s) in sized if not _size_matches(s, BODY_FONT_SIZE)
        ]
        if sized and len(size_mismatches) >= max(1, len(sized) // 2):
            p, s = size_mismatches[0]
            result.findings.append(ZoneFinding(
                zone="body", aspect="font_size", severity="fail",
                expected=f"{BODY_FONT_SIZE}pt", found=f"{s}pt",
                paragraph_index=p.index,
                message=(
                    f"Body ({len(size_mismatches)}/{len(sized)} paragraf) "
                    f"pakai ukuran {s}pt"
                ),
            ))

        # Alignment
        align_mismatches = [
            (p, a) for p in body_paras
            for a in [self.resolver.resolve_paragraph_alignment(p.index)]
            if a is not None and a != BODY_ALIGN
        ]
        if body_paras and len(align_mismatches) >= max(1, len(body_paras) // 2):
            p, a = align_mismatches[0]
            result.findings.append(ZoneFinding(
                zone="body", aspect="alignment", severity="fail",
                expected="rata kiri-kanan (justify)", found=a,
                paragraph_index=p.index,
                message=(
                    f"Body ({len(align_mismatches)}/{len(body_paras)} paragraf) "
                    f"ditulis rata '{a}', bukan justify"
                ),
            ))

        # Line spacing
        spaced = [p for p in body_paras if p.line_spacing is not None]
        spacing_mismatches = [
            p for p in spaced
            if abs(p.line_spacing - BODY_LINE_SPACING) > BODY_LINE_SPACING_TOL
        ]
        if spaced and len(spacing_mismatches) >= max(1, len(spaced) // 2):
            p = spacing_mismatches[0]
            result.findings.append(ZoneFinding(
                zone="body", aspect="line_spacing", severity="fail",
                expected=f"{BODY_LINE_SPACING} (1,15 spasi)",
                found=f"{p.line_spacing}",
                paragraph_index=p.index,
                message=(
                    f"Body ({len(spacing_mismatches)}/{len(spaced)} paragraf) "
                    f"pakai jarak baris {p.line_spacing}"
                ),
            ))

    # ------------------------------------------------------------------------
    # Foreign words wajib italic di body (warning)
    # ------------------------------------------------------------------------

    # Max issue per kategori agar tidak spam (selaras FormatChecker)
    _MAX_FOREIGN_ISSUES = 10

    def _validate_foreign_italic_body(
        self,
        paragraphs: list[ParagraphInfo],
        landmarks: dict[str, Optional[int]],
        result: AiFormatResult,
    ) -> None:
        body_paras = self._iter_body_paragraphs(paragraphs, landmarks)
        if not body_paras:
            return
        patterns = [
            (w, re.compile(r"\b" + re.escape(w) + r"\b", re.IGNORECASE))
            for w in FOREIGN_WORDS
        ]
        emitted = 0
        for p in body_paras:
            if emitted >= self._MAX_FOREIGN_ISSUES:
                break
            matched = [w for (w, pat) in patterns if pat.search(p.text)]
            if not matched:
                continue
            has_italic = any(r.italic for r in p.runs)
            if has_italic:
                continue
            result.findings.append(ZoneFinding(
                zone="body", aspect="foreign_italic", severity="warning",
                expected="italic", found="tidak italic",
                paragraph_index=p.index,
                message=(
                    f"Body memuat kata/frasa asing ({', '.join(matched[:3])}) "
                    f"tapi tidak ada run italic"
                ),
            ))
            emitted += 1

    # ------------------------------------------------------------------------
    # Finalize
    # ------------------------------------------------------------------------

    def _finalize(self, result: AiFormatResult) -> None:
        if not result.findings:
            result.messages.append(CheckMessage(
                level="pass",
                text=(
                    "Format khusus PKM-AI sesuai panduan: judul TNR 12 bold "
                    "rata tengah, penulis TNR 10 rata tengah, "
                    "abstrak/abstract TNR 11 justify (semua 1,0 spasi), "
                    "body TNR 12 justify 1,15 spasi, caption TNR 11 rata tengah."
                ),
            ))
            result.status = "pass"
            return

        for f in result.findings:
            perbaikan = f.expected or "perbaiki sesuai aturan"
            result.messages.append(
                CheckMessage(
                    level=f.severity,
                    text=format_finding(
                        _page_of(self.parser, f.paragraph_index),
                        f.message,
                        perbaikan,
                    ),
                )
            )

        has_fail = any(f.severity == "fail" for f in result.findings)
        has_warn = any(f.severity == "warning" for f in result.findings)
        if has_fail:
            result.status = "fail"
        elif has_warn:
            result.status = "warning"
        else:
            result.status = "pass"
