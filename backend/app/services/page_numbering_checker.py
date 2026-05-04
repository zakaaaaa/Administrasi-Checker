"""
PageNumberingChecker — modul pengecek penomoran halaman per zona.

Sumber blueprint: v0.3 §4.3 (page_numbering_zones), §3.3 (page_numbering_rules).

Aturan PKM:
| Zona            | Numeral      | Posisi           | Font              |
|-----------------|--------------|------------------|-------------------|
| Awal (DAFTAR *) | romawi kecil | pojok kanan BAWAH | Times New Roman 12 |
| Inti (BAB 1+)   | angka arab   | pojok kanan ATAS  | Times New Roman 12 |

Pendekatan teknis:
1. Parse header*.xml dan footer*.xml dari paket .docx
2. Untuk setiap header/footer, ekstrak:
   - apakah memuat field PAGE (= memang nomor halaman)
   - alignment paragraf (left/center/right)
   - resolved font name + size dari run/style chain
3. Map section ke header/footer yang dipakainya (via header_refs/footer_refs
   yang sudah di-extract DocxParser)
4. Identifikasi section mana yang termasuk zona awal vs zona inti dengan
   strategi: section yang memuat heading "DAFTAR ISI"/"DAFTAR LAMPIRAN"
   adalah zona awal; section yang memuat "BAB 1" adalah awal zona inti.
5. Validasi tiap section:
   - format numeral di section.page_num_format vs aturan zona
   - posisi (header=top / footer=bottom) vs aturan zona
   - alignment right vs aturan zona
   - font TNR 12pt

Catatan: Kalau section tidak punya header/footer reference dan tidak inherit
dari section sebelumnya, dianggap "tanpa nomor halaman" → flag fail untuk
section di zona inti.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from lxml import etree

from app.services.docx_parser import (
    DocxParser,
    SectionInfo,
    half_points_to_pt,
)
from app.services.schema_rules import SchemaRules
from app.services.style_resolver import StyleResolver


W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PKG_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"


def _q(tag: str) -> str:
    return f"{{{W_NS}}}{tag}"


# ============================================================================
# Aturan zona
# ============================================================================


@dataclass
class ZoneRule:
    """Aturan satu zona penomoran."""
    name: str                       # 'front_matter' | 'core_matter'
    numeral_type: str               # 'roman_lower' | 'arabic'
    position: str                   # 'top' | 'bottom'
    alignment: str = "right"
    font_name: str = "Times New Roman"
    font_size_pt: float = 12.0


@dataclass
class PageNumberingRules:
    front_matter: ZoneRule
    core_matter: ZoneRule


def get_pkm_page_numbering_rules() -> PageNumberingRules:
    """Default PKM: zona awal romawi-bawah, zona inti arab-atas, both TNR 12pt."""
    return PageNumberingRules(
        front_matter=ZoneRule(
            name="front_matter",
            numeral_type="roman_lower",
            position="bottom",
        ),
        core_matter=ZoneRule(
            name="core_matter",
            numeral_type="arabic",
            position="top",
        ),
    )


# ============================================================================
# Data: hasil parsing satu header/footer XML
# ============================================================================


@dataclass
class HeaderFooterAnalysis:
    """Hasil parsing satu file header/footer XML."""
    part_name: str                  # 'word/header1.xml'
    kind: str                       # 'header' | 'footer'
    has_page_field: bool = False    # ada <w:instrText>PAGE</w:instrText> atau <w:fldSimple instr="PAGE">
    alignment: Optional[str] = None # 'left' | 'center' | 'right' atau None (default = left)
    font_name: Optional[str] = None
    font_size_pt: Optional[float] = None


@dataclass
class SectionPageNumberingAnalysis:
    """Hasil analisis penomoran untuk satu section."""
    section_index: int
    zone: Optional[str] = None       # 'front_matter' | 'core_matter' | 'unknown'
    has_header_with_page: bool = False
    has_footer_with_page: bool = False
    actual_position: Optional[str] = None      # 'top' | 'bottom' atau None
    actual_numeral_type: Optional[str] = None  # 'arabic' | 'roman_lower' | dst.
    actual_alignment: Optional[str] = None
    actual_font_name: Optional[str] = None
    actual_font_size_pt: Optional[float] = None
    header_part: Optional[str] = None
    footer_part: Optional[str] = None


# ============================================================================
# Hasil checker
# ============================================================================


@dataclass
class CheckMessage:
    level: str
    text: str


@dataclass
class ZoneFinding:
    zone: str                   # 'front_matter' | 'core_matter'
    severity: str               # 'fail' | 'warning' | 'pass'
    aspect: str                 # 'numeral' | 'position' | 'alignment' | 'font' | 'missing'
    expected: Optional[str]
    found: Optional[str]
    section_index: Optional[int]
    message: str


@dataclass
class PageNumberingResult:
    status: str                 # 'pass' | 'warning' | 'fail'
    front_matter_status: str = "unknown"
    core_matter_status: str = "unknown"
    sections_analysis: list[SectionPageNumberingAnalysis] = field(default_factory=list)
    findings: list[ZoneFinding] = field(default_factory=list)
    messages: list[CheckMessage] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "front_matter": {"status": self.front_matter_status},
            "core_matter": {"status": self.core_matter_status},
            "sections_analysis": [
                {
                    "section_index": s.section_index,
                    "zone": s.zone,
                    "has_header_with_page": s.has_header_with_page,
                    "has_footer_with_page": s.has_footer_with_page,
                    "actual_position": s.actual_position,
                    "actual_numeral_type": s.actual_numeral_type,
                    "actual_alignment": s.actual_alignment,
                    "actual_font_name": s.actual_font_name,
                    "actual_font_size_pt": s.actual_font_size_pt,
                    "header_part": s.header_part,
                    "footer_part": s.footer_part,
                }
                for s in self.sections_analysis
            ],
            "findings": [
                {
                    "zone": f.zone,
                    "severity": f.severity,
                    "aspect": f.aspect,
                    "expected": f.expected,
                    "found": f.found,
                    "section_index": f.section_index,
                    "message": f.message,
                }
                for f in self.findings
            ],
            "messages": [{"level": m.level, "text": m.text} for m in self.messages],
        }


# ============================================================================
# PageNumberingChecker
# ============================================================================


class PageNumberingChecker:
    """
    Checker penomoran halaman per zona.

    Usage:
        parser = DocxParser('proposal.docx')
        schema = get_pkm_kc_proposal_rules()
        result = PageNumberingChecker(parser, schema).check()
    """

    # Map page_num_format OOXML → label internal
    NUMERAL_FORMAT_MAP = {
        "decimal": "arabic",
        "lowerRoman": "roman_lower",
        "upperRoman": "roman_upper",
        "lowerLetter": "alpha_lower",
        "upperLetter": "alpha_upper",
        None: "arabic",  # default Word kalau tidak di-set adalah decimal/arabic
    }

    def __init__(
        self,
        parser: DocxParser,
        schema: SchemaRules,
        rules: Optional[PageNumberingRules] = None,
    ):
        self.parser = parser
        self.schema = schema
        self.rules = rules or get_pkm_page_numbering_rules()
        self.resolver = StyleResolver(parser)
        # Cache: rId → part_name (mis. 'rId6' → 'word/header1.xml')
        self._rid_to_part: Optional[dict[str, str]] = None
        # Cache: part_name → HeaderFooterAnalysis
        self._hf_cache: dict[str, HeaderFooterAnalysis] = {}

    def check(self) -> PageNumberingResult:
        result = PageNumberingResult(status="pass")

        # 1. Identifikasi zona tiap section
        zone_map = self._identify_section_zones()

        # 2. Analisis tiap section
        for sec in self.parser.sections:
            analysis = self._analyze_section(sec, zone=zone_map.get(sec.index))
            result.sections_analysis.append(analysis)

        # 3. Validasi per zona
        front_findings = self._validate_zone(
            result.sections_analysis,
            zone_name="front_matter",
            zone_rule=self.rules.front_matter,
        )
        core_findings = self._validate_zone(
            result.sections_analysis,
            zone_name="core_matter",
            zone_rule=self.rules.core_matter,
        )
        result.findings.extend(front_findings)
        result.findings.extend(core_findings)

        # 4. Tentukan status per zona
        result.front_matter_status = self._zone_status(front_findings)
        result.core_matter_status = self._zone_status(core_findings)

        # 5. Status overall
        all_severities = [f.severity for f in result.findings]
        if "fail" in all_severities:
            result.status = "fail"
        elif "warning" in all_severities:
            result.status = "warning"
        else:
            result.status = "pass"

        # 6. Build messages
        self._build_messages(result)

        return result

    # ------------------------------------------------------------------------
    # Step 1: Identifikasi zona tiap section
    # ------------------------------------------------------------------------

    def _identify_section_zones(self) -> dict[int, str]:
        """
        Map section index → 'front_matter' | 'core_matter' | 'unknown'.

        Strategi (versi rev):
        Untuk tiap section dengan range [start_para, end_para]:
        - Kalau end_para < daftar_isi_para → unknown (cover/pengesahan)
        - Kalau end_para < bab1_para → front_matter (memuat DAFTAR *, tidak
          mencapai BAB 1)
        - Kalau start_para <= bab1_para <= end_para → core_matter
          (section ini memuat BAB 1 = bagian inti dimulai di sini)
        - Kalau start_para > bab1_para → core_matter (sudah pasti di bagian inti)

        Kalau DAFTAR ISI atau BAB 1 tidak ditemukan, return semua 'unknown'.
        """
        boundaries = self.parser.find_section_boundaries(
            ["DAFTAR ISI", "BAB 1"], headings_only=True
        )
        daftar_isi_para = boundaries["DAFTAR ISI"]
        bab1_para = boundaries["BAB 1"]

        section_para_ranges = self._compute_section_paragraph_ranges()

        zone_map: dict[int, str] = {}
        for sec_idx, (start_para, end_para) in section_para_ranges.items():
            if bab1_para is None:
                # Tanpa BAB 1, kita tidak bisa identify zona dengan andal.
                # Kalau ada DAFTAR ISI tapi tidak ada BAB 1, asumsikan
                # semua dari DAFTAR ISI ke akhir = front_matter (best effort).
                if daftar_isi_para is not None and end_para >= daftar_isi_para:
                    zone_map[sec_idx] = "front_matter"
                else:
                    zone_map[sec_idx] = "unknown"
                continue

            # Ada BAB 1 — pakai logic utama
            if start_para >= bab1_para:
                # Section dimulai DI ATAS atau SETELAH BAB 1 → bagian inti
                zone_map[sec_idx] = "core_matter"
            elif end_para >= bab1_para:
                # Section MEMUAT BAB 1 → ini awal bagian inti
                zone_map[sec_idx] = "core_matter"
            elif daftar_isi_para is not None and end_para >= daftar_isi_para:
                # Section memuat DAFTAR * tapi tidak BAB 1 → zona awal
                zone_map[sec_idx] = "front_matter"
            elif daftar_isi_para is not None and end_para < daftar_isi_para:
                # Section sebelum DAFTAR ISI = cover / pengesahan
                zone_map[sec_idx] = "unknown"
            else:
                # DAFTAR ISI tidak ada tapi BAB 1 ada — section sebelum BAB 1
                # bisa berisi cover atau front matter. Tidak bisa di-disambig.
                zone_map[sec_idx] = "unknown"

        return zone_map

    def _compute_section_paragraph_ranges(self) -> dict[int, tuple[int, int]]:
        """
        Hitung paragraph range (start_inclusive, end_inclusive) untuk tiap section.

        Strategi: walk body element children secara berurutan. Section pindah
        ke section berikutnya saat ketemu <w:p> dengan <w:pPr><w:sectPr>
        (section break) — paragraf itu adalah TERAKHIR dari section saat ini.
        Section terakhir punya <w:sectPr> langsung di body.

        Return: {section_index: (first_para_idx, last_para_idx)}.
        """
        doc_xml = self.parser.document_xml
        body = doc_xml.find(_q("body"))
        if body is None:
            return {}

        ranges: dict[int, tuple[int, int]] = {}
        para_idx = -1
        section_idx = 0
        section_first_para = 0

        for child in body:
            tag = child.tag
            if tag == _q("p"):
                para_idx += 1
                # Apakah paragraf ini punya sectPr (= akhir section)
                ppr = child.find(_q("pPr"))
                if ppr is not None and ppr.find(_q("sectPr")) is not None:
                    ranges[section_idx] = (section_first_para, para_idx)
                    section_idx += 1
                    section_first_para = para_idx + 1
            elif tag == _q("tbl"):
                # Tabel tidak counted sebagai paragraf di parser.paragraphs
                # (python-docx hanya count <w:p> di body, skip yang di tabel)
                pass
            elif tag == _q("sectPr"):
                # Section break terakhir di akhir body
                ranges[section_idx] = (section_first_para, para_idx)
                section_idx += 1
                section_first_para = para_idx + 1

        # Kalau section_idx belum ditutup (jarang, tapi safe)
        if section_idx not in ranges and section_first_para <= para_idx:
            ranges[section_idx] = (section_first_para, para_idx)

        return ranges

    # ------------------------------------------------------------------------
    # Step 2: Analisis tiap section
    # ------------------------------------------------------------------------

    def _analyze_section(
        self, sec: SectionInfo, zone: Optional[str]
    ) -> SectionPageNumberingAnalysis:
        analysis = SectionPageNumberingAnalysis(
            section_index=sec.index,
            zone=zone,
        )

        # Numeral format dari sectPr
        analysis.actual_numeral_type = self.NUMERAL_FORMAT_MAP.get(
            sec.page_num_format, sec.page_num_format
        )

        # Map header/footer rId → part name
        rid_map = self._get_rid_to_part_map()

        # Header references (default + first + even)
        for ref_type, rid in sec.header_refs.items():
            part = rid_map.get(rid)
            if part is None:
                continue
            hf = self._analyze_header_footer(part, kind="header")
            if hf.has_page_field:
                analysis.has_header_with_page = True
                analysis.header_part = part
                analysis.actual_position = "top"
                analysis.actual_alignment = hf.alignment
                analysis.actual_font_name = hf.font_name
                analysis.actual_font_size_pt = hf.font_size_pt

        # Footer references
        for ref_type, rid in sec.footer_refs.items():
            part = rid_map.get(rid)
            if part is None:
                continue
            hf = self._analyze_header_footer(part, kind="footer")
            if hf.has_page_field:
                analysis.has_footer_with_page = True
                analysis.footer_part = part
                # Footer override header? Tidak — biasanya hanya satu yang dipakai
                # untuk page number. Kalau dua-duanya ada, kita ambil yang ada.
                if not analysis.has_header_with_page:
                    analysis.actual_position = "bottom"
                    analysis.actual_alignment = hf.alignment
                    analysis.actual_font_name = hf.font_name
                    analysis.actual_font_size_pt = hf.font_size_pt

        return analysis

    # ------------------------------------------------------------------------
    # Helpers: parse rels & header/footer XML
    # ------------------------------------------------------------------------

    def _get_rid_to_part_map(self) -> dict[str, str]:
        """Parse word/_rels/document.xml.rels untuk map rId → Target."""
        if self._rid_to_part is not None:
            return self._rid_to_part
        self._rid_to_part = {}
        rels_raw = self.parser.read_raw_part("word/_rels/document.xml.rels")
        if rels_raw is None:
            return self._rid_to_part
        try:
            rels_root = etree.fromstring(rels_raw)
        except etree.XMLSyntaxError:
            return self._rid_to_part
        # Namespace: package relationships
        for rel in rels_root.findall(f"{{{PKG_REL_NS}}}Relationship"):
            rid = rel.get("Id")
            target = rel.get("Target")
            if rid and target:
                # Target relatif ke folder word/ → prefix
                full = "word/" + target if not target.startswith("/") else target.lstrip("/")
                self._rid_to_part[rid] = full
        return self._rid_to_part

    def _analyze_header_footer(
        self, part_name: str, kind: str
    ) -> HeaderFooterAnalysis:
        """Parse satu header*.xml atau footer*.xml."""
        if part_name in self._hf_cache:
            return self._hf_cache[part_name]

        analysis = HeaderFooterAnalysis(part_name=part_name, kind=kind)
        # Ambil dari parser cache header/footer XMLs
        xml_root = (
            self.parser.header_xmls.get(part_name)
            if kind == "header"
            else self.parser.footer_xmls.get(part_name)
        )
        if xml_root is None:
            self._hf_cache[part_name] = analysis
            return analysis

        # Detect PAGE field. Dua varian:
        # 1. <w:instrText>PAGE</w:instrText>
        # 2. <w:fldSimple w:instr="PAGE"/>
        has_page = False
        for instr in xml_root.iter(_q("instrText")):
            if instr.text and "PAGE" in instr.text.upper():
                has_page = True
                break
        if not has_page:
            for fld in xml_root.iter(_q("fldSimple")):
                instr = fld.get(_q("instr")) or ""
                if "PAGE" in instr.upper():
                    has_page = True
                    break
        analysis.has_page_field = has_page

        if not has_page:
            self._hf_cache[part_name] = analysis
            return analysis

        # Cari paragraf yang memuat PAGE field, ambil alignment & font
        # Heuristik: ambil alignment paragraf pertama, atau paragraf yang punya
        # PAGE field paling spesifik.
        target_para = None
        for p in xml_root.iter(_q("p")):
            # Apakah paragraf ini punya PAGE?
            has_page_in_para = False
            for instr in p.iter(_q("instrText")):
                if instr.text and "PAGE" in instr.text.upper():
                    has_page_in_para = True
                    break
            if not has_page_in_para:
                for fld in p.iter(_q("fldSimple")):
                    if "PAGE" in (fld.get(_q("instr")) or "").upper():
                        has_page_in_para = True
                        break
            if has_page_in_para:
                target_para = p
                break

        if target_para is None:
            self._hf_cache[part_name] = analysis
            return analysis

        # Alignment: <w:pPr><w:jc w:val="..."/>
        ppr = target_para.find(_q("pPr"))
        if ppr is not None:
            jc = ppr.find(_q("jc"))
            if jc is not None:
                analysis.alignment = jc.get(_q("val"))
        if analysis.alignment is None:
            # Default Word kalau tidak di-set adalah 'left'
            analysis.alignment = "left"

        # Font dari run yang memuat PAGE
        # Strategi: cari rPr di run pertama paragraf, dan kalau kosong, resolve via style
        # Untuk header/footer, style biasanya inherit dari "BodyText" → resolver akan
        # walk basedOn chain.
        font_name, font_size = self._extract_font_from_header_para(target_para, ppr)
        analysis.font_name = font_name
        analysis.font_size_pt = font_size

        self._hf_cache[part_name] = analysis
        return analysis

    def _extract_font_from_header_para(
        self,
        para: etree._Element,
        ppr: Optional[etree._Element],
    ) -> tuple[Optional[str], Optional[float]]:
        """
        Extract font name & size dari paragraf header/footer.
        Hierarchy: run rPr → paragraph rPr (di pPr) → paragraph style → docDefaults.
        """
        font_name: Optional[str] = None
        font_size: Optional[float] = None

        # Step 1: cek run rPr (run pertama yang punya rPr)
        for r in para.iter(_q("r")):
            rpr = r.find(_q("rPr"))
            if rpr is None:
                continue
            if font_name is None:
                rfonts = rpr.find(_q("rFonts"))
                if rfonts is not None:
                    for attr in ("ascii", "hAnsi", "eastAsia", "cs"):
                        v = rfonts.get(_q(attr))
                        if v:
                            font_name = v
                            break
            if font_size is None:
                sz = rpr.find(_q("sz"))
                if sz is not None:
                    font_size = half_points_to_pt(sz.get(_q("val")))
            if font_name is not None and font_size is not None:
                break

        # Step 2: paragraph rPr di pPr
        if ppr is not None:
            ppr_rpr = ppr.find(_q("rPr"))
            if ppr_rpr is not None:
                if font_name is None:
                    rfonts = ppr_rpr.find(_q("rFonts"))
                    if rfonts is not None:
                        for attr in ("ascii", "hAnsi", "eastAsia", "cs"):
                            v = rfonts.get(_q(attr))
                            if v:
                                font_name = v
                                break
                if font_size is None:
                    sz = ppr_rpr.find(_q("sz"))
                    if sz is not None:
                        font_size = half_points_to_pt(sz.get(_q("val")))

        # Step 3: paragraph style → walk basedOn chain
        if font_name is None or font_size is None:
            style_id = None
            if ppr is not None:
                p_style = ppr.find(_q("pStyle"))
                if p_style is not None:
                    style_id = p_style.get(_q("val"))
            style_id = style_id or "Normal"

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
                    if font_name is None:
                        rfonts = rpr.find(_q("rFonts"))
                        if rfonts is not None:
                            for attr in ("ascii", "hAnsi", "eastAsia", "cs"):
                                v = rfonts.get(_q(attr))
                                if v:
                                    font_name = v
                                    break
                    if font_size is None:
                        sz = rpr.find(_q("sz"))
                        if sz is not None:
                            font_size = half_points_to_pt(sz.get(_q("val")))
                if font_name is not None and font_size is not None:
                    break
                # basedOn
                based_on = style.find(_q("basedOn"))
                current = based_on.get(_q("val")) if based_on is not None else None

        return font_name, font_size

    def _get_styles_index(self) -> dict:
        """Reuse logic dari StyleResolver: index styleId → element."""
        # Kita tidak pakai resolver._styles_index langsung supaya tidak coupling
        # internal. Tapi resolver punya _get_styles_index() public-ish via
        # akses parser.styles_xml — kita copy logic-nya simpel di sini.
        result: dict = {}
        styles_xml = self.parser.styles_xml
        if styles_xml is None:
            return result
        for st in styles_xml.findall(_q("style")):
            sid = st.get(_q("styleId"))
            if sid:
                result[sid] = st
        return result

    # ------------------------------------------------------------------------
    # Step 3: Validasi per zona
    # ------------------------------------------------------------------------

    def _validate_zone(
        self,
        analyses: list[SectionPageNumberingAnalysis],
        zone_name: str,
        zone_rule: ZoneRule,
    ) -> list[ZoneFinding]:
        """
        Validasi semua section yang termasuk zona tertentu.
        Return list ZoneFinding (kosong = pass untuk zona ini).
        """
        zone_secs = [a for a in analyses if a.zone == zone_name]
        if not zone_secs:
            # Tidak ada section di zona ini — bukan otomatis fail.
            # Untuk zona awal: kalau dokumen tidak punya DAFTAR ISI sama
            # sekali, StructureChecker akan flag itu — tidak duplikasi di sini.
            return []

        findings: list[ZoneFinding] = []

        # Cari section "leader" zona ini — section yang memang punya nomor halaman.
        # Kita validasi DARI section yang punya nomor (kalau tidak ada, flag missing).
        with_page = [
            a for a in zone_secs
            if a.has_header_with_page or a.has_footer_with_page
        ]
        if not with_page:
            findings.append(
                ZoneFinding(
                    zone=zone_name,
                    severity="fail",
                    aspect="missing",
                    expected=(
                        f"{zone_rule.numeral_type} di {zone_rule.position}-"
                        f"{zone_rule.alignment}, {zone_rule.font_name} "
                        f"{zone_rule.font_size_pt}pt"
                    ),
                    found="tidak ada nomor halaman di zona ini",
                    section_index=zone_secs[0].section_index,
                    message=(
                        f"Zona {zone_name}: tidak terdeteksi nomor halaman di section "
                        f"manapun. Zona ini wajib pakai {zone_rule.numeral_type} "
                        f"di {zone_rule.position}-{zone_rule.alignment}."
                    ),
                )
            )
            return findings

        # Validasi section pertama yang punya page number (dianggap representatif)
        for analysis in with_page:
            findings.extend(
                self._validate_section_against_zone(analysis, zone_rule)
            )

        return findings

    def _validate_section_against_zone(
        self,
        analysis: SectionPageNumberingAnalysis,
        rule: ZoneRule,
    ) -> list[ZoneFinding]:
        findings: list[ZoneFinding] = []
        si = analysis.section_index

        # 1. Numeral type
        if (
            analysis.actual_numeral_type is not None
            and analysis.actual_numeral_type != rule.numeral_type
        ):
            findings.append(
                ZoneFinding(
                    zone=rule.name,
                    severity="fail",
                    aspect="numeral",
                    expected=rule.numeral_type,
                    found=analysis.actual_numeral_type,
                    section_index=si,
                    message=(
                        f"Section #{si} ({rule.name}): jenis numeral "
                        f"'{analysis.actual_numeral_type}', seharusnya "
                        f"'{rule.numeral_type}'."
                    ),
                )
            )

        # 2. Position (top/bottom)
        if (
            analysis.actual_position is not None
            and analysis.actual_position != rule.position
        ):
            findings.append(
                ZoneFinding(
                    zone=rule.name,
                    severity="fail",
                    aspect="position",
                    expected=rule.position,
                    found=analysis.actual_position,
                    section_index=si,
                    message=(
                        f"Section #{si} ({rule.name}): posisi nomor halaman di "
                        f"'{analysis.actual_position}', seharusnya '{rule.position}'."
                    ),
                )
            )

        # 3. Alignment
        if (
            analysis.actual_alignment is not None
            and analysis.actual_alignment != rule.alignment
        ):
            findings.append(
                ZoneFinding(
                    zone=rule.name,
                    severity="fail",
                    aspect="alignment",
                    expected=rule.alignment,
                    found=analysis.actual_alignment,
                    section_index=si,
                    message=(
                        f"Section #{si} ({rule.name}): alignment nomor halaman "
                        f"'{analysis.actual_alignment}', seharusnya '{rule.alignment}'."
                    ),
                )
            )

        # 4. Font name
        if (
            analysis.actual_font_name is not None
            and analysis.actual_font_name != rule.font_name
        ):
            findings.append(
                ZoneFinding(
                    zone=rule.name,
                    severity="fail",
                    aspect="font",
                    expected=rule.font_name,
                    found=analysis.actual_font_name,
                    section_index=si,
                    message=(
                        f"Section #{si} ({rule.name}): font nomor halaman "
                        f"'{analysis.actual_font_name}', seharusnya '{rule.font_name}'."
                    ),
                )
            )

        # 5. Font size
        if (
            analysis.actual_font_size_pt is not None
            and analysis.actual_font_size_pt != rule.font_size_pt
        ):
            findings.append(
                ZoneFinding(
                    zone=rule.name,
                    severity="fail",
                    aspect="font",
                    expected=f"{rule.font_size_pt}pt",
                    found=f"{analysis.actual_font_size_pt}pt",
                    section_index=si,
                    message=(
                        f"Section #{si} ({rule.name}): ukuran font nomor halaman "
                        f"{analysis.actual_font_size_pt}pt, seharusnya {rule.font_size_pt}pt."
                    ),
                )
            )

        return findings

    @staticmethod
    def _zone_status(findings: list[ZoneFinding]) -> str:
        if not findings:
            return "pass"
        if any(f.severity == "fail" for f in findings):
            return "fail"
        if any(f.severity == "warning" for f in findings):
            return "warning"
        return "pass"

    # ------------------------------------------------------------------------
    # Step 6: Build messages
    # ------------------------------------------------------------------------

    def _build_messages(self, result: PageNumberingResult) -> None:
        if result.status == "pass":
            result.messages.append(
                CheckMessage(
                    level="pass",
                    text=(
                        f"Penomoran halaman sesuai aturan: zona awal "
                        f"{self.rules.front_matter.numeral_type} di "
                        f"{self.rules.front_matter.position}, zona inti "
                        f"{self.rules.core_matter.numeral_type} di "
                        f"{self.rules.core_matter.position}."
                    ),
                )
            )
            return

        # Fail/warning — list semua finding sebagai message
        for f in result.findings:
            result.messages.append(CheckMessage(level=f.severity, text=f.message))