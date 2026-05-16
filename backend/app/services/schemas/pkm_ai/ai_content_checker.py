"""
AiContentChecker — validator khas konten Artikel Ilmiah PKM-AI.

Sumber aturan: PKM-AI-2026_fix.pdf hal 5-7 (Sistematika Penulisan Isi Utama
Artikel Ilmiah).

Yang dicek:
1. Judul
   - ≤ 20 kata
   - Semua huruf kapital
   - Hindari singkatan (advisory)
2. Abstrak (Bahasa Indonesia)
   - Ada di dokumen
   - ≤ 250 kata
   - Satu paragraf (saran)
3. Abstract (Bahasa Inggris)
   - Ada di dokumen
   - ≤ 250 kata
   - Italic (cetak miring)
4. Kata-kata kunci (ID) & Keywords (EN)
   - Ada di dokumen
   - 3-5 frasa

Catatan: modul ini hanya dipanggil untuk PKM-AI (registry orchestrator).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

from app.services.core.base_rules import SchemaRules
from app.services.core.docx_parser import DocxParser, ParagraphInfo


# ============================================================================
# Konstanta
# ============================================================================

MAX_TITLE_WORDS = 20
MAX_ABSTRACT_WORDS = 250
MIN_KEYWORDS = 3
MAX_KEYWORDS = 5

# Heading kandidat
_ABSTRAK_PATTERNS = [
    re.compile(r"^\s*ABSTRAK\s*[:.\-]?\s*$", re.IGNORECASE),
]
_ABSTRACT_PATTERNS = [
    re.compile(r"^\s*ABSTRACT\s*[:.\-]?\s*$", re.IGNORECASE),
]
_KATA_KUNCI_PATTERNS = [
    re.compile(r"^\s*kata[-\s]?kata\s+kunci\s*[:\-–—]", re.IGNORECASE),
    re.compile(r"^\s*kata\s+kunci\s*[:\-–—]", re.IGNORECASE),
]
_KEYWORDS_PATTERNS = [
    re.compile(r"^\s*keywords?\s*[:\-–—]", re.IGNORECASE),
]
_PENDAHULUAN_PATTERNS = [
    re.compile(r"^\s*(?:1\s*\.?\s*)?pendahuluan\s*$", re.IGNORECASE),
    re.compile(r"^\s*bab\s+(?:1|i)\.?\s+pendahuluan", re.IGNORECASE),
]

# Singkatan/akronim umum di domain PKM yang BOLEH muncul di judul
# (program name, institusi, satuan ilmiah umum). Tambahkan kalau perlu.
ABBREV_SAFELIST = {
    "PKM", "PKM-AI", "AI", "PT", "RI", "UU", "PP", "NO",
    "BPS", "OKI", "DNA", "RNA", "PCR", "IoT", "GIS",
    "S-1", "S1", "D-3", "D3", "D-4", "D4",
    "KKN", "PPL", "PKL",
    "UMKM", "IKN",
}


def _word_count(text: str) -> int:
    """Hitung kata (token non-empty setelah split whitespace)."""
    return len([w for w in text.strip().split() if w])


def _normalize_para_text(text: str) -> str:
    """Strip whitespace, normalisasi spasi multiple."""
    return re.sub(r"\s+", " ", text).strip()


def _looks_like_blank(text: str) -> bool:
    return not text.strip()


# ============================================================================
# Hasil
# ============================================================================


@dataclass
class CheckMessage:
    level: str   # 'pass' | 'warning' | 'fail'
    text: str


@dataclass
class TitleAnalysis:
    found: bool = False
    text: str = ""
    paragraph_index: Optional[int] = None
    word_count: int = 0
    is_uppercase: bool = False
    suspected_abbreviations: list[str] = field(default_factory=list)


@dataclass
class AbstractAnalysis:
    """Untuk abstrak (ID) maupun abstract (EN)."""
    language: str            # 'id' | 'en'
    found: bool = False
    heading_paragraph_index: Optional[int] = None
    content_paragraph_indices: list[int] = field(default_factory=list)
    word_count: int = 0
    paragraph_count: int = 0
    italic_ratio: float = 0.0    # rasio teks (by chars) yang italic
    is_italic: bool = False      # bermakna untuk EN; cek italic_ratio >= 0.8


@dataclass
class KeywordsAnalysis:
    language: str            # 'id' | 'en'
    found: bool = False
    paragraph_index: Optional[int] = None
    raw_text: str = ""
    items: list[str] = field(default_factory=list)


@dataclass
class AiContentResult:
    status: str = "pass"
    title: TitleAnalysis = field(default_factory=TitleAnalysis)
    abstrak: AbstractAnalysis = field(default_factory=lambda: AbstractAnalysis(language="id"))
    abstract: AbstractAnalysis = field(default_factory=lambda: AbstractAnalysis(language="en"))
    kata_kunci: KeywordsAnalysis = field(default_factory=lambda: KeywordsAnalysis(language="id"))
    keywords: KeywordsAnalysis = field(default_factory=lambda: KeywordsAnalysis(language="en"))
    messages: list[CheckMessage] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "title": {
                "found": self.title.found,
                "text": self.title.text,
                "paragraph_index": self.title.paragraph_index,
                "word_count": self.title.word_count,
                "max_words": MAX_TITLE_WORDS,
                "is_uppercase": self.title.is_uppercase,
                "suspected_abbreviations": self.title.suspected_abbreviations,
            },
            "abstrak": _abstract_to_dict(self.abstrak),
            "abstract": _abstract_to_dict(self.abstract),
            "kata_kunci": _keywords_to_dict(self.kata_kunci),
            "keywords": _keywords_to_dict(self.keywords),
            "messages": [{"level": m.level, "text": m.text} for m in self.messages],
        }


def _abstract_to_dict(a: AbstractAnalysis) -> dict:
    return {
        "language": a.language,
        "found": a.found,
        "heading_paragraph_index": a.heading_paragraph_index,
        "content_paragraph_indices": a.content_paragraph_indices,
        "word_count": a.word_count,
        "max_words": MAX_ABSTRACT_WORDS,
        "paragraph_count": a.paragraph_count,
        "italic_ratio": round(a.italic_ratio, 3),
        "is_italic": a.is_italic,
    }


def _keywords_to_dict(k: KeywordsAnalysis) -> dict:
    return {
        "language": k.language,
        "found": k.found,
        "paragraph_index": k.paragraph_index,
        "raw_text": k.raw_text,
        "items": k.items,
        "count": len(k.items),
        "min": MIN_KEYWORDS,
        "max": MAX_KEYWORDS,
    }


# ============================================================================
# Checker
# ============================================================================


class AiContentChecker:
    """
    Checker konten PKM-AI: judul, abstrak/abstract, kata kunci/keywords.

    Usage:
        parser = DocxParser('artikel.docx')
        rules = get_pkm_ai_article_rules()
        result = AiContentChecker(parser, rules).check()
    """

    def __init__(self, parser: DocxParser, schema: SchemaRules):
        self.parser = parser
        self.schema = schema

    def check(self) -> AiContentResult:
        result = AiContentResult()

        paragraphs = self.parser.paragraphs

        # Step 1: Locate landmark headings
        landmarks = self._locate_landmarks(paragraphs)

        # Step 2: Title (paragraf signifikan pertama sebelum ABSTRAK/penulis area)
        result.title = self._analyze_title(paragraphs, landmarks)

        # Step 3: Abstrak (ID)
        result.abstrak = self._analyze_abstract_block(
            paragraphs,
            heading_idx=landmarks["abstrak"],
            stop_at_indices=[
                landmarks["kata_kunci"],
                landmarks["abstract"],
                landmarks["keywords"],
                landmarks["pendahuluan"],
            ],
            language="id",
        )

        # Step 4: Abstract (EN)
        result.abstract = self._analyze_abstract_block(
            paragraphs,
            heading_idx=landmarks["abstract"],
            stop_at_indices=[
                landmarks["keywords"],
                landmarks["kata_kunci"],
                landmarks["pendahuluan"],
            ],
            language="en",
        )

        # Step 5: Kata kunci & Keywords
        result.kata_kunci = self._analyze_keywords_line(
            paragraphs, landmarks["kata_kunci"], language="id"
        )
        result.keywords = self._analyze_keywords_line(
            paragraphs, landmarks["keywords"], language="en"
        )

        # Step 6: Compose messages + finalize status
        self._finalize(result)

        return result

    # ------------------------------------------------------------------------
    # Landmark detection
    # ------------------------------------------------------------------------

    def _locate_landmarks(self, paragraphs: list[ParagraphInfo]) -> dict[str, Optional[int]]:
        """Cari paragraph_index untuk heading kunci. None kalau tidak ketemu."""
        result: dict[str, Optional[int]] = {
            "abstrak": None,
            "abstract": None,
            "kata_kunci": None,
            "keywords": None,
            "pendahuluan": None,
        }

        def _match_any(text: str, patterns: list[re.Pattern]) -> bool:
            return any(p.search(text) for p in patterns)

        for para in paragraphs:
            text = para.text or ""
            if not text.strip():
                continue
            stripped = _normalize_para_text(text)
            if result["abstrak"] is None and _match_any(stripped, _ABSTRAK_PATTERNS):
                result["abstrak"] = para.index
            if result["abstract"] is None and _match_any(stripped, _ABSTRACT_PATTERNS):
                result["abstract"] = para.index
            if result["kata_kunci"] is None and _match_any(stripped, _KATA_KUNCI_PATTERNS):
                result["kata_kunci"] = para.index
            if result["keywords"] is None and _match_any(stripped, _KEYWORDS_PATTERNS):
                result["keywords"] = para.index
            if result["pendahuluan"] is None and _match_any(stripped, _PENDAHULUAN_PATTERNS):
                result["pendahuluan"] = para.index

        return result

    # ------------------------------------------------------------------------
    # Title
    # ------------------------------------------------------------------------

    def _analyze_title(
        self,
        paragraphs: list[ParagraphInfo],
        landmarks: dict[str, Optional[int]],
    ) -> TitleAnalysis:
        """
        Ambil paragraf signifikan pertama sebagai judul.

        Strategi: paragraf pertama non-empty yang panjang ≥ 5 kata,
        sebelum ABSTRAK/ABSTRACT/PENDAHULUAN. Kalau tidak ada landmark
        sama sekali, ambil paragraf signifikan pertama saja.
        """
        # Batas atas: posisi heading paling awal di antara landmark
        upper_bound = min(
            [v for v in landmarks.values() if v is not None],
            default=len(paragraphs),
        )

        title_para: Optional[ParagraphInfo] = None
        for para in paragraphs:
            if para.index >= upper_bound:
                break
            text = (para.text or "").strip()
            if not text:
                continue
            # Skip paragraf yang jelas bukan judul: penulis ("Penulis Satu...")
            # email, baris institusi pendek. Heuristik kasar: judul biasanya
            # ≥ 4 kata DAN sebagian besar huruf kapital.
            words = _word_count(text)
            if words < 4:
                continue
            title_para = para
            break

        if title_para is None:
            return TitleAnalysis()

        text = _normalize_para_text(title_para.text)
        words = _word_count(text)

        # Uppercase check: rasio huruf kapital ≥ 0.85 dianggap "semua kapital"
        letters = [c for c in text if c.isalpha()]
        upper_ratio = (
            sum(1 for c in letters if c.isupper()) / len(letters) if letters else 0.0
        )
        is_uppercase = upper_ratio >= 0.85

        # Suspected abbreviations: token UPPERCASE 2-5 char yang TIDAK di
        # safelist. Hanya bermakna kalau judul TIDAK seluruhnya kapital
        # (kalau seluruhnya kapital, akronim sulit dideteksi tanpa kamus).
        suspected: list[str] = []
        if not is_uppercase:
            for token in re.findall(r"[A-Z][A-Z0-9\-]{1,4}", text):
                if token in ABBREV_SAFELIST:
                    continue
                if token in suspected:
                    continue
                suspected.append(token)

        return TitleAnalysis(
            found=True,
            text=text,
            paragraph_index=title_para.index,
            word_count=words,
            is_uppercase=is_uppercase,
            suspected_abbreviations=suspected,
        )

    # ------------------------------------------------------------------------
    # Abstract block (ID/EN)
    # ------------------------------------------------------------------------

    def _analyze_abstract_block(
        self,
        paragraphs: list[ParagraphInfo],
        heading_idx: Optional[int],
        stop_at_indices: list[Optional[int]],
        language: str,
    ) -> AbstractAnalysis:
        result = AbstractAnalysis(language=language)
        if heading_idx is None:
            return result

        result.found = True
        result.heading_paragraph_index = heading_idx

        # Batas akhir: indeks landmark terkecil > heading_idx
        candidates = [v for v in stop_at_indices if v is not None and v > heading_idx]
        end_idx = min(candidates) if candidates else len(paragraphs)

        # Ambil paragraf antara (heading_idx, end_idx)
        content_paras: list[ParagraphInfo] = []
        for para in paragraphs:
            if para.index <= heading_idx:
                continue
            if para.index >= end_idx:
                break
            text = (para.text or "").strip()
            if not text:
                continue
            content_paras.append(para)

        result.content_paragraph_indices = [p.index for p in content_paras]
        result.paragraph_count = len(content_paras)

        # Word count gabungan
        joined = " ".join(_normalize_para_text(p.text) for p in content_paras)
        result.word_count = _word_count(joined)

        # Italic ratio (penting untuk Abstract EN)
        total_chars = 0
        italic_chars = 0
        for para in content_paras:
            for run in para.runs:
                run_text = (run.text or "").strip()
                if not run_text:
                    continue
                total_chars += len(run_text)
                if run.italic is True:
                    italic_chars += len(run_text)
        result.italic_ratio = (italic_chars / total_chars) if total_chars else 0.0
        result.is_italic = result.italic_ratio >= 0.8

        return result

    # ------------------------------------------------------------------------
    # Keywords line
    # ------------------------------------------------------------------------

    def _analyze_keywords_line(
        self,
        paragraphs: list[ParagraphInfo],
        para_idx: Optional[int],
        language: str,
    ) -> KeywordsAnalysis:
        result = KeywordsAnalysis(language=language)
        if para_idx is None:
            return result

        para = next((p for p in paragraphs if p.index == para_idx), None)
        if para is None:
            return result

        result.found = True
        result.paragraph_index = para_idx
        text = _normalize_para_text(para.text)
        result.raw_text = text

        # Buang prefix "Kata-kata kunci:" / "Kata kunci:" / "Keywords:"
        cleaned = re.sub(
            r"^\s*(?:kata[-\s]?kata\s+kunci|kata\s+kunci|keywords?)\s*[:\-–—]\s*",
            "",
            text,
            flags=re.IGNORECASE,
        )
        # Buang annotation "(3-5 kata/frasa)" yang ada di template panduan
        cleaned = re.sub(r"\([^)]*\)\s*$", "", cleaned).strip()

        # Split by koma atau titik koma (kata kunci umumnya pisah koma)
        parts = re.split(r"[;,]", cleaned)
        items = [p.strip().rstrip(".") for p in parts if p.strip()]
        result.items = items
        return result

    # ------------------------------------------------------------------------
    # Finalize
    # ------------------------------------------------------------------------

    def _finalize(self, result: AiContentResult) -> None:
        msgs: list[CheckMessage] = []

        # --- TITLE ---
        t = result.title
        if not t.found:
            msgs.append(CheckMessage(
                level="fail",
                text="Judul artikel tidak terdeteksi (tidak ada paragraf signifikan sebelum ABSTRAK).",
            ))
        else:
            if t.word_count > MAX_TITLE_WORDS:
                msgs.append(CheckMessage(
                    level="fail",
                    text=(
                        f"Judul artikel {t.word_count} kata — melebihi batas "
                        f"maksimum {MAX_TITLE_WORDS} kata."
                    ),
                ))
            else:
                msgs.append(CheckMessage(
                    level="pass",
                    text=f"Judul {t.word_count} kata (≤ {MAX_TITLE_WORDS}).",
                ))

            if not t.is_uppercase:
                msgs.append(CheckMessage(
                    level="fail",
                    text="Judul harus ditulis dengan HURUF KAPITAL semua (panduan PKM-AI).",
                ))
            else:
                msgs.append(CheckMessage(level="pass", text="Judul ditulis dalam huruf kapital."))

            if t.suspected_abbreviations:
                msgs.append(CheckMessage(
                    level="warning",
                    text=(
                        f"Judul tampak memuat singkatan: "
                        f"{', '.join(t.suspected_abbreviations)}. Panduan menyarankan "
                        f"hindari singkatan; verifikasi manual."
                    ),
                ))

        # --- ABSTRAK (ID) ---
        a = result.abstrak
        if not a.found:
            msgs.append(CheckMessage(
                level="fail",
                text="Heading 'ABSTRAK' (Bahasa Indonesia) tidak ditemukan.",
            ))
        else:
            if a.word_count == 0:
                msgs.append(CheckMessage(
                    level="fail",
                    text="ABSTRAK ditemukan tapi isinya kosong.",
                ))
            elif a.word_count > MAX_ABSTRACT_WORDS:
                msgs.append(CheckMessage(
                    level="fail",
                    text=(
                        f"Abstrak (ID) {a.word_count} kata — melebihi batas "
                        f"{MAX_ABSTRACT_WORDS} kata."
                    ),
                ))
            else:
                msgs.append(CheckMessage(
                    level="pass",
                    text=f"Abstrak (ID) {a.word_count} kata (≤ {MAX_ABSTRACT_WORDS}).",
                ))
            if a.paragraph_count > 1:
                msgs.append(CheckMessage(
                    level="warning",
                    text=(
                        f"Abstrak (ID) terdiri dari {a.paragraph_count} paragraf. "
                        f"Panduan: satu paragraf."
                    ),
                ))

        # --- ABSTRACT (EN) ---
        b = result.abstract
        if not b.found:
            msgs.append(CheckMessage(
                level="fail",
                text="Heading 'ABSTRACT' (Bahasa Inggris) tidak ditemukan.",
            ))
        else:
            if b.word_count == 0:
                msgs.append(CheckMessage(
                    level="fail",
                    text="ABSTRACT ditemukan tapi isinya kosong.",
                ))
            elif b.word_count > MAX_ABSTRACT_WORDS:
                msgs.append(CheckMessage(
                    level="fail",
                    text=(
                        f"Abstract (EN) {b.word_count} kata — melebihi batas "
                        f"{MAX_ABSTRACT_WORDS} kata."
                    ),
                ))
            else:
                msgs.append(CheckMessage(
                    level="pass",
                    text=f"Abstract (EN) {b.word_count} kata (≤ {MAX_ABSTRACT_WORDS}).",
                ))
            if not b.is_italic:
                msgs.append(CheckMessage(
                    level="fail",
                    text=(
                        f"Abstract (EN) harus dicetak miring (italic). "
                        f"Terdeteksi {int(b.italic_ratio * 100)}% teks italic "
                        f"(threshold ≥ 80%)."
                    ),
                ))
            else:
                msgs.append(CheckMessage(level="pass", text="Abstract (EN) dicetak italic."))
            if b.paragraph_count > 1:
                msgs.append(CheckMessage(
                    level="warning",
                    text=(
                        f"Abstract (EN) terdiri dari {b.paragraph_count} paragraf. "
                        f"Panduan: satu paragraf."
                    ),
                ))

        # --- KATA KUNCI (ID) ---
        k = result.kata_kunci
        if not k.found:
            msgs.append(CheckMessage(
                level="fail",
                text="Baris 'Kata-kata kunci:' (Bahasa Indonesia) tidak ditemukan.",
            ))
        else:
            n = len(k.items)
            if n < MIN_KEYWORDS:
                msgs.append(CheckMessage(
                    level="fail",
                    text=(
                        f"Kata kunci (ID) hanya {n} frasa. Panduan: "
                        f"{MIN_KEYWORDS}-{MAX_KEYWORDS} kata/frasa."
                    ),
                ))
            elif n > MAX_KEYWORDS:
                msgs.append(CheckMessage(
                    level="fail",
                    text=(
                        f"Kata kunci (ID) {n} frasa — melebihi batas {MAX_KEYWORDS}."
                    ),
                ))
            else:
                msgs.append(CheckMessage(
                    level="pass",
                    text=f"Kata kunci (ID) {n} frasa (rentang {MIN_KEYWORDS}-{MAX_KEYWORDS}).",
                ))

        # --- KEYWORDS (EN) ---
        kw = result.keywords
        if not kw.found:
            msgs.append(CheckMessage(
                level="fail",
                text="Baris 'Keywords:' (Bahasa Inggris) tidak ditemukan.",
            ))
        else:
            n = len(kw.items)
            if n < MIN_KEYWORDS:
                msgs.append(CheckMessage(
                    level="fail",
                    text=(
                        f"Keywords (EN) hanya {n} frasa. Panduan: "
                        f"{MIN_KEYWORDS}-{MAX_KEYWORDS} kata/frasa."
                    ),
                ))
            elif n > MAX_KEYWORDS:
                msgs.append(CheckMessage(
                    level="fail",
                    text=f"Keywords (EN) {n} frasa — melebihi batas {MAX_KEYWORDS}.",
                ))
            else:
                msgs.append(CheckMessage(
                    level="pass",
                    text=f"Keywords (EN) {n} frasa (rentang {MIN_KEYWORDS}-{MAX_KEYWORDS}).",
                ))

        result.messages = msgs

        # Status overall
        has_fail = any(m.level == "fail" for m in msgs)
        has_warn = any(m.level == "warning" for m in msgs)
        if has_fail:
            result.status = "fail"
        elif has_warn:
            result.status = "warning"
        else:
            result.status = "pass"
