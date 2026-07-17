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
from app.services.schema_rules import (
    get_pkm_kc_proposal_rules,
    get_pkm_ai_proposal_rules,
    get_pkm_vgk_proposal_rules,
    get_pkm_re_proposal_rules,
    get_pkm_rsh_proposal_rules,
    get_pkm_k_proposal_rules,
    get_pkm_ki_proposal_rules,
    get_pkm_pi_proposal_rules,
    get_pkm_pm_proposal_rules,
    get_pkm_gft_proposal_rules,
    get_pkm_laporan_kemajuan_rules,
    get_pkm_laporan_akhir_rules,
)
from app.services.budget_rules import (
    get_pkm_kc_budget_rules,
    get_pkm_vgk_budget_rules,
    get_pkm_re_budget_rules,
    get_pkm_rsh_budget_rules,
    get_pkm_k_budget_rules,
    get_pkm_ki_budget_rules,
    get_pkm_pi_budget_rules,
    get_pkm_pm_budget_rules,
)
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
from app.services.surat_pernyataan_checker import SuratPernyataanChecker
from app.services.signature_crop_checker import SignatureCropChecker
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
    """Baca teks per lembar dari PDF (path di physical_result.pdf_path)."""
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


def _render_pdf_for_format(docx_path: str) -> Optional[str]:
    """
    Render DOCX → PDF (via LibreOffice headless) untuk dipakai FormatChecker
    sebagai ground-truth pemetaan halaman. Graceful fallback: kalau LibreOffice
    tidak ada / konversi gagal, return None — FormatChecker akan jatuh ke
    estimator DOCX (kurang akurat).
    """
    try:
        from app.services.pdf_converter import PdfConverter
        import tempfile
        out_dir = tempfile.mkdtemp(prefix="format-pdf-")
        return str(PdfConverter().convert(docx_path, output_dir=out_dir))
    except Exception as e:
        _log.info(f"[format] skip PDF render: {e}")
        return None


def _move_similarity_undetected_to_lampiran(
    results: dict[str, Any], statuses: list[str]
) -> None:
    """
    Kalau similarity check tidak bisa mendeteksi persentase ('tidak terdeteksi'),
    pindahkan pesan tsb ke section Lampiran sebagai 'Tidak ditemukan "Uji
    similaritas" pada halaman lampiran' — TAPI HANYA jika lampiran_checker juga
    melaporkan lampiran similaritas missing dari body. Kalau lampiran_checker
    sudah konfirmasi lampiran ADA (cuma OCR gagal baca %), biarkan pesan
    similarity sebagai warning ('periksa manual') — JANGAN salahkan user soal
    lampiran missing yang sebenarnya tidak missing.

    Statuses list ikut di-update agar overall_status mencerminkan kondisi baru.
    """
    sim = results.get("similarity")
    lamp = results.get("lampiran")
    if not isinstance(sim, dict) or not isinstance(lamp, dict):
        return
    sim_msgs = sim.get("messages", []) or []
    has_undetected = any(
        "tidak terdeteksi" in (m.get("text", "") or "").lower() for m in sim_msgs
    )
    if not has_undetected:
        return

    # Cek apakah lampiran_checker melaporkan lampiran similaritas missing.
    # Pesan dari lampiran_checker format-nya:
    #   'Tidak ditemukan Lampiran N "...Similaritas..." pada halaman lampiran'
    lamp_msgs = lamp.get("messages", []) or []
    lampiran_similaritas_missing = any(
        "tidak ditemukan" in (m.get("text", "") or "").lower()
        and "similar" in (m.get("text", "") or "").lower()
        for m in lamp_msgs
    )

    if not lampiran_similaritas_missing:
        # Lampiran ADA tapi OCR gagal baca % → biarkan pesan similarity sebagai
        # warning "periksa manual". Tidak ada yang dipindahkan.
        return

    # Lampiran beneran missing → pindahkan undetected ke lampiran.
    remaining = [
        m for m in sim_msgs if "tidak terdeteksi" not in (m.get("text", "") or "").lower()
    ]
    if remaining:
        sim["messages"] = remaining
    else:
        sim["messages"] = []
        sim["status"] = "pass"

    # Buang pass-level message lampiran ("Kelengkapan ... sesuai") agar tidak
    # bertabrakan dengan fail baru yang kita tambahkan.
    lamp["messages"] = [
        m for m in lamp.get("messages", []) if (m.get("level") or "").lower() != "pass"
    ]
    lamp["messages"].append({
        "level": "fail",
        "text": 'Tidak ditemukan "Uji similaritas" pada halaman lampiran',
    })
    lamp["status"] = "fail"

    # Aggregate ulang statuses dari semua modul agar overall_status konsisten
    # (similarity yang berubah ke pass, lampiran yang berubah ke fail).
    statuses[:] = [
        v.get("status", "pass")
        for k, v in results.items()
        if isinstance(v, dict) and "status" in v and k != "overall_status"
    ]


