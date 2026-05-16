"""
Schema rules — representasi aturan untuk satu skema/jenis laporan.

Di production nanti, instance SchemaRules akan di-load dari tabel
`competition_schemas` di Supabase (lihat blueprint §3.3). Untuk Phase 1
kita hardcode PKM-KC dulu sebagai dict literal di bawah.

Field structure_rules dirancang agar StructureChecker tidak perlu tahu
detail skema PKM/P2MW/BIMA — cukup baca SectionRule satu per satu.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


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
# HARDCODED RULES — PKM-KC Proposal 2026
# ============================================================================
#
# Sumber aturan: blueprint v0.3 §8.1 (PKM-KC — Aturan Struktur Proposal)
# + Red Flags PKM-KC (halaman sampul, pengesahan, ringkasan/abstrak DILARANG)
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
# HARDCODED RULES — PKM-AI Artikel Ilmiah 2026
# ============================================================================
#
# Sumber: PKM-AI-2026_fix.pdf (Panduan PKM-AI 2026).
# Sistematika isi utama (hal 6 panduan, bagian C "Sistematika Penulisan Isi
# Utama Artikel Ilmiah"):
#   - JUDUL (≤ 20 kata, huruf kapital, tanpa singkatan)
#   - Penulis & alamat institusi
#   - ABSTRAK (Bahasa Indonesia, ≤ 250 kata)
#   - ABSTRACT (Bahasa Inggris, italic, ≤ 250 kata)
#   - Kata-kata kunci / Keywords
#   - 1. Pendahuluan
#   - 2. Metode
#   - 3. Hasil dan Pembahasan
#   - 4. Kesimpulan
#   - 5. Ucapan Terima Kasih
#   - 6. Kontribusi Penulis
#   - 7. Daftar Pustaka
#   - LAMPIRAN (Biodata; Kontribusi; Surat Pernyataan Ketua; Pernyataan
#     Sumber Tulisan; opsional Hasil Uji Similaritas)
#
# Larangan eksplisit (hal 5-6): TIDAK ada halaman sampul, halaman pengesahan,
# dan daftar isi pada berkas naskah artikel ilmiah.
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