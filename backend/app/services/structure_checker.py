
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
        * status: 'pass' | 'warning' | 'fail'
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
class CheckMessage:
    """Pesan feedback yang akan ditampilkan ke user."""
    level: str    # 'pass' | 'warning' | 'fail'
    text: str


@dataclass
class StructureCheckResult:
    """Hasil pengecekan struktur — siap dikonversi ke JSON."""
    status: str  # 'pass' | 'warning' | 'fail'
    schema_competition: str
    schema_code: str
    report_type: str
    found_sections: list[FoundSection] = field(default_factory=list)
    missing_required: list[MissingSection] = field(default_factory=list)
    forbidden_found: list[ForbiddenFinding] = field(default_factory=list)
    out_of_order: list[OrderViolation] = field(default_factory=list)
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
                }
                for s in self.found_sections
            ],
            "missing_required": [
                {"rule_name": m.rule_name, "expected_order": m.expected_order, "message": m.message}
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


def _heading_matches_rule(heading_text: str, rule: SectionRule) -> bool:
    """
    Cek apakah teks heading match dengan rule (canonical name atau aliases).
    Pencocokan: heading dimulai dengan name atau salah satu alias (setelah normalisasi).
    """
    norm_heading = _normalize(heading_text)
    candidates = [rule.name] + rule.aliases
    for cand in candidates:
        norm_cand = _normalize(cand)
        if norm_heading.startswith(norm_cand):
            return True
    return False


def _looks_like_toc_line(text: str) -> bool:
    """Heuristik sederhana untuk entri daftar isi/lampiran."""
    t = text.strip()
    if not t:
        return False
    if re.search(r"\t+\s*([ivxlcdm]+|\d+)\s*$", t, flags=re.IGNORECASE):
        return True
    if re.search(r"[.\s]{4,}\s*(\d+|[ivxlcdm]+)\s*$", t, flags=re.IGNORECASE):
        return True
    return False


def _looks_like_heading_candidate(text: str, para=None) -> bool:
    """
    Kandidat judul section saat style Heading tidak konsisten.
    Termasuk: pola BAB N, mayoritas uppercase, atau paragraf pendek all-bold.
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
    # Paragraf pendek (≤60 char) dengan semua run explicitly bold = heading
    if para is not None and len(t) <= 60:
        text_runs = [r for r in para.runs if r.text.strip()]
        if text_runs and all(r.bold is True for r in text_runs):
            return True
    return False


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

        # 2. Cari section wajib yang HILANG
        result.missing_required = self._find_missing_required(result.found_sections)

        # 3. Section terlarang yang muncul = red flag
        result.forbidden_found = self._collect_forbidden(result.found_sections)

        # 4. Validasi urutan section wajib yang ditemukan
        result.out_of_order = self._check_order(result.found_sections)

        # 5. Tentukan status overall + bangun messages
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

        for para in self.parser.paragraphs:
            text = para.text.strip()
            if not text:
                continue
            # Skip baris daftar isi yang sering false-positive.
            if _looks_like_toc_line(text):
                continue
            if not para.is_heading and not _looks_like_heading_candidate(text, para=para):
                continue
            # Dokumen real sering pakai style Normal untuk judul section.
            # Tetap izinkan selama text cocok rule.

            # Cek terhadap semua rule
            for rule in self.rules.sections:
                if not _heading_matches_rule(text, rule):
                    continue

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
                    )
                )
                # Satu paragraf cukup match satu rule (rule paling spesifik
                # diharapkan ditemukan duluan via urutan di sections list)
                break

        return found

    # ------------------------------------------------------------------------
    # Step 2: Cari section wajib yang hilang
    # ------------------------------------------------------------------------

    def _find_missing_required(
        self, found: list[FoundSection]
    ) -> list[MissingSection]:
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

    def _collect_forbidden(
        self, found: list[FoundSection]
    ) -> list[ForbiddenFinding]:
        forbidden: list[ForbiddenFinding] = []
        for f in found:
            if not f.is_forbidden:
                continue
            forbidden.append(
                ForbiddenFinding(
                    rule_name=f.rule_name,
                    matched_text=f.matched_text,
                    paragraph_index=f.paragraph_index,
                    severity="fail",
                    message=(
                        f"Red flag: dokumen memuat '{f.rule_name}' "
                        f"(\"{f.matched_text[:60]}\") yang DILARANG di "
                        f"{self.rules.competition_code}-{self.rules.schema_code} "
                        f"{self.rules.report_type_code}."
                    ),
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
        # Required sections yang ditemukan, urut sesuai dokumen
        actual = [f for f in found if f.is_required]

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

        # Status logic:
        # - fail jika ada forbidden ATAU ada missing required ATAU ada out_of_order
        # - pass jika semua bersih
        # (warning belum dipakai — di skema struktur, semuanya jelas pass/fail)

        has_fail = bool(
            result.forbidden_found
            or result.missing_required
            or result.out_of_order
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