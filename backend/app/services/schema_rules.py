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
# HARDCODED RULES — PKM-VGK Proposal 2026
# ============================================================================
#
# Sumber aturan: blueprint v0.3 §8.x (PKM-VGK — Video Gagasan Konstruktif)
# Struktur berbeda dari KC: 5 BAB dengan BAB 2 Gagasan & BAB 3 Skenario Konten
# ============================================================================


def get_pkm_vgk_proposal_rules() -> SchemaRules:
    """
    Aturan PKM-VGK Proposal 2026.

    Section yang diizinkan, urutannya:
        1. DAFTAR ISI                           (wajib)
        2. DAFTAR GAMBAR                        (opsional)
        3. DAFTAR TABEL                         (opsional)
        4. DAFTAR LAMPIRAN                      (wajib)
        5. BAB 1. PENDAHULUAN                   (wajib, inti)
        6. BAB 2. GAGASAN                       (wajib, inti)
        7. BAB 3. SKENARIO KONTEN               (wajib, inti)
        8. BAB 4. METODE PELAKSANAAN            (wajib, inti)
        9. BAB 5. BIAYA DAN JADWAL KEGIATAN     (wajib, inti)
       10. DAFTAR PUSTAKA                       (wajib, inti)
       11. LAMPIRAN                             (wajib)

    Section TERLARANG:
        - Halaman Sampul / Cover
        - Halaman Pengesahan / Lembar Pengesahan
        - Ringkasan / Abstrak
    """
    return SchemaRules(
        competition_code="PKM",
        schema_code="VGK",
        report_type_code="PROPOSAL",
        schema_name="Video Gagasan Konstruktif",
        year=2026,
        sections=[
            # --- SECTION WAJIB ---
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
                name="BAB 2. GAGASAN",
                aliases=[
                    "BAB II. GAGASAN",
                    "BAB 2 GAGASAN",
                    "BAB II GAGASAN",
                ],
                required=True,
                is_core=True,
                order=6,
            ),
            SectionRule(
                name="BAB 3. SKENARIO KONTEN",
                aliases=[
                    "BAB III. SKENARIO KONTEN",
                    "BAB 3 SKENARIO KONTEN",
                    "BAB III SKENARIO KONTEN",
                    "BAB 3. SKENARIO",
                    "BAB III. SKENARIO",
                ],
                required=True,
                is_core=True,
                order=7,
            ),
            SectionRule(
                name="BAB 4. METODE PELAKSANAAN",
                aliases=[
                    "BAB IV. METODE PELAKSANAAN",
                    "BAB 4 METODE PELAKSANAAN",
                    "BAB IV METODE PELAKSANAAN",
                    "BAB 4. METODE",
                    "BAB IV. METODE",
                ],
                required=True,
                is_core=True,
                order=8,
            ),
            SectionRule(
                name="BAB 5. BIAYA DAN JADWAL KEGIATAN",
                aliases=[
                    "BAB V. BIAYA DAN JADWAL KEGIATAN",
                    "BAB 5 BIAYA DAN JADWAL KEGIATAN",
                    "BAB V BIAYA DAN JADWAL KEGIATAN",
                    "BAB 5. BIAYA DAN JADWAL",
                    "BAB V. BIAYA DAN JADWAL",
                ],
                required=True,
                is_core=True,
                order=9,
            ),
            SectionRule(
                name="DAFTAR PUSTAKA",
                required=True,
                is_core=True,
                order=10,
            ),
            SectionRule(
                name="LAMPIRAN",
                aliases=[
                    "LAMPIRAN 1",
                    "LAMPIRAN 1.",
                    "LAMPIRAN-LAMPIRAN",
                ],
                required=True,
                order=11,
            ),

            # --- SECTION OPSIONAL ---
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

            # --- SECTION TERLARANG ---
            SectionRule(
                name="HALAMAN SAMPUL",
                aliases=[
                    "COVER",
                    "SAMPUL",
                    "PROPOSAL PKM",
                    "PROPOSAL PKM-VGK",
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
# HARDCODED RULES — PKM-AI Proposal 2026
# ============================================================================
#
# Format artikel ilmiah — tidak memakai "BAB N" tapi heading section biasa.
# Struktur inti sesudah abstract:
#   Pendahuluan → Metode → Hasil dan Pembahasan → Kesimpulan →
#   Ucapan Terimakasih → Kontribusi Penulis → Daftar Pustaka → LAMPIRAN
# ============================================================================


def get_pkm_ai_proposal_rules() -> SchemaRules:
    """
    Aturan PKM-AI Proposal 2026.

    Struktur wajib (sesudah front matter Judul/Abstrak):
        1. Pendahuluan
        2. Metode
        3. Hasil dan Pembahasan
        4. Kesimpulan
        5. Ucapan Terimakasih
        6. Kontribusi Penulis
        7. Daftar Pustaka
        8. LAMPIRAN

    Section TERLARANG:
        - BAB N (format artikel tidak pakai "BAB")
        - HALAMAN SAMPUL / PENGESAHAN
        - RINGKASAN (bukan ABSTRAK — front matter PKM-AI memang ada abstrak)
        - BIAYA DAN JADWAL KEGIATAN
    """
    return SchemaRules(
        competition_code="PKM",
        schema_code="AI",
        report_type_code="SCIENTIFIC_ARTICLE",
        schema_name="Artikel Ilmiah",
        year=2026,
        sections=[
            # --- SECTION WAJIB (inti) ---
            SectionRule(
                name="Pendahuluan",
                aliases=["PENDAHULUAN"],
                required=True,
                is_core=True,
                order=1,
            ),
            SectionRule(
                name="Metode",
                aliases=["METODE", "Metode Pelaksanaan", "METODE PELAKSANAAN"],
                required=True,
                is_core=True,
                order=2,
            ),
            SectionRule(
                name="Hasil dan Pembahasan",
                aliases=[
                    "HASIL DAN PEMBAHASAN",
                    "Hasil dan Diskusi",
                    "HASIL DAN DISKUSI",
                    "Hasil",
                    "HASIL",
                ],
                required=True,
                is_core=True,
                order=3,
            ),
            SectionRule(
                name="Kesimpulan",
                aliases=["KESIMPULAN", "Simpulan", "SIMPULAN"],
                required=True,
                is_core=True,
                order=4,
            ),
            SectionRule(
                name="Ucapan Terimakasih",
                aliases=[
                    "UCAPAN TERIMAKASIH",
                    "Ucapan Terima Kasih",
                    "UCAPAN TERIMA KASIH",
                ],
                required=True,
                is_core=True,
                order=5,
            ),
            SectionRule(
                name="Kontribusi Penulis",
                aliases=["KONTRIBUSI PENULIS"],
                required=True,
                is_core=True,
                order=6,
            ),
            SectionRule(
                name="Daftar Pustaka",
                aliases=["DAFTAR PUSTAKA"],
                required=True,
                is_core=True,
                order=7,
            ),
            SectionRule(
                name="LAMPIRAN",
                aliases=["LAMPIRAN 1", "LAMPIRAN 1.", "LAMPIRAN-LAMPIRAN"],
                required=True,
                order=8,
            ),

            # --- SECTION OPSIONAL ---
            SectionRule(name="Daftar Gambar", aliases=["DAFTAR GAMBAR"], required=False),
            SectionRule(name="Daftar Tabel", aliases=["DAFTAR TABEL"], required=False),

            # --- SECTION TERLARANG ---
            SectionRule(
                name="BAB 1",
                aliases=[
                    "BAB I", "BAB 2", "BAB II", "BAB 3", "BAB III",
                    "BAB 4", "BAB IV", "BAB 1. PENDAHULUAN", "BAB I. PENDAHULUAN",
                ],
                forbidden=True,
            ),
            SectionRule(
                name="BIAYA DAN JADWAL KEGIATAN",
                aliases=[
                    "BIAYA DAN JADWAL",
                    "RENCANA ANGGARAN BIAYA",
                    "ANGGARAN BIAYA",
                ],
                forbidden=True,
            ),
            SectionRule(
                name="HALAMAN SAMPUL",
                aliases=["COVER", "SAMPUL", "PROPOSAL PKM-AI"],
                forbidden=True,
            ),
            SectionRule(
                name="HALAMAN PENGESAHAN",
                aliases=[
                    "LEMBAR PENGESAHAN",
                    "PENGESAHAN PROPOSAL",
                    "PENGESAHAN PKM",
                ],
                forbidden=True,
            ),
            SectionRule(
                name="RINGKASAN",
                forbidden=True,
            ),
        ],
    )