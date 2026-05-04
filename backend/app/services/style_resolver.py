"""
StyleResolver — resolve font properties melalui style hierarchy OOXML.

Masalah: di .docx, font biasanya di-set di level STYLE (mis. style "Normal"),
bukan di tiap run. python-docx hanya return font di level run kalau di-set
explicit. Akibatnya, run yang inherit dari style "Normal" akan return None
untuk run.font.name padahal sebenarnya pakai font tertentu.

Solusi: resolver ini parse word/styles.xml dan resolve font per paragraf
dengan urutan prioritas:
    1. Run-level override (rPr di run)
    2. Paragraph-level rPr (di paragraf langsung)
    3. Paragraph style (mis. "Normal", "Heading 1")
    4. Style yang di-extend (basedOn chain)
    5. docDefaults (default global)

Dipakai oleh FormatChecker untuk validasi konsistensi font TNR 12pt.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from lxml import etree

from app.services.docx_parser import DocxParser, half_points_to_pt

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


def _q(tag: str) -> str:
    """Helper: namespaced tag."""
    return f"{{{W_NS}}}{tag}"


@dataclass
class ResolvedFont:
    """Font yang sudah di-resolve dari style hierarchy."""
    name: Optional[str] = None
    size_pt: Optional[float] = None
    bold: Optional[bool] = None
    italic: Optional[bool] = None
    # Source tracking untuk debugging
    name_source: str = "unknown"   # 'run' | 'paragraph' | 'style:X' | 'default'
    size_source: str = "unknown"


class StyleResolver:
    """
    Resolver font properties yang tahu hierarchy OOXML.

    Usage:
        resolver = StyleResolver(parser)
        # Resolve font untuk satu paragraf (apply ke seluruh paragraf):
        font = resolver.resolve_paragraph_font(paragraph_index=10)
        # Resolve font untuk satu run di dalam paragraf:
        font = resolver.resolve_run_font(paragraph_index=10, run_index=2)
    """

    def __init__(self, parser: DocxParser):
        self.parser = parser
        self._styles_index: Optional[dict[str, etree._Element]] = None
        self._default_font: Optional[ResolvedFont] = None

    # ------------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------------

    def resolve_paragraph_font(self, paragraph_index: int) -> ResolvedFont:
        """
        Resolve font default untuk paragraf (tanpa run-level override).
        Hierarchy: paragraph style → basedOn chain → docDefaults.
        """
        para_xml = self._get_paragraph_xml(paragraph_index)
        if para_xml is None:
            return self._get_default_font()

        result = ResolvedFont()

        # Step 1: cek paragraph-level rPr di pPr (jarang, tapi ada)
        ppr = para_xml.find(_q("pPr"))
        if ppr is not None:
            ppr_rpr = ppr.find(_q("rPr"))
            if ppr_rpr is not None:
                self._fill_from_rpr(result, ppr_rpr, source="paragraph")

        # Step 2: paragraph style → basedOn chain
        # Default ke "Normal" kalau pStyle tidak eksplisit (konvensi OOXML)
        style_id = self._get_paragraph_style_id(para_xml) or "Normal"
        self._fill_from_style_chain(result, style_id)

        # Step 3: docDefaults sebagai fallback
        self._fill_from_defaults(result)

        return result

    def resolve_run_font(
        self, paragraph_index: int, run_index: int
    ) -> ResolvedFont:
        """
        Resolve font untuk satu run dengan override hierarchy lengkap.
        Hierarchy: run rPr → paragraph rPr → paragraph style → basedOn → defaults.
        """
        para_xml = self._get_paragraph_xml(paragraph_index)
        if para_xml is None:
            return self._get_default_font()

        result = ResolvedFont()

        # Step 1: run-level override (paling spesifik)
        runs = para_xml.findall(_q("r"))
        if 0 <= run_index < len(runs):
            run_xml = runs[run_index]
            run_rpr = run_xml.find(_q("rPr"))
            if run_rpr is not None:
                self._fill_from_rpr(result, run_rpr, source="run")

        # Step 2: paragraph-level rPr
        ppr = para_xml.find(_q("pPr"))
        if ppr is not None:
            ppr_rpr = ppr.find(_q("rPr"))
            if ppr_rpr is not None:
                self._fill_from_rpr(result, ppr_rpr, source="paragraph")

        # Step 3: paragraph style chain (default Normal kalau pStyle kosong)
        style_id = self._get_paragraph_style_id(para_xml) or "Normal"
        self._fill_from_style_chain(result, style_id)

        # Step 4: docDefaults
        self._fill_from_defaults(result)

        return result

    # ------------------------------------------------------------------------
    # Internal: index styles
    # ------------------------------------------------------------------------

    def _get_styles_index(self) -> dict[str, etree._Element]:
        """Index style: styleId → <w:style> element."""
        if self._styles_index is not None:
            return self._styles_index
        self._styles_index = {}
        styles_xml = self.parser.styles_xml
        if styles_xml is None:
            return self._styles_index
        for style in styles_xml.findall(_q("style")):
            sid = style.get(_q("styleId"))
            if sid:
                self._styles_index[sid] = style
        return self._styles_index

    def _get_default_font(self) -> ResolvedFont:
        """Resolve docDefaults dari styles.xml."""
        if self._default_font is not None:
            return self._default_font
        result = ResolvedFont(name_source="default", size_source="default")
        styles_xml = self.parser.styles_xml
        if styles_xml is not None:
            doc_defaults = styles_xml.find(_q("docDefaults"))
            if doc_defaults is not None:
                rpr_default = doc_defaults.find(_q("rPrDefault"))
                if rpr_default is not None:
                    rpr = rpr_default.find(_q("rPr"))
                    if rpr is not None:
                        self._fill_from_rpr(result, rpr, source="default")
        self._default_font = result
        return result

    # ------------------------------------------------------------------------
    # Internal: extract dari rPr
    # ------------------------------------------------------------------------

    @staticmethod
    def _fill_from_rpr(
        result: ResolvedFont, rpr: etree._Element, source: str
    ) -> None:
        """
        Isi result dari elemen <w:rPr>. Hanya overwrite kalau field belum ter-set.
        Ini cara implement "more specific wins" — caller harus panggil dari
        yang paling spesifik ke yang paling umum.
        """
        # Font name
        if result.name is None:
            rfonts = rpr.find(_q("rFonts"))
            if rfonts is not None:
                # Coba ascii dulu (paling umum), lalu hAnsi, eastAsia, cs
                for attr in ("ascii", "hAnsi", "eastAsia", "cs"):
                    val = rfonts.get(_q(attr))
                    if val:
                        result.name = val
                        result.name_source = source
                        break

        # Font size
        if result.size_pt is None:
            sz = rpr.find(_q("sz"))
            if sz is not None:
                val = sz.get(_q("val"))
                if val:
                    result.size_pt = half_points_to_pt(val)
                    result.size_source = source

        # Bold
        if result.bold is None:
            b = rpr.find(_q("b"))
            if b is not None:
                # <w:b/> = bold true; <w:b w:val="0"/> = false
                val = b.get(_q("val"))
                result.bold = (val != "0" and val != "false")

        # Italic
        if result.italic is None:
            i = rpr.find(_q("i"))
            if i is not None:
                val = i.get(_q("val"))
                result.italic = (val != "0" and val != "false")

    # ------------------------------------------------------------------------
    # Internal: paragraph helpers
    # ------------------------------------------------------------------------

    def _get_paragraph_xml(self, paragraph_index: int) -> Optional[etree._Element]:
        """Ambil <w:p> XML dari document.xml berdasarkan urutan."""
        doc_xml = self.parser.document_xml
        if doc_xml is None:
            return None
        # body > p (skip yang di dalam tbl)
        body = doc_xml.find(_q("body"))
        if body is None:
            return None
        all_paras = body.findall(_q("p"))
        if 0 <= paragraph_index < len(all_paras):
            return all_paras[paragraph_index]
        return None

    @staticmethod
    def _get_paragraph_style_id(para_xml: etree._Element) -> Optional[str]:
        ppr = para_xml.find(_q("pPr"))
        if ppr is None:
            return None
        p_style = ppr.find(_q("pStyle"))
        if p_style is None:
            return None
        return p_style.get(_q("val"))

    def _fill_from_style_chain(self, result: ResolvedFont, style_id: str) -> None:
        """Walk basedOn chain dari style_id sampai root."""
        styles_index = self._get_styles_index()
        visited: set[str] = set()
        current = style_id
        while current and current not in visited:
            visited.add(current)
            style = styles_index.get(current)
            if style is None:
                break
            rpr = style.find(_q("rPr"))
            if rpr is not None:
                self._fill_from_rpr(result, rpr, source=f"style:{current}")
            # Lanjut ke basedOn
            based_on = style.find(_q("basedOn"))
            if based_on is None:
                break
            current = based_on.get(_q("val"))

    def _fill_from_defaults(self, result: ResolvedFont) -> None:
        """Final fallback: docDefaults."""
        if result.name is not None and result.size_pt is not None:
            return  # tidak perlu fallback
        defaults = self._get_default_font()
        if result.name is None:
            result.name = defaults.name
            result.name_source = defaults.name_source
        if result.size_pt is None:
            result.size_pt = defaults.size_pt
            result.size_source = defaults.size_source