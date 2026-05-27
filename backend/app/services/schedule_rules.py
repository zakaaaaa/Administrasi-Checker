"""
ScheduleRules — konfigurasi aturan tabel "Jadwal Kegiatan" (BAB 4) per skema.

Acuan format diturunkan dari template `format tabel.docx`:

    | No | Jadwal Kegiatan | Bulan (1 2 3 4) | Penanggung Jawab |

Seperti budget_rules.py, aturan di-encode sebagai data (bukan menyimpan contoh
dokumen "yang benar"). ScheduleChecker memvalidasi tabel dokumen terhadap rules
ini.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ScheduleTableRules:
    """Aturan satu tabel jadwal kegiatan."""
    schema_label: str                       # "PKM-KC", dst.
    # Header kolom logis (urut), setelah merged-cell dinormalkan.
    expected_headers: list[str] = field(default_factory=list)
    strict_headers: bool = True             # header wajib persis sama (tidak boleh sinonim, mis. "PIC")
    required_months: int = 4                # jumlah kolom bulan wajib (tepat)
    require_pic_filled: bool = True         # tiap kegiatan wajib punya penanggung jawab
    pic_severity: str = "warning"           # severity jika sel penanggung jawab kosong


def get_pkm_kc_schedule_rules() -> ScheduleTableRules:
    """Aturan tabel jadwal kegiatan PKM-KC 2026 (acuan: format tabel.docx)."""
    return ScheduleTableRules(
        schema_label="PKM-KC",
        expected_headers=["No", "Jadwal Kegiatan", "Bulan", "Penanggung Jawab"],
        strict_headers=True,
        required_months=4,
        require_pic_filled=True,
        pic_severity="warning",
    )


def get_pkm_vgk_schedule_rules() -> ScheduleTableRules:
    """Aturan tabel jadwal kegiatan PKM-VGK — sama dengan PKM-KC."""
    rules = get_pkm_kc_schedule_rules()
    rules.schema_label = "PKM-VGK"
    return rules


def get_pkm_re_schedule_rules() -> ScheduleTableRules:
    """Aturan tabel jadwal kegiatan PKM-RE — sama dengan PKM-KC."""
    rules = get_pkm_kc_schedule_rules()
    rules.schema_label = "PKM-RE"
    return rules


def get_pkm_rsh_schedule_rules() -> ScheduleTableRules:
    """Aturan tabel jadwal kegiatan PKM-RSH — sama dengan PKM-KC."""
    rules = get_pkm_kc_schedule_rules()
    rules.schema_label = "PKM-RSH"
    return rules


def get_pkm_k_schedule_rules() -> ScheduleTableRules:
    """Aturan tabel jadwal kegiatan PKM-K — sama dengan PKM-KC."""
    rules = get_pkm_kc_schedule_rules()
    rules.schema_label = "PKM-K"
    return rules


def get_pkm_ki_schedule_rules() -> ScheduleTableRules:
    """Aturan tabel jadwal kegiatan PKM-KI — sama dengan PKM-KC."""
    rules = get_pkm_kc_schedule_rules()
    rules.schema_label = "PKM-KI"
    return rules


def get_pkm_pi_schedule_rules() -> ScheduleTableRules:
    """Aturan tabel jadwal kegiatan PKM-PI — sama dengan PKM-KC."""
    rules = get_pkm_kc_schedule_rules()
    rules.schema_label = "PKM-PI"
    return rules


def get_pkm_pm_schedule_rules() -> ScheduleTableRules:
    """Aturan tabel jadwal kegiatan PKM-PM — sama dengan PKM-KC."""
    rules = get_pkm_kc_schedule_rules()
    rules.schema_label = "PKM-PM"
    return rules
