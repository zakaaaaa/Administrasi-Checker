"""
Orchestrator — panggil 7 checker secara berurutan untuk satu submission.

Sementara hanya support PKM-KC Proposal. Skema lain → raise UnsupportedSchemaError.
"""
from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from app.services.docx_parser import DocxParser
from app.services.schema_rules import get_pkm_kc_proposal_rules, get_pkm_ai_proposal_rules, get_pkm_vgk_proposal_rules
from app.services.budget_rules import get_pkm_kc_budget_rules, get_pkm_vgk_budget_rules
from app.services.structure_checker import StructureChecker
from app.services.physical_sheet_counter import PhysicalSheetCounter, PhysicalSheetResult
from app.services.format_checker import FormatChecker, get_pkm_ai_format_rules
from app.services.pkm_ai_format_checker import PkmAiFormatChecker
from app.services.page_numbering_checker import PageNumberingChecker, get_pkm_ai_page_numbering_rules
from app.services.budget_auditor import BudgetAuditor
from app.services.reference_validator import ReferenceValidator
from app.services.luaran_checker import LuaranChecker
from app.services.lampiran_checker import LampiranChecker
from app.services.biodata_date_checker import BiodataDateChecker
from app.services.schedule_checker import ScheduleChecker
from app.services.similarity_checker import SimilarityChecker
from app.services.lampiran_index import LampiranOcrIndex


class UnsupportedSchemaError(ValueError):
    pass


def _find_core_start_idx(structure_result) -> Optional[int]:
    """Return paragraph index section inti pertama (Bab 1), atau None."""
    if structure_result is None:
        return None
    core_found = [s for s in structure_result.found_sections if s.is_core]
    if not core_found:
        return None
    return min(s.paragraph_index for s in core_found)


def _load_pdf_sheet_texts(physical_result: PhysicalSheetResult) -> Optional[list[str]]:
    """Baca teks per lembar dari PDF hasil konversi PhysicalSheetCounter."""
    if not physical_result.pdf_path:
        return None
    try:
        from pypdf import PdfReader
        reader = PdfReader(physical_result.pdf_path)
        texts: list[str] = []
        for page in reader.pages:
            try:
                texts.append(page.extract_text() or "")
            except Exception:
                texts.append("")
        return texts
    except Exception:
        return None


def _module_error_payload(exc: BaseException) -> dict[str, Any]:
    """Payload konsisten untuk UI: status error + messages (bukan hanya `message`)."""
    msg = str(exc)
    return {
        "status": "error",
        "message": msg,
        "messages": [{"level": "error", "text": msg}],
    }


_log = logging.getLogger(__name__)
_TIMING_ENABLED = os.environ.get("CHECK_TIMING", "1").lower() not in ("0", "false", "no", "")


def _log_timing(key: str, t0: float, sink: dict[str, float] | None = None) -> None:
    """Catat & log durasi satu checker (instrumentasi Fase 0). Aktif kecuali CHECK_TIMING=0."""
    dt = time.perf_counter() - t0
    if sink is not None:
        sink[key] = round(dt, 3)
    if _TIMING_ENABLED:
        msg = f"[timing] {key}: {dt:.2f}s"
        _log.info(msg)
        print(msg, flush=True)


@dataclass
class CheckRequest:
    docx_path: str
    competition: str   # "PKM"
    report_type: str   # "PROPOSAL"
    schema_code: str   # "PKM-KC"


def run_all_checks(req: CheckRequest) -> dict[str, Any]:
    """
    Jalankan 7 checker, return dict per modul + overall_status.

    Raises:
        UnsupportedSchemaError: jika kombinasi competition/report/schema belum di-support
        FileNotFoundError: jika docx_path tidak ada
        Exception: error lain dari checker (bubble up ke caller)
    """
    docx_path = Path(req.docx_path)
    if not docx_path.exists():
        raise FileNotFoundError(f"File tidak ditemukan: {docx_path}")

    parser = DocxParser(str(docx_path))
    key = (req.competition, req.report_type, req.schema_code)

    if key == ("PKM", "PROPOSAL", "PKM-KC"):
        return _run_pkm_kc(parser)
    elif key == ("PKM", "PROPOSAL", "PKM-VGK"):
        return _run_pkm_vgk(parser)
    elif key == ("PKM", "SCIENTIFIC_ARTICLE", "PKM-AI"):
        return _run_pkm_ai(parser)
    else:
        raise UnsupportedSchemaError(
            f"Belum di-support: {req.competition}/{req.report_type}/{req.schema_code}. "
            "Skema yang tersedia: PKM/PROPOSAL/PKM-KC, PKM/PROPOSAL/PKM-VGK, PKM/SCIENTIFIC_ARTICLE/PKM-AI."
        )


