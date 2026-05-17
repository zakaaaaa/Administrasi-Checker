"""
LuaranChecker — validasi luaran PKM-KC dan PKM-VGK.

PKM-KC wajib tepat 4 luaran:
    1. Laporan kemajuan
    2. Laporan akhir
    3. Prototipe
    4. Akun media sosial

PKM-VGK wajib tepat 4 luaran:
    1. Laporan kemajuan
    2. Laporan akhir
    3. Video YouTube
    4. Akun media sosial
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

from app.services.docx_parser import DocxParser, ParagraphInfo


# =============================================================================
# Required luaran per skema
# =============================================================================

_PKM_KC_REQUIRED: list[tuple[str, re.Pattern]] = [
    ("laporan kemajuan",  re.compile(r"laporan\s+kemajuan",    re.IGNORECASE)),
    ("laporan akhir",     re.compile(r"laporan\s+akhir",       re.IGNORECASE)),
    ("prototipe",         re.compile(r"prototip[e]?",          re.IGNORECASE)),
    ("akun media sosial", re.compile(r"akun\s+media\s+sosial", re.IGNORECASE)),
]

_PKM_VGK_REQUIRED: list[tuple[str, re.Pattern]] = [
    ("laporan kemajuan",  re.compile(r"laporan\s+kemajuan",        re.IGNORECASE)),
    ("laporan akhir",     re.compile(r"laporan\s+akhir",           re.IGNORECASE)),
    ("video youtube",     re.compile(r"video\s+you\s*tube",        re.IGNORECASE)),
    ("akun media sosial", re.compile(r"akun\s+media\s+sosial",     re.IGNORECASE)),
]

_LUARAN_LABEL_RE = re.compile(r"\bluaran\b", re.IGNORECASE)
_TOC_LINE_RE = re.compile(r"\.{3,}|\t\s*\d+\s*$")
_NUMBERED_ITEM_RE = re.compile(r"\(\s*(\d+)\s*\)")
_NEXT_HEADING_RE = re.compile(
    r"^(?:BAB\s+[IVXLCM0-9]+|\d+\.\d+\s|\d+\s+[A-Z]|[A-Z][A-Z\s]{2,}$)",
)


# =============================================================================
# Data classes
# =============================================================================


@dataclass
class CheckMessage:
    level: str
    text: str


@dataclass
class LuaranCheckResult:
    status: str
    messages: list[CheckMessage] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "messages": [{"level": m.level, "text": m.text} for m in self.messages],
        }


# =============================================================================
# LuaranChecker (generik)
# =============================================================================


class LuaranChecker:
    """
    Validasi section Luaran — mendukung PKM-KC dan PKM-VGK.

    Cara pakai:
        checker = LuaranChecker.for_pkm_kc(parser)
        checker = LuaranChecker.for_pkm_vgk(parser)
        result  = checker.check()
    """

    def __init__(
        self,
        parser: DocxParser,
        required: list[tuple[str, re.Pattern]],
        schema_label: str,
    ):
        self.parser = parser
        self.required = required
        self.schema_label = schema_label   # "PKM-KC" / "PKM-VGK"

    # --- factory ---

    @classmethod
    def for_pkm_kc(cls, parser: DocxParser) -> "LuaranChecker":
        return cls(parser, _PKM_KC_REQUIRED, "PKM-KC")

    @classmethod
    def for_pkm_vgk(cls, parser: DocxParser) -> "LuaranChecker":
        return cls(parser, _PKM_VGK_REQUIRED, "PKM-VGK")

    # --- public ---

    def check(self) -> LuaranCheckResult:
        result = LuaranCheckResult(status="pass")

        label_para = self._find_luaran_label()
        if label_para is None:
            result.status = "fail"
            result.messages.append(CheckMessage(
                level="fail",
                text=(
                    f"Section 'Luaran' tidak ditemukan di dokumen {self.schema_label}. "
                    f"Wajib mencantumkan luaran: "
                    f"{', '.join(l for l, _ in self.required)}."
                ),
            ))
            return result

        full_text = self._collect_luaran_text(label_para)

        missing: list[str] = [
            label for label, pat in self.required if not pat.search(full_text)
        ]
        item_count = self._count_items(full_text)

        if missing:
            result.status = "fail"
            missing_str = ", ".join(f"'{m}'" for m in missing)
            result.messages.append(CheckMessage(
                level="fail",
                text=(
                    f"Luaran {self.schema_label} tidak lengkap. "
                    f"Yang tidak ditemukan: {missing_str}. "
                    f"Wajib mencantumkan tepat 4 luaran: "
                    f"{', '.join(l for l, _ in self.required)}."
                ),
            ))

        if item_count is not None and item_count != 4:
            result.status = "fail"
            if item_count > 4:
                result.messages.append(CheckMessage(
                    level="fail",
                    text=(
                        f"Section Luaran {self.schema_label} memuat {item_count} luaran "
                        f"— melebihi batas. Harus tepat 4: "
                        f"{', '.join(l for l, _ in self.required)}."
                    ),
                ))
            else:
                result.messages.append(CheckMessage(
                    level="fail",
                    text=(
                        f"Section Luaran {self.schema_label} hanya memuat {item_count} luaran. "
                        f"Harus tepat 4: "
                        f"{', '.join(l for l, _ in self.required)}."
                    ),
                ))

        if not result.messages:
            result.messages.append(CheckMessage(
                level="pass",
                text=(
                    f"Luaran {self.schema_label} sesuai: tepat 4 jenis luaran "
                    f"({', '.join(l for l, _ in self.required)})."
                ),
            ))

        return result

    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------

    def _find_luaran_label(self) -> Optional[ParagraphInfo]:
        """
        Cari paragraf heading/label yang mengandung 'Luaran'.
        Prioritas: is_heading=True (panjang bebas), lalu non-heading ≤80 char.
        """
        fallback: Optional[ParagraphInfo] = None
        for para in self.parser.paragraphs:
            text = para.text.strip()
            if not text:
                continue
            if _TOC_LINE_RE.search(text):
                continue
            if not _LUARAN_LABEL_RE.search(text):
                continue
            if para.is_heading:
                return para
            if len(text) <= 80 and fallback is None:
                fallback = para
        return fallback

    def _collect_luaran_text(self, label_para: ParagraphInfo) -> str:
        """Kumpulkan teks label + paragraf sesudahnya + tabel relevan."""
        parts: list[str] = [label_para.text]
        for para in self.parser.paragraphs:
            if para.index <= label_para.index:
                continue
            if _is_next_section(para):
                break
            if para.text.strip():
                parts.append(para.text)

        for tbl in self.parser.tables:
            tbl_text = " ".join(c.text for c in tbl.cells if c.text.strip())
            if _LUARAN_LABEL_RE.search(tbl_text):
                parts.append(tbl_text)

        return " ".join(parts)

    def _count_items(self, full_text: str) -> Optional[int]:
        """Hitung jumlah item dari inline numbered format (1)...(2)..."""
        nums = _NUMBERED_ITEM_RE.findall(full_text)
        if len(nums) >= 2:
            try:
                return max(int(n) for n in nums)
            except ValueError:
                pass
        return None


def _is_next_section(para: ParagraphInfo) -> bool:
    if para.is_heading:
        return True
    text = para.text.strip()
    if not text or len(text) > 80:
        return False
    if _NEXT_HEADING_RE.match(text):
        return True
    if len(text) <= 60 and para.runs:
        if all(r.bold is True for r in para.runs if r.text.strip()):
            return True
    return False
