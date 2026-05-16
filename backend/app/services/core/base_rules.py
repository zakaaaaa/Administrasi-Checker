"""
Base rules — dataclass aturan generik & schema-agnostic.

Berisi:
- SectionRule, SchemaRules: dipakai StructureChecker / ReferenceValidator /
  PhysicalSheetCounter. Setiap skema (PKM-KC, PKM-AI, ...) mengisi instance
  SchemaRules lewat factory `get_<skema>_rules()` di `schemas/<skema>/rules.py`.
- FormatRules: aturan format generik (font/margin/paper/spacing) dipakai
  FormatChecker. Factory `get_pkm_format_rules()` mengembalikan default PKM
  yang sama untuk semua skema PKM (KC, K, AI, GFT, dst.).

Di production, instance ini akan di-load dari tabel `competition_schemas` di
Supabase (lihat blueprint §3.3). Untuk Phase 1 hardcoded di per-skema rules.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


# ============================================================================
# Struktur dokumen
# ============================================================================


@dataclass
class SectionRule:
    """
    Aturan satu section dalam dokumen.

    Atribut:
        name: nama canonical section, mis. "BAB 1. PENDAHULUAN".
              Akan dipakai untuk pencocokan teks heading dokumen.
        aliases: variasi penulisan yang juga diterima
                 (mis. ["BAB I. PENDAHULUAN", "BAB 1 PENDAHULUAN"]).
        required: True jika section wajib ada.
        forbidden: True jika section TIDAK BOLEH ada (red flag).
                   required dan forbidden tidak boleh keduanya True.
        is_core: True jika termasuk "bagian inti" (untuk PhysicalSheetCounter).
        order: urutan relatif (integer naik). Section dengan order lebih kecil
               harus muncul lebih dulu di dokumen. Hanya digunakan untuk
               required section (forbidden tidak punya order).
    """
    name: str
    aliases: list[str] = field(default_factory=list)
    required: bool = False
    forbidden: bool = False
    is_core: bool = False
    order: Optional[int] = None

    def __post_init__(self):
        if self.required and self.forbidden:
            raise ValueError(
                f"Section {self.name!r} tidak boleh required dan forbidden sekaligus"
            )
        if self.required and self.order is None:
            raise ValueError(
                f"Section required {self.name!r} wajib punya order"
            )


@dataclass
class SchemaRules:
    """
    Aturan lengkap satu skema-laporan, mis. PKM-KC Proposal 2026.

    Untuk Phase 1, instance ini di-construct hardcoded.
    Nanti di Phase 2 akan di-load dari Supabase via:
        SchemaRules.from_db(competition_schema_row)
    """
    competition_code: str       # 'PKM', 'P2MW', dst.
    schema_code: str            # 'KC', 'AI', dst.
    report_type_code: str       # 'PROPOSAL', 'PROGRESS_REPORT', dst.
    schema_name: str            # 'Karsa Cipta'
    year: int = 2026

    # Daftar SectionRule lengkap (required + forbidden)
    sections: list[SectionRule] = field(default_factory=list)

    # PKM-AI dan sejenisnya pakai heading Title Case ("Pendahuluan", "Metode")
    # alih-alih ALL CAPS ("BAB 1. PENDAHULUAN"). Aktifkan flag ini supaya
    # StructureChecker juga mengizinkan paragraf pendek non-ALL-CAPS sebagai
    # kandidat heading selama match SectionRule.
    section_titles_titlecase: bool = False

    # Cara menentukan awal "bagian inti" untuk PhysicalSheetCounter:
    #   - 'bab1': cari heading "BAB 1" (default; PKM-KC dkk.)
    #   - 'first_page': halaman fisik pertama PDF (PKM-AI: mulai dari halaman judul)
    core_start_mode: str = "bab1"

    # Konfigurasi ReferenceValidator (Daftar Pustaka).
    # Default: PKM-KC dkk. (≥ 8 referensi mutakhir dalam 10 tahun terakhir).
    # PKM-AI: ≥ 10 referensi dalam 5 tahun terakhir (panduan PKM-AI hal 11).
    min_recent_references: int = 8
    recent_threshold_years: int = 10

    # ---- Helper queries ----

    def required_sections(self) -> list[SectionRule]:
        return sorted(
            [s for s in self.sections if s.required],
            key=lambda s: s.order or 999,
        )

    def forbidden_sections(self) -> list[SectionRule]:
        return [s for s in self.sections if s.forbidden]

    def core_sections(self) -> list[SectionRule]:
        return [s for s in self.sections if s.is_core]


# ============================================================================
# Format generik (font/margin/paper/spacing)
# ============================================================================


@dataclass
class FormatRules:
    font_name: str = "Times New Roman"
    font_size_pt: float = 12.0
    font_size_tolerance_pt: float = 0.3   # 11.7–12.3 diterima
    margin_left_cm: float = 4.0
    margin_right_cm: float = 3.0
    margin_top_cm: float = 3.0
    margin_bottom_cm: float = 3.0
    margin_tolerance_cm: float = 0.05
    paper_width_cm: float = 21.0      # A4
    paper_height_cm: float = 29.7
    paper_tolerance_cm: float = 0.1
    line_spacing: float = 1.15
    line_spacing_tolerance: float = 0.05
    require_justify: bool = True


def get_pkm_format_rules() -> FormatRules:
    """Default rules untuk semua skema PKM (sama untuk KC, K, AI, GFT, dll)."""
    return FormatRules()
