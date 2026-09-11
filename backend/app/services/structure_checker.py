
"""
StructureChecker — modul pengecek struktur dokumen sesuai SchemaRules.

Tugas:
1. Validasi semua section WAJIB ada di dokumen
2. Deteksi section TERLARANG (red flag) yang muncul di dokumen
3. Validasi urutan section sesuai aturan skema
4. Output JSON sesuai format blueprint v0.3 §4.1

Input:
    - DocxParser (sudah parse dokumen)
    - SchemaRules (aturan skema target)

Output:
    - StructureCheckResult dengan:
        * status: 'pass' | 'fail'
        * found_sections: list section yang teridentifikasi (urut sesuai dokumen)
        * missing_required: list section wajib yang tidak ditemukan
        * forbidden_found: list section terlarang yang ditemukan (RED FLAG)
        * out_of_order: list pasangan section yang urutannya salah
        * messages: human-readable feedback per finding
        * to_dict(): konversi ke dict untuk disimpan ke check_results.structure_result
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional
import re

from app.services.docx_parser import DocxParser
from app.services.schema_rules import SchemaRules, SectionRule


# ============================================================================
# Hasil per-finding & per-modul
# ============================================================================


@dataclass
class FoundSection:
    """Section yang teridentifikasi di dokumen."""
    rule_name: str          # nama canonical dari SectionRule
    matched_text: str       # teks heading yang match (apa adanya dari dokumen)
    paragraph_index: int    # posisi di parser.paragraphs
    is_forbidden: bool = False
    is_required: bool = False
    is_core: bool = False
    # Dasar pengenalan section ini:
    #   'style' — style Heading N / Title / outlineLvl (deklarasi Word, PASTI)
    #   'shape' — heuristik bentuk teks (rasio kapital / bold / pola "BAB N")
    #   'sdt'   — node content control (TOC field), posisinya perkiraan
    # Temuan yang bersandar pada 'shape'/'sdt' tidak bisa dibuktikan langsung.
    # Vonis di sistem ini biner (salah / benar), jadi temuan semacam itu TIDAK
    # dilaporkan sama sekali — lebih baik terlewat daripada memvonis salah.
    evidence: str = "shape"
    # 'exact' = teks heading persis nama section; 'prefix' = hanya diawali.
    match_quality: str = "prefix"

    @property
    def is_authoritative(self) -> bool:
        """Cukup kuat untuk jadi vonis?

        Butuh salah satu: Word menyatakan paragraf ini heading (style/outlineLvl),
        ATAU teksnya persis nama section. Yang tidak punya keduanya — dikenali
        cuma dari bentuk teks DAN cocok sebagai awalan saja — bisa jadi paragraf
        biasa yang kebetulan berawalan sama, jadi tidak dipakai memvonis.
        """
        return self.evidence == "style" or self.match_quality == "exact"


@dataclass
class MissingSection:
    """Section wajib yang tidak ditemukan."""
    rule_name: str
    expected_order: int
    message: str


@dataclass
class ForbiddenFinding:
    """Section terlarang yang ditemukan — RED FLAG."""
    rule_name: str
    matched_text: str
    paragraph_index: int
    severity: str = "fail"  # red flag selalu fail
    message: str = ""


@dataclass
class OrderViolation:
    """Pasangan section yang urutannya salah."""
    earlier_should_be: str    # section yang seharusnya muncul lebih dulu
    later_should_be: str      # section yang seharusnya muncul kemudian
    actual_earlier_index: int
    actual_later_index: int
    message: str


@dataclass
class FormatViolation:
    """BAB heading ditemukan tapi format tidak sesuai (angka Arab + titik wajib)."""
    rule_name: str
    matched_text: str
    paragraph_index: int
    expected_format: str
    issues: list[str]
    message: str


@dataclass
class CheckMessage:
    """Pesan feedback yang akan ditampilkan ke user."""
    level: str    # 'pass' | 'fail'
    text: str


@dataclass
class StructureCheckResult:
    """Hasil pengecekan struktur — siap dikonversi ke JSON."""
    status: str  # 'pass' | 'fail'
    schema_competition: str
    schema_code: str
    report_type: str
    found_sections: list[FoundSection] = field(default_factory=list)
    missing_required: list[MissingSection] = field(default_factory=list)
    forbidden_found: list[ForbiddenFinding] = field(default_factory=list)
    out_of_order: list[OrderViolation] = field(default_factory=list)
    format_violations: list[FormatViolation] = field(default_factory=list)
    messages: list[CheckMessage] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Konversi ke dict untuk disimpan ke `check_results.structure_result` (JSONB)."""
        return {
            "status": self.status,
            "schema": {
                "competition": self.schema_competition,
                "code": self.schema_code,
                "report_type": self.report_type,
            },
            "found_sections": [
                {
                    "rule_name": s.rule_name,
                    "matched_text": s.matched_text,
                    "paragraph_index": s.paragraph_index,
                    "is_required": s.is_required,
                    "is_core": s.is_core,
                    "is_forbidden": s.is_forbidden,
                    "evidence": s.evidence,
                    "match_quality": s.match_quality,
                }
                for s in self.found_sections
            ],
            "missing_required": [
                {
                    "rule_name": m.rule_name,
                    "expected_order": m.expected_order,
                    "message": m.message,
                }
                for m in self.missing_required
            ],
            "forbidden_found": [
                {
                    "rule_name": f.rule_name,
                    "matched_text": f.matched_text,
                    "paragraph_index": f.paragraph_index,
                    "severity": f.severity,
                    "message": f.message,
                }
                for f in self.forbidden_found
            ],
            "out_of_order": [
                {
                    "earlier_should_be": o.earlier_should_be,
                    "later_should_be": o.later_should_be,
                    "actual_earlier_index": o.actual_earlier_index,
                    "actual_later_index": o.actual_later_index,
                    "message": o.message,
                }
                for o in self.out_of_order
            ],
            "format_violations": [
                {
                    "rule_name": fv.rule_name,
                    "matched_text": fv.matched_text,
                    "paragraph_index": fv.paragraph_index,
                    "expected_format": fv.expected_format,
                    "issues": fv.issues,
                    "message": fv.message,
                }
                for fv in self.format_violations
            ],
            "messages": [{"level": m.level, "text": m.text} for m in self.messages],
        }


