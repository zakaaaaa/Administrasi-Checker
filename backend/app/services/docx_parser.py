"""
DocxParser — Foundation layer untuk semua checker module.

Tugas utama:
1. Parse file .docx satu kali, expose data ke checker via interface bersih
2. Berikan akses tingkat tinggi (via python-docx) DAN tingkat rendah (raw OOXML via lxml)
3. Lazy-load XML hanya saat dibutuhkan, cache hasil parse
4. Read-only: parser TIDAK memodifikasi file (hanya normalisasi in-memory —
   lihat _hoist_sections_out_of_sdt)
5. Toleran terhadap dokumen "weird" — simpan warning di self.warnings, return data partial

Dipakai oleh:
- StructureChecker         (paragraphs, headings, tables)
- PhysicalSheetCounter     (perlu PDF konversi terpisah, tapi parser ini extract teks rujukan section)
- FormatChecker            (sections, runs, font properties)
- PageNumberingChecker     (header_xmls, footer_xmls, sections)
- BudgetAuditor            (tables — extract RAB Bab 4 dan Lampiran 2)
- ReferenceValidator       (paragraphs body teks + section "DAFTAR PUSTAKA")
- BiodataOCRVerifier       (paragraphs section biodata + images)
"""

from __future__ import annotations

import zipfile
from dataclasses import dataclass, field
import re
from pathlib import Path
from typing import Iterator, Optional, Union

from docx import Document
from docx.document import Document as DocxDocument
from docx.oxml.ns import qn
from docx.shared import Length
from docx.table import Table
from docx.text.paragraph import Paragraph
from lxml import etree


# ============================================================================
# Konstanta OOXML namespaces
# ============================================================================

# Namespace paling sering dipakai di OOXML
W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PKG_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"

NSMAP = {"w": W_NS, "r": R_NS}


# ============================================================================
# Data classes — output struktur untuk konsumsi checker
# ============================================================================


@dataclass
class RunInfo:
    """Informasi satu run (potongan teks dengan formatting seragam)."""
    text: str
    font_name: Optional[str] = None
    font_size_pt: Optional[float] = None  # point (bukan half-point)
    bold: Optional[bool] = None
    italic: Optional[bool] = None
    underline: Optional[bool] = None


@dataclass
class ParagraphInfo:
    """Informasi satu paragraf di body dokumen."""
    index: int                                # urutan paragraf di body (0-based)
    text: str                                 # teks lengkap paragraf
    style_name: Optional[str] = None          # nama style (mis. "Heading 1", "Normal")
    alignment: Optional[str] = None           # 'left', 'center', 'right', 'justify', None
    line_spacing: Optional[float] = None      # spasi baris (1.0, 1.15, 1.5, 2.0, dst.)
    runs: list[RunInfo] = field(default_factory=list)
    is_heading: bool = False                  # True jika style 'Heading N'/outlineLvl, atau pola UPPERCASE
    heading_level: Optional[int] = None       # 1, 2, 3, ... jika is_heading
    ind_left_dxa: Optional[int] = None        # indentasi kiri paragraf dalam DXA (0 = normal)
    # Entri Daftar Isi / Daftar Gambar / Daftar Tabel. Word menandai paragraf ini
    # dengan style bawaan 'toc 1'..'toc 9' / 'table of figures' — deklarasi
    # eksplisit di dalam file, bukan tebakan dari titik-titik & tab.
    is_toc_entry: bool = False
    # Dari mana is_toc_entry disimpulkan: 'style' (otoritatif) | 'leader' (heuristik
    # per baris) | 'manual-block' (baris tanpa leader di dalam blok Daftar Isi
    # manual yang sudah terkonfirmasi) | None.
    toc_evidence: Optional[str] = None
    # Label penomoran otomatis yang Word cetak di depan teks, mis. "BAB 1." dari
    # <w:lvlText w:val="BAB %1."/>. Sengaja TIDAK digabung ke `text`: label ini
    # bukan ketikan, dan modul format/kemiripan membaca `text` apa adanya.
    list_label: Optional[str] = None

    @property
    def heading_text(self) -> str:
        """Teks judul seperti tercetak: label nomor otomatis + teks paragraf.

        Dipakai pencari judul section. Tanpa label, judul yang diketik
        "PENDAHULUAN" dengan "BAB 1." dari penomoran style Heading 1 terbaca
        sebagai "PENDAHULUAN" saja — BAB 1 divonis tidak ada.
        """
        if self.list_label:
            return f"{self.list_label} {self.text.lstrip()}"
        return self.text

    @property
    def heading_texts(self) -> tuple[str, ...]:
        """Bentuk teks yang dicoba pencari judul: seperti tercetak, lalu teks
        ketikan saja. Label hanya MENAMBAH kecocokan — judul yang cocok lewat
        teks ketikan tetap cocok, mis. "DAFTAR PUSTAKA" yang lupa dimatikan
        penomorannya sehingga tercetak "BAB 7. DAFTAR PUSTAKA"."""
        if self.list_label:
            return (self.heading_text, self.text)
        return (self.text,)


@dataclass
class TableCellInfo:
    """Informasi satu cell tabel."""
    row: int
    col: int
    text: str
    paragraphs: list[str] = field(default_factory=list)


@dataclass
class TableInfo:
    """Informasi satu tabel."""
    index: int                                # urutan tabel di body (0-based)
    rows: int
    cols: int
    cells: list[TableCellInfo] = field(default_factory=list)
    # Heuristik kasar: tabel ini "kira-kira" tabel apa (RAB? jadwal? biodata?)
    # Diisi nanti oleh checker, parser hanya menyediakan strukturnya
    header_texts: list[str] = field(default_factory=list)  # teks baris pertama


@dataclass
class SectionInfo:
    """
    Informasi satu section dokumen.
    Section di Word = blok dokumen dengan setting halaman/header/footer sendiri.
    """
    index: int
    page_width_dxa: Optional[int] = None      # DXA (1/20 point); A4 = 11906
    page_height_dxa: Optional[int] = None     # A4 = 16838
    margin_top_dxa: Optional[int] = None
    margin_bottom_dxa: Optional[int] = None
    margin_left_dxa: Optional[int] = None
    margin_right_dxa: Optional[int] = None
    page_num_format: Optional[str] = None     # 'decimal', 'lowerRoman', 'upperRoman', dll
    page_num_start: Optional[int] = None      # angka mulai (jika di-restart)
    num_columns: Optional[int] = None         # jumlah kolom teks; 1 = normal, ≥2 = format jurnal
    # Reference ke header/footer (rId yang dipakai untuk lookup di header_xmls/footer_xmls)
    header_refs: dict[str, str] = field(default_factory=dict)  # {'default': 'rId4', 'first': 'rId5', 'even': 'rId6'}
    footer_refs: dict[str, str] = field(default_factory=dict)
    # <w:titlePg/> — kalau False, header/footer ber-type "first" TIDAK dirender
    # Word sama sekali (ECMA-376 §17.10.6). Banyak dokumen menyimpan sisa part
    # 'first' dari editan lama; tanpa flag ini part mati itu ikut terbaca.
    title_pg: bool = False


@dataclass
class ImageInfo:
    """Informasi gambar di word/media/."""
    filename: str                             # mis. 'image1.png'
    content_type: str                         # mis. 'image/png'
    size_bytes: int


# ============================================================================
# Helper: konversi unit
# ============================================================================


def dxa_to_cm(dxa: Optional[int]) -> Optional[float]:
    """Konversi DXA (1/20 point) ke cm. 1 inch = 1440 DXA = 2.54 cm."""
    if dxa is None:
        return None
    return round(dxa / 1440.0 * 2.54, 3)


def half_points_to_pt(hp: Optional[Union[int, str]]) -> Optional[float]:
    """Konversi half-points (unit OOXML untuk font size) ke point."""
    if hp is None:
        return None
    try:
        return float(hp) / 2.0
    except (ValueError, TypeError):
        return None


def _unlink_quietly(path: str) -> None:
    """Hapus berkas sementara; diam saja kalau sudah tidak ada."""
    import os

    try:
        os.unlink(path)
    except OSError:
        pass


# ============================================================================
# Normalisasi: section yang "terperangkap" di dalam content control
# ============================================================================
#
# Bibliografi Mendeley/Zotero berupa <w:sdt>. Kalau penulis mengetik terus
# setelah bibliografi, judul LAMPIRAN beserta seluruh isinya ikut masuk ke
# content control yang sama. Di Word tampilannya normal, tetapi python-docx
# tidak mengenumerasi paragraf di dalam <w:sdt> — judul LAMPIRAN hilang dari
# parser.paragraphs, lampiran divonis tidak ada, dan isinya terbaca sebagai
# entri Daftar Pustaka.
#
# Perbaikannya: mulai dari judul pertama di dalam content control, pindahkan
# sisa isinya ke luar tepat setelah <w:sdt>. Urutan dokumen tidak berubah.
# Daftar Isi (docPartGallery "Table of Contents") tidak disentuh — judul
# "DAFTAR ISI" di dalamnya memang bagian dari blok itu.

_TOC_GALLERIES = frozenset({"Table of Contents"})
_LAMPIRAN_TEXT_RE = re.compile(r"^\s*LAMPIRAN(\s*-\s*LAMPIRAN)?\s*$", re.IGNORECASE)


_HEADING_WORD_RE = re.compile(r"\bheading\b", re.IGNORECASE)