# ============================================================================
# Runner PKM-KC
# ============================================================================


def _run_pkm_kc(parser: DocxParser) -> dict[str, Any]:
    schema = get_pkm_kc_proposal_rules()
    budget_rules = get_pkm_kc_budget_rules()
    results: dict[str, Any] = {}
    statuses: list[str] = []
    timings: dict[str, float] = {}

    # 1. Structure
    structure_result = None
    _t0 = time.perf_counter()
    try:
        structure_result = StructureChecker(parser, schema).check()
        results["structure"] = structure_result.to_dict()
        statuses.append(_extract_status(results["structure"]))
    except Exception as e:
        results["structure"] = _module_error_payload(e)
        statuses.append("error")
    _log_timing("structure", _t0, timings)

    # 2. Physical Sheet (termasuk konversi docx→PDF via LibreOffice)
    _physical_result = None
    _t0 = time.perf_counter()
    try:
        _physical_result = PhysicalSheetCounter(parser, schema).check()
        results["physical_sheet"] = _physical_result.to_dict()
        statuses.append(_extract_status(results["physical_sheet"]))
    except Exception as e:
        results["physical_sheet"] = _module_error_payload(e)
        statuses.append("error")
    _log_timing("physical_sheet", _t0, timings)

    # 3. Format (bagian inti: Bab 1 s.d. sebelum Lampiran)
    _t0 = time.perf_counter()
    try:
        _pdf_texts = _load_pdf_sheet_texts(_physical_result) if _physical_result else None
        r = FormatChecker(parser, schema=schema, pdf_sheet_texts=_pdf_texts).check(
            start_para_idx=_find_core_start_idx(structure_result)
        )
        results["format"] = r.to_dict()
        statuses.append(_extract_status(results["format"]))
    except Exception as e:
        results["format"] = _module_error_payload(e)
        statuses.append("error")
    _log_timing("format", _t0, timings)

    # 4. Page Numbering
    _t0 = time.perf_counter()
    try:
        r = PageNumberingChecker(parser, schema).check()
        results["page_numbering"] = r.to_dict()
        statuses.append(_extract_status(results["page_numbering"]))
    except Exception as e:
        results["page_numbering"] = _module_error_payload(e)
        statuses.append("error")
    _log_timing("page_numbering", _t0, timings)

    # 5. Budget
    _t0 = time.perf_counter()
    try:
        r = BudgetAuditor(parser, budget_rules).check()
        results["budget"] = r.to_dict()
        statuses.append(_extract_status(results["budget"]))
    except Exception as e:
        results["budget"] = _module_error_payload(e)
        statuses.append("error")
    _log_timing("budget", _t0, timings)

    # 6. Reference
    _t0 = time.perf_counter()
    try:
        r = ReferenceValidator(parser, schema).check()
        results["reference"] = r.to_dict()
        statuses.append(_extract_status(results["reference"]))
    except Exception as e:
        results["reference"] = _module_error_payload(e)
        statuses.append("error")
    _log_timing("reference", _t0, timings)

    # 7. Luaran (khusus PKM-KC)
    _t0 = time.perf_counter()
    try:
        r = LuaranChecker.for_pkm_kc(parser).check()
        results["luaran"] = r.to_dict()
        statuses.append(_extract_status(results["luaran"]))
    except Exception as e:
        results["luaran"] = _module_error_payload(e)
        statuses.append("error")
    _log_timing("luaran", _t0, timings)

    # Index Lampiran bersama: cache OCR per-gambar dipakai lampiran + biodata_date
    # (tiap gambar di-OCR maksimal sekali untuk kedua checker).
    lampiran_index = LampiranOcrIndex(parser)

    # 8. Lampiran (khusus PKM-KC) — OCR scoped (segment belum teridentifikasi)
    _t0 = time.perf_counter()
    try:
        r = LampiranChecker.for_pkm_kc(parser).check(index=lampiran_index)
        results["lampiran"] = r.to_dict()
        statuses.append(_extract_status(results["lampiran"]))
    except Exception as e:
        results["lampiran"] = _module_error_payload(e)
        statuses.append("error")
    _log_timing("lampiran", _t0, timings)

    # 9. Tanggal biodata (khusus PKM-KC) — OCR scoped (biodata + surat pernyataan), reuse cache
    _t0 = time.perf_counter()
    try:
        r = BiodataDateChecker.for_pkm_kc(parser).check(index=lampiran_index)
        results["biodata_date"] = r.to_dict()
        statuses.append(_extract_status(results["biodata_date"]))
    except Exception as e:
        results["biodata_date"] = _module_error_payload(e)
        statuses.append("error")
    _log_timing("biodata_date", _t0, timings)

    # 10. Jadwal kegiatan (khusus PKM-KC)
    _t0 = time.perf_counter()
    try:
        r = ScheduleChecker.for_pkm_kc(parser).check()
        results["schedule"] = r.to_dict()
        statuses.append(_extract_status(results["schedule"]))
    except Exception as e:
        results["schedule"] = _module_error_payload(e)
        statuses.append("error")
    _log_timing("schedule", _t0, timings)

    # 11. Hasil uji similaritas ≤ 25% (khusus PKM-KC) — OCR gambar similaritas
    _t0 = time.perf_counter()
    try:
        r = SimilarityChecker.for_pkm_kc(parser).check()
        results["similarity"] = r.to_dict()
        statuses.append(_extract_status(results["similarity"]))
    except Exception as e:
        results["similarity"] = _module_error_payload(e)
        statuses.append("error")
    _log_timing("similarity", _t0, timings)

    results["_timings"] = {**timings, "total": round(sum(timings.values()), 3)}
    if _TIMING_ENABLED:
        print(f"[timing] TOTAL PKM-KC: {results['_timings']['total']:.2f}s", flush=True)
    results["overall_status"] = _aggregate_status(statuses)
    return results