# ============================================================================
# Helper: normalisasi teks untuk matching
# ============================================================================


def _normalize(text: str) -> str:
    """
    Normalisasi teks untuk pencocokan:
    - uppercase
    - hapus dot leader & nomor halaman ToC ('BAB 1 .... 5' → 'BAB 1')
    - normalisasi spasi multiple → 1
    - strip trailing punctuation
    """
    t = text.upper().strip()
    # Hapus pola dot leader + angka di akhir (entri ToC)
    # mis. "BAB 1. PENDAHULUAN ............... 1" → "BAB 1. PENDAHULUAN"
    import re
    t = re.sub(r"\s*[\.\s]{4,}\s*\d+\s*$", "", t)
    # Normalisasi multiple spaces
    t = re.sub(r"\s+", " ", t)
    return t.strip()


def _heading_match_quality(heading_text: str, rule: SectionRule) -> Optional[str]:
    """Mutu kecocokan heading dengan rule: 'exact' | 'prefix' | None.

    'exact'  — seluruh teks heading persis nama/alias section. Tidak ambigu.
    'prefix' — heading hanya DIAWALI nama section, ada lanjutannya. Perlu untuk
               "BAB 1. PENDAHULUAN ... 5" dan judul ber-ekor, tapi juga pintu
               masuk false positive: sub-bab "Ringkasan Hasil yang Dicapai"
               ikut cocok dengan section terlarang "RINGKASAN".
    """
    norm_heading = _normalize(heading_text)
    best: Optional[str] = None
    for cand in [rule.name] + rule.aliases:
        norm_cand = _normalize(cand)
        if norm_heading == norm_cand:
            return "exact"
        if norm_heading.startswith(norm_cand):
            best = "prefix"
    return best


