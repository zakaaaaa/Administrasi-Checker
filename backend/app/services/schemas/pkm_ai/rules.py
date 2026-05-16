"""
Aturan skema PKM-AI (Artikel Ilmiah).

Berisi factory:
- get_pkm_ai_article_rules() → SchemaRules untuk struktur Artikel Ilmiah PKM-AI.
- get_pkm_ai_page_numbering_rules() → PageNumberingRules untuk PKM-AI (semua
  halaman arab di pojok kanan atas, mulai dari halaman judul).

Sumber: PKM-AI-2026_fix.pdf (Panduan PKM-AI 2026, sistematika hal 6-7).
Larangan eksplisit (hal 5-6): TIDAK ada halaman sampul, halaman pengesahan,
dan daftar isi pada berkas naskah artikel ilmiah.
"""

from __future__ import annotations

from app.services.core.base_rules import SchemaRules, SectionRule
from app.services.checkers.page_numbering_checker import (
    PageNumberingRules,
    ZoneRule,
)


# ============================================================================
# Schema rules — PKM-AI Artikel Ilmiah 2026
# ============================================================================


def get_pkm_ai_article_rules() -> SchemaRules:
    """
    Aturan PKM-AI Artikel Ilmiah 2026.

    Section heading PKM-AI berbentuk Title Case + bold ("Pendahuluan",
    "Metode", "Hasil dan Pembahasan", dst.) — bukan ALL CAPS "BAB 1 …".
    Karena itu kita set `section_titles_titlecase=True` supaya
    StructureChecker mau menerima paragraf pendek non-ALL-CAPS sebagai
    kandidat heading.

    Untuk PhysicalSheetCounter: bagian inti = halaman judul s/d Daftar
    Pustaka (8–15 halaman). Tidak ada anchor "BAB 1" — kita set
    `core_start_mode='first_page'`; akhir bagian inti dihitung sebagai
    halaman tepat sebelum heading "LAMPIRAN" (kalau ada).
    """
    return SchemaRules(
        competition_code="PKM",
        schema_code="AI",
        report_type_code="SCIENTIFIC_ARTICLE",
        schema_name="Artikel Ilmiah",
        year=2026,
        section_titles_titlecase=True,
        core_start_mode="first_page",
        min_recent_references=10,
        recent_threshold_years=5,
        sections=[
            # --- WAJIB (urutan harus benar) ---
            SectionRule(
                name="ABSTRAK",
                # Heading kadang ditulis "Abstrak" bold di tengah halaman
                # judul. Aliases mencakup variasi penulisan umum.
                aliases=["ABSTRAK ", "ABSTRAK:"],
                required=True,
                order=1,
            ),
            SectionRule(
                name="ABSTRACT",
                aliases=["ABSTRACT ", "ABSTRACT:"],
                required=True,
                order=2,
            ),
            SectionRule(
                name="PENDAHULUAN",
                aliases=[
                    "1. PENDAHULUAN",
                    "1 PENDAHULUAN",
                    "I. PENDAHULUAN",
                    "BAB 1. PENDAHULUAN",
                    "BAB I. PENDAHULUAN",
                ],
                required=True,
                is_core=True,
                order=3,
            ),
            SectionRule(
                name="METODE",
                aliases=[
                    "2. METODE",
                    "2 METODE",
                    "II. METODE",
                    "METODE PENELITIAN",
                    "METODE PELAKSANAAN",
                    "2. METODE PENELITIAN",
                ],
                required=True,
                is_core=True,
                order=4,
            ),
            SectionRule(
                name="HASIL DAN PEMBAHASAN",
                aliases=[
                    "3. HASIL DAN PEMBAHASAN",
                    "3 HASIL DAN PEMBAHASAN",
                    "III. HASIL DAN PEMBAHASAN",
                    "HASIL & PEMBAHASAN",
                    "3. HASIL & PEMBAHASAN",
                    "HASIL PENELITIAN DAN PEMBAHASAN",
                ],
                required=True,
                is_core=True,
                order=5,
            ),
            SectionRule(
                name="KESIMPULAN",
                aliases=[
                    "4. KESIMPULAN",
                    "4 KESIMPULAN",
                    "IV. KESIMPULAN",
                    "SIMPULAN",
                    "KESIMPULAN DAN SARAN",
                ],
                required=True,
                is_core=True,
                order=6,
            ),
            SectionRule(
                name="DAFTAR PUSTAKA",
                aliases=[
                    "7. DAFTAR PUSTAKA",
                    "DAFTAR REFERENSI",
                    "REFERENSI",
                ],
                required=True,
                is_core=True,
                order=8,
            ),
            SectionRule(
                name="LAMPIRAN",
                aliases=[
                    "LAMPIRAN 1",
                    "LAMPIRAN 1.",
                    "LAMPIRAN-LAMPIRAN",
                    "8. LAMPIRAN",
                ],
                required=True,
                order=9,
            ),

            # --- OPSIONAL (boleh ada, tidak wajib) ---
            SectionRule(
                name="UCAPAN TERIMA KASIH",
                aliases=[
                    "5. UCAPAN TERIMA KASIH",
                    "UCAPAN TERIMAKASIH",
                ],
                required=False,
                order=61,
            ),
            SectionRule(
                name="KONTRIBUSI PENULIS",
                aliases=["6. KONTRIBUSI PENULIS"],
                required=False,
                order=62,
            ),
            SectionRule(
                name="KATA KUNCI",
                aliases=["KATA-KATA KUNCI", "KEYWORDS"],
                required=False,
                order=21,
            ),

            # --- TERLARANG (panduan PKM-AI hal 5-6) ---
            SectionRule(
                name="DAFTAR ISI",
                forbidden=True,
            ),
            SectionRule(
                name="HALAMAN SAMPUL",
                aliases=[
                    "COVER",
                    "SAMPUL",
                    "PROPOSAL PKM",
                    "PROPOSAL PKM-AI",
                ],
                forbidden=True,
            ),
            SectionRule(
                name="HALAMAN PENGESAHAN",
                aliases=[
                    "LEMBAR PENGESAHAN",
                    "PENGESAHAN PROPOSAL",
                    "PENGESAHAN PKM",
                    "PENGESAHAN ARTIKEL ILMIAH",
                ],
                forbidden=True,
            ),
        ],
    )


# ============================================================================
# Page numbering rules — PKM-AI
# ============================================================================


def get_pkm_ai_page_numbering_rules() -> PageNumberingRules:
    """
    PKM-AI: semua halaman pakai angka arab di pojok kanan ATAS, TNR 12pt,
    mulai dari halaman judul (panduan PKM-AI 2026 hal 5-6, butir 1-2).
    Tidak ada zona romawi/front-matter — DAFTAR ISI sendiri terlarang.
    """
    arab_top_right = ZoneRule(
        name="core_matter",
        numeral_type="arabic",
        position="top",
    )
    return PageNumberingRules(
        # front_matter di-isi placeholder yang identik supaya validator
        # tidak crash jika ada section yang salah ter-klasifikasi.
        front_matter=arab_top_right,
        core_matter=arab_top_right,
        mode="single_zone_core",
    )