def _funding_letter_required(results: dict[str, Any]) -> bool:
    """
    True bila hasil budget menunjukkan ada dana Instansi Lain (>Rp0) pada Rekap
    Sumber Dana Bab 4 → proposal wajib melampirkan Surat Pernyataan Komitmen
    Tambahan Pendanaan. external_rp None (blok rekap tak terbaca) → False
    (tidak bisa dipastikan, jadi tidak diwajibkan).
    """
    rekap = (results.get("budget") or {}).get("rekap_sumber_dana") or {}
    ext = rekap.get("external_rp")
    return bool(ext and ext > 0)


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
_SCIENTIFIC_ARTICLE_SCHEMAS = {
    "PKM-KC",
    "PKM-RE",
    "PKM-RSH",
    "PKM-K",
    "PKM-PM",
    "PKM-PI",
    "PKM-KI",
    "PKM-AI",
}
# Skema pendanaan yang punya Laporan Kemajuan & Laporan Akhir
_LAPORAN_SCHEMAS = {
    "PKM-K",
    "PKM-KC",
    "PKM-KI",
    "PKM-PI",
    "PKM-PM",
    "PKM-RE",
    "PKM-RSH",
    "PKM-VGK",
}


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
    elif key == ("PKM", "PROPOSAL", "PKM-RE"):
        return _run_pkm_re(parser)
    elif key == ("PKM", "PROPOSAL", "PKM-RSH"):
        return _run_pkm_rsh(parser)
    elif key == ("PKM", "PROPOSAL", "PKM-K"):
        return _run_pkm_k(parser)
    elif key == ("PKM", "PROPOSAL", "PKM-KI"):
        return _run_pkm_ki(parser)
    elif key == ("PKM", "PROPOSAL", "PKM-PI"):
        return _run_pkm_pi(parser)
    elif key == ("PKM", "PROPOSAL", "PKM-PM"):
        return _run_pkm_pm(parser)
    elif req.competition == "PKM" and req.report_type == "SCIENTIFIC_ARTICLE" and req.schema_code in _SCIENTIFIC_ARTICLE_SCHEMAS:
        return _run_pkm_ai(parser)
    elif (
        req.competition == "PKM"
        and req.report_type in ("PROGRESS_REPORT", "FINAL_REPORT")
        and req.schema_code in _LAPORAN_SCHEMAS
    ):
        return _run_pkm_laporan(parser, report_type=req.report_type, schema_code=req.schema_code)
    elif key == ("PKM", "PROPOSAL", "PKM-GFT"):
        return _run_pkm_gft(parser)
    else:
        raise UnsupportedSchemaError(
            f"Belum di-support: {req.competition}/{req.report_type}/{req.schema_code}. "
            "Skema yang tersedia: PKM/PROPOSAL/PKM-KC, PKM/PROPOSAL/PKM-VGK, "
            "PKM/PROPOSAL/PKM-RE, PKM/PROPOSAL/PKM-RSH, "
            "PKM/PROPOSAL/PKM-K, PKM/PROPOSAL/PKM-KI, "
            "PKM/PROPOSAL/PKM-PI, PKM/PROPOSAL/PKM-PM, "
            "PKM/PROPOSAL/PKM-GFT, PKM/SCIENTIFIC_ARTICLE/PKM-KC, "
            "PKM/SCIENTIFIC_ARTICLE/PKM-RE, PKM/SCIENTIFIC_ARTICLE/PKM-RSH, "
            "PKM/SCIENTIFIC_ARTICLE/PKM-K, PKM/SCIENTIFIC_ARTICLE/PKM-PM, "
            "PKM/SCIENTIFIC_ARTICLE/PKM-PI, PKM/SCIENTIFIC_ARTICLE/PKM-KI, "
            "PKM/SCIENTIFIC_ARTICLE/PKM-AI, serta PROGRESS_REPORT/FINAL_REPORT "
            "untuk skema pendanaan PKM (K, KC, KI, PI, PM, RE, RSH, VGK)."
        )