def _heading_matches_rule(heading_text: str, rule: SectionRule) -> bool:
    """
    Cek apakah teks heading match dengan rule (canonical name atau aliases).
    Pencocokan: heading dimulai dengan name atau salah satu alias (setelah normalisasi).
    """
    return _heading_match_quality(heading_text, rule) is not None


def _looks_like_toc_line(text: str, para=None) -> bool:
    """Apakah baris ini entri daftar isi/lampiran?

    Kalau ParagraphInfo tersedia, pakai `is_toc_entry` dari parser — sinyalnya
    dibaca dari style bawaan Word ('toc 1'..'toc 9', 'table of figures'), yaitu
    deklarasi eksplisit di dalam file, bukan tebakan. Argumen `text` saja tetap
    didukung untuk pemanggil yang tidak punya paragraf (mis. node SDT).
    """
    if para is not None and getattr(para, "is_toc_entry", False):
        return True
    return DocxParser._detect_toc_entry(text, None)[0]


# Judul lampiran bernomor: "Lampiran 1. Penggunaan Dana", "Lampiran 2.1 ...".
# Banyak dokumen langsung masuk ke sini tanpa halaman pemisah "LAMPIRAN", dan
# menulisnya sebagai paragraf biasa — tanpa style heading, tanpa bold, huruf
# campuran. Pola ini cukup khas untuk dikenali, asalkan bukan entri Daftar
# Lampiran (dibedakan lewat ParagraphInfo.is_toc_entry).
_LAMPIRAN_NUMBERED_RE = re.compile(r"^\s*LAMPIRAN\s*\d", re.IGNORECASE)
# Judul lampiran yang berdiri sendiri, tanpa embel-embel.
_LAMPIRAN_EXACT_RE = re.compile(r"^\s*LAMPIRAN(?:-LAMPIRAN)?\s*$", re.IGNORECASE)
_MAX_LAMPIRAN_HEADING_CHARS = 80


def _looks_like_numbered_lampiran(text: str, para=None) -> bool:
    """Judul lampiran bernomor yang ditulis sebagai paragraf biasa."""
    t = text.strip()
    if not t or len(t) > _MAX_LAMPIRAN_HEADING_CHARS:
        return False
    if not _LAMPIRAN_NUMBERED_RE.match(t):
        return False
    # Entri Daftar Lampiran teksnya nyaris identik — dibedakan dari style Word.
    return not (para is not None and getattr(para, "is_toc_entry", False))


def _looks_like_heading_candidate(text: str, para=None) -> bool:
    """
    Kandidat judul section saat style Heading tidak konsisten.
    Termasuk: pola BAB N, judul lampiran bernomor, mayoritas uppercase,
    atau paragraf pendek all-bold.
    """
    t = text.strip()
    if not t:
        return False
    if re.match(r"^BAB\s+[IVXLCM0-9]+(?:[.\s]|$)", t, flags=re.IGNORECASE):
        return True
    if _looks_like_numbered_lampiran(t, para):
        return True
    letters = [c for c in t if c.isalpha()]
    if not letters:
        return False
    upper_ratio = sum(1 for c in letters if c.isupper()) / len(letters)
    if upper_ratio >= 0.8:
        return True
    # Paragraf pendek (≤60 char) dengan semua run explicitly bold = heading
    if para is not None and len(t) <= 60:
        text_runs = [r for r in para.runs if r.text.strip()]
        if text_runs and all(r.bold is True for r in text_runs):
            return True
    return False


