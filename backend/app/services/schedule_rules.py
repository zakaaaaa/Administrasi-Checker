"""
ScheduleRules — konfigurasi aturan tabel "Jadwal Kegiatan" (BAB 4) per skema.

Yang dicek:
- Rentang bulan (wajib tepat required_months bulan)
- Penanggung Jawab terisi di tiap baris kegiatan

Nama kolom bebas — tidak divalidasi.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ScheduleTableRules:
    """Aturan satu tabel jadwal kegiatan."""
    schema_label: str                       # "PKM-KC", dst.
    required_months: int = 4                # jumlah kolom bulan wajib (tepat)
    require_pic_filled: bool = True         # tiap kegiatan wajib punya penanggung jawab
    pic_severity: str = "warning"           # severity jika sel penanggung jawab kosong


def get_pkm_kc_schedule_rules() -> ScheduleTableRules:
    return ScheduleTableRules(
        schema_label="PKM-KC",
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