# ============================================================================
# Runner PKM-KC
# ============================================================================


def _run_pkm_kc(parser: DocxParser) -> dict[str, Any]:
    """PKM-KC runner — delegasi ke helper bersama (sama dengan PKM-RE/RSH)."""
    return _run_pkm_kc_like(
        parser,
        schema=get_pkm_kc_proposal_rules(),
        budget_rules=get_pkm_kc_budget_rules(),
        schema_suffix="kc",
        log_label="PKM-KC",
    )


def _run_pkm_re(parser: DocxParser) -> dict[str, Any]:
    """PKM-RE runner — pipeline sama dengan PKM-KC."""
    return _run_pkm_kc_like(
        parser,
        schema=get_pkm_re_proposal_rules(),
        budget_rules=get_pkm_re_budget_rules(),
        schema_suffix="re",
        log_label="PKM-RE",
    )


def _run_pkm_rsh(parser: DocxParser) -> dict[str, Any]:
    """PKM-RSH runner — pipeline sama dengan PKM-KC."""
    return _run_pkm_kc_like(
        parser,
        schema=get_pkm_rsh_proposal_rules(),
        budget_rules=get_pkm_rsh_budget_rules(),
        schema_suffix="rsh",
        log_label="PKM-RSH",
    )


def _run_pkm_k(parser: DocxParser) -> dict[str, Any]:
    """PKM-K runner — pipeline sama dengan PKM-KC."""
    return _run_pkm_kc_like(
        parser,
        schema=get_pkm_k_proposal_rules(),
        budget_rules=get_pkm_k_budget_rules(),
        schema_suffix="k",
        log_label="PKM-K",
    )


def _run_pkm_ki(parser: DocxParser) -> dict[str, Any]:
    """PKM-KI runner — pipeline sama dengan PKM-KC."""
    return _run_pkm_kc_like(
        parser,
        schema=get_pkm_ki_proposal_rules(),
        budget_rules=get_pkm_ki_budget_rules(),
        schema_suffix="ki",
        log_label="PKM-KI",
    )


def _run_pkm_pi(parser: DocxParser) -> dict[str, Any]:
    """PKM-PI runner — pipeline sama dengan PKM-KC."""
    return _run_pkm_kc_like(
        parser,
        schema=get_pkm_pi_proposal_rules(),
        budget_rules=get_pkm_pi_budget_rules(),
        schema_suffix="pi",
        log_label="PKM-PI",
    )


def _run_pkm_pm(parser: DocxParser) -> dict[str, Any]:
    """PKM-PM runner — pipeline sama dengan PKM-KC."""
    return _run_pkm_kc_like(
        parser,
        schema=get_pkm_pm_proposal_rules(),
        budget_rules=get_pkm_pm_budget_rules(),
        schema_suffix="pm",
        log_label="PKM-PM",
    )


