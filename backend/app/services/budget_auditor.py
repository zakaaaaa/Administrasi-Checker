"""
BudgetAuditor — modul audit anggaran sesuai blueprint v0.3 §4.4 (5 lapis pengecekan).

Lapis pengecekan:
1. Validasi sumber dana (Belmawa 6-8jt, PT > 0 + max 2jt, Eksternal max 1jt)
2. Integritas tabel RAB (semua kolom kategori wajib ada)
3. Validasi alokasi per kategori (% maksimum dari total)
4. Cross-check Bab 4 ↔ Lampiran 2 (toleransi Rp0)
5. Rekomendasi relokasi / pecah justifikasi bila harga satuan per item
   melebihi patokan (default Rp1jt) — warning, bukan fail; total baris boleh besar
   selama volume × harga satuan masuk akal dan satuan ≤ patokan.
6. Item terlarang & restriksi khusus

Input:
    - DocxParser
    - BudgetRules (skema spesifik)
    - User input pendanaan: belmawa, university, external (Rp)

Output:
    - BudgetAuditResult dengan to_dict() siap simpan ke check_results.budget_result
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from app.services.budget_rules import BudgetRules, BudgetCategory
from app.services.budget_table_parser import (
    Bab4ParseResult,
    Lampiran2ParseResult,
    is_bab4_rab_table,
    is_lampiran2_table,
    match_category_to_canonical,
    parse_bab4_table,
    parse_lampiran2_table,
)
from app.services.docx_parser import DocxParser


# ============================================================================
# Data classes hasil
# ============================================================================


@dataclass
class FundingValidationResult:
    """Hasil validasi satu sumber dana."""
    name: str
    display_name: str
    input_rp: int
    min_rp: int
    max_rp: int
    status: str  # 'pass' | 'fail'
    message: str = ""


@dataclass
class CategoryAllocationResult:
    """Hasil validasi alokasi satu kategori."""
    canonical_name: str
    found_in_table: bool
    table_name: Optional[str] = None
    actual_rp: Optional[int] = None
    actual_pct: Optional[float] = None
    max_pct: float = 0.0
    status: str = "pass"  # 'pass' | 'fail' | 'missing'
    message: str = ""


@dataclass
class CrossCheckDiscrepancy:
    canonical_name: str
    bab4_rp: Optional[int]
    lampiran2_rp: Optional[int]
    delta_rp: int


@dataclass
class RelocationItem:
    """Item yang harga satuannya melewati patokan (bukan total baris)."""
    description: str
    category: Optional[str]
    amount_rp: int  # harga satuan yang memicu saran
    total_rp: Optional[int] = None
    volume: Optional[str] = None
    approx_page: Optional[int] = None


@dataclass
class ProhibitedItemFinding:
    description: str
    matched_keyword: str
    amount_rp: Optional[int] = None
    category: Optional[str] = None
    approx_page: Optional[int] = None


@dataclass
class CheckMessage:
    level: str
    text: str


@dataclass
class BudgetAuditResult:
    status: str  # 'pass' | 'warning' | 'fail'
    total_input_funding_rp: int = 0
    funding_validation: list[FundingValidationResult] = field(default_factory=list)
    table_integrity_status: str = "pass"  # 'pass' | 'fail'
    table_integrity_missing: list[str] = field(default_factory=list)
    categories: list[CategoryAllocationResult] = field(default_factory=list)
    cross_check_status: str = "skipped"  # 'pass' | 'fail' | 'skipped'
    cross_check_discrepancies: list[CrossCheckDiscrepancy] = field(default_factory=list)
    relocation_items: list[RelocationItem] = field(default_factory=list)
    prohibited_items: list[ProhibitedItemFinding] = field(default_factory=list)
    bab4_grand_total_rp: Optional[int] = None
    lampiran2_grand_total_rp: Optional[int] = None
    messages: list[CheckMessage] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "total_input_funding_rp": self.total_input_funding_rp,
            "funding_validation": [
                {
                    "name": fv.name,
                    "display_name": fv.display_name,
                    "input_rp": fv.input_rp,
                    "min_rp": fv.min_rp,
                    "max_rp": fv.max_rp,
                    "status": fv.status,
                    "message": fv.message,
                }
                for fv in self.funding_validation
            ],
            "table_integrity": {
                "status": self.table_integrity_status,
                "missing_categories": self.table_integrity_missing,
            },
            "categories": [
                {
                    "canonical_name": c.canonical_name,
                    "found_in_table": c.found_in_table,
                    "table_name": c.table_name,
                    "actual_rp": c.actual_rp,
                    "actual_pct": c.actual_pct,
                    "max_pct": c.max_pct,
                    "status": c.status,
                    "message": c.message,
                }
                for c in self.categories
            ],
            "cross_check_bab4_vs_lampiran2": {
                "status": self.cross_check_status,
                "bab4_grand_total_rp": self.bab4_grand_total_rp,
                "lampiran2_grand_total_rp": self.lampiran2_grand_total_rp,
                "discrepancies": [
                    {
                        "canonical_name": d.canonical_name,
                        "bab4_rp": d.bab4_rp,
                        "lampiran2_rp": d.lampiran2_rp,
                        "delta_rp": d.delta_rp,
                    }
                    for d in self.cross_check_discrepancies
                ],
            },
            "relocation_advisory": {
                "items_above_threshold": [
                    {
                        "description": r.description,
                        "category": r.category,
                        "unit_price_rp": r.amount_rp,
                        "total_line_rp": r.total_rp,
                        "volume": r.volume,
                        "approx_page": r.approx_page,
                    }
                    for r in self.relocation_items
                ],
            },
            "prohibited_items_found": [
                {
                    "description": p.description,
                    "matched_keyword": p.matched_keyword,
                    "amount_rp": p.amount_rp,
                    "category": p.category,
                    "approx_page": p.approx_page,
                }
                for p in self.prohibited_items
            ],
            "messages": [{"level": m.level, "text": m.text} for m in self.messages],
        }


# ============================================================================
# BudgetAuditor
# ============================================================================


@dataclass
class FundingInput:
    """Input pendanaan dari user (form di /check/new)."""
    belmawa: int = 0
    university: int = 0
    external: int = 0

    @property
    def total(self) -> int:
        return self.belmawa + self.university + self.external


class BudgetAuditor:
    """
    Audit anggaran dokumen.

    Usage:
        parser = DocxParser('proposal.docx')
        rules = get_pkm_kc_budget_rules()
        result = BudgetAuditor(parser, rules).check()
        # dengan validasi input pendanaan dari form:
        result = BudgetAuditor(parser, rules, FundingInput(...)).check()
    """

    def __init__(
        self,
        parser: DocxParser,
        rules: BudgetRules,
        funding: Optional[FundingInput] = None,
    ):
        self.parser = parser
        self.rules = rules
        self.funding = funding

    def check(self) -> BudgetAuditResult:
        result = BudgetAuditResult(status="pass")

        if self.funding is not None:
            result.total_input_funding_rp = self.funding.total
            self._validate_funding_sources(result)

        # Parse tabel RAB Bab 4 dan Lampiran 2
        bab4 = self._find_and_parse_bab4()
        lamp2 = self._find_and_parse_lampiran2()
        if bab4:
            result.bab4_grand_total_rp = bab4.grand_total_rp
        if lamp2:
            result.lampiran2_grand_total_rp = lamp2.grand_total_rp

        # Lapis 2: Integritas tabel (semua kategori wajib ada)
        self._check_table_integrity(result, bab4)

        # Lapis 3: Validasi alokasi per kategori
        self._validate_category_allocation(result, bab4)

        # Lapis 4: Cross-check Bab 4 vs Lampiran 2
        if self.rules.cross_check.enabled:
            self._cross_check(result, bab4, lamp2)

        # Lapis 5: Rekomendasi relokasi item tunggal besar
        if self.rules.relocation_advisory.enabled and lamp2:
            self._scan_relocation(result, lamp2)

        # Lapis 6: Item terlarang
        if lamp2:
            self._scan_prohibited(result, lamp2)

        # Aggregate status
        self._finalize_status(result)

        return result

    # ------------------------------------------------------------------------
    # Lapis 1: Validasi sumber dana
    # ------------------------------------------------------------------------

    def _validate_funding_sources(self, result: BudgetAuditResult) -> None:
        for source_rule in self.rules.funding_sources:
            input_value = getattr(self.funding, source_rule.name, 0)

            # Cek zero_value_is_error (PT wajib > 0)
            if source_rule.zero_value_is_error and input_value == 0:
                fv = FundingValidationResult(
                    name=source_rule.name,
                    display_name=source_rule.display_name,
                    input_rp=input_value,
                    min_rp=source_rule.min_rp,
                    max_rp=source_rule.max_rp,
                    status="fail",
                    message=(
                        f"Dana {source_rule.display_name} wajib > Rp0 (minimal "
                        f"Rp{source_rule.min_rp:,}). Tidak diperkenankan Rp0."
                    ),
                )
                result.funding_validation.append(fv)
                continue

            # Validasi range
            if input_value < source_rule.min_rp:
                if not source_rule.mandatory and input_value == 0:
                    # Opsional & tidak diisi → pass
                    fv = FundingValidationResult(
                        name=source_rule.name,
                        display_name=source_rule.display_name,
                        input_rp=input_value,
                        min_rp=source_rule.min_rp,
                        max_rp=source_rule.max_rp,
                        status="pass",
                        message=f"Dana {source_rule.display_name} tidak diisi (opsional).",
                    )
                else:
                    fv = FundingValidationResult(
                        name=source_rule.name,
                        display_name=source_rule.display_name,
                        input_rp=input_value,
                        min_rp=source_rule.min_rp,
                        max_rp=source_rule.max_rp,
                        status="fail",
                        message=(
                            f"Dana {source_rule.display_name} Rp{input_value:,} "
                            f"di bawah minimum Rp{source_rule.min_rp:,}."
                        ),
                    )
            elif input_value > source_rule.max_rp:
                fv = FundingValidationResult(
                    name=source_rule.name,
                    display_name=source_rule.display_name,
                    input_rp=input_value,
                    min_rp=source_rule.min_rp,
                    max_rp=source_rule.max_rp,
                    status="fail",
                    message=(
                        f"Dana {source_rule.display_name} Rp{input_value:,} "
                        f"melebihi maksimum Rp{source_rule.max_rp:,}."
                    ),
                )
            else:
                fv = FundingValidationResult(
                    name=source_rule.name,
                    display_name=source_rule.display_name,
                    input_rp=input_value,
                    min_rp=source_rule.min_rp,
                    max_rp=source_rule.max_rp,
                    status="pass",
                    message=(
                        f"Dana {source_rule.display_name} Rp{input_value:,} "
                        f"dalam rentang yang diizinkan."
                    ),
                )
            result.funding_validation.append(fv)

    # ------------------------------------------------------------------------
    # Parse tabel
    # ------------------------------------------------------------------------

    def _find_and_parse_bab4(self) -> Optional[Bab4ParseResult]:
        for table in self.parser.tables:
            if is_bab4_rab_table(table):
                return parse_bab4_table(table)
        return None

    def _find_and_parse_lampiran2(self) -> Optional[Lampiran2ParseResult]:
        for table in self.parser.tables:
            if is_lampiran2_table(table):
                return parse_lampiran2_table(table)
        return None

    # ------------------------------------------------------------------------
    # Lapis 2: Integritas tabel — kolom kategori wajib utuh
    # ------------------------------------------------------------------------

    def _check_table_integrity(
        self,
        result: BudgetAuditResult,
        bab4: Optional[Bab4ParseResult],
    ) -> None:
        if bab4 is None:
            result.table_integrity_status = "fail"
            result.table_integrity_missing = [
                c.name for c in self.rules.categories if c.must_exist_in_table
            ]
            return

        # Map kategori dari tabel ke canonical
        found_canonical: set[str] = set()
        for cat_total in bab4.categories:
            canonical = match_category_to_canonical(
                cat_total.category_name, self.rules.categories
            )
            if canonical:
                found_canonical.add(canonical)

        missing: list[str] = []
        for cat in self.rules.categories:
            if cat.must_exist_in_table and cat.name not in found_canonical:
                missing.append(cat.name)

        if missing:
            result.table_integrity_status = "fail"
            result.table_integrity_missing = missing
        else:
            result.table_integrity_status = "pass"

    # ------------------------------------------------------------------------
    # Lapis 3: Validasi alokasi per kategori
    # ------------------------------------------------------------------------

    def _validate_category_allocation(
        self,
        result: BudgetAuditResult,
        bab4: Optional[Bab4ParseResult],
    ) -> None:
        if bab4 is None:
            for cat in self.rules.categories:
                result.categories.append(
                    CategoryAllocationResult(
                        canonical_name=cat.name,
                        found_in_table=False,
                        max_pct=cat.max_percentage,
                        status="missing",
                        message=f"Kategori '{cat.name}' tidak ada — tabel RAB tidak ditemukan.",
                    )
                )
            return

        # Total dari tabel Bab 4 (basis untuk hitung persentase)
        # Kalau grand_total kosong, hitung dari sum kategori
        denominator = bab4.grand_total_rp
        if not denominator:
            denominator = sum(c.total_rp for c in bab4.categories if c.total_rp)
        if not denominator or denominator == 0:
            denominator = 1  # avoid division by zero

        # Map: canonical → (table_name, total_rp)
        canonical_map: dict[str, tuple[str, Optional[int]]] = {}
        for cat_total in bab4.categories:
            canonical = match_category_to_canonical(
                cat_total.category_name, self.rules.categories
            )
            if canonical:
                canonical_map[canonical] = (cat_total.category_name, cat_total.total_rp)

        for cat in self.rules.categories:
            if cat.name not in canonical_map:
                # Sudah di-flag table_integrity, tapi kita tetap tambah entry
                result.categories.append(
                    CategoryAllocationResult(
                        canonical_name=cat.name,
                        found_in_table=False,
                        max_pct=cat.max_percentage,
                        status="missing",
                        message=f"Kategori '{cat.name}' tidak ditemukan di tabel RAB.",
                    )
                )
                continue

            table_name, actual_rp = canonical_map[cat.name]
            if actual_rp is None:
                result.categories.append(
                    CategoryAllocationResult(
                        canonical_name=cat.name,
                        found_in_table=True,
                        table_name=table_name,
                        max_pct=cat.max_percentage,
                        status="fail",
                        message=f"Kategori '{cat.name}' nilai tidak terbaca.",
                    )
                )
                continue

            actual_pct = (actual_rp / denominator) * 100.0
            if actual_pct > cat.max_percentage:
                result.categories.append(
                    CategoryAllocationResult(
                        canonical_name=cat.name,
                        found_in_table=True,
                        table_name=table_name,
                        actual_rp=actual_rp,
                        actual_pct=round(actual_pct, 2),
                        max_pct=cat.max_percentage,
                        status="fail",
                        message=(
                            f"Kategori '{cat.name}' = {actual_pct:.1f}% "
                            f"melebihi batas maks {cat.max_percentage}%."
                        ),
                    )
                )
            else:
                result.categories.append(
                    CategoryAllocationResult(
                        canonical_name=cat.name,
                        found_in_table=True,
                        table_name=table_name,
                        actual_rp=actual_rp,
                        actual_pct=round(actual_pct, 2),
                        max_pct=cat.max_percentage,
                        status="pass",
                        message=(
                            f"Kategori '{cat.name}' = {actual_pct:.1f}% "
                            f"(maks {cat.max_percentage}%)."
                        ),
                    )
                )

    # ------------------------------------------------------------------------
    # Lapis 4: Cross-check Bab 4 ↔ Lampiran 2
    # ------------------------------------------------------------------------

    def _cross_check(
        self,
        result: BudgetAuditResult,
        bab4: Optional[Bab4ParseResult],
        lamp2: Optional[Lampiran2ParseResult],
    ) -> None:
        if bab4 is None or lamp2 is None:
            result.cross_check_status = "skipped"
            return

        tol = self.rules.cross_check.tolerance_rupiah

        # Map per kategori canonical
        bab4_map: dict[str, Optional[int]] = {}
        for c in bab4.categories:
            canonical = match_category_to_canonical(c.category_name, self.rules.categories)
            if canonical:
                bab4_map[canonical] = c.total_rp

        lamp2_map: dict[str, Optional[int]] = {}
        for c in lamp2.categories:
            canonical = match_category_to_canonical(c.category_name, self.rules.categories)
            if canonical:
                lamp2_map[canonical] = c.total_rp

        # Bandingkan tiap canonical
        all_canonicals = set(bab4_map.keys()) | set(lamp2_map.keys())
        for canonical in sorted(all_canonicals):
            b = bab4_map.get(canonical)
            l = lamp2_map.get(canonical)
            if b is None or l is None:
                continue
            delta = abs(b - l)
            if delta > tol:
                result.cross_check_discrepancies.append(
                    CrossCheckDiscrepancy(
                        canonical_name=canonical,
                        bab4_rp=b,
                        lampiran2_rp=l,
                        delta_rp=delta,
                    )
                )

        # Cek grand total
        if (
            bab4.grand_total_rp is not None
            and lamp2.grand_total_rp is not None
            and abs(bab4.grand_total_rp - lamp2.grand_total_rp) > tol
        ):
            result.cross_check_discrepancies.append(
                CrossCheckDiscrepancy(
                    canonical_name="GRAND_TOTAL",
                    bab4_rp=bab4.grand_total_rp,
                    lampiran2_rp=lamp2.grand_total_rp,
                    delta_rp=abs(bab4.grand_total_rp - lamp2.grand_total_rp),
                )
            )

        result.cross_check_status = (
            "fail" if result.cross_check_discrepancies else "pass"
        )

    # ------------------------------------------------------------------------
    # Lapis 5: Rekomendasi relokasi
    # ------------------------------------------------------------------------

    def _scan_relocation(
        self, result: BudgetAuditResult, lamp2: Lampiran2ParseResult
    ) -> None:
        """
        Patokan Rp1jt (atau dari rules) pada **harga satuan**, bukan total nilai baris.
        Baris tanpa harga satuan terbaca → tidak diberi saran relokasi berbasis patokan ini.
        """
        threshold = self.rules.relocation_advisory.threshold_rp
        for item in lamp2.items:
            unit = item.unit_price
            if unit is None or unit <= threshold:
                continue
            page: Optional[int] = None
            if item.table_index >= 0 and item.row_index >= 0:
                page = self.parser.estimate_page_for_table_cell(
                    item.table_index, item.row_index, 0
                )
            result.relocation_items.append(
                RelocationItem(
                    description=item.description,
                    category=item.category,
                    amount_rp=unit,
                    total_rp=item.total_rp,
                    volume=item.volume,
                    approx_page=page,
                )
            )

    # ------------------------------------------------------------------------
    # Lapis 6: Item terlarang
    # ------------------------------------------------------------------------

    def _scan_prohibited(
        self, result: BudgetAuditResult, lamp2: Lampiran2ParseResult
    ) -> None:
        prohibited_lower = [(p, p.lower()) for p in self.rules.prohibited_items]
        for item in lamp2.items:
            desc_lower = item.description.lower()
            for original, lower in prohibited_lower:
                if lower in desc_lower:
                    page: Optional[int] = None
                    if item.table_index >= 0 and item.row_index >= 0:
                        page = self.parser.estimate_page_for_table_cell(
                            item.table_index, item.row_index, 0
                        )
                    result.prohibited_items.append(
                        ProhibitedItemFinding(
                            description=item.description,
                            matched_keyword=original,
                            amount_rp=item.total_rp,
                            category=item.category,
                            approx_page=page,
                        )
                    )
                    break  # Satu match per item cukup

    # ------------------------------------------------------------------------
    # Finalize status & messages
    # ------------------------------------------------------------------------

    def _finalize_status(self, result: BudgetAuditResult) -> None:
        # Collect all sub-statuses
        has_fail = False
        has_warning = False

        # Funding
        for fv in result.funding_validation:
            if fv.status == "fail":
                has_fail = True
                result.messages.append(CheckMessage(level="fail", text=fv.message))
            else:
                result.messages.append(CheckMessage(level="pass", text=fv.message))

        # Table integrity
        if result.table_integrity_status == "fail":
            has_fail = True
            result.messages.append(
                CheckMessage(
                    level="fail",
                    text=(
                        f"Integritas tabel RAB: kategori hilang/dihapus: "
                        f"{', '.join(result.table_integrity_missing)}. "
                        f"Kolom kategori wajib utuh meskipun nilainya Rp0."
                    ),
                )
            )

        # Categories
        for c in result.categories:
            if c.status == "fail":
                has_fail = True
                result.messages.append(CheckMessage(level="fail", text=c.message))
            elif c.status == "missing":
                # Sudah di-cover di table_integrity, skip duplikat
                pass

        # Cross-check
        if result.cross_check_status == "fail":
            has_fail = True
            for d in result.cross_check_discrepancies:
                result.messages.append(
                    CheckMessage(
                        level="fail",
                        text=(
                            f"Cross-check Bab 4 ↔ Lampiran 2 untuk "
                            f"'{d.canonical_name}': Bab 4 = Rp{d.bab4_rp:,}, "
                            f"Lampiran 2 = Rp{d.lampiran2_rp:,}, selisih "
                            f"Rp{d.delta_rp:,}."
                        ),
                    )
                )

        # Relocation advisory
        if result.relocation_items:
            has_warning = True
            thr = self.rules.relocation_advisory.threshold_rp
            for r in result.relocation_items:
                loc = (
                    f"[Halaman ~{r.approx_page}] "
                    if r.approx_page is not None
                    else ""
                )
                vol_txt = f"Volume: {r.volume}. " if r.volume else ""
                total_txt = (
                    f"Nilai baris: Rp{r.total_rp:,}. "
                    if r.total_rp is not None
                    else ""
                )
                result.messages.append(
                    CheckMessage(
                        level="warning",
                        text=(
                            f"{loc}Saran relokasi / pecah justifikasi: '{r.description}' — "
                            f"harga satuan Rp{r.amount_rp:,} melebihi patokan Rp{thr:,} per satuan. "
                            f"{vol_txt}{total_txt}"
                            f"Pertimbangkan memecah menjadi beberapa item pos atau menyesuaikan volume dan harga satuan "
                            f"agar justifikasi jenis pengeluaran sesuai aturan (saran, bukan error)."
                        ),
                    )
                )

        # Prohibited items
        if result.prohibited_items:
            has_fail = True
            for p in result.prohibited_items:
                loc = (
                    f"[Halaman ~{p.approx_page}] "
                    if p.approx_page is not None
                    else ""
                )
                result.messages.append(
                    CheckMessage(
                        level="fail",
                        text=(
                            f"{loc}Item TERLARANG: '{p.description}' "
                            f"({'Rp' + format(p.amount_rp, ',') if p.amount_rp else 'nilai tidak terbaca'}) "
                            f"— mengandung kata kunci '{p.matched_keyword}' yang dilarang "
                            f"di {self.rules.competition_code}-{self.rules.schema_code}."
                        ),
                    )
                )

        # Set overall status
        if has_fail:
            result.status = "fail"
        elif has_warning:
            result.status = "warning"
        else:
            result.status = "pass"