def _heading_style_ids(styles_root: Optional[etree._Element]) -> set[str]:
    """styleId paragraf yang merupakan judul: nama "Heading N" (nama bawaan,
    tetap bahasa Inggris walau Word berbahasa lain) ATAU nama custom yang
    memuat kata "heading" (mis. template jurnal "Article Heading 1"/"Article
    Heading 2" — dibuat penulis/publisher, bukan style bawaan Word, dan
    umumnya tanpa outlineLvl sama sekali), punya outlineLvl, atau diturunkan
    (basedOn) dari style judul.

    REGRESI lapangan: artikel ilmiah pakai style "Article Heading 1" untuk
    "Pendahuluan"/"Metode"/dst — cek lama (startswith "heading") melewatkan
    ini karena nama dimulai "Article", bukan "Heading". Section-section itu
    lalu divonis hilang padahal ada dan sudah diberi style judul.
    """
    if styles_root is None:
        return set()
    based_on: dict[str, str] = {}
    heading: set[str] = set()
    for st in styles_root.findall("w:style", NSMAP):
        if st.get(qn("w:type")) != "paragraph":
            continue
        sid = st.get(qn("w:styleId"))
        if not sid:
            continue
        name_el = st.find("w:name", NSMAP)
        name = (name_el.get(qn("w:val")) or "") if name_el is not None else ""
        lvl = st.find("w:pPr/w:outlineLvl", NSMAP)
        if _HEADING_WORD_RE.search(name) or (
            lvl is not None and str(lvl.get(qn("w:val"))) not in ("9", "None")
        ):
            heading.add(sid)
        base = st.find("w:basedOn", NSMAP)
        if base is not None and base.get(qn("w:val")):
            based_on[sid] = base.get(qn("w:val"))
    changed = True
    while changed:
        changed = False
        for sid, base in based_on.items():
            if sid not in heading and base in heading:
                heading.add(sid)
                changed = True
    return heading


def _is_heading_p(p: etree._Element, heading_ids: set[str]) -> bool:
    style = p.find("w:pPr/w:pStyle", NSMAP)
    if style is not None and style.get(qn("w:val")) in heading_ids:
        return True
    lvl = p.find("w:pPr/w:outlineLvl", NSMAP)
    if lvl is not None and str(lvl.get(qn("w:val"))) not in ("9", "None"):
        return True
    text = "".join(t.text or "" for t in p.iter(qn("w:t")))
    return bool(_LAMPIRAN_TEXT_RE.match(text))


def _hoist_sections_out_of_sdt(
    body: Optional[etree._Element], heading_ids: set[str]
) -> int:
    """Pindahkan isi <w:sdt> body mulai judul pertama (bukan anak pertama) ke
    luar content control, tepat setelahnya. Return jumlah elemen dipindah."""
    if body is None:
        return 0
    moved = 0
    for sdt in [c for c in body if c.tag == qn("w:sdt")]:
        gallery = sdt.find("w:sdtPr/w:docPartObj/w:docPartGallery", NSMAP)
        if gallery is not None and gallery.get(qn("w:val")) in _TOC_GALLERIES:
            continue
        content = sdt.find("w:sdtContent", NSMAP)
        if content is None:
            continue
        kids = list(content)
        cut = next(
            (
                i
                for i, k in enumerate(kids)
                if i > 0 and k.tag == qn("w:p") and _is_heading_p(k, heading_ids)
            ),
            None,
        )
        if cut is None:
            continue
        anchor = sdt
        for k in kids[cut:]:
            anchor.addnext(k)  # lxml: memindahkan, bukan menyalin
            anchor = k
        moved += len(kids) - cut
    return moved


# ============================================================================
# Label penomoran otomatis (word/numbering.xml)
# ============================================================================
#
# Judul bab kerap diketik "PENDAHULUAN" saja; "BAB 1." di depannya dicetak Word
# dari daftar bernomor yang diikat ke style Heading 1. Label itu tidak ada di
# teks paragraf, sehingga pencarian "BAB 1" di teks gagal padahal di layar
# tercetak jelas. Di sini label dirakit dari deklarasi yang sama dengan yang
# dipakai Word: numPr paragraf (atau warisan style), definisi level di
# abstractNum, dan pencacah per daftar menurut urutan dokumen.
#
# Format angka yang tidak dikenal (bullet, aksara lain) tidak ditebak — label
# dibiarkan kosong, sama seperti sebelum fitur ini ada.