# ============================================================================
# Runner PKM-VGK
# ============================================================================


def _run_pkm_vgk(parser: DocxParser) -> dict[str, Any]:
    schema = get_pkm_vgk_proposal_rules()
    budget_rules = get_pkm_vgk_budget_rules()
    results: dict[str, Any] = {}
    statuses: list[str] = []

    # 1. Structure
    structure_result = None
    try:
        structure_result = StructureChecker(parser, schema).check()
        results["structure"] = structure_result.to_dict()
        statuses.append(_extract_status(results["structure"]))
    except Exception as e:
        results["structure"] = _module_error_payload(e)
        statuses.append("error")

    # 2. Physical Sheet
    _physical_result = None
    try:
        _physical_result = PhysicalSheetCounter(parser, schema).check()
        results["physical_sheet"] = _physical_result.to_dict()
        statuses.append(_extract_status(results["physical_sheet"]))
    except Exception as e:
        results["physical_sheet"] = _module_error_payload(e)
        statuses.append("error")

    # 3. Format (bagian inti: Bab 1 s.d. sebelum Lampiran)
    try:
        _pdf_texts = _load_pdf_sheet_texts(_physical_result) if _physical_result else None
        r = FormatChecker(parser, schema=schema, pdf_sheet_texts=_pdf_texts).check(
            start_para_idx=_find_core_start_idx(structure_result)
        )
        results["format"] = r.to_dict()
        statuses.append(_extract_status(results["format"]))
    except Exception as e:
        results["format"] = _module_error_payload(e)
        statuses.append("error")

    # 4. Page Numbering
    try:
        r = PageNumberingChecker(parser, schema).check()
        results["page_numbering"] = r.to_dict()
        statuses.append(_extract_status(results["page_numbering"]))
    except Exception as e:
        results["page_numbering"] = _module_error_payload(e)
        statuses.append("error")

    # 5. Budget
    try:
        r = BudgetAuditor(parser, budget_rules).check()
        results["budget"] = r.to_dict()
        statuses.append(_extract_status(results["budget"]))
    except Exception as e:
        results["budget"] = _module_error_payload(e)
        statuses.append("error")

    # 6. Reference
    try:
        r = ReferenceValidator(parser, schema).check()
        results["reference"] = r.to_dict()
        statuses.append(_extract_status(results["reference"]))
    except Exception as e:
        results["reference"] = _module_error_payload(e)
        statuses.append("error")

    # 7. Luaran (khusus PKM-VGK)
    try:
        r = LuaranChecker.for_pkm_vgk(parser).check()
        results["luaran"] = r.to_dict()
        statuses.append(_extract_status(results["luaran"]))
    except Exception as e:
        results["luaran"] = _module_error_payload(e)
        statuses.append("error")

    results["overall_status"] = _aggregate_status(statuses)
    return results