def _run_pkm_kc_like(
    parser: DocxParser,
    *,
    schema: Any,
    budget_rules: Any,
    schema_suffix: str,
    log_label: str,
) -> dict[str, Any]:
    """
    Pipeline 11-step yang dipakai bersama semua skema PKM pendanaan
    (KC, RE, RSH, K, KI, PI, PM, VGK).
    schema_suffix dipakai untuk pilih factory: for_pkm_{suffix}.
    """
    s = schema_suffix.lower()
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
        if _physical_result and not _physical_result.pdf_path:
            _physical_result.pdf_path = _render_pdf_for_format(str(parser.file_path))
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

    # 7. Luaran
    _t0 = time.perf_counter()
    try:
        r = getattr(LuaranChecker, f"for_pkm_{s}")(parser).check()
        results["luaran"] = r.to_dict()
        statuses.append(_extract_status(results["luaran"]))
    except Exception as e:
        results["luaran"] = _module_error_payload(e)
        statuses.append("error")
    _log_timing("luaran", _t0, timings)

    # Index Lampiran bersama: cache OCR per-gambar dipakai lampiran + biodata_date
    # (tiap gambar di-OCR maksimal sekali untuk kedua checker).
    lampiran_index = LampiranOcrIndex(parser)

    # 8. Lampiran — OCR scoped (segment belum teridentifikasi)
    _t0 = time.perf_counter()
    try:
        r = getattr(LampiranChecker, f"for_pkm_{s}")(parser).check(
            index=lampiran_index,
            require_funding_letter=_funding_letter_required(results),
        )
        results["lampiran"] = r.to_dict()
        statuses.append(_extract_status(results["lampiran"]))
    except Exception as e:
        results["lampiran"] = _module_error_payload(e)
        statuses.append("error")
    _log_timing("lampiran", _t0, timings)

    # 9. Tanggal biodata — OCR scoped (biodata + surat pernyataan), reuse cache
    _t0 = time.perf_counter()
    try:
        r = getattr(BiodataDateChecker, f"for_pkm_{s}")(parser).check(index=lampiran_index)
        results["biodata_date"] = r.to_dict()
        statuses.append(_extract_status(results["biodata_date"]))
    except Exception as e:
        results["biodata_date"] = _module_error_payload(e)
        statuses.append("error")
    _log_timing("biodata_date", _t0, timings)

    # 9b. Format Surat Pernyataan Ketua — OCR scoped (segment surat), reuse cache
    _t0 = time.perf_counter()
    try:
        r = getattr(SuratPernyataanChecker, f"for_pkm_{s}")(parser).check(index=lampiran_index)
        results["surat_pernyataan"] = r.to_dict()
        statuses.append(_extract_status(results["surat_pernyataan"]))
    except Exception as e:
        results["surat_pernyataan"] = _module_error_payload(e)
        statuses.append("error")
    _log_timing("surat_pernyataan", _t0, timings)

    # 9c. Deteksi tanda tangan crop/paste pada lampiran — reuse cache
    _t0 = time.perf_counter()
    try:
        r = SignatureCropChecker(parser).check(index=lampiran_index)
        results["signature_crop"] = r.to_dict()
        statuses.append(_extract_status(results["signature_crop"]))
    except Exception as e:
        results["signature_crop"] = _module_error_payload(e)
        statuses.append("error")
    _log_timing("signature_crop", _t0, timings)

    # 10. Jadwal kegiatan
    _t0 = time.perf_counter()
    try:
        r = getattr(ScheduleChecker, f"for_pkm_{s}")(parser).check()
        results["schedule"] = r.to_dict()
        statuses.append(_extract_status(results["schedule"]))
    except Exception as e:
        results["schedule"] = _module_error_payload(e)
        statuses.append("error")
    _log_timing("schedule", _t0, timings)

    # 11. Hasil uji similaritas ≤ 25% — OCR gambar similaritas
    _t0 = time.perf_counter()
    try:
        r = getattr(SimilarityChecker, f"for_pkm_{s}")(parser).check()
        results["similarity"] = r.to_dict()
        statuses.append(_extract_status(results["similarity"]))
    except Exception as e:
        results["similarity"] = _module_error_payload(e)
        statuses.append("error")
    _log_timing("similarity", _t0, timings)

    # Kalau % similaritas tak bisa terdeteksi (gambar tak ada / OCR tak baca angka),
    # pindahkan ke bagian Lampiran sebagai "Tidak ditemukan 'Uji similaritas'".
    _move_similarity_undetected_to_lampiran(results, statuses)

    results["_timings"] = {**timings, "total": round(sum(timings.values()), 3)}
    if _TIMING_ENABLED:
        print(f"[timing] TOTAL {log_label}: {results['_timings']['total']:.2f}s", flush=True)
    results["overall_status"] = _aggregate_status(statuses)
    return results