_ROMAN_VALUES = (
    (1000, "M"), (900, "CM"), (500, "D"), (400, "CD"), (100, "C"), (90, "XC"),
    (50, "L"), (40, "XL"), (10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I"),
)


def _format_list_counter(n: int, fmt: Optional[str]) -> Optional[str]:
    """Nilai pencacah dalam numFmt Word, atau None kalau formatnya tak dikenal."""
    if fmt in (None, "decimal"):
        return str(n)
    if fmt == "decimalZero":
        return f"{n:02d}"
    if fmt in ("upperRoman", "lowerRoman"):
        if n <= 0:
            return None
        out = []
        for value, sym in _ROMAN_VALUES:
            while n >= value:
                out.append(sym)
                n -= value
        roman = "".join(out)
        return roman if fmt == "upperRoman" else roman.lower()
    if fmt in ("upperLetter", "lowerLetter"):
        if n <= 0:
            return None
        # Word: A..Z, lalu AA..ZZ, AAA.. (huruf diulang, bukan basis-26).
        letter = chr(ord("A") + (n - 1) % 26) * ((n - 1) // 26 + 1)
        return letter if fmt == "upperLetter" else letter.lower()
    return None


@dataclass
class _ListLevel:
    start: int
    fmt: Optional[str]
    text: Optional[str]
    is_lgl: bool
    restart: Optional[int]  # <w:lvlRestart>; None = default Word
    p_style: Optional[str]


class _ListLabeler:
    """Merakit label nomor otomatis paragraf. Panggil `label_for` untuk SETIAP
    paragraf dalam urutan dokumen — pencacahnya bergantung pada urutan itu."""

    def __init__(
        self,
        styles_root: Optional[etree._Element],
        numbering_root: Optional[etree._Element],
    ):
        # styleId -> (numId, ilvl, basedOn) seperti tertulis di style itu sendiri
        self._style_numpr: dict[str, tuple[Optional[str], Optional[int], Optional[str]]] = {}
        # Style yang dipakai paragraf tanpa <w:pStyle> (w:default="1").
        self._default_style: Optional[str] = None
        if styles_root is not None:
            for st in styles_root.findall("w:style", NSMAP):
                sid = st.get(qn("w:styleId"))
                if not sid:
                    continue
                if (
                    st.get(qn("w:type")) == "paragraph"
                    and st.get(qn("w:default")) in ("1", "true")
                ):
                    self._default_style = sid
                num_id, ilvl = self._read_numpr(st.find("w:pPr", NSMAP))
                base = st.find("w:basedOn", NSMAP)
                self._style_numpr[sid] = (
                    num_id, ilvl, base.get(qn("w:val")) if base is not None else None
                )

        self._num_abs: dict[str, str] = {}
        self._num_start_override: dict[str, dict[int, int]] = {}
        self._abs_levels: dict[str, dict[int, _ListLevel]] = {}
        self._abs_style_link: dict[str, str] = {}
        if numbering_root is not None:
            for an in numbering_root.findall("w:abstractNum", NSMAP):
                aid = an.get(qn("w:abstractNumId"))
                if aid is None:
                    continue
                link = an.find("w:numStyleLink", NSMAP)
                if link is not None and link.get(qn("w:val")):
                    self._abs_style_link[aid] = link.get(qn("w:val"))
                self._abs_levels[aid] = {
                    lvl_idx: lvl
                    for lvl_idx, lvl in (self._read_level(el) for el in an.findall("w:lvl", NSMAP))
                    if lvl_idx is not None
                }
            for num in numbering_root.findall("w:num", NSMAP):
                nid = num.get(qn("w:numId"))
                abs_el = num.find("w:abstractNumId", NSMAP)
                if nid is None or abs_el is None:
                    continue
                self._num_abs[nid] = abs_el.get(qn("w:val"))
                overrides: dict[int, int] = {}
                for ov in num.findall("w:lvlOverride", NSMAP):
                    ilvl = _to_int(ov.get(qn("w:ilvl")))
                    start = ov.find("w:startOverride", NSMAP)
                    if ilvl is not None and start is not None:
                        val = _to_int(start.get(qn("w:val")))
                        if val is not None:
                            overrides[ilvl] = val
                if overrides:
                    self._num_start_override[nid] = overrides

        # Pencacah per abstractNum: Word melanjutkan hitungan antar-<w:num> yang
        # merujuk abstractNum yang sama, kecuali ada startOverride.
        self._counters: dict[str, dict[int, int]] = {}
        self._starts: dict[str, dict[int, int]] = {}
        self._seen_nums: set[str] = set()

    @staticmethod
    def _read_numpr(ppr: Optional[etree._Element]) -> tuple[Optional[str], Optional[int]]:
        if ppr is None:
            return None, None
        numpr = ppr.find("w:numPr", NSMAP)
        if numpr is None:
            return None, None
        num_el = numpr.find("w:numId", NSMAP)
        ilvl_el = numpr.find("w:ilvl", NSMAP)
        num_id = num_el.get(qn("w:val")) if num_el is not None else None
        ilvl = _to_int(ilvl_el.get(qn("w:val"))) if ilvl_el is not None else None
        return num_id, ilvl

    @staticmethod
    def _read_level(el: etree._Element) -> tuple[Optional[int], _ListLevel]:
        def val(tag: str) -> Optional[str]:
            child = el.find(tag, NSMAP)
            return child.get(qn("w:val")) if child is not None else None

        is_lgl_el = el.find("w:isLgl", NSMAP)
        is_lgl = is_lgl_el is not None and is_lgl_el.get(qn("w:val"), "1") not in ("0", "false")
        return _to_int(el.get(qn("w:ilvl"))), _ListLevel(
            start=_to_int(val("w:start")) or 0,  # ECMA-376: tanpa <w:start> = 0
            fmt=val("w:numFmt"),
            text=val("w:lvlText"),
            is_lgl=is_lgl,
            restart=_to_int(val("w:lvlRestart")),
            p_style=val("w:pStyle"),
        )

    @staticmethod
    def _is_bare_section_break(p: etree._Element, ppr: Optional[etree._Element]) -> bool:
        """Paragraf kosong yang hanya membawa <w:sectPr> — pemisah section.

        Word tidak mencetak nomor di paragraf ini dan tidak mencacahnya.
        Kasus nyata: Heading 1 kosong pembawa section break antara halaman
        romawi dan halaman inti. Kalau ikut dicacah, semua bab bergeser satu
        ("BAB 2. PENDAHULUAN"), padahal Daftar Isi Word dan render
        LibreOffice sama-sama mencetak "BAB 1. PENDAHULUAN".
        """
        if ppr is None or ppr.find("w:sectPr", NSMAP) is None:
            return False
        if any((t.text or "").strip() for t in p.iter(qn("w:t"))):
            return False
        return all(
            p.find(f".//{tag}", NSMAP) is None
            for tag in ("w:drawing", "w:pict", "w:object")
        )

    def _style_chain_numpr(self, style_id: Optional[str]) -> tuple[Optional[str], Optional[int], Optional[str]]:
        """(numId, ilvl, styleId pemilik numId) dari rantai basedOn style."""
        num_id: Optional[str] = None
        ilvl: Optional[int] = None
        owner: Optional[str] = None
        seen: set[str] = set()
        sid = style_id
        while sid and sid not in seen and sid in self._style_numpr:
            seen.add(sid)
            s_num, s_ilvl, base = self._style_numpr[sid]
            if num_id is None and s_num is not None:
                num_id, owner = s_num, sid
            if ilvl is None and s_ilvl is not None:
                ilvl = s_ilvl
            sid = base
        return num_id, ilvl, owner

    def _resolve_abs(self, num_id: str) -> Optional[str]:
        aid = self._num_abs.get(num_id)
        # numStyleLink: definisi level ada di abstractNum milik style penomoran.
        if aid is not None and aid in self._abs_style_link:
            linked_num, _, _ = self._style_chain_numpr(self._abs_style_link[aid])
            if linked_num is not None and linked_num != num_id:
                aid = self._num_abs.get(linked_num, aid)
        return aid

    def label_for(self, p: etree._Element) -> Optional[str]:
        ppr = p.find("w:pPr", NSMAP)
        if self._is_bare_section_break(p, ppr):
            return None
        p_num, p_ilvl = self._read_numpr(ppr)
        style_el = ppr.find("w:pStyle", NSMAP) if ppr is not None else None
        style_id = style_el.get(qn("w:val")) if style_el is not None else None
        if style_id is None:
            style_id = self._default_style
        s_num, s_ilvl, s_owner = self._style_chain_numpr(style_id)

        num_id = p_num if p_num is not None else s_num
        if num_id is None or num_id == "0":
            return None  # numId 0 = penomoran dimatikan eksplisit
        aid = self._resolve_abs(num_id)
        levels = self._abs_levels.get(aid) if aid is not None else None
        if not levels:
            return None

        ilvl = p_ilvl if p_ilvl is not None else s_ilvl
        if ilvl is None and p_num is None:
            # Style tertaut ke level lewat <w:lvl><w:pStyle> di abstractNum.
            ilvl = next(
                (i for i, lvl in levels.items() if lvl.p_style in (style_id, s_owner)),
                0,
            )
        ilvl = ilvl or 0
        lvl = levels.get(ilvl)
        if lvl is None:
            return None

        counters = self._counters.setdefault(aid, {})
        starts = self._starts.setdefault(aid, {})
        if num_id not in self._seen_nums:
            self._seen_nums.add(num_id)
            for ov_lvl, start in self._num_start_override.get(num_id, {}).items():
                starts[ov_lvl] = start
                counters.pop(ov_lvl, None)

        counters[ilvl] = counters[ilvl] + 1 if ilvl in counters else starts.get(ilvl, lvl.start)
        for deeper in [k for k in counters if k > ilvl]:
            restart = levels[deeper].restart if deeper in levels else None
            # lvlRestart 0 = tidak pernah diulang; N = diulang oleh level ≤ N (1-based).
            if restart is None or (restart != 0 and ilvl <= restart - 1):
                del counters[deeper]

        if lvl.text is None:
            return None
        # Label nomor mengikuti format penanda paragraf: kalau penanda itu
        # <w:vanish/>, Word tidak mencetak nomornya (pencacah tetap maju).
        vanish = ppr.find("w:rPr/w:vanish", NSMAP) if ppr is not None else None
        if vanish is not None and vanish.get(qn("w:val"), "1") not in ("0", "false"):
            return None

        def render(match: re.Match) -> str:
            ref = int(match.group(1)) - 1
            ref_lvl = levels.get(ref)
            if ref_lvl is None:
                raise ValueError
            value = counters.get(ref, starts.get(ref, ref_lvl.start))
            fmt = "decimal" if lvl.is_lgl else ref_lvl.fmt
            out = _format_list_counter(value, fmt)
            if out is None:
                raise ValueError
            return out

        try:
            label = re.sub(r"%([1-9])", render, lvl.text).strip()
        except ValueError:
            return None
        return label or None


def _to_int(val: Optional[str]) -> Optional[int]:
    if val is None:
        return None
    try:
        return int(val)
    except (TypeError, ValueError):
        return None


# ============================================================================
# DocxParser
# ============================================================================


class DocxParser:
    """
    Parser .docx untuk konsumsi semua checker module.

    Usage:
        parser = DocxParser('/path/to/laporan.docx')
        for para in parser.paragraphs:
            print(para.text, para.style_name)
        for header_part_name, xml_root in parser.header_xmls.items():
            # parse manual untuk page numbering checker
            ...
    """

    def __init__(self, file_path: Union[str, Path]):
        self.file_path = Path(file_path)
        if not self.file_path.exists():
            raise FileNotFoundError(f"File tidak ditemukan: {self.file_path}")
        if not self.file_path.suffix.lower() == ".docx":
            raise ValueError(f"Bukan file .docx: {self.file_path}")

        # Warning yang dikumpulkan selama parsing (parser tidak melempar error)
        self.warnings: list[str] = []

        # Bagian ZIP yang CRC-nya rusak (biasanya gambar). Kalau ada, dokumen
        # dibaca dari salinan yang sudah diperbaiki — lihat _repair_if_corrupt.
        self.original_file_path = self.file_path
        self.corrupt_parts: list[str] = []
        self._repair_if_corrupt()

        # Elemen yang dikeluarkan dari content control (lihat
        # _hoist_sections_out_of_sdt). 0 = dokumen tidak butuh normalisasi.
        self.hoisted_sdt_elements = 0

        # Lazy-load: hanya di-init saat property pertama kali diakses
        self._doc: Optional[DocxDocument] = None
        self._paragraphs: Optional[list[ParagraphInfo]] = None
        self._tables: Optional[list[TableInfo]] = None
        self._sections: Optional[list[SectionInfo]] = None
        self._header_xmls: Optional[dict[str, etree._Element]] = None
        self._footer_xmls: Optional[dict[str, etree._Element]] = None
        self._images: Optional[list[ImageInfo]] = None
        self._even_and_odd_headers: Optional[bool] = None
        self._document_xml: Optional[etree._Element] = None
        self._styles_xml: Optional[etree._Element] = None
        self._numbering_xml: Optional[etree._Element] = None
        self._paragraph_page_estimates: Optional[list[int]] = None
        self._paragraph_index_in_page: Optional[list[int]] = None
        self._has_lrpb: Optional[bool] = None

    # ------------------------------------------------------------------------
    # Akses dokumen via python-docx (high-level)
    # ------------------------------------------------------------------------

    # PNG 1x1 transparan — pengganti gambar yang isinya tak bisa dipulihkan.
    _PLACEHOLDER_PNG = bytes.fromhex(
        "89504e470d0a1a0a0000000d4948445200000001000000010806000000"
        "1f15c4890000000d49444154789c6300010000050001"
        "0d0a2db40000000049454e44ae426082"
    )

    def _repair_if_corrupt(self) -> None:
        """Pulihkan dokumen yang punya bagian ZIP rusak (CRC tidak cocok).

        Satu gambar rusak di dalam .docx membuat SEMUA modul gagal membuka
        dokumen ("Bad CRC-32 for file 'word/media/image1.png'"), padahal teks
        dokumennya utuh dan Word tetap bisa membukanya. Akibatnya tak satu pun
        pengecekan berjalan — dan pesan galat itu sempat tampil di UI sebagai
        "Kesalahan Judul Bab (word/media/image1.png)".

        Di sini bagian yang rusak dibaca ulang tanpa pemeriksaan CRC dan ditulis
        ke salinan sementara yang ZIP-nya sehat. Isi gambarnya mungkin cacat,
        tapi pemeriksaan administrasi tidak bergantung pada isi gambar. Kalau
        byte-nya pun tak terbaca, diganti gambar kosong 1x1 supaya relasi
        dokumen tetap utuh.
        """
        import tempfile

        try:
            zf = zipfile.ZipFile(self.file_path)
        except zipfile.BadZipFile:
            return  # bukan ZIP sama sekali — biar Document() yang melapor
        bad = []
        for info in zf.infolist():
            try:
                zf.read(info.filename)
            except zipfile.BadZipFile:
                bad.append(info.filename)
        if not bad:
            zf.close()
            return

        tmp = tempfile.NamedTemporaryFile(
            prefix="repaired_", suffix=".docx", delete=False
        )
        tmp.close()
        with zipfile.ZipFile(tmp.name, "w", zipfile.ZIP_DEFLATED) as out:
            for info in zf.infolist():
                if info.filename not in bad:
                    out.writestr(info, zf.read(info.filename))
                    continue
                try:
                    ext = zf.open(info)
                    ext._expected_crc = None  # lewati pemeriksaan CRC
                    data = ext.read()
                except Exception:
                    data = b""
                if not data and info.filename.lower().endswith(".png"):
                    data = self._PLACEHOLDER_PNG
                out.writestr(info.filename, data)
        zf.close()
        self.corrupt_parts = bad
        self.file_path = Path(tmp.name)
        # Salinan sementara dihapus begitu parser tidak dipakai lagi. Tanpa ini
        # setiap unggahan dokumen rusak meninggalkan satu berkas di /tmp.
        import weakref

        weakref.finalize(self, _unlink_quietly, tmp.name)
        self.warnings.append(
            f"Bagian dokumen rusak dan diperbaiki otomatis: {', '.join(bad)}"
        )

    @property
    def doc(self) -> DocxDocument:
        """Objek python-docx Document (lazy)."""
        if self._doc is None:
            self._doc = Document(str(self.file_path))
            self.hoisted_sdt_elements = _hoist_sections_out_of_sdt(
                self._doc.element.body, _heading_style_ids(self._doc.styles.element)
            )
        return self._doc

    @property
    def paragraphs(self) -> list[ParagraphInfo]:
        """List semua paragraf di body dokumen."""
        if self._paragraphs is None:
            self._paragraphs = self._extract_paragraphs()
        return self._paragraphs

    @property
    def tables(self) -> list[TableInfo]:
        """List semua tabel di body dokumen."""
        if self._tables is None:
            self._tables = self._extract_tables()
        return self._tables

    @property
    def sections(self) -> list[SectionInfo]:
        """List semua section dokumen (settings halaman + ref ke header/footer)."""
        if self._sections is None:
            self._sections = self._extract_sections()
        return self._sections

    # ------------------------------------------------------------------------
    # Akses raw OOXML (low-level) — untuk PageNumberingChecker
    # ------------------------------------------------------------------------

    @property
    def document_xml(self) -> etree._Element:
        """Raw XML word/document.xml (lazy)."""
        if self._document_xml is None:
            self._document_xml = self._read_xml_part("word/document.xml")
            # Harus sama dengan self.doc supaya index paragraf tetap sejajar.
            if self._document_xml is not None:
                _hoist_sections_out_of_sdt(
                    self._document_xml.find("w:body", NSMAP),
                    _heading_style_ids(self.styles_xml),
                )
        return self._document_xml

    @property
    def styles_xml(self) -> Optional[etree._Element]:
        """Raw XML word/styles.xml (lazy)."""
        if self._styles_xml is None:
            self._styles_xml = self._read_xml_part("word/styles.xml", required=False)
        return self._styles_xml

    @property
    def numbering_xml(self) -> Optional[etree._Element]:
        """Raw XML word/numbering.xml (lazy, optional — tidak semua docx punya)."""
        if self._numbering_xml is None:
            self._numbering_xml = self._read_xml_part("word/numbering.xml", required=False)
        return self._numbering_xml

    @property
    def header_xmls(self) -> dict[str, etree._Element]:
        """
        Dict {part_name: xml_root} untuk semua word/headerN.xml.
        part_name = nama file di dalam zip, mis. 'word/header1.xml'.
        Dipakai PageNumberingChecker untuk validasi zona awal (romawi pojok kanan bawah).
        """
        if self._header_xmls is None:
            self._header_xmls = self._read_header_footer_xmls(prefix="word/header")
        return self._header_xmls

    @property
    def footer_xmls(self) -> dict[str, etree._Element]:
        """
        Dict {part_name: xml_root} untuk semua word/footerN.xml.
        Dipakai PageNumberingChecker untuk validasi zona awal di footer.
        """
        if self._footer_xmls is None:
            self._footer_xmls = self._read_header_footer_xmls(prefix="word/footer")
        return self._footer_xmls

    @property
    def even_and_odd_headers(self) -> bool:
        """<w:evenAndOddHeaders/> di word/settings.xml.

        Kalau False (default), header/footer ber-type "even" TIDAK pernah
        dirender Word — halaman genap ikut memakai part "default".
        """
        if self._even_and_odd_headers is None:
            raw = self.read_raw_part("word/settings.xml")
            self._even_and_odd_headers = bool(
                raw and b"evenAndOddHeaders" in raw
            )
        return self._even_and_odd_headers

    @property
    def images(self) -> list[ImageInfo]:
        """List gambar di word/media/. Dipakai BiodataOCRVerifier (deteksi TTD crop)."""
        if self._images is None:
            self._images = self._extract_images()
        return self._images

    # ------------------------------------------------------------------------
    # Helper public
    # ------------------------------------------------------------------------

    def iter_runs(self) -> Iterator[tuple[int, RunInfo]]:
        """
        Iterate semua run di body teks beserta indeks paragrafnya.
        Berguna untuk FormatChecker memeriksa konsistensi font.
        """
        for para in self.paragraphs:
            for run in para.runs:
                yield para.index, run

    def estimate_physical_page(self, paragraph_index: int) -> Optional[int]:
        """
        Estimasi nomor halaman fisik (1-based) untuk suatu paragraf.
        Mengandalkan page break marker di OOXML:
        - w:lastRenderedPageBreak
        - w:br w:type="page"
        - section break non-continuous

        Catatan: ini estimasi terbaik dari metadata DOCX, bukan layout engine penuh.
        """
        if paragraph_index < 0:
            return None
        if self._paragraph_page_estimates is None:
            self._paragraph_page_estimates = self._build_page_estimates()
        if paragraph_index >= len(self._paragraph_page_estimates):
            return None
        return self._paragraph_page_estimates[paragraph_index]

    def estimate_paragraph_index_in_page(self, paragraph_index: int) -> Optional[int]:
        """
        Estimasi urutan paragraf (1-based) di halaman fisik tempat paragraf berada.
        Hanya menghitung paragraf yang non-kosong agar lebih relevan untuk user.
        """
        if paragraph_index < 0:
            return None
        if self._paragraph_index_in_page is None:
            self._paragraph_index_in_page = self._build_paragraph_index_in_page()
        if paragraph_index >= len(self._paragraph_index_in_page):
            return None
        return self._paragraph_index_in_page[paragraph_index]

    def _document_has_lrpb(self) -> bool:
        """True jika dokumen punya marker w:lastRenderedPageBreak (ciri dokumen
        yang terakhir di-render/disimpan oleh MS Word). Marker ini = cache layout
        Word; jika ada, ia sudah merekam SEMUA page break (manual & section)."""
        if self._has_lrpb is None:
            body = self.doc.element.body
            self._has_lrpb = (
                body.find(".//w:lastRenderedPageBreak", namespaces=NSMAP) is not None
            )
        return self._has_lrpb

    def _element_break_delta(self, el: etree._Element) -> int:
        """
        Pertambahan halaman akibat satu elemen body (paragraf / tabel / sdt).

        - Mode Word (ada lastRenderedPageBreak): hitung lastRenderedPageBreak SAJA.
          Word sudah mencatat setiap page break (termasuk break manual & section)
          sebagai lastRenderedPageBreak, jadi menambah break manual/section lagi =
          double-count (inilah penyebab over-count lama).
        - Mode non-Word (tanpa lastRenderedPageBreak): fallback ke break manual +
          section break non-continuous — perkiraan terbaik tanpa cache layout Word.

        Catatan sdt: untuk elemen multi-paragraf, setiap page break menghasilkan
        SEPASANG LRPB — satu "rest" di paragraf terakhir halaman lama, satu
        "lead" di paragraf pertama halaman baru. Menghitung keduanya =
        double-count. Solusi: hanya hitung LEAD LRPB (sebelum teks).
        Tabel punya aturan sendiri per baris — lihat _table_lrpb_breaks.
        """
        if self._document_has_lrpb():
            tag = etree.QName(el).localname
            if tag == "tbl":
                return self._table_lrpb_breaks(el)[0]
            if tag == "sdt":
                count = 0
                for p_el in el.findall(".//w:p", namespaces=NSMAP):
                    lead, _ = self._split_lrpb_around_text(p_el)
                    count += lead
                return count
            return len(el.findall(".//w:lastRenderedPageBreak", namespaces=NSMAP))
        delta = len(el.findall(".//w:br[@w:type='page']", namespaces=NSMAP))
        for sect_pr in el.findall(".//w:pPr/w:sectPr", namespaces=NSMAP):
            sect_type = sect_pr.find("w:type", namespaces=NSMAP)
            val = sect_type.get(qn("w:val")) if sect_type is not None else None
            if val is None or str(val).lower() != "continuous":
                delta += 1
        return delta

    def _split_lrpb_around_text(self, p_el: etree._Element) -> tuple[int, int]:
        """Pisah lastRenderedPageBreak sebuah paragraf menjadi (lead, rest):
        - lead  = break SEBELUM teks pertama → paragraf ini mulai di halaman baru.
        - rest  = break SETELAH teks → mempengaruhi konten sesudahnya saja.
        Dipakai agar paragraf yang diawali page break tercatat di halaman yang benar."""
        lead = rest = 0
        seen_text = False
        lrpb_tag = qn("w:lastRenderedPageBreak")
        t_tag = qn("w:t")
        for el in p_el.iter():
            if el.tag == lrpb_tag:
                if seen_text:
                    rest += 1
                else:
                    lead += 1
            elif el.tag == t_tag and (el.text or "").strip():
                seen_text = True
        return lead, rest

    def _table_lrpb_breaks(
        self, tbl_el: etree._Element, after_split_row: bool = False
    ) -> tuple[int, bool]:
        """Jumlah halaman baru akibat satu <w:tbl> (mode Word), plus apakah
        baris terakhirnya terbelah melewati batas halaman.

        Word menulis LRPB setiap kali halaman BERPINDAH menurut urutan dokumen,
        termasuk perpindahan MUNDUR. Baris tabel dibaca sel demi sel, padahal
        sel-sel sebaris tercetak berdampingan. Pada baris yang terbelah: sel A
        menyeberang ke halaman berikut (LRPB di tengah teks), lalu sel B kembali
        ke puncak baris di halaman lama — dan awal sel B ikut diberi LRPB,
        padahal tidak ada halaman baru. Elemen sesudah baris terbelah (baris
        berikut / paragraf sesudah tabel) juga kerap diawali LRPB padahal masih
        di halaman ekor baris itu. Menjumlah semua LRPB "lead" di tabel (aturan
        lama) menghitung perpindahan mundur itu sebagai halaman baru.

        Maka dihitung per baris:
        - baris mulai di halaman baru bila sel pertamanya diawali LRPB, kecuali
          tepat sesudah baris terbelah (LRPB itu artefak tadi);
        - baris menyeberang sebanyak LRPB di TENGAH isi sel — ambil sel yang
          terbanyak, bukan dijumlah, karena sel sebaris berjalan paralel.

        `after_split_row` membawa status baris terakhir elemen sebelumnya, dan
        nilai kembaliannya diteruskan ke elemen sesudah tabel.
        """
        lrpb_tag = qn("w:lastRenderedPageBreak")
        t_tag = qn("w:t")
        content_tags = (qn("w:drawing"), qn("w:pict"))
        breaks = 0
        rows = etree._Element.xpath(
            tbl_el, "./w:tr | ./w:sdt/w:sdtContent/w:tr", namespaces=NSMAP
        )
        for tr in rows:
            starts_new_page = False
            span = 0
            cells = etree._Element.xpath(
                tr, "./w:tc | ./w:sdt/w:sdtContent/w:tc", namespaces=NSMAP
            )
            for ci, tc in enumerate(cells):
                seen_content = False
                mid = 0
                for el in tc.iter(lrpb_tag, t_tag, *content_tags):
                    if el.tag == lrpb_tag:
                        if seen_content:
                            mid += 1
                        elif ci == 0:
                            starts_new_page = True
                    elif el.tag != t_tag or (el.text or "").strip():
                        seen_content = True
                span = max(span, mid)
            if starts_new_page and not after_split_row:
                breaks += 1
            breaks += span
            after_split_row = span > 0
        return breaks, after_split_row

    def _forces_page_break_before(self, p_el: etree._Element) -> bool:
        """True bila paragraf memaksa halaman baru sebelum teksnya: w:br page
        sebelum teks pertama, atau pageBreakBefore (langsung/diwarisi style)."""
        br_tag, t_tag = qn("w:br"), qn("w:t")
        for el in p_el.iter(br_tag, t_tag):
            if el.tag == t_tag:
                if (el.text or "").strip():
                    break
            elif el.get(qn("w:type")) == "page":
                return True

        def _on(flag: etree._Element) -> bool:
            val = flag.get(qn("w:val"))
            return val is None or val.lower() in ("1", "true", "on")

        flag = p_el.find("w:pPr/w:pageBreakBefore", namespaces=NSMAP)
        if flag is not None:
            return _on(flag)
        style = p_el.find("w:pPr/w:pStyle", namespaces=NSMAP)
        style_id = style.get(qn("w:val")) if style is not None else None
        styles_el = self.doc.styles.element
        if style_id is None:
            default = styles_el.find(
                "w:style[@w:type='paragraph'][@w:default='1']", namespaces=NSMAP
            )
            style_id = default.get(qn("w:styleId")) if default is not None else None
        for _ in range(20):  # rantai basedOn; batasi agar siklus tidak menggantung
            if style_id is None:
                break
            st = styles_el.find(f"w:style[@w:styleId='{style_id}']", namespaces=NSMAP)
            if st is None:
                break
            flag = st.find("w:pPr/w:pageBreakBefore", namespaces=NSMAP)
            if flag is not None:
                return _on(flag)
            based = st.find("w:basedOn", namespaces=NSMAP)
            style_id = based.get(qn("w:val")) if based is not None else None
        return False

    def _delta_pages_after_paragraph_element(self, p_el: etree._Element) -> int:
        """
        Tambahan nomor halaman setelah me-render satu elemen <w:p>
        (sama dengan logika _build_page_estimates untuk body paragraf).
        """
        return self._element_break_delta(p_el)

    def estimate_page_for_table_cell(
        self, table_index: int, row: int, col: int = 0
    ) -> Optional[int]:
        """
        Estimasi nomor halaman (1-based) untuk sel tabel (baris `row`, kolom `col`).
        Memakai urutan isi dokumen + page break di OOXML (sama filosofi dengan
        estimate_physical_page untuk paragraf body).

        Catatan: isi tabel tidak masuk `self.paragraphs`; harus traverse w:tbl.
        """
        if table_index < 0 or table_index >= len(self.doc.tables):
            return None
        tbl = self.doc.tables[table_index]
        if row < 0 or row >= len(tbl.rows):
            return None
        r = tbl.rows[row]
        if col < 0 or col >= len(r.cells):
            return None
        cell = r.cells[col]
        target_p: Optional[etree._Element] = None
        for para in cell.paragraphs:
            target_p = para._element
            break
        if target_p is None:
            return None

        target_tbl = tbl._element
        page = 1

        for child in self.doc.element.body:
            if child.tag == qn("w:p"):
                if child is target_p:
                    return page
                page += self._delta_pages_after_paragraph_element(child)
            elif child.tag == qn("w:tbl"):
                if child is target_tbl:
                    for tr in child.findall(qn("w:tr")):
                        for tc in tr.findall(qn("w:tc")):
                            for p_el in tc.findall(qn("w:p")):
                                if p_el is target_p:
                                    return page
                                page += self._delta_pages_after_paragraph_element(p_el)
                else:
                    for p_el in child.findall(".//w:p", namespaces=NSMAP):
                        page += self._delta_pages_after_paragraph_element(p_el)

        return None

    def find_section_boundaries(
        self,
        section_names: list[str],
        case_sensitive: bool = False,
        headings_only: bool = False,
    ) -> dict[str, Optional[int]]:
        """
        Cari indeks paragraf awal untuk tiap nama section di list.
        Return dict {section_name: paragraph_index | None}.

        Args:
            section_names: list nama section yang dicari, mis. ['BAB 1', 'DAFTAR PUSTAKA'].
            case_sensitive: jika False (default), pencocokan tidak case-sensitive.
            headings_only: jika True, hanya match paragraf yang terdeteksi sebagai
                heading (is_heading=True). Berguna untuk menghindari false-match
                dari baris di Daftar Isi yang teksnya juga dimulai dengan "BAB 1".
                Default False untuk backward compatibility (StructureChecker mungkin
                justru butuh deteksi entri ToC).

        Contoh:
            # Tanpa headings_only — bisa match baris ToC "BAB 1. ........... 1"
            parser.find_section_boundaries(['BAB 1'])

            # Dengan headings_only — hanya match heading "BAB 1. PENDAHULUAN" asli
            parser.find_section_boundaries(['BAB 1'], headings_only=True)

        Pencocokan: paragraf yang teksnya DIMULAI dengan section_name (setelah strip).
        Yang ditemukan adalah kemunculan PERTAMA yang memenuhi kriteria.
        """
        result: dict[str, Optional[int]] = {name: None for name in section_names}

        # Pass 1: perilaku normal
        for para in self.paragraphs:
            if headings_only and not para.is_heading:
                continue
            # Label penomoran otomatis ("BAB 1.") ikut dicoba, di samping teks
            # ketikan — lihat ParagraphInfo.heading_texts.
            cmp_texts = [
                t.strip() if case_sensitive else t.strip().upper()
                for t in para.heading_texts
            ]
            for name in section_names:
                if result[name] is not None:
                    continue  # sudah ketemu yang pertama
                cmp_name = name if case_sensitive else name.upper()
                if any(t.startswith(cmp_name) for t in cmp_texts):
                    result[name] = para.index

        # Pass 2 (fallback): jika headings_only=True dan ada section belum ketemu,
        # coba cari baris non-heading yang "mirip heading nyata" dan bukan baris ToC.
        if headings_only and any(v is None for v in result.values()):
            missing = {k for k, v in result.items() if v is None}
            for para in self.paragraphs:
                if not para.text.strip():
                    continue
                if self._looks_like_toc_entry(para.text.strip()):
                    continue
                variants = [t.strip() for t in para.heading_texts]
                if not any(
                    self._looks_like_heading_fallback(t, para=para) for t in variants
                ):
                    continue
                cmp_texts = [t if case_sensitive else t.upper() for t in variants]
                for name in list(missing):
                    cmp_name = name if case_sensitive else name.upper()
                    if any(t.startswith(cmp_name) for t in cmp_texts):
                        result[name] = para.index
                        missing.remove(name)
                        if not missing:
                            break
                if not missing:
                    break
        return result

    # Style bawaan Word untuk entri daftar otomatis. Word menulis nama style ini
    # dalam bahasa Inggris apa pun bahasa UI-nya, jadi aman dicocokkan langsung.
    _TOC_STYLE_RE = re.compile(
        r"^(?:toc\s*\d*|table\s+of\s+(?:figures|authorities)|"
        r"daftar\s+isi\s*\d*|indeks\s*\d*)$",
        re.IGNORECASE,
    )

    @classmethod
    def _detect_toc_entry(
        cls, text: str, style_name: Optional[str]
    ) -> tuple[bool, Optional[str]]:
        """Apakah paragraf ini entri daftar otomatis? Return (hasil, sumber bukti).

        Bukti diurut dari yang pasti ke yang menerka:

        1. 'style'  — style bawaan Word ('toc 1'..'toc 9', 'table of figures').
                      Ini deklarasi eksplisit di dalam file: kalau Word yang
                      membuat daftarnya, paragrafnya PASTI ber-style ini.
        2. 'leader' — cadangan untuk Daftar Isi yang diketik manual: dot leader
                      atau TAB diikuti nomor halaman. Perlu dipertahankan karena
                      banyak dokumen mahasiswa mengetik Daftar Isi dengan tangan.

        Dulu hanya (2) yang ada, dan versinya berbeda-beda di tiap modul —
        sumber false positive: entri ToC dikira heading section sungguhan.
        """
        t = (text or "").strip()
        if not t:
            return False, None
        if style_name and cls._TOC_STYLE_RE.match(style_name.strip()):
            return True, "style"
        if re.search(r"\t+\s*([ivxlcdm]+|\d+)\s*$", t, flags=re.IGNORECASE):
            return True, "leader"
        if re.search(r"[.\s]{4,}\s*(\d+|[ivxlcdm]+)\s*$", t, flags=re.IGNORECASE):
            return True, "leader"
        return False, None

    @staticmethod
    def _looks_like_toc_entry(text: str) -> bool:
        """Kompatibilitas: versi lama yang hanya melihat bentuk teks.

        Dipertahankan karena masih dipanggil `find_section_boundaries`. Untuk
        pengecekan baru pakai `ParagraphInfo.is_toc_entry` yang membaca style.
        """
        return DocxParser._detect_toc_entry(text, None)[0]

    @staticmethod
    def _read_outline_level(para) -> Optional[int]:
        """<w:outlineLvl w:val="N"/> dari pPr paragraf (0-based), atau None.

        Dipakai style heading kustom yang namanya bukan 'Heading N' — lazim di
        template kampus. Tanpa ini, heading semacam itu hanya terdeteksi lewat
        heuristik bentuk (rasio kapital / bold).
        """
        try:
            ppr = para._element.find(qn("w:pPr"))
            if ppr is None:
                return None
            el = ppr.find(qn("w:outlineLvl"))
            if el is None:
                return None
            val = el.get(qn("w:val"))
            if val is None or not str(val).lstrip("-").isdigit():
                return None
            lvl = int(val)
            # 9 = "body text" (bukan heading) menurut ECMA-376.
            return lvl if 0 <= lvl <= 8 else None
        except Exception:
            return None

    @staticmethod
    def _looks_like_heading_fallback(text: str, para=None) -> bool:
        """
        Heuristik heading saat style Heading tidak dipakai:
        - Pola BAB N...
        - Mayoritas huruf uppercase (mis. DAFTAR PUSTAKA, LAMPIRAN)
        - Paragraf pendek (≤60 char) dengan semua run explicitly bold
        """
        t = text.strip()
        if not t:
            return False
        if re.match(r"^BAB\s+[IVXLCM0-9]+(?:[.\s]|$)", t, flags=re.IGNORECASE):
            return True
        letters = [c for c in t if c.isalpha()]
        if not letters:
            return False
        upper_ratio = sum(1 for c in letters if c.isupper()) / len(letters)
        if upper_ratio >= 0.8:
            return True
        if para is not None and len(t) <= 60:
            text_runs = [r for r in para.runs if r.text.strip()]
            if text_runs and all(r.bold is True for r in text_runs):
                return True
        return False

    def read_raw_part(self, part_name: str) -> Optional[bytes]:
        """
        Baca bytes mentah dari part di zip .docx.
        Berguna kalau ada checker yang butuh akses XML/file lain di paket.
        """
        try:
            with zipfile.ZipFile(self.file_path, "r") as z:
                return z.read(part_name)
        except KeyError:
            return None
        except zipfile.BadZipFile:
            self.warnings.append(f"Bad zip: {self.file_path}")
            return None

    # ------------------------------------------------------------------------
    # Implementasi internal
    # ------------------------------------------------------------------------

    def _extract_paragraphs(self) -> list[ParagraphInfo]:
        labels = self._build_list_labels()
        result: list[ParagraphInfo] = []
        for idx, para in enumerate(self.doc.paragraphs):
            info = self._paragraph_to_info(idx, para)
            info.list_label = labels.get(para._element)
            result.append(info)
        self._mark_manual_toc_block_entries(result, self.doc.paragraphs)
        return result

    def _mark_manual_toc_block_entries(
        self,
        paragraphs: list[ParagraphInfo],
        source_paragraphs,
    ) -> None:
        """Tandai baris tanpa leader di dalam blok Daftar Isi manual.

        Daftar Isi yang diketik tangan tidak selalu konsisten. Sebagian baris
        memakai ``..... 3`` sehingga dikenali oleh :meth:`_detect_toc_entry`,
        tetapi baris lain kadang hanya berisi ``BAB 3. ...``. Kalau dinilai per
        baris, judul tanpa leader itu tampak persis seperti heading isi dan
        StructureChecker mengambilnya sebagai kemunculan BAB yang sebenarnya.

        Konteks blok dipakai secara konservatif:

        * harus diawali judul tersendiri ``DAFTAR ISI``;
        * sebelum pemisah halaman/section atau heading ber-style berikutnya,
          harus ada sedikitnya dua baris ber-dot/TAB leader;
        * hanya rentang dari sesudah judul sampai baris leader terakhir yang
          diwarisi sebagai entri TOC.

        Dengan syarat tersebut, satu kalimat bertitik di isi dokumen tidak
        cukup untuk mengubah paragraf lain menjadi entri TOC.
        """
        if not paragraphs or len(paragraphs) != len(source_paragraphs):
            return

        title_indices = [
            p.index
            for p in paragraphs
            if re.sub(r"\s+", " ", p.text.upper().strip()) == "DAFTAR ISI"
            and not p.is_toc_entry
        ]
        for title_idx in title_indices:
            region_end = len(paragraphs)
            leader_indices: list[int] = []

            for idx in range(title_idx + 1, len(paragraphs)):
                info = paragraphs[idx]
                source = source_paragraphs[idx]

                # Pemisah halaman kosong seperti pada daftar isi manual
                # NeuroRehab menutup blok sebelum heading front matter lain.
                has_page_break = bool(
                    source._element.xpath(
                        ".//w:br[@w:type='page'] | .//w:lastRenderedPageBreak"
                    )
                )
                has_section_break = source._element.find(
                    "w:pPr/w:sectPr", namespaces=NSMAP
                ) is not None
                if has_page_break or has_section_break:
                    region_end = idx
                    break

                # Sesudah sekurangnya satu entri manual, Heading/Title yang
                # sebenarnya merupakan batas aman walau tidak ada page break.
                if info.is_heading and leader_indices:
                    region_end = idx
                    break

                if info.toc_evidence == "leader":
                    leader_indices.append(idx)

            leaders_in_region = [i for i in leader_indices if i < region_end]
            if len(leaders_in_region) < 2:
                continue

            last_leader = leaders_in_region[-1]
            for idx in range(title_idx + 1, last_leader + 1):
                info = paragraphs[idx]
                if not info.text.strip() or info.is_toc_entry:
                    continue
                info.is_toc_entry = True
                info.toc_evidence = "manual-block"
                info.is_heading = False
                info.heading_level = None

            # Hanya blok DAFTAR ISI pertama yang relevan sebagai front matter.
            break

    def _build_list_labels(self) -> dict[etree._Element, str]:
        """Label nomor otomatis per elemen <w:p>, dirakit dalam urutan dokumen.

        Semua paragraf body ikut dicacah — termasuk yang di dalam tabel dan
        content control — karena Word juga mencacahnya. Paragraf di dalam kotak
        teks dilewati: posisinya di alur dokumen tidak pasti.
        """
        try:
            labeler = _ListLabeler(self.doc.styles.element, self.numbering_xml)
            labels: dict[etree._Element, str] = {}
            txbx = qn("w:txbxContent")
            for p in self.doc.element.body.iter(qn("w:p")):
                if next(p.iterancestors(txbx), None) is not None:
                    continue
                label = labeler.label_for(p)
                if label:
                    labels[p] = label
            return labels
        except Exception as e:
            self.warnings.append(f"Gagal membaca penomoran otomatis: {e}")
            return {}

    def _build_page_estimates(self) -> list[int]:
        """Estimasi halaman fisik per paragraf body (index sejajar self.paragraphs).

        Menyusuri anak-LANGSUNG <w:body> berurutan (bukan hanya self.doc.paragraphs)
        supaya page break di dalam <w:tbl>/<w:sdt> — mis. bibliografi dalam content
        control — ikut menggeser halaman. Setiap <w:p> anak-langsung body sejajar
        1:1 dengan self.doc.paragraphs, sehingga index tetap sinkron.

        Mode Word: hitung lastRenderedPageBreak saja, dan letakkan leading break
        (sebelum teks paragraf) agar paragraf yang mengawali halaman tercatat benar.
        """
        use_lrpb = self._document_has_lrpb()
        page = 1
        estimates: list[int] = []
        after_split_row = False  # elemen sebelumnya tabel dgn baris akhir terbelah
        for child in self.doc.element.body:
            if child.tag == qn("w:p"):
                if use_lrpb:
                    lead, rest = self._split_lrpb_around_text(child)
                    if (
                        after_split_row
                        and lead
                        and not self._forces_page_break_before(child)
                    ):
                        # Artefak baris terbelah (lihat _table_lrpb_breaks):
                        # paragraf ini masih di halaman ekor baris tsb.
                        lead -= 1
                    page += lead
                    estimates.append(page)
                    page += rest
                else:
                    estimates.append(page)
                    page += self._element_break_delta(child)
                after_split_row = False
            elif use_lrpb and child.tag == qn("w:tbl"):
                delta, after_split_row = self._table_lrpb_breaks(
                    child, after_split_row
                )
                page += delta
            else:
                if child.tag == qn("w:sdt"):
                    after_split_row = False
                # tabel / sdt / elemen body lain: tidak masuk self.paragraphs,
                # tapi break di dalamnya tetap menggeser halaman paragraf berikutnya.
                page += self._element_break_delta(child)
        return estimates

    def _build_paragraph_index_in_page(self) -> list[int]:
        if self._paragraph_page_estimates is None:
            self._paragraph_page_estimates = self._build_page_estimates()

        counts_per_page: dict[int, int] = {}
        result: list[int] = []
        for idx, para in enumerate(self.paragraphs):
            page = self._paragraph_page_estimates[idx]
            if not para.text.strip():
                # Paragraf kosong tidak menambah hitungan "ke-n" user-facing.
                result.append(counts_per_page.get(page, 0))
                continue
            counts_per_page[page] = counts_per_page.get(page, 0) + 1
            result.append(counts_per_page[page])
        return result

    def _paragraph_to_info(self, idx: int, para: Paragraph) -> ParagraphInfo:
        # Style name
        style_name: Optional[str] = None
        try:
            if para.style is not None:
                style_name = para.style.name
        except Exception as e:
            self.warnings.append(f"Gagal baca style paragraf {idx}: {e}")

        # Alignment
        alignment_str: Optional[str] = None
        try:
            align = para.paragraph_format.alignment
            if align is not None:
                # WD_ALIGN_PARAGRAPH enum → string. Format: "CENTER (1)" → "center"
                raw = str(align)
                # Ambil kata sebelum spasi atau setelah titik terakhir
                if "." in raw:
                    raw = raw.rsplit(".", 1)[-1]
                if " " in raw:
                    raw = raw.split(" ", 1)[0]
                alignment_str = raw.lower()
        except Exception:
            pass

        # Line spacing
        line_spacing: Optional[float] = None
        try:
            ls = para.paragraph_format.line_spacing
            if isinstance(ls, Length):
                # Mode "Exactly"/"At least" (w:lineRule bukan "auto"): python-docx
                # balikin Length (EMU), bukan multiplier. Field ini dipakai
                # checker sebagai multiplier ("1.0", "1.15", dst.) — EMU mentah
                # (ratusan ribu) lolos tanpa konversi bikin pesan absurd macam
                # "spasi baris ditemukan 144780.0". Dua unit itu tidak
                # sepadan (poin tetap vs kelipatan tinggi baris), jadi biarkan
                # None (tidak dinilai) daripada memvonis salah dari angka yang
                # salah baca.
                line_spacing = None
            elif ls is not None:
                line_spacing = float(ls)
        except Exception:
            pass

        # Runs
        runs: list[RunInfo] = []
        for run in para.runs:
            run_info = RunInfo(
                text=run.text or "",
                font_name=self._safe_font_name(run),
                font_size_pt=self._safe_font_size(run),
                bold=run.bold,
                italic=run.italic,
                underline=run.underline,
            )
            runs.append(run_info)

        # --- Entri Daftar Isi ---------------------------------------------
        # Dibaca dari deklarasi Word lebih dulu; heuristik dot/tab leader hanya
        # cadangan untuk Daftar Isi yang diketik manual tanpa style.
        is_toc_entry, toc_evidence = self._detect_toc_entry(
            para.text or "", style_name
        )

        # --- Heading -------------------------------------------------------
        # Urutan bukti: style bawaan → outlineLvl eksplisit → heuristik bentuk.
        # Entri Daftar Isi TIDAK PERNAH heading: teksnya kerap UPPERCASE
        # ("DAFTAR PUSTAKA\t12") sehingga lolos heuristik bentuk dan bikin
        # checker mengira section-nya dimulai di halaman Daftar Isi.
        is_heading = False
        heading_level: Optional[int] = None
        if style_name:
            sn_lower = style_name.lower()
            # Bukan cuma style bawaan Word "Heading N": template jurnal/kampus
            # kerap punya style custom yang memuat kata "heading" di posisi
            # lain, mis. "Article Heading 1" (bukan diawali "Heading"). Tanpa
            # ini, section itu dibaca sebagai teks biasa dan divonis hilang.
            if _HEADING_WORD_RE.search(style_name):
                is_heading = True
                # Coba ekstrak level dari nama style ("Heading 1" → 1,
                # "Article Heading 2" → 2)
                parts = style_name.split()
                if len(parts) > 1 and parts[-1].isdigit():
                    heading_level = int(parts[-1])
                else:
                    heading_level = 1
            elif sn_lower in ("title", "subtitle"):
                is_heading = True
                heading_level = 0  # judul

        if not is_heading and not is_toc_entry:
            # <w:outlineLvl w:val="0"/> — dipakai style heading kustom yang
            # namanya bukan "Heading N" (lazim di template kampus).
            outline = self._read_outline_level(para)
            if outline is not None:
                is_heading = True
                heading_level = outline + 1

        if is_toc_entry:
            is_heading = False
            heading_level = None

        # Paragraph left indentation (dari XML pPr/ind@w:left)
        ind_left_dxa: Optional[int] = None
        try:
            ppr_el = para._element.find(qn("w:pPr"))
            if ppr_el is not None:
                ind_el = ppr_el.find(qn("w:ind"))
                if ind_el is not None:
                    raw = ind_el.get(qn("w:left"))
                    if raw is not None:
                        ind_left_dxa = int(float(raw))
        except Exception:
            pass

        return ParagraphInfo(
            index=idx,
            text=para.text or "",
            style_name=style_name,
            alignment=alignment_str,
            line_spacing=line_spacing,
            runs=runs,
            is_heading=is_heading,
            heading_level=heading_level,
            ind_left_dxa=ind_left_dxa,
            is_toc_entry=is_toc_entry,
            toc_evidence=toc_evidence,
        )

    def _safe_font_name(self, run) -> Optional[str]:
        """python-docx kadang return None walau XML punya font. Cek manual ke XML run."""
        try:
            if run.font.name:
                return run.font.name
        except Exception:
            pass
        # Fallback: cek XML rPr/rFonts
        try:
            rpr = run._element.find(qn("w:rPr"))
            if rpr is not None:
                rfonts = rpr.find(qn("w:rFonts"))
                if rfonts is not None:
                    # Coba beberapa atribut umum
                    for attr in ("ascii", "hAnsi", "cs", "eastAsia"):
                        val = rfonts.get(qn(f"w:{attr}"))
                        if val:
                            return val
        except Exception:
            pass
        return None

    def _safe_font_size(self, run) -> Optional[float]:
        """Return font size dalam point. python-docx return Pt object atau None."""
        try:
            size = run.font.size
            if size is not None:
                # size adalah objek Emu/Length; .pt mengembalikan float
                return float(size.pt)
        except Exception:
            pass
        # Fallback: parse XML
        try:
            rpr = run._element.find(qn("w:rPr"))
            if rpr is not None:
                sz = rpr.find(qn("w:sz"))
                if sz is not None:
                    val = sz.get(qn("w:val"))
                    if val:
                        return half_points_to_pt(val)
        except Exception:
            pass
        return None

    def _extract_tables(self) -> list[TableInfo]:
        result: list[TableInfo] = []
        for idx, tbl in enumerate(self.doc.tables):
            info = self._table_to_info(idx, tbl)
            result.append(info)
        return result

    def _table_to_info(self, idx: int, tbl: Table) -> TableInfo:
        rows = len(tbl.rows)
        cols = len(tbl.columns) if rows > 0 else 0

        cells: list[TableCellInfo] = []
        header_texts: list[str] = []

        for r_idx, row in enumerate(tbl.rows):
            for c_idx, cell in enumerate(row.cells):
                # Cell.text bisa duplicate jika ada merge — kita ambil apa adanya
                cell_text = cell.text or ""
                cell_paragraphs = [p.text for p in cell.paragraphs]
                cells.append(
                    TableCellInfo(
                        row=r_idx, col=c_idx, text=cell_text, paragraphs=cell_paragraphs
                    )
                )
                if r_idx == 0:
                    header_texts.append(cell_text)

        return TableInfo(
            index=idx, rows=rows, cols=cols, cells=cells, header_texts=header_texts
        )

    def _extract_sections(self) -> list[SectionInfo]:
        """
        Extract section info dengan membaca langsung dari XML <w:sectPr>.

        Pendekatan ini lebih reliable daripada lewat python-docx wrapper:
        wrapper kadang return objek Twips/Emu yang konversi int()-nya tidak
        konsisten antar versi python-docx — nilai bisa terbaca 0 di dokumen
        real meski XML-nya valid. XML attributes pgMar dan pgSz langsung
        memberi DXA sebagai string, jadi konversi tinggal int().
        """
        result: list[SectionInfo] = []
        for idx, sect_pr in enumerate(self._iter_sect_pr()):
            info = SectionInfo(index=idx)
            self._populate_section_from_xml(info, sect_pr)
            result.append(info)
        # Warisan header/footer: section yang tidak mendeklarasikan referensi
        # sendiri memakai milik section sebelumnya, per tipe (ECMA-376
        # §17.10.1). Tanpa ini, dokumen yang menaruh nomor halaman sekali di
        # section pertama terbaca seolah section berikutnya tak bernomor.
        inherited_header: dict[str, str] = {}
        inherited_footer: dict[str, str] = {}
        for info in result:
            inherited_header.update(info.header_refs)
            inherited_footer.update(info.footer_refs)
            info.header_refs = dict(inherited_header)
            info.footer_refs = dict(inherited_footer)
        return result

    def _iter_sect_pr(self) -> list[etree._Element]:
        """Semua <w:sectPr> di document.xml, urut dokumen.

        TIDAK memakai python-docx `doc.sections`: wrapper itu hanya
        mengenumerasi sectPr pada paragraf tingkat-body dan sectPr penutup body,
        sehingga section break yang bersarang di dalam content control
        (<w:sdt>) hilang. Dokumen dengan Daftar Isi otomatis kerap menaruh
        section break di situ — beserta header berisi nomor halamannya —
        dan section itu jadi tak terlihat.

        <w:sectPrChange> (rekaman revisi) memuat salinan sectPr LAMA; itu bukan
        section sungguhan dan harus dilewati.
        """
        doc_xml = self.document_xml
        if doc_xml is None:
            return []
        body = doc_xml.find(qn("w:body"))
        if body is None:
            return []
        out: list[etree._Element] = []
        for el in body.iter(qn("w:sectPr")):
            parent = el.getparent()
            if parent is not None and parent.tag == qn("w:sectPrChange"):
                continue
            out.append(el)
        return out

    def _populate_section_from_xml(
        self, info: SectionInfo, sect_pr: Optional[etree._Element]
    ) -> None:
        """Isi SectionInfo dari elemen <w:sectPr> via parsing XML langsung."""
        if sect_pr is None:
            return

        # Page size: <w:pgSz w:w="11906" w:h="16838"/>
        pg_sz = sect_pr.find(qn("w:pgSz"))
        if pg_sz is not None:
            info.page_width_dxa = self._safe_int(pg_sz.get(qn("w:w")))
            info.page_height_dxa = self._safe_int(pg_sz.get(qn("w:h")))

        # Margin: <w:pgMar w:top="..." w:right="..." w:bottom="..." w:left="..."/>
        pg_mar = sect_pr.find(qn("w:pgMar"))
        if pg_mar is not None:
            info.margin_top_dxa = self._safe_int(pg_mar.get(qn("w:top")))
            info.margin_right_dxa = self._safe_int(pg_mar.get(qn("w:right")))
            info.margin_bottom_dxa = self._safe_int(pg_mar.get(qn("w:bottom")))
            info.margin_left_dxa = self._safe_int(pg_mar.get(qn("w:left")))

        # Jumlah kolom teks: <w:cols w:num="2" .../>
        # - Elemen <w:cols> absen        → 1 kolom (default Word)
        # - Ada w:num                    → pakai nilainya
        # - w:num absen tapi ada <w:col> → hitung jumlah anak <w:col>
        # - selain itu                   → 1 kolom
        cols = sect_pr.find(qn("w:cols"))
        if cols is None:
            info.num_columns = 1
        else:
            num = self._safe_int(cols.get(qn("w:num")))
            if num is not None:
                info.num_columns = num
            else:
                col_children = cols.findall(qn("w:col"))
                info.num_columns = len(col_children) if col_children else 1

        # Page number type: <w:pgNumType w:fmt="lowerRoman" w:start="1"/>
        pg_num_type = sect_pr.find(qn("w:pgNumType"))
        if pg_num_type is not None:
            info.page_num_format = pg_num_type.get(qn("w:fmt"))
            start = pg_num_type.get(qn("w:start"))
            if start and start.lstrip("-").isdigit():
                info.page_num_start = int(start)

        # <w:titlePg/> — mengaktifkan header/footer ber-type "first"
        info.title_pg = sect_pr.find(qn("w:titlePg")) is not None

        # Header references: <w:headerReference w:type="default" r:id="rId4"/>
        for ref in sect_pr.findall(qn("w:headerReference")):
            ref_type = ref.get(qn("w:type")) or "default"
            ref_id = ref.get(qn("r:id"))
            if ref_id:
                info.header_refs[ref_type] = ref_id

        for ref in sect_pr.findall(qn("w:footerReference")):
            ref_type = ref.get(qn("w:type")) or "default"
            ref_id = ref.get(qn("r:id"))
            if ref_id:
                info.footer_refs[ref_type] = ref_id

    @staticmethod
    def _safe_int(val: Optional[str]) -> Optional[int]:
        """Konversi string XML attribute ke int, atau None jika tidak valid."""
        if val is None:
            return None
        try:
            return int(val)
        except (ValueError, TypeError):
            return None

    def _read_xml_part(
        self, part_name: str, required: bool = True
    ) -> Optional[etree._Element]:
        raw = self.read_raw_part(part_name)
        if raw is None:
            if required:
                self.warnings.append(f"Part wajib tidak ditemukan: {part_name}")
            return None
        try:
            return etree.fromstring(raw)
        except etree.XMLSyntaxError as e:
            self.warnings.append(f"Gagal parse XML {part_name}: {e}")
            return None

    def _read_header_footer_xmls(self, prefix: str) -> dict[str, etree._Element]:
        """Baca semua part yang namanya diawali prefix (mis. 'word/header')."""
        result: dict[str, etree._Element] = {}
        try:
            with zipfile.ZipFile(self.file_path, "r") as z:
                for name in z.namelist():
                    if name.startswith(prefix) and name.endswith(".xml"):
                        try:
                            raw = z.read(name)
                            result[name] = etree.fromstring(raw)
                        except (etree.XMLSyntaxError, KeyError) as e:
                            self.warnings.append(f"Gagal parse {name}: {e}")
        except zipfile.BadZipFile:
            self.warnings.append(f"Bad zip saat baca {prefix}*.xml")
        return result

    def _extract_images(self) -> list[ImageInfo]:
        """List file di word/media/."""
        result: list[ImageInfo] = []
        try:
            with zipfile.ZipFile(self.file_path, "r") as z:
                for name in z.namelist():
                    if name.startswith("word/media/"):
                        info = z.getinfo(name)
                        ext = Path(name).suffix.lower().lstrip(".")
                        # Mapping ekstensi → content type sederhana
                        ct_map = {
                            "png": "image/png",
                            "jpg": "image/jpeg",
                            "jpeg": "image/jpeg",
                            "gif": "image/gif",
                            "bmp": "image/bmp",
                            "tiff": "image/tiff",
                            "tif": "image/tiff",
                            "svg": "image/svg+xml",
                            "emf": "image/x-emf",
                            "wmf": "image/x-wmf",
                        }
                        content_type = ct_map.get(ext, f"application/{ext}")
                        result.append(
                            ImageInfo(
                                filename=Path(name).name,
                                content_type=content_type,
                                size_bytes=info.file_size,
                            )
                        )
        except zipfile.BadZipFile:
            self.warnings.append("Bad zip saat extract images")
        return result

    # ------------------------------------------------------------------------
    # Debug / introspection
    # ------------------------------------------------------------------------

    def summary(self) -> dict:
        """Ringkasan cepat untuk debugging / smoke test."""
        return {
            "file": str(self.file_path),
            "paragraph_count": len(self.paragraphs),
            "table_count": len(self.tables),
            "section_count": len(self.sections),
            "header_part_count": len(self.header_xmls),
            "footer_part_count": len(self.footer_xmls),
            "image_count": len(self.images),
            "warnings": list(self.warnings),
        }