def find_lampiran_start(
    paragraphs,
    *,
    after_idx: Optional[int] = None,
    pustaka_idx: Optional[int] = None,
) -> Optional[int]:
    """Index paragraf tempat bagian LAMPIRAN dimulai, atau None.

    SATU sumber kebenaran untuk seluruh modul — sebelumnya format_checker,
    physical_sheet_counter, dan structure_checker punya aturan sendiri-sendiri
    yang berbeda kualitas. Batas ini menentukan banyak hal sekaligus: sampai
    mana format diperiksa, sampai mana halaman inti dihitung, dan apakah
    section LAMPIRAN dianggap ada.

    Tiga bentuk diterima:
    (a) teks paragrafnya PERSIS "LAMPIRAN" / "LAMPIRAN-LAMPIRAN" — konklusif
        apa pun gayanya, tidak perlu style heading maupun huruf besar
    (b) judul "LAMPIRAN ..." yang tampak heading — lewat
        _looks_like_heading_candidate
    (c) judul lampiran bernomor "Lampiran 1. ..." yang ditulis sebagai paragraf
        biasa tanpa style heading

    Bentuk (b) hanya dicari SETELAH Daftar Pustaka (kalau ketemu) supaya
    kalimat isi yang kebetulan menyebut "Lampiran 1" tidak dikira judul.
    Entri Daftar Lampiran juga tidak pernah cocok karena is_toc_entry-nya True.
    """
    floor_idx = after_idx
    for para in paragraphs:
        idx = para.index
        if floor_idx is not None and idx < floor_idx:
            continue
        text = para.text.strip()
        if not text or getattr(para, "is_toc_entry", False):
            continue
        if not re.match(r"^\s*LAMPIRAN\b", text, flags=re.IGNORECASE):
            continue
        # (a) teksnya persis nama section — cukup kuat tanpa syarat lain.
        if _LAMPIRAN_EXACT_RE.match(text):
            return idx
        if para.is_heading or _looks_like_heading_candidate(text, para=para):
            # Judul bernomor tanpa style: butuh konfirmasi posisi (sesudah
            # Daftar Pustaka) supaya tidak menabrak kalimat isi.
            if (
                _looks_like_numbered_lampiran(text, para)
                and not para.is_heading
                and pustaka_idx is not None
                and idx < pustaka_idx
            ):
                continue
            return idx
    return None


# ============================================================================
# StructureChecker
# ============================================================================