# ============================================================================
# Runner PKM-VGK
# ============================================================================


def _run_pkm_vgk(parser: DocxParser) -> dict[str, Any]:
    """PKM-VGK runner — pipeline sama dengan PKM-KC."""
    return _run_pkm_kc_like(
        parser,
        schema=get_pkm_vgk_proposal_rules(),
        budget_rules=get_pkm_vgk_budget_rules(),
        schema_suffix="vgk",
        log_label="PKM-VGK",
    )


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
        if _physical_result and not _physical_result.pdf_path:
            _physical_result.pdf_path = _render_pdf_for_format(str(parser.file_path))
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

    # 6. Reference (PKM-AI: min 10 rujukan, maks 5 tahun ke belakang)
    try:
        r = ReferenceValidator(
            parser,
            schema,
            recent_threshold_years=5,
            minimum_recommended_recent=10,
        ).check()
        results["reference"] = r.to_dict()
        statuses.append(_extract_status(results["reference"]))
    except Exception as e:
        results["reference"] = _module_error_payload(e)
        statuses.append("error")

    # 7. Lampiran PKM-AI (5 item, tanpa Daftar Lampiran)
    lampiran_index = LampiranOcrIndex(parser)
    try:
        r = LampiranChecker.for_pkm_ai(parser).check(index=lampiran_index)
        results["lampiran"] = r.to_dict()
        statuses.append(_extract_status(results["lampiran"]))
    except Exception as e:
        results["lampiran"] = _module_error_payload(e)
        statuses.append("error")

    # 7a. Tanggal biodata — TT 9 Mar–9 Apr 2026, reuse OCR cache.
    try:
        r = BiodataDateChecker.for_pkm_ai(parser).check(index=lampiran_index)
        results["biodata_date"] = r.to_dict()
        statuses.append(_extract_status(results["biodata_date"]))
    except Exception as e:
        results["biodata_date"] = _module_error_payload(e)
        statuses.append("error")

    # 7b. Format Surat Pernyataan Ketua — reuse OCR cache.
    try:
        r = SuratPernyataanChecker.for_pkm_ai(parser).check(index=lampiran_index)
        results["surat_pernyataan"] = r.to_dict()
        statuses.append(_extract_status(results["surat_pernyataan"]))
    except Exception as e:
        results["surat_pernyataan"] = _module_error_payload(e)
        statuses.append("error")

    # 7c. Deteksi tanda tangan crop/paste pada lampiran.
    try:
        r = SignatureCropChecker(parser).check(index=lampiran_index)
        results["signature_crop"] = r.to_dict()
        statuses.append(_extract_status(results["signature_crop"]))
    except Exception as e:
        results["signature_crop"] = _module_error_payload(e)
        statuses.append("error")

    # 8. Uji Similaritas ≤ 25%
    try:
        r = SimilarityChecker.for_pkm_ai(parser).check()
        results["similarity"] = r.to_dict()
        statuses.append(_extract_status(results["similarity"]))
    except Exception as e:
        results["similarity"] = _module_error_payload(e)
        statuses.append("error")

    results["overall_status"] = _aggregate_status(statuses)
    return results


# ============================================================================
# Runner PKM-GFT
# ============================================================================
#
# PKM-GFT (Gagasan Futuristik Tertulis) = PKM insentif tanpa pelaksanaan.
# Pipeline lebih ringkas dibanding skema pendanaan:
#   1. Structure       — 3 BAB + DP + LAMPIRAN, forbidden sampul/pengesahan/ringkasan
#   2. Physical Sheet  — 8–15 lembar inti
#   3. Format          — TNR 12, spasi 1.15, justify, margin 4/3/3/3 (default PKM)
#   4. Page Numbering  — roman bawah utk Daftar Isi, arab atas utk Bagian Inti
#   5. Reference       — Harvard style (default ReferenceValidator)
#   6. Lampiran        — 4 item, tanpa Daftar Lampiran (gabung di Daftar Isi)
#   7. Biodata Date    — TT 9 Mar–9 Apr 2026 (sama skema lain)
#   8. Similarity      — ≤ 25%
# Modul yang SKIP: budget, schedule, luaran (PKM-GFT tanpa pelaksanaan & luaran).


