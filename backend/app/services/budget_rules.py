"""
BudgetRules — konfigurasi aturan anggaran per skema.

Sumber: blueprint v0.3 §3.3 (budget_rules JSONB) & §8.3 (PKM-KC anggaran).

Nantinya rules ini akan di-load dari tabel `competition_schemas.budget_rules`
di Supabase. Untuk Phase 1, hardcoded di sini.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


# ============================================================================
# Sub-dataclass
# ============================================================================


@dataclass
class FundingSourceRule:
    """Aturan sumber dana (Belmawa/PT/Eksternal)."""
    name: str                    # 'belmawa' | 'university' | 'external'
    display_name: str            # 'Belmawa', 'Perguruan Tinggi', dst.
    min_rp: int                  # nilai minimum (Rp)
    max_rp: int                  # nilai maximum (Rp)
    mandatory: bool = False
    zero_value_is_error: bool = False  # PT wajib > 0
    validation_message: str = ""


@dataclass
class BudgetCategory:
    """Aturan satu kategori RAB."""
    name: str                    # 'Bahan habis pakai', dst.
    aliases: list[str] = field(default_factory=list)  # variasi penulisan dokumen
    max_percentage: float = 100.0       # % maksimum dari total
    must_exist_in_table: bool = True    # kolom kategori wajib utuh


@dataclass
class CrossCheckRule:
    """Aturan cross-check Bab 4 ↔ Lampiran 2."""
    enabled: bool = True
    tolerance_rupiah: int = 0   # toleransi nilai delta


@dataclass
class RelocationAdvisory:
    """
    Saran relokasi/pecah pos anggaran (warning, bukan error).
    Patokan `threshold_rp` berlaku untuk **harga satuan** per baris Lampiran 2,
    bukan untuk total nilai (volume × satuan). Total boleh besar selama satuan
    tidak melewati patokan.
    """
    threshold_rp: int = 1_000_000
    enabled: bool = True


@dataclass
class BudgetRules:
    """Aturan anggaran lengkap untuk satu skema."""
    competition_code: str        # 'PKM'
    schema_code: str             # 'KC'
    funding_type: str            # 'pendanaan' | 'insentif' | 'none'
    funding_sources: list[FundingSourceRule] = field(default_factory=list)
    categories: list[BudgetCategory] = field(default_factory=list)
    cross_check: CrossCheckRule = field(default_factory=CrossCheckRule)
    relocation_advisory: RelocationAdvisory = field(default_factory=RelocationAdvisory)
    prohibited_items: list[str] = field(default_factory=list)
    # (Restriksi spesifik seperti "ads medsos ≤ 500rb" akan ditambah nanti)

    def get_funding_source(self, name: str) -> Optional[FundingSourceRule]:
        """Lookup funding source rule by name (case-insensitive)."""
        n = name.lower()
        for fs in self.funding_sources:
            if fs.name.lower() == n:
                return fs
        return None


# ============================================================================
# Hardcoded: PKM-KC budget rules (blueprint v0.3 §8.3)
# ============================================================================


def get_pkm_kc_budget_rules() -> BudgetRules:
    """Aturan anggaran PKM-KC 2026 (blueprint §8.3)."""
    return BudgetRules(
        competition_code="PKM",
        schema_code="KC",
        funding_type="pendanaan",
        funding_sources=[
            FundingSourceRule(
                name="belmawa",
                display_name="Belmawa",
                min_rp=6_000_000,
                max_rp=8_000_000,
                mandatory=True,
                validation_message=(
                    "Dana Belmawa wajib di rentang Rp6.000.000 — Rp8.000.000."
                ),
            ),
            FundingSourceRule(
                name="university",
                display_name="Perguruan Tinggi",
                min_rp=500,           # WAJIB > 0; minimal Rp500
                max_rp=2_000_000,
                mandatory=True,
                zero_value_is_error=True,
                validation_message=(
                    "Dana PT wajib > Rp0 (minimal Rp500), maksimal Rp2.000.000."
                ),
            ),
            FundingSourceRule(
                name="external",
                display_name="Institusi Lain (Eksternal)",
                min_rp=0,
                max_rp=1_000_000,
                mandatory=False,
                validation_message="Dana eksternal opsional, maks Rp1.000.000.",
            ),
        ],
        categories=[
            BudgetCategory(
                name="Bahan habis pakai",
                aliases=[
                    "Bahan Habis Pakai",
                    "Bahan habis",
                    "Bahan Habis",
                    "Belanja Bahan",
                    "Belanja Bahan (maks. 60%)",
                ],
                max_percentage=60.0,
                must_exist_in_table=True,
            ),
            BudgetCategory(
                name="Sewa dan jasa",
                aliases=[
                    "Sewa & Jasa",
                    "Sewa dan Jasa",
                    "Belanja Sewa",
                    "Belanja Sewa (maks. 15%)",
                    "Perlengkapan yang diperlukan",   # variasi yang ditemukan di dokumen real
                    "Perlengkapan",
                ],
                max_percentage=15.0,
                must_exist_in_table=True,
            ),
            BudgetCategory(
                name="Transportasi lokal",
                aliases=[
                    "Transport",
                    "Transportasi",
                    "Perjalanan",                     # variasi yang ditemukan di dokumen real
                    "Belanja Perjalanan",
                    "Perjalanan (maks. 30%)",
                ],
                max_percentage=30.0,
                must_exist_in_table=True,
            ),
            BudgetCategory(
                name="Lain-lain",
                aliases=[
                    "Lain – lain",                    # dengan en-dash (di dokumen real)
                    "Lain - lain",
                    "Lainnya",
                    "Lain Lain",
                    "Lain-lain (maks. 15%)",
                ],
                max_percentage=15.0,
                must_exist_in_table=True,
            ),
        ],
        cross_check=CrossCheckRule(enabled=True, tolerance_rupiah=0),
        relocation_advisory=RelocationAdvisory(threshold_rp=1_000_000, enabled=True),
        prohibited_items=[
            # Sumber: blueprint §3.3 budget_rules.prohibited_items
            "Honorarium",
            "Konsumsi",
            "Hadiah",
            "Sewa komputer",
            "Sewa laptop",
            "Sewa printer",
            "Sewa ponsel",
            "Sewa kamera",
            "Pembelian penyimpanan data",
            "Pembelian hardisk",
            "Pembelian SSD",
            "Pembelian flashdisk",
            "Pembelian harddisk",
            "Hard Disk",
            "Hardisk",
            "SSD",
            "Flashdisk",
            "Biaya seminar",
            "Biaya publikasi jurnal",
            "Publikasi Artikel Jurnal",
            "Souvenir",
        ],
    )


def get_pkm_vgk_budget_rules() -> BudgetRules:
    """Aturan anggaran PKM-VGK 2026 — identik dengan PKM-KC."""
    rules = get_pkm_kc_budget_rules()
    rules.schema_code = "VGK"
    return rules