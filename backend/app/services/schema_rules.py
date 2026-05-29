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
# HARDCODED RULES — PKM-RE & PKM-RSH Proposal 2026
# ============================================================================
#
# PKM-RE  : Riset Eksakta
# PKM-RSH : Riset Sosial Humaniora
#
# Struktur sama (4 BAB), beda hanya pada nama skema (label & schema_code):
#   1. BAB 1. PENDAHULUAN
#   2. BAB 2. TINJAUAN PUSTAKA
#   3. BAB 3. METODE PENELITIAN
#   4. BAB 4. BIAYA DAN JADWAL KEGIATAN
#   5. DAFTAR PUSTAKA
#   6. LAMPIRAN
# ============================================================================


def _build_pkm_riset_sections() -> list[SectionRule]:
    """Section list bersama untuk PKM-RE & PKM-RSH (struktur identik)."""
    return [
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
            name="BAB 3. METODE PENELITIAN",
            aliases=[
                "BAB III. METODE PENELITIAN",
                "BAB 3 METODE PENELITIAN",
                "BAB III METODE PENELITIAN",
                "BAB 3. METODE",
                "BAB III. METODE",
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
            aliases=[
                "LAMPIRAN 1",
                "LAMPIRAN 1.",
                "LAMPIRAN-LAMPIRAN",
            ],
            required=True,
            order=10,
        ),
        # --- OPSIONAL ---
        SectionRule(name="DAFTAR GAMBAR", required=False, order=2),
        SectionRule(name="DAFTAR TABEL", required=False, order=3),
        # --- TERLARANG ---
        SectionRule(
            name="HALAMAN SAMPUL",
            aliases=[
                "COVER",
                "SAMPUL",
                "PROPOSAL PKM",
                "PROPOSAL PKM-RE",
                "PROPOSAL PKM-RSH",
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
    ]


def get_pkm_re_proposal_rules() -> SchemaRules:
    """Aturan PKM-RE (Riset Eksakta) Proposal 2026."""
    return SchemaRules(
        competition_code="PKM",
        schema_code="RE",
        report_type_code="PROPOSAL",
        schema_name="Riset Eksakta",
        year=2026,
        sections=_build_pkm_riset_sections(),
    )


def get_pkm_rsh_proposal_rules() -> SchemaRules:
    """Aturan PKM-RSH (Riset Sosial Humaniora) Proposal 2026."""
    return SchemaRules(
        competition_code="PKM",
        schema_code="RSH",
        report_type_code="PROPOSAL",
        schema_name="Riset Sosial Humaniora",
        year=2026,
        sections=_build_pkm_riset_sections(),
    )


# ============================================================================
# HARDCODED RULES — PKM-K / PKM-KI / PKM-PI / PKM-PM Proposal 2026
# ============================================================================
#
# Keempat skema ini bergaya "KC-like": 4 BAB + Daftar Pustaka + Lampiran,
# section terlarang sama (sampul/pengesahan/ringkasan DILARANG). Yang berbeda
# antarskema hanya judul BAB 2 & BAB 3:
#
#   Skema    | BAB 2                          | BAB 3
#   ---------|--------------------------------|--------------------
#   PKM-K    | GAMBARAN UMUM RENCANA USAHA     | METODE PELAKSANAAN
#   PKM-KI   | TINJAUAN PUSTAKA                | TAHAP PELAKSANAAN
#   PKM-PI   | TINJAUAN PUSTAKA                | METODE PELAKSANAAN
#   PKM-PM   | GAMBARAN UMUM MASYARAKAT MITRA  | METODE PELAKSANAAN
# ============================================================================


def _build_pkm_kc_like_sections(
    schema_label: str,
    bab2_title: str,
    bab3_title: str,
    bab3_extra_aliases: tuple[str, ...] = (),
) -> list[SectionRule]:
    """Section list untuk skema PKM 4-BAB bergaya KC (PKM-K/KI/PI/PM).

    BAB 1 PENDAHULUAN & BAB 4 BIAYA DAN JADWAL KEGIATAN identik antarskema;
    hanya BAB 2 & BAB 3 yang berbeda judul. `schema_label` dipakai untuk alias
    forbidden "PROPOSAL PKM-XX". `bab3_extra_aliases` untuk variasi judul BAB 3
    yang lazim tertukar di dokumen lapangan (mis. "METODE" / "METODE PELAKSANAAN").
    """
    return [
        # --- SECTION WAJIB ---
        SectionRule(name="DAFTAR ISI", required=True, order=1),
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
            name=f"BAB 2. {bab2_title}",
            aliases=[
                f"BAB II. {bab2_title}",
                f"BAB 2 {bab2_title}",
                f"BAB II {bab2_title}",
            ],
            required=True,
            is_core=True,
            order=6,
        ),
        SectionRule(
            name=f"BAB 3. {bab3_title}",
            aliases=[
                f"BAB III. {bab3_title}",
                f"BAB 3 {bab3_title}",
                f"BAB III {bab3_title}",
                *bab3_extra_aliases,
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
        SectionRule(name="DAFTAR PUSTAKA", required=True, is_core=True, order=9),
        SectionRule(
            name="LAMPIRAN",
            aliases=["LAMPIRAN 1", "LAMPIRAN 1.", "LAMPIRAN-LAMPIRAN"],
            required=True,
            order=10,
        ),
        # --- SECTION OPSIONAL ---
        SectionRule(name="DAFTAR GAMBAR", required=False, order=2),
        SectionRule(name="DAFTAR TABEL", required=False, order=3),
        # --- SECTION TERLARANG ---
        SectionRule(
            name="HALAMAN SAMPUL",
            aliases=[
                "COVER",
                "SAMPUL",
                "PROPOSAL PKM",
                f"PROPOSAL {schema_label}",
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
    ]


def get_pkm_k_proposal_rules() -> SchemaRules:
    """Aturan PKM-K (Kewirausahaan) Proposal 2026."""
    return SchemaRules(
        competition_code="PKM",
        schema_code="K",
        report_type_code="PROPOSAL",
        schema_name="Kewirausahaan",
        year=2026,
        sections=_build_pkm_kc_like_sections(
            schema_label="PKM-K",
            bab2_title="GAMBARAN UMUM RENCANA USAHA",
            bab3_title="METODE PELAKSANAAN",
            bab3_extra_aliases=("BAB 3. METODE", "BAB III. METODE"),
        ),
    )


def get_pkm_ki_proposal_rules() -> SchemaRules:
    """Aturan PKM-KI (Karya Inovatif) Proposal 2026."""
    return SchemaRules(
        competition_code="PKM",
        schema_code="KI",
        report_type_code="PROPOSAL",
        schema_name="Karya Inovatif",
        year=2026,
        sections=_build_pkm_kc_like_sections(
            schema_label="PKM-KI",
            bab2_title="TINJAUAN PUSTAKA",
            bab3_title="TAHAP PELAKSANAAN",
            bab3_extra_aliases=(
                "BAB 3. METODE PELAKSANAAN",
                "BAB III. METODE PELAKSANAAN",
                "BAB 3. METODE",
                "BAB III. METODE",
            ),
        ),
    )


def get_pkm_pi_proposal_rules() -> SchemaRules:
    """Aturan PKM-PI (Penerapan IPTEK) Proposal 2026."""
    return SchemaRules(
        competition_code="PKM",
        schema_code="PI",
        report_type_code="PROPOSAL",
        schema_name="Penerapan IPTEK",
        year=2026,
        sections=_build_pkm_kc_like_sections(
            schema_label="PKM-PI",
            bab2_title="TINJAUAN PUSTAKA",
            bab3_title="METODE PELAKSANAAN",
            bab3_extra_aliases=("BAB 3. METODE", "BAB III. METODE"),
        ),
    )


def get_pkm_pm_proposal_rules() -> SchemaRules:
    """Aturan PKM-PM (Pengabdian kepada Masyarakat) Proposal 2026."""
    return SchemaRules(
        competition_code="PKM",
        schema_code="PM",
        report_type_code="PROPOSAL",
        schema_name="Pengabdian kepada Masyarakat",
        year=2026,
        sections=_build_pkm_kc_like_sections(
            schema_label="PKM-PM",
            bab2_title="GAMBARAN UMUM MASYARAKAT MITRA",
            bab3_title="METODE PELAKSANAAN",
            bab3_extra_aliases=("BAB 3. METODE", "BAB III. METODE"),
        ),
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


# ============================================================================
# HARDCODED RULES — PKM-GFT Proposal 2026
# ============================================================================
#
# PKM-GFT (Gagasan Futuristik Tertulis) = PKM insentif TANPA pelaksanaan
# kegiatan. Struktur lebih ringkas dibanding skema pendanaan: 3 BAB + Daftar
# Pustaka + Lampiran, TIDAK ada BAB 4 Biaya & Jadwal Kegiatan.
#
# Sistematika sesuai PDF panduan §C halaman 6:
#   DAFTAR ISI
#   BAB 1. PENDAHULUAN
#   BAB 2. GAGASAN
#   BAB 3. KESIMPULAN
#   DAFTAR PUSTAKA
#   LAMPIRAN
#
# Catatan: PDF tidak menyebut "DAFTAR LAMPIRAN" sebagai section terpisah,
# jadi tidak diwajibkan.
#
# Section TERLARANG (PDF halaman 5 paragraf akhir bagian A. Susunan Artikel):
#   halaman sampul, halaman pengesahan, ringkasan / abstrak
#   → "Jika isi utama proposal ada halaman sampul, lembar pengesahan,
#      ringkasan atau abstrak, maka gagasan tersebut TIDAK LOLOS tahap 1."
# ============================================================================


def get_pkm_gft_proposal_rules() -> SchemaRules:
    """
    Aturan PKM-GFT (Gagasan Futuristik Tertulis) Proposal 2026.

    Section yang diizinkan, urutannya:
        1. DAFTAR ISI            (wajib)
        2. DAFTAR GAMBAR         (opsional)
        3. DAFTAR TABEL          (opsional)
        4. BAB 1. PENDAHULUAN    (wajib, inti)
        5. BAB 2. GAGASAN        (wajib, inti)
        6. BAB 3. KESIMPULAN     (wajib, inti)
        7. DAFTAR PUSTAKA        (wajib, inti)
        8. LAMPIRAN              (wajib)

    Section TERLARANG (red flag → tidak lolos tahap 1):
        - Halaman Sampul / Cover
        - Halaman Pengesahan / Lembar Pengesahan
        - Ringkasan / Abstrak
    """
    return SchemaRules(
        competition_code="PKM",
        schema_code="GFT",
        report_type_code="PROPOSAL",
        schema_name="Gagasan Futuristik Tertulis",
        year=2026,
        sections=[
            # --- SECTION WAJIB ---
            SectionRule(name="DAFTAR ISI", required=True, order=1),
            SectionRule(
                name="BAB 1. PENDAHULUAN",
                aliases=[
                    "BAB I. PENDAHULUAN",
                    "BAB 1 PENDAHULUAN",
                    "BAB I PENDAHULUAN",
                ],
                required=True,
                is_core=True,
                order=4,
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
                order=5,
            ),
            SectionRule(
                name="BAB 3. KESIMPULAN",
                aliases=[
                    "BAB III. KESIMPULAN",
                    "BAB 3 KESIMPULAN",
                    "BAB III KESIMPULAN",
                    "BAB 3. SIMPULAN",
                    "BAB III. SIMPULAN",
                ],
                required=True,
                is_core=True,
                order=6,
            ),
            SectionRule(
                name="DAFTAR PUSTAKA",
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
            SectionRule(name="DAFTAR GAMBAR", required=False, order=2),
            SectionRule(name="DAFTAR TABEL", required=False, order=3),
            # --- SECTION TERLARANG ---
            SectionRule(
                name="HALAMAN SAMPUL",
                aliases=[
                    "COVER",
                    "SAMPUL",
                    "PROPOSAL PKM",
                    "PROPOSAL PKM-GFT",
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