def _run_pkm_gft(parser: DocxParser) -> dict[str, Any]:
    schema = get_pkm_gft_proposal_rules()
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

    # 2. Physical Sheet (8–15 halaman, ditangani via SHEET_COUNT_RULES)
    _physical_result = None
    try:
        _physical_result = PhysicalSheetCounter(parser, schema).check()
        results["physical_sheet"] = _physical_result.to_dict()
        statuses.append(_extract_status(results["physical_sheet"]))
    except Exception as e:
        results["physical_sheet"] = _module_error_payload(e)
        statuses.append("error")

    # 3. Format (default PKM rules: TNR 12, spasi 1.15, justify, margin 4/3/3/3, A4)
    try:
        if _physical_result and not _physical_result.pdf_path:
            _physical_result.pdf_path = _render_pdf_for_format(str(parser.file_path))
        _pdf_texts = _load_pdf_sheet_texts(_physical_result) if _physical_result else None
        r = FormatChecker(parser, schema=schema, pdf_sheet_texts=_pdf_texts).check(
            start_para_idx=_find_core_start_idx(structure_result)
        )
        results["format"] = r.to_dict()
        statuses.append(_extract_status(results["format"]))
    except Exception as e:
        results["format"] = _module_error_payload(e)
        statuses.append("error")

    # 4. Page Numbering (default PKM: roman bawah di front, arab atas di inti)
    try:
        r = PageNumberingChecker(parser, schema).check()
        results["page_numbering"] = r.to_dict()
        statuses.append(_extract_status(results["page_numbering"]))
    except Exception as e:
        results["page_numbering"] = _module_error_payload(e)
        statuses.append("error")

    # 5. Budget — tidak ada di PKM-GFT (PKM insentif tanpa pelaksanaan)
    results["budget"] = {
        "status": "pass",
        "messages": [{"level": "pass", "text": "Anggaran biaya tidak diperlukan untuk PKM-GFT."}],
    }
    statuses.append("pass")

    # 6. Reference (Harvard style, default threshold)
    try:
        r = ReferenceValidator(parser, schema).check()
        results["reference"] = r.to_dict()
        statuses.append(_extract_status(results["reference"]))
    except Exception as e:
        results["reference"] = _module_error_payload(e)
        statuses.append("error")

    # Index Lampiran bersama untuk Lampiran + Biodata Date (share OCR cache).
    lampiran_index = LampiranOcrIndex(parser)

    # 7. Lampiran PKM-GFT (4 item, tanpa Daftar Lampiran)
    try:
        r = LampiranChecker.for_pkm_gft(parser).check(index=lampiran_index)
        results["lampiran"] = r.to_dict()
        statuses.append(_extract_status(results["lampiran"]))
    except Exception as e:
        results["lampiran"] = _module_error_payload(e)
        statuses.append("error")

    # 8. Tanggal biodata — TT 9 Mar–9 Apr 2026
    try:
        r = BiodataDateChecker.for_pkm_gft(parser).check(index=lampiran_index)
        results["biodata_date"] = r.to_dict()
        statuses.append(_extract_status(results["biodata_date"]))
    except Exception as e:
        results["biodata_date"] = _module_error_payload(e)
        statuses.append("error")

    # 8b. Format Surat Pernyataan Ketua — reuse OCR cache.
    try:
        r = SuratPernyataanChecker.for_pkm_gft(parser).check(index=lampiran_index)
        results["surat_pernyataan"] = r.to_dict()
        statuses.append(_extract_status(results["surat_pernyataan"]))
    except Exception as e:
        results["surat_pernyataan"] = _module_error_payload(e)
        statuses.append("error")

    # 8c. Deteksi tanda tangan crop/paste pada lampiran.
    try:
        r = SignatureCropChecker(parser).check(index=lampiran_index)
        results["signature_crop"] = r.to_dict()
        statuses.append(_extract_status(results["signature_crop"]))
    except Exception as e:
        results["signature_crop"] = _module_error_payload(e)
        statuses.append("error")

    # 9. Uji Similaritas ≤ 25%
    try:
        r = SimilarityChecker.for_pkm_gft(parser).check()
        results["similarity"] = r.to_dict()
        statuses.append(_extract_status(results["similarity"]))
    except Exception as e:
        results["similarity"] = _module_error_payload(e)
        statuses.append("error")

    # Pindahkan undetected similarity ke pesan lampiran (konsisten dengan KC-like).
    _move_similarity_undetected_to_lampiran(results, statuses)

    results["overall_status"] = _aggregate_status(statuses)
    return results


