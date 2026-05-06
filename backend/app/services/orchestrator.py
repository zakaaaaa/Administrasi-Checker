"""
Orchestrator — panggil 7 checker secara berurutan untuk satu submission.

Sementara hanya support PKM-KC Proposal. Skema lain → raise UnsupportedSchemaError.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.services.docx_parser import DocxParser
from app.services.schema_rules import get_pkm_kc_proposal_rules
from app.services.budget_rules import get_pkm_kc_budget_rules
from app.services.structure_checker import StructureChecker
from app.services.physical_sheet_counter import PhysicalSheetCounter
from app.services.format_checker import FormatChecker
from app.services.page_numbering_checker import PageNumberingChecker
from app.services.budget_auditor import BudgetAuditor, FundingInput
from app.services.reference_validator import ReferenceValidator


class UnsupportedSchemaError(ValueError):
    pass


@dataclass
class CheckRequest:
    docx_path: str
    competition: str   # "PKM"
    report_type: str   # "PROPOSAL"
    schema_code: str   # "PKM-KC"
    funding_belmawa: int
    funding_pt: int
    funding_external: int


def run_all_checks(req: CheckRequest) -> dict[str, Any]:
    """
    Jalankan 7 checker, return dict per modul + overall_status.

    Raises:
        UnsupportedSchemaError: jika kombinasi competition/report/schema belum di-support
        FileNotFoundError: jika docx_path tidak ada
        Exception: error lain dari checker (bubble up ke caller)
    """
    # Validasi kombinasi
    if (req.competition, req.report_type, req.schema_code) != ("PKM", "PROPOSAL", "PKM-KC"):
        raise UnsupportedSchemaError(
            f"Belum di-support: {req.competition}/{req.report_type}/{req.schema_code}. "
            "Saat ini hanya PKM/PROPOSAL/PKM-KC."
        )

    docx_path = Path(req.docx_path)
    if not docx_path.exists():
        raise FileNotFoundError(f"File tidak ditemukan: {docx_path}")

    # Setup
    parser = DocxParser(str(docx_path))
    schema = get_pkm_kc_proposal_rules()
    budget_rules = get_pkm_kc_budget_rules()
    funding = FundingInput(
        belmawa=req.funding_belmawa,
        university=req.funding_pt,
        external=req.funding_external,
    )

    results: dict[str, Any] = {}
    statuses: list[str] = []

    # 1. Structure
    try:
        r = StructureChecker(parser, schema).check()
        results["structure"] = r.to_dict()
        statuses.append(_extract_status(results["structure"]))
    except Exception as e:
        results["structure"] = {"status": "error", "message": str(e)}
        statuses.append("error")

    # 2. Physical Sheet
    try:
        r = PhysicalSheetCounter(parser, schema).check()
        results["physical_sheet"] = r.to_dict()
        statuses.append(_extract_status(results["physical_sheet"]))
    except Exception as e:
        results["physical_sheet"] = {"status": "error", "message": str(e)}
        statuses.append("error")

    # 3. Format
    try:
        r = FormatChecker(parser, schema=schema).check()
        results["format"] = r.to_dict()
        statuses.append(_extract_status(results["format"]))
    except Exception as e:
        results["format"] = {"status": "error", "message": str(e)}
        statuses.append("error")

    # 4. Page Numbering
    try:
        r = PageNumberingChecker(parser, schema).check()
        results["page_numbering"] = r.to_dict()
        statuses.append(_extract_status(results["page_numbering"]))
    except Exception as e:
        results["page_numbering"] = {"status": "error", "message": str(e)}
        statuses.append("error")

    # 5. Budget
    try:
        r = BudgetAuditor(parser, budget_rules, funding).check()
        results["budget"] = r.to_dict()
        statuses.append(_extract_status(results["budget"]))
    except Exception as e:
        results["budget"] = {"status": "error", "message": str(e)}
        statuses.append("error")

    # 6. Reference
    try:
        r = ReferenceValidator(parser, schema).check()
        results["reference"] = r.to_dict()
        statuses.append(_extract_status(results["reference"]))
    except Exception as e:
        results["reference"] = {"status": "error", "message": str(e)}
        statuses.append("error")

    results["overall_status"] = _aggregate_status(statuses)
    return results


def _extract_status(d: dict) -> str:
    """Ambil 'status' dari dict; default 'unknown'."""
    s = d.get("status", "unknown")
    return s if isinstance(s, str) else "unknown"


def _aggregate_status(statuses: list[str]) -> str:
    """fail kalau ada fail/error; warning kalau ada warning; pass kalau semua pass."""
    if any(s in ("fail", "error") for s in statuses):
        return "fail"
    if any(s == "warning" for s in statuses):
        return "warning"
    return "pass"