class StructureChecker:
    """
    Checker struktur dokumen.

    Usage:
        from app.services.docx_parser import DocxParser
        from app.services.schema_rules import get_pkm_kc_proposal_rules
        from app.services.structure_checker import StructureChecker

        parser = DocxParser('path/to/doc.docx')
        rules = get_pkm_kc_proposal_rules()
        result = StructureChecker(parser, rules).check()
        print(result.to_dict())
    """

    def __init__(self, parser: DocxParser, rules: SchemaRules):
        self.parser = parser
        self.rules = rules

    def check(self) -> StructureCheckResult:
        result = StructureCheckResult(
            status="pass",
            schema_competition=self.rules.competition_code,
            schema_code=self.rules.schema_code,
            report_type=self.rules.report_type_code,
        )

        # 1. Identifikasi semua section yang muncul di dokumen
        result.found_sections = self._identify_sections()

        # 2. Validasi format penulisan judul BAB (angka Arab wajib, titik opsional)
        result.format_violations = self._check_bab_format(result.found_sections)

        # 3. Cari section wajib yang HILANG
        result.missing_required = self._find_missing_required(result.found_sections)

        # 4. Section terlarang yang muncul = red flag
        result.forbidden_found = self._collect_forbidden(result.found_sections)

        # 5. Validasi urutan section wajib yang ditemukan
        result.out_of_order = self._check_order(result.found_sections)

        # 6. Tentukan status overall + bangun messages
        self._finalize(result)

        return result

    # ------------------------------------------------------------------------
    # Step 1: Identifikasi section
    # ------------------------------------------------------------------------

    def _identify_sections(self) -> list[FoundSection]:
        """
        Iterate semua heading di dokumen, cocokkan dengan SectionRule.
        Untuk required sections, ambil HANYA kemunculan pertama (skip ToC).
        Untuk forbidden sections, ambil SEMUA kemunculan agar semua red flag terdaftar.
        """
        found: list[FoundSection] = []
        already_matched_required: set[str] = set()

        # Pre-pass: scan SDT nodes (Word TOC field) untuk heading yang tidak masuk
        # parser.paragraphs — kasus umum: "DAFTAR ISI" di-wrap dalam <w:sdt>.
        for text, virtual_idx in self._extract_sdt_heading_candidates():
            if _looks_like_toc_line(text):
                continue
            for rule in self.rules.sections:
                quality = _heading_match_quality(text, rule)
                if quality is None:
                    continue
                if rule.required and rule.name in already_matched_required:
                    break
                if rule.required:
                    already_matched_required.add(rule.name)
                found.append(
                    FoundSection(
                        rule_name=rule.name,
                        matched_text=text,
                        paragraph_index=virtual_idx,
                        is_forbidden=rule.forbidden,
                        is_required=rule.required,
                        is_core=rule.is_core,
                        evidence="sdt",
                        match_quality=quality,
                    )
                )
                break

        for para in self.parser.paragraphs:
            text = para.text.strip()
            if not text:
                continue
            # Skip baris daftar isi yang sering false-positive.
            if _looks_like_toc_line(text, para=para):
                continue
            # Judul seperti tercetak ("BAB 1. PENDAHULUAN", dengan "BAB 1." dari
            # penomoran otomatis Word) dicoba dulu, lalu teks ketikan saja.
            variants = [t.strip() for t in para.heading_texts]
            # is_heading = style Heading/Title atau outlineLvl → deklarasi Word.
            # Selain itu hanya lolos lewat heuristik bentuk → bukti lemah.
            if para.is_heading:
                evidence = "style"
            elif any(_looks_like_heading_candidate(t, para=para) for t in variants):
                evidence = "shape"
            else:
                continue
            # Dokumen real sering pakai style Normal untuk judul section.
            # Tetap izinkan selama text cocok rule.

            # Cek terhadap semua rule
            for rule in self.rules.sections:
                matches = [
                    (q, v) for v in variants
                    if (q := _heading_match_quality(v, rule)) is not None
                ]
                if not matches:
                    continue
                # 'exact' mengalahkan 'prefix'; kalau seri, versi tercetak.
                quality, text = min(matches, key=lambda m: m[0] != "exact")

                # Required: ambil kemunculan pertama saja
                if rule.required and rule.name in already_matched_required:
                    break  # sudah pernah match rule lain di paragraf ini? unlikely
                if rule.required:
                    already_matched_required.add(rule.name)

                found.append(
                    FoundSection(
                        rule_name=rule.name,
                        matched_text=text,
                        paragraph_index=para.index,
                        is_forbidden=rule.forbidden,
                        is_required=rule.required,
                        is_core=rule.is_core,
                        evidence=evidence,
                        match_quality=quality,
                    )
                )
                # Satu paragraf cukup match satu rule (rule paling spesifik
                # diharapkan ditemukan duluan via urutan di sections list)
                break

        return found

    def _extract_sdt_heading_candidates(self) -> list[tuple[str, int]]:
        """
        Ambil paragraf heading dari SDT nodes di body XML (mis. TOC field Word).
        Hanya paragraf dengan style name mengandung 'heading' yang diambil —
        mengecualikan entri TOC (style 'TOC1', 'TOC2', dll.).
        Mengembalikan (teks, virtual_index) dengan virtual_index negatif agar
        SDT headings ditempatkan sebelum semua paragraf normal dalam ordering.
        """
        try:
            from docx.oxml.ns import qn
            body = self.parser.doc.element.body
            results: list[tuple[str, int]] = []
            virtual_idx = -10000
            for child in body:
                tag = child.tag.split("}")[1] if "}" in child.tag else child.tag
                if tag != "sdt":
                    continue
                for p in child.iter(qn("w:p")):
                    pStyle = p.find(".//" + qn("w:pStyle"))
                    style_val = pStyle.get(qn("w:val"), "") if pStyle is not None else ""
                    if "heading" not in style_val.lower():
                        continue
                    text = "".join(wt.text or "" for wt in p.iter(qn("w:t"))).strip()
                    if text:
                        results.append((text, virtual_idx))
                        virtual_idx += 1
            return results
        except Exception:
            return []

    # ------------------------------------------------------------------------
    # Step 2: Validasi format penulisan judul BAB
    # ------------------------------------------------------------------------

    _BAB_NUM_PATTERN = re.compile(r"^BAB\s+([IVXLCM0-9]+)([.\s]|$)", re.IGNORECASE)
    _ROMAN_PATTERN = re.compile(r"^[IVXLCM]+$", re.IGNORECASE)

    def _check_bab_format(self, found: list[FoundSection]) -> list[FormatViolation]:
        """
        Pastikan judul BAB menggunakan angka Arab (bukan Romawi).
        Titik setelah nomor bab opsional — "BAB 1." dan "BAB 1 " sama-sama valid.
        Yang tidak diperbolehkan: "BAB I.", "BAB IV.", dsb.
        """
        violations = []
        for section in found:
            if section.is_forbidden:
                continue
            # Bukti pengenalan lemah → tidak cukup untuk memvonis format judulnya.
            if not section.is_authoritative:
                continue
            if not section.rule_name.upper().startswith("BAB "):
                continue

            norm = _normalize(section.matched_text)
            m = self._BAB_NUM_PATTERN.match(norm)
            if not m:
                continue

            num_str = m.group(1).upper()
            if not self._ROMAN_PATTERN.match(num_str):
                continue

            violations.append(
                FormatViolation(
                    rule_name=section.rule_name,
                    matched_text=section.matched_text,
                    paragraph_index=section.paragraph_index,
                    expected_format=section.rule_name,
                    issues=["gunakan angka Arab (bukan angka Romawi)"],
                    message=(
                        f"Format judul bab tidak sesuai: '{section.matched_text}' "
                        f"— gunakan angka Arab (bukan angka Romawi). "
                        f"Format yang benar: '{section.rule_name}'."
                    ),
                )
            )
        return violations

    # ------------------------------------------------------------------------
    # Step 3: Cari section wajib yang hilang
    # ------------------------------------------------------------------------

    def _find_missing_required(
        self, found: list[FoundSection]
    ) -> list[MissingSection]:
        """Section wajib yang tidak ketemu.

        Pencarian memakai style heading DAN heuristik bentuk, jadi "tidak ketemu
        oleh keduanya" sudah dasar yang cukup untuk memvonis.
        """
        found_required_names = {f.rule_name for f in found if f.is_required}
        missing: list[MissingSection] = []
        for rule in self.rules.required_sections():
            if rule.name not in found_required_names:
                missing.append(
                    MissingSection(
                        rule_name=rule.name,
                        expected_order=rule.order or 0,
                        message=f"Section wajib '{rule.name}' tidak ditemukan di dokumen.",
                    )
                )
        return missing

    # ------------------------------------------------------------------------
    # Step 3: Kumpulkan red flag
    # ------------------------------------------------------------------------

    def _find_front_zone_end(
        self, found: list[FoundSection]
    ) -> tuple[Optional[int], bool]:
        """Batas akhir zona depan dokumen, plus apakah batas itu tepercaya.

        Batasnya = paragraf section inti paling awal yang ditemukan. Tepercaya
        hanya bila section inti PERTAMA menurut aturan (BAB 1, atau "Pendahuluan"
        utk PKM-AI) memang ter-detect; kalau yang ketemu cuma section inti
        belakangan (mis. DAFTAR PUSTAKA saja), batasnya terlalu lebar untuk
        dipakai memvonis — temuannya tidak dilaporkan.

        Return: (paragraph_index batas, tepercaya). None = tidak ada acuan sama
        sekali, seluruh dokumen dianggap zona depan.
        """
        core_found = [f for f in found if f.is_core and not f.is_forbidden]
        if not core_found:
            return None, False

        core_rules = [
            r for r in self.rules.sections
            if r.is_core and not r.forbidden and r.order is not None
        ]
        first_core_rule = min(core_rules, key=lambda r: r.order).name if core_rules else None
        trusted = any(f.rule_name == first_core_rule for f in core_found)
        return min(f.paragraph_index for f in core_found), trusted

    def _collect_forbidden(
        self, found: list[FoundSection]
    ) -> list[ForbiddenFinding]:
        # Batas scope "before_lampiran": paragraf heading LAMPIRAN body (bila
        # ketemu). Kemunculan forbidden di dalam LAMPIRAN diabaikan untuk rule
        # ber-forbidden_scope — isi lampiran (salinan artikel, poster, dsb.)
        # bukan bagian struktur isi utama.
        lampiran_idx = next(
            (f.paragraph_index for f in found
             if f.rule_name == "LAMPIRAN" and not f.is_forbidden),
            None,
        )
        # Batas scope "front_matter": section inti pertama. Sampul, pengesahan
        # dan ringkasan didefinisikan oleh LETAK — hanya pelanggaran bila muncul
        # sebelum batas ini. Kalau batas tidak bisa ditegakkan (BAB 1 tidak
        # ter-detect: dokumen rusak / hasil scan), posisinya tidak bisa
        # diverifikasi sehingga tidak cukup untuk memvonis.
        front_zone_end, front_zone_trusted = self._find_front_zone_end(found)
        scope_by_rule = {
            r.name: getattr(r, "forbidden_scope", None) for r in self.rules.sections
        }

        forbidden: list[ForbiddenFinding] = []
        for f in found:
            if not f.is_forbidden:
                continue
            scope = scope_by_rule.get(f.rule_name)

            if (
                scope == "before_lampiran"
                and lampiran_idx is not None
                and f.paragraph_index >= lampiran_idx
            ):
                continue
            if scope == "front_matter":
                if front_zone_end is not None and f.paragraph_index >= front_zone_end:
                    continue
                # Batas zona depan tidak bisa ditegakkan (BAB 1 tidak ter-detect):
                # posisinya tak terverifikasi, jadi tidak cukup untuk memvonis.
                if not front_zone_trusted:
                    continue
            # Bukti pengenalan lemah: bukan heading ber-style DAN teksnya cuma
            # berawalan nama section. Bisa jadi paragraf biasa yang kebetulan
            # berawalan sama — tidak cukup untuk memvonis.
            if not f.is_authoritative:
                continue

            message = (
                f"Red flag: dokumen memuat '{f.rule_name}' "
                f"(\"{f.matched_text[:60]}\") yang DILARANG di "
                f"{self.rules.competition_code}-{self.rules.schema_code} "
                f"{self.rules.report_type_code}."
            )

            forbidden.append(
                ForbiddenFinding(
                    rule_name=f.rule_name,
                    matched_text=f.matched_text,
                    paragraph_index=f.paragraph_index,
                    message=message,
                )
            )
        return forbidden

    # ------------------------------------------------------------------------
    # Step 4: Validasi urutan section
    # ------------------------------------------------------------------------

    def _check_order(self, found: list[FoundSection]) -> list[OrderViolation]:
        """
        Cek apakah section wajib yang ditemukan muncul dalam urutan yang benar.
        Algoritma:
          - Filter found ke required-only, dapatkan list (rule_name, paragraph_index)
          - Bandingkan order yang seharusnya (dari SchemaRules) vs urutan paragraph_index
          - Setiap pasangan (a, b) di mana order(a) < order(b) tapi
            paragraph_index(a) > paragraph_index(b) → violation
        """
        # Map name → expected order
        order_map = {
            r.name: r.order
            for r in self.rules.sections
            if r.required and r.order is not None
        }
        # Required sections yang ditemukan, urut sesuai dokumen. Section dengan
        # bukti pengenalan lemah dikeluarkan: posisinya belum tentu posisi
        # section sungguhan, jadi tidak layak dipakai memvonis urutan.
        actual = [f for f in found if f.is_required and f.is_authoritative]

        violations: list[OrderViolation] = []
        # Bandingkan setiap pasangan
        for i in range(len(actual)):
            for j in range(i + 1, len(actual)):
                a = actual[i]
                b = actual[j]
                order_a = order_map.get(a.rule_name)
                order_b = order_map.get(b.rule_name)
                if order_a is None or order_b is None:
                    continue
                # Di dokumen: a muncul sebelum b (karena loop i < j)
                # Tapi di rules: order_a > order_b → seharusnya b lebih dulu
                if order_a > order_b:
                    violations.append(
                        OrderViolation(
                            earlier_should_be=b.rule_name,
                            later_should_be=a.rule_name,
                            actual_earlier_index=a.paragraph_index,
                            actual_later_index=b.paragraph_index,
                            message=(
                                f"Urutan salah: '{a.rule_name}' (paragraf #{a.paragraph_index}) "
                                f"muncul sebelum '{b.rule_name}' (paragraf #{b.paragraph_index}), "
                                f"seharusnya '{b.rule_name}' duluan."
                            ),
                        )
                    )
        return violations

    # ------------------------------------------------------------------------
    # Step 5: Finalize status & messages
    # ------------------------------------------------------------------------

    def _finalize(self, result: StructureCheckResult) -> None:
        def loc(paragraph_index: int) -> str:
            estimator = getattr(self.parser, "estimate_physical_page", None)
            in_page_estimator = getattr(self.parser, "estimate_paragraph_index_in_page", None)
            page = estimator(paragraph_index) if callable(estimator) else None
            in_page = (
                in_page_estimator(paragraph_index)
                if callable(in_page_estimator)
                else None
            )
            if page is None:
                return f"(paragraf #{paragraph_index})"
            if in_page is None or in_page <= 0:
                return f"(halaman fisik ~{page}, paragraf #{paragraph_index})"
            return (
                f"(halaman fisik ~{page}, paragraf ke-{in_page} "
                f"(global #{paragraph_index}))"
            )

        # Status logic: BINER — 'fail' kalau ada temuan apa pun, 'pass' kalau
        # bersih. Temuan yang buktinya tidak cukup kuat sudah disaring lebih
        # awal (tidak dilaporkan sama sekali), sehingga apa pun yang sampai ke
        # sini adalah pelanggaran yang bisa dibuktikan.
        has_fail = bool(
            result.forbidden_found
            or result.missing_required
            or result.out_of_order
            or result.format_violations
        )
        result.status = "fail" if has_fail else "pass"

        # Bangun messages
        if not has_fail:
            result.messages.append(
                CheckMessage(
                    level="pass",
                    text=(
                        f"Struktur dokumen sesuai dengan {self.rules.competition_code}-"
                        f"{self.rules.schema_code} {self.rules.report_type_code}. "
                        f"{len([f for f in result.found_sections if f.is_required])} "
                        f"section wajib ditemukan, tidak ada section terlarang, urutan benar."
                    ),
                )
            )
            return

        # Forbidden findings (paling kritis)
        for f in result.forbidden_found:
            result.messages.append(
                CheckMessage(level="fail", text=f"{f.message} {loc(f.paragraph_index)}")
            )

        # Missing required
        for m in result.missing_required:
            result.messages.append(CheckMessage(level="fail", text=m.message))

        # Out of order
        for o in result.out_of_order:
            result.messages.append(
                CheckMessage(
                    level="fail",
                    text=(
                        f"{o.message} "
                        f"{loc(o.actual_earlier_index)} vs {loc(o.actual_later_index)}"
                    ),
                )
            )

        # Format violations (angka Arab wajib, titik opsional)
        for fv in result.format_violations:
            result.messages.append(
                CheckMessage(
                    level="fail",
                    text=f"{fv.message} {loc(fv.paragraph_index)}",
                )
            )