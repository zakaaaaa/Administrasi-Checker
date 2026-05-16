"""
Aturan skema PKM-KC (Karsa Cipta).

Berisi factory:
- get_pkm_kc_proposal_rules() → SchemaRules untuk struktur Proposal PKM-KC.
- get_pkm_page_numbering_rules() → PageNumberingRules untuk PKM-KC dkk
  (zona awal romawi-bawah, zona inti arab-atas).

Sumber: blueprint v0.3 §8.1 (PKM-KC) + Red Flags PKM-KC.
"""

from __future__ import annotations

from app.services.core.base_rules import SchemaRules, SectionRule
from app.services.checkers.page_numbering_checker import (
    PageNumberingRules,
    ZoneRule,
)


# ============================================================================
# Schema rules — PKM-KC Proposal 2026
# ============================================================================


def get_pkm_kc_proposal_rules() -> SchemaRules:
    """
    Aturan PKM-KC Proposal 2026 (blueprint v0.3 §8.1).

    Section yang diizinkan, urutannya:
        1. DAFTAR ISI                       (wajib)
        2. DAFTAR GAMBAR                    (opsional)
        3. DAFTAR TABEL                     (opsional)
        4. DAFTAR LAMPIRAN                  (wajib)
        5. BAB 1. PENDAHULUAN               (wajib, inti)
        6. BAB 2. TINJAUAN PUSTAKA          (wajib, inti)
        7. BAB 3. TAHAP PELAKSANAAN         (wajib, inti)
        8. BAB 4. BIAYA DAN JADWAL KEGIATAN (wajib, inti)
        9. DAFTAR PUSTAKA                   (wajib, inti)
       10. LAMPIRAN                         (wajib)

    Section TERLARANG (red flag → langsung tidak lolos tahap 1):
        - Halaman Sampul / Cover
        - Halaman Pengesahan / Lembar Pengesahan
        - Ringkasan / Abstrak
    """
    return SchemaRules(
        competition_code="PKM",
        schema_code="KC",
        report_type_code="PROPOSAL",
        schema_name="Karsa Cipta",
        year=2026,
        sections=[
            # --- SECTION WAJIB (urutan harus benar) ---
            SectionRule(
                name="DAFTAR ISI",
                required=True,
                order=1,
            ),
            SectionRule(
                name="DAFTAR LAMPIRAN",
                aliases=["DAFTAR LAMPIRAN-LAMPIRAN"],
                required=True,
                order=4,
            ),
            SectionRule(
                name="BAB 1. PENDAHULUAN",
                aliases=[
                    "BAB I. PENDAHULUAN",
                    "BAB 1 PENDAHULUAN",
                    "BAB I PENDAHULUAN",
                ],
                required=True,
                is_core=True,
                order=5,
            ),
            SectionRule(
                name="BAB 2. TINJAUAN PUSTAKA",
                aliases=[
                    "BAB II. TINJAUAN PUSTAKA",
                    "BAB 2 TINJAUAN PUSTAKA",
                    "BAB II TINJAUAN PUSTAKA",
                ],
                required=True,
                is_core=True,
                order=6,
            ),
            SectionRule(
                name="BAB 3. TAHAP PELAKSANAAN",
                aliases=[
                    "BAB III. TAHAP PELAKSANAAN",
                    "BAB 3 TAHAP PELAKSANAAN",
                    "BAB III TAHAP PELAKSANAAN",
                    # variasi yang ditemukan di dokumen real:
                    "BAB 3. METODE PELAKSANAAN",
                    "BAB III. METODE PELAKSANAAN",
                ],
                required=True,
                is_core=True,
                order=7,
            ),
            SectionRule(
                name="BAB 4. BIAYA DAN JADWAL KEGIATAN",
                aliases=[
                    "BAB IV. BIAYA DAN JADWAL KEGIATAN",
                    "BAB 4 BIAYA DAN JADWAL KEGIATAN",
                    "BAB IV BIAYA DAN JADWAL KEGIATAN",
                    "BAB 4. BIAYA DAN JADWAL",
                    "BAB IV. BIAYA DAN JADWAL",
                ],
                required=True,
                is_core=True,
                order=8,
            ),
            SectionRule(
                name="DAFTAR PUSTAKA",
                required=True,
                is_core=True,
                order=9,
            ),
            SectionRule(
                name="LAMPIRAN",
                # Lampiran 1, Lampiran 2, dst di-detect via aliases ini
                aliases=[
                    "LAMPIRAN 1",
                    "LAMPIRAN 1.",
                    "LAMPIRAN-LAMPIRAN",
                ],
                required=True,
                order=10,
            ),

            # --- SECTION OPSIONAL (boleh ada, tidak required) ---
            SectionRule(
                name="DAFTAR GAMBAR",
                required=False,
                order=2,
            ),
            SectionRule(
                name="DAFTAR TABEL",
                required=False,
                order=3,
            ),

            # --- SECTION TERLARANG (red flag) ---
            SectionRule(
                name="HALAMAN SAMPUL",
                aliases=[
                    "COVER",
                    "SAMPUL",
                    "PROPOSAL PKM",  # judul yang biasa muncul di cover
                    "PROPOSAL PKM-KC",
                    "PROPOSAL PROGRAM KREATIVITAS MAHASISWA",
                ],
                forbidden=True,
            ),
            SectionRule(
                name="HALAMAN PENGESAHAN",
                aliases=[
                    "LEMBAR PENGESAHAN",
                    "PENGESAHAN PROPOSAL",
                    "PENGESAHAN PKM",
                    "PENGESAHAN USULAN",
                ],
                forbidden=True,
            ),
            SectionRule(
                name="RINGKASAN",
                aliases=["ABSTRAK", "ABSTRACT"],
                forbidden=True,
            ),
        ],
    )


# ============================================================================
# Page numbering rules — PKM-KC dkk
# ============================================================================


def get_pkm_page_numbering_rules() -> PageNumberingRules:
    """Default PKM: zona awal romawi-bawah, zona inti arab-atas, both TNR 12pt."""
    return PageNumberingRules(
        front_matter=ZoneRule(
            name="front_matter",
            numeral_type="roman_lower",
            position="bottom",
        ),
        core_matter=ZoneRule(
            name="core_matter",
            numeral_type="arabic",
            position="top",
        ),
        mode="two_zone",
    )