# ============================================================================
# Runner PKM-AI
# ============================================================================


def _run_pkm_ai(parser: DocxParser) -> dict[str, Any]:
    schema = get_pkm_ai_proposal_rules()
    results: dict[str, Any] = {}
    statuses: list[str] = []

    # 1. Structure
    try:
        r = StructureChecker(parser, schema).check()
        results["structure"] = r.to_dict()
        statuses.append(_extract_status(results["structure"]))
    except Exception as e:
        results["structure"] = _module_error_payload(e)
        statuses.append("error")

    # 2. Physical Sheet (8–15 halaman, ditangani via SHEET_COUNT_RULES)
    _physical_result = None
    try:
        _physical_result = PhysicalSheetCounter(parser, schema).check()
        results["physical_sheet"] = _physical_result.to_dict()
        statuses.append(_extract_status(results["physical_sheet"]))
    except Exception as e:
        results["physical_sheet"] = _module_error_payload(e)
        statuses.append("error")

    # 3a. Format front matter (judul, penulis, abstrak) — khusus PKM-AI
    ai_format_status = "pass"
    try:
        ai_fmt = PkmAiFormatChecker(parser, schema).check()
        results["ai_front_matter"] = ai_fmt.to_dict()
        ai_format_status = _extract_status(results["ai_front_matter"])
        statuses.append(ai_format_status)
    except Exception as e:
        results["ai_front_matter"] = _module_error_payload(e)
        statuses.append("error")

    # 3b. Format body (mulai BAB 1, stop sebelum Lampiran)
    try:
        import re as _re
        _pendahuluan_re = _re.compile(r"^\s*(?:Pendahuluan|PENDAHULUAN)\s*$", _re.IGNORECASE)
        bab1_idx = next(
            (p.index for p in parser.paragraphs if _pendahuluan_re.match(p.text.strip())),
            None,
        )
        _pdf_texts = _load_pdf_sheet_texts(_physical_result) if _physical_result else None
        r = FormatChecker(parser, rules=get_pkm_ai_format_rules(), schema=schema, pdf_sheet_texts=_pdf_texts).check(start_para_idx=bab1_idx)
        results["format"] = r.to_dict()
        statuses.append(_extract_status(results["format"]))
    except Exception as e:
        results["format"] = _module_error_payload(e)
        statuses.append("error")

    # 4. Page Numbering (PKM-AI: semua halaman arabic di atas kanan)
    try:
        r = PageNumberingChecker(parser, schema, rules=get_pkm_ai_page_numbering_rules()).check()
        results["page_numbering"] = r.to_dict()
        statuses.append(_extract_status(results["page_numbering"]))
    except Exception as e:
        results["page_numbering"] = _module_error_payload(e)
        statuses.append("error")

    # 5. Budget — tidak ada di PKM-AI
    results["budget"] = {
        "status": "pass",
        "messages": [{"level": "pass", "text": "Anggaran biaya tidak diperlukan untuk PKM-AI."}],
    }
    statuses.append("pass")

    # 6. Reference
    try:
        r = ReferenceValidator(parser, schema).check()
        results["reference"] = r.to_dict()
        statuses.append(_extract_status(results["reference"]))
    except Exception as e:
        results["reference"] = _module_error_payload(e)
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