# ============================================================================
# Runner Laporan Kemajuan & Laporan Akhir (8 skema pendanaan)
# ============================================================================
#
# Pipeline lebih ringkas dari proposal — checker yang relevan saja:
#   1. Structure       — bab per skema/jenis laporan, forbidden sampul/pengesahan
#                        (+ ringkasan utk kemajuan; ringkasan WAJIB utk akhir)
#   2. Physical Sheet  — bagian inti maks 10 halaman (sama dengan proposal)
#   3. Format          — TNR 12, spasi 1,15, justify, margin 4/3/3/3, A4
#   4. Page Numbering  — roman bawah utk front matter, arab atas utk inti
#   5. Reference       — Harvard style
#   6. Lampiran        — Penggunaan Dana + Bukti Pendukung (KI kemajuan
#                        +Draft Dokumen Teknis), OCR fallback via index
# Modul yang SKIP: budget/justifikasi, luaran proposal, biodata_date,
# surat_pernyataan, signature_crop, schedule, similarity — item tersebut
# bagian dari proposal, tidak dipersyaratkan pada berkas laporan.


def _run_pkm_laporan(
    parser: DocxParser, *, report_type: str, schema_code: str
) -> dict[str, Any]:
    suffix = schema_code.removeprefix("PKM-")
    if report_type == "PROGRESS_REPORT":
        schema = get_pkm_laporan_kemajuan_rules(suffix)
        log_label = f"{schema_code} Laporan Kemajuan"
    else:
        schema = get_pkm_laporan_akhir_rules(suffix)
        log_label = f"{schema_code} Laporan Akhir"

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

    # 2. Physical Sheet (bagian inti maks 10 halaman)
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

    # 3. Format (mulai Bab 1 s.d. sebelum Lampiran)
    _t0 = time.perf_counter()
    try:
        if _physical_result and not _physical_result.pdf_path:
            _physical_result.pdf_path = _render_pdf_for_format(str(parser.file_path))
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

    # 5. Reference (Harvard style)
    _t0 = time.perf_counter()
    try:
        r = ReferenceValidator(parser, schema).check()
        results["reference"] = r.to_dict()
        statuses.append(_extract_status(results["reference"]))
    except Exception as e:
        results["reference"] = _module_error_payload(e)
        statuses.append("error")
    _log_timing("reference", _t0, timings)

    # 6. Lampiran laporan — Penggunaan Dana + Bukti Pendukung, OCR fallback
    _t0 = time.perf_counter()
    try:
        lampiran_index = LampiranOcrIndex(parser)
        r = LampiranChecker.for_pkm_laporan(parser, suffix, report_type).check(
            index=lampiran_index
        )
        results["lampiran"] = r.to_dict()
        statuses.append(_extract_status(results["lampiran"]))
    except Exception as e:
        results["lampiran"] = _module_error_payload(e)
        statuses.append("error")
    _log_timing("lampiran", _t0, timings)

    results["_timings"] = {**timings, "total": round(sum(timings.values()), 3)}
    if _TIMING_ENABLED:
        print(f"[timing] TOTAL {log_label}: {results['_timings']['total']:.2f}s", flush=True)
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
