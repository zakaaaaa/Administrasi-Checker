"""
Orchestrator — jalankan checker per skema lewat registry.

Registry memetakan (competition, report_type, schema_code) ke konfigurasi yang
menentukan: factory SchemaRules, factory budget rules (opsional), factory
page-numbering rules, dan urutan modul yang dijalankan. Tiap skema bebas
mengaktifkan subset modul (mis. PKM-AI: tanpa budget & reference).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

from app.services.checkers.format_checker import FormatChecker
from app.services.checkers.page_numbering_checker import (
    PageNumberingChecker,
    PageNumberingRules,
)
from app.services.checkers.physical_sheet_counter import PhysicalSheetCounter
from app.services.checkers.reference_validator import ReferenceValidator
from app.services.checkers.structure_checker import StructureChecker
from app.services.core.base_rules import FormatRules, SchemaRules
from app.services.core.docx_parser import DocxParser
from app.services.schemas.pkm_ai.ai_content_checker import AiContentChecker
from app.services.schemas.pkm_ai.ai_format_checker import AiFormatChecker
from app.services.schemas.pkm_ai.rules import (
    get_pkm_ai_article_rules,
    get_pkm_ai_page_numbering_rules,
)
from app.services.schemas.pkm_kc.budget_auditor import BudgetAuditor
from app.services.schemas.pkm_kc.budget_rules import (
    BudgetRules,
    get_pkm_kc_budget_rules,
)
from app.services.schemas.pkm_kc.rules import (
    get_pkm_kc_proposal_rules,
    get_pkm_page_numbering_rules,
)


# ============================================================================
# Error & request
# ============================================================================


class UnsupportedSchemaError(ValueError):
    pass


@dataclass
class CheckRequest:
    docx_path: str
    competition: str   # mis. "PKM"
    report_type: str   # mis. "PROPOSAL" / "SCIENTIFIC_ARTICLE"
    schema_code: str   # mis. "PKM-KC" / "PKM-AI"


def _module_error_payload(exc: BaseException) -> dict[str, Any]:
    """Payload konsisten untuk UI: status error + messages (bukan hanya `message`)."""
    msg = str(exc)
    return {
        "status": "error",
        "message": msg,
        "messages": [{"level": "error", "text": msg}],
    }


# ============================================================================
# Registry config
# ============================================================================


# Module key — dipakai sebagai key di response JSON `results` dan kolom DB.
ALL_MODULES = (
    "structure",
    "physical_sheet",
    "format",
    "page_numbering",
    "budget",
    "reference",
)

# Modul yang dipakai PKM-KC (semua kecuali AI-specific).
PKM_KC_MODULES = ALL_MODULES

# Modul yang dipakai PKM-AI: 4 core + reference + 2 AI-specific (tanpa budget).
PKM_AI_MODULES = (
    "structure",
    "physical_sheet",
    "format",
    "page_numbering",
    "reference",
    "ai_content",
    "ai_format",
)


@dataclass
class SchemaConfig:
    """Konfigurasi satu skema di registry."""
    schema_rules_factory: Callable[[], SchemaRules]
    modules: tuple[str, ...]
    budget_rules_factory: Optional[Callable[[], BudgetRules]] = None
    page_numbering_rules_factory: Optional[Callable[[], PageNumberingRules]] = None
    # Optional override untuk FormatChecker. `format_checks=None` = jalankan
    # semua sub-check (default, PKM-KC). Set = whitelist sub-check yang aktif
    # (mis. PKM-AI hanya {"paper_size","margin"} karena sisanya divalidasi
    # AiFormatChecker dengan aturan per-zona).
    format_rules_factory: Optional[Callable[[], FormatRules]] = None
    format_checks: Optional[tuple[str, ...]] = None


# Key = (competition, report_type, schema_code) — sesuai field di CheckRequest.
SCHEMA_REGISTRY: dict[tuple[str, str, str], SchemaConfig] = {
    ("PKM", "PROPOSAL", "PKM-KC"): SchemaConfig(
        schema_rules_factory=get_pkm_kc_proposal_rules,
        modules=PKM_KC_MODULES,
        budget_rules_factory=get_pkm_kc_budget_rules,
        page_numbering_rules_factory=get_pkm_page_numbering_rules,
    ),
    ("PKM", "SCIENTIFIC_ARTICLE", "PKM-AI"): SchemaConfig(
        schema_rules_factory=get_pkm_ai_article_rules,
        modules=PKM_AI_MODULES,
        budget_rules_factory=None,  # PKM-AI tanpa RAB
        page_numbering_rules_factory=get_pkm_ai_page_numbering_rules,
        format_checks=("paper_size", "margin"),  # sisanya: AiFormatChecker
    ),
}


def get_schema_config(req: CheckRequest) -> SchemaConfig:
    key = (req.competition, req.report_type, req.schema_code)
    cfg = SCHEMA_REGISTRY.get(key)
    if cfg is None:
        supported = ", ".join(
            f"{c}/{r}/{s}" for (c, r, s) in SCHEMA_REGISTRY.keys()
        )
        raise UnsupportedSchemaError(
            f"Belum di-support: {req.competition}/{req.report_type}/"
            f"{req.schema_code}. Saat ini hanya: {supported}."
        )
    return cfg


# ============================================================================
# Module runners
# ============================================================================


def _run_structure(parser: DocxParser, schema: SchemaRules, cfg: SchemaConfig) -> dict:
    return StructureChecker(parser, schema).check().to_dict()


def _run_physical_sheet(parser: DocxParser, schema: SchemaRules, cfg: SchemaConfig) -> dict:
    return PhysicalSheetCounter(parser, schema).check().to_dict()


def _run_format(parser: DocxParser, schema: SchemaRules, cfg: SchemaConfig) -> dict:
    rules = cfg.format_rules_factory() if cfg.format_rules_factory else None
    checks = set(cfg.format_checks) if cfg.format_checks else None
    return FormatChecker(
        parser,
        rules=rules,
        schema=schema,
        enabled_checks=checks,
    ).check().to_dict()


def _run_page_numbering(parser: DocxParser, schema: SchemaRules, cfg: SchemaConfig) -> dict:
    rules = (
        cfg.page_numbering_rules_factory()
        if cfg.page_numbering_rules_factory is not None
        else None
    )
    return PageNumberingChecker(parser, schema, rules=rules).check().to_dict()


def _run_budget(parser: DocxParser, schema: SchemaRules, cfg: SchemaConfig) -> dict:
    if cfg.budget_rules_factory is None:
        raise RuntimeError(
            "Module 'budget' aktif tapi tidak ada budget_rules_factory di registry."
        )
    budget_rules = cfg.budget_rules_factory()
    return BudgetAuditor(parser, budget_rules).check().to_dict()


def _run_reference(parser: DocxParser, schema: SchemaRules, cfg: SchemaConfig) -> dict:
    return ReferenceValidator(
        parser,
        schema,
        recent_threshold_years=schema.recent_threshold_years,
        minimum_recommended_recent=schema.min_recent_references,
    ).check().to_dict()


def _run_ai_content(parser: DocxParser, schema: SchemaRules, cfg: SchemaConfig) -> dict:
    return AiContentChecker(parser, schema).check().to_dict()


def _run_ai_format(parser: DocxParser, schema: SchemaRules, cfg: SchemaConfig) -> dict:
    return AiFormatChecker(parser, schema).check().to_dict()


MODULE_RUNNERS: dict[str, Callable[[DocxParser, SchemaRules, SchemaConfig], dict]] = {
    "structure": _run_structure,
    "physical_sheet": _run_physical_sheet,
    "format": _run_format,
    "page_numbering": _run_page_numbering,
    "budget": _run_budget,
    "reference": _run_reference,
    "ai_content": _run_ai_content,
    "ai_format": _run_ai_format,
}


# ============================================================================
# Entry point
# ============================================================================


def run_all_checks(req: CheckRequest) -> dict[str, Any]:
    """
    Jalankan semua modul yang terdaftar di SchemaConfig untuk skema yang diminta.

    Return dict berisi:
        - key per modul yang dijalankan (mis. 'structure', 'physical_sheet')
        - 'overall_status': agregasi dari semua modul

    Modul yang TIDAK di-list di SchemaConfig.modules tidak muncul di hasil
    (caller bertanggung jawab handle key yang absent).

    Raises:
        UnsupportedSchemaError: jika kombinasi competition/report/schema belum
            terdaftar.
        FileNotFoundError: jika docx_path tidak ada.
    """
    cfg = get_schema_config(req)

    docx_path = Path(req.docx_path)
    if not docx_path.exists():
        raise FileNotFoundError(f"File tidak ditemukan: {docx_path}")

    parser = DocxParser(str(docx_path))
    schema = cfg.schema_rules_factory()

    results: dict[str, Any] = {}
    statuses: list[str] = []

    for module_key in cfg.modules:
        runner = MODULE_RUNNERS.get(module_key)
        if runner is None:
            results[module_key] = _module_error_payload(
                RuntimeError(f"Module '{module_key}' tidak dikenal di runner registry.")
            )
            statuses.append("error")
            continue
        try:
            payload = runner(parser, schema, cfg)
            results[module_key] = payload
            statuses.append(_extract_status(payload))
        except Exception as e:
            results[module_key] = _module_error_payload(e)
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
