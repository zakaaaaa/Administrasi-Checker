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
        forbidden_scope: None = forbidden dicek di seluruh dokumen (default).
               "before_lampiran" = kemunculan di dalam body LAMPIRAN diabaikan —
               dipakai rules laporan, karena bukti pendukung kegiatan lazim
               memuat salinan artikel/abstrak yang bukan pelanggaran struktur.
    """
    name: str
    aliases: list[str] = field(default_factory=list)
    required: bool = False
    forbidden: bool = False
    is_core: bool = False
    order: Optional[int] = None
    forbidden_scope: Optional[str] = None

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


# ============================================================================
# HARDCODED RULES — Laporan Kemajuan & Laporan Akhir PKM 2026
# ============================================================================
#
# Sumber: PDF panduan per skema 2026 folder panduan/ (§Sistematika Laporan
# Kemajuan & §Sistematika Laporan Akhir). Berlaku untuk 8 skema pendanaan:
# K, KC, KI, PI, PM, RE, RSH, VGK.
#
# Laporan Kemajuan — 6 BAB identik antarskema, hanya judul BAB 3 yang beda:
#   BAB 1 PENDAHULUAN → BAB 2 TARGET LUARAN → BAB 3 (METODE PELAKSANAAN:
#   K/PI/PM; TAHAP PELAKSANAAN: KC/KI/VGK; METODE PENELITIAN: RE/RSH) →
#   BAB 4 HASIL YANG DICAPAI → BAB 5 POTENSI HASIL →
#   BAB 6 RENCANA TAHAPAN BERIKUTNYA → DAFTAR PUSTAKA → LAMPIRAN
#   TANPA ringkasan (forbidden, sama seperti proposal).
#
# Laporan Akhir — RINGKASAN WAJIB (tanpa nomor halaman) + 5 BAB
# (VGK 6 BAB), variasi di BAB 2–4:
#   K   : GAMBARAN UMUM USAHA / METODE PELAKSANAAN / HASIL...PENGEMBANGAN USAHA
#   KC,KI: TINJAUAN PUSTAKA / TAHAP PELAKSANAAN / HASIL...POTENSI KHUSUS
#   PI  : TINJAUAN PUSTAKA / METODE PELAKSANAAN / HASIL...POTENSI KHUSUS
#   PM  : GAMBARAN UMUM MASYARAKAT MITRA / METODE PELAKSANAAN /
#         HASIL...POTENSI KEBERLANJUTAN
#   RE,RSH: TINJAUAN PUSTAKA / METODE PENELITIAN / HASIL...POTENSI KHUSUS
#   VGK : GAGASAN / SKENARIO KONTEN / TAHAP PELAKSANAAN /
#         HASIL...POTENSI KHUSUS / PENUTUP (BAB 6)
#
# Ketentuan lain sama dengan proposal: bagian inti maks 10 halaman, tanpa
# halaman sampul & pengesahan, penomoran romawi/arab, format TNR 12 spasi
# 1,15 margin 4/3/3/3, daftar pustaka Harvard.
# ============================================================================

_ROMAN = {1: "I", 2: "II", 3: "III", 4: "IV", 5: "V", 6: "VI"}

_LAPORAN_SCHEMA_NAMES = {
    "K": "Kewirausahaan",
    "KC": "Karsa Cipta",
    "KI": "Karya Inovatif",
    "PI": "Penerapan IPTEK",
    "PM": "Pengabdian kepada Masyarakat",
    "RE": "Riset Eksakta",
    "RSH": "Riset Sosial Humaniora",
    "VGK": "Video Gagasan Konstruktif",
}

# Judul BAB 3 Laporan Kemajuan per skema (satu-satunya variasi antarskema)
_KEMAJUAN_BAB3 = {
    "K": "METODE PELAKSANAAN",
    "PI": "METODE PELAKSANAAN",
    "PM": "METODE PELAKSANAAN",
    "KC": "TAHAP PELAKSANAAN",
    "KI": "TAHAP PELAKSANAAN",
    "VGK": "TAHAP PELAKSANAAN",
    "RE": "METODE PENELITIAN",
    "RSH": "METODE PENELITIAN",
}

# Judul BAB 2 & BAB 4 Laporan Akhir per skema (BAB 3 reuse _KEMAJUAN_BAB3;
# VGK dirakit khusus karena punya 6 BAB)
_AKHIR_BAB2 = {
    "K": "GAMBARAN UMUM USAHA",
    "KC": "TINJAUAN PUSTAKA",
    "KI": "TINJAUAN PUSTAKA",
    "PI": "TINJAUAN PUSTAKA",
    "PM": "GAMBARAN UMUM MASYARAKAT MITRA",
    "RE": "TINJAUAN PUSTAKA",
    "RSH": "TINJAUAN PUSTAKA",
}
_AKHIR_BAB4 = {
    "K": "HASIL YANG DICAPAI DAN POTENSI PENGEMBANGAN USAHA",
    "PM": "HASIL YANG DICAPAI DAN POTENSI KEBERLANJUTAN",
    # default skema lain: HASIL YANG DICAPAI DAN POTENSI KHUSUS
}


def _bab3_field_variants(canonical: str) -> tuple[str, ...]:
    """Alias BAB 3 laporan utk variasi lapangan (judul antarskema kerap tertukar,
    dan dokumen riset lazim menulis 'METODE RISET')."""
    pool = {
        "METODE PELAKSANAAN",
        "TAHAP PELAKSANAAN",
        "METODE PENELITIAN",
        "METODE RISET",
    } - {canonical}
    return tuple(f"BAB {n}. {t}" for t in sorted(pool) for n in ("3", "III"))


def _laporan_bab_rule(
    num: int,
    title: str,
    *,
    order: int,
    extra_aliases: tuple[str, ...] = (),
) -> SectionRule:
    """SectionRule 'BAB N. JUDUL' dengan permutasi alias arab/romawi standar."""
    roman = _ROMAN[num]
    return SectionRule(
        name=f"BAB {num}. {title}",
        aliases=[
            f"BAB {roman}. {title}",
            f"BAB {num} {title}",
            f"BAB {roman} {title}",
            *extra_aliases,
        ],
        required=True,
        is_core=True,
        order=order,
    )


def _laporan_forbidden_sections(
    schema_label: str, doc_label: str, *, forbid_ringkasan: bool
) -> list[SectionRule]:
    """Section terlarang laporan: sampul & pengesahan (+ ringkasan utk kemajuan).

    Semua di-scope "before_lampiran": bukti pendukung kegiatan di LAMPIRAN
    lazim memuat salinan artikel/poster (ada ABSTRAK) — bukan pelanggaran.
    doc_label sengaja TIDAK dipakai telanjang sebagai alias sampul: frasa
    "Laporan Kemajuan" muncul wajar di body (mis. daftar luaran Bab 4).
    """
    sections = [
        SectionRule(
            name="HALAMAN SAMPUL",
            aliases=[
                "COVER",
                "SAMPUL",
                f"{doc_label} PKM",
                f"{doc_label} {schema_label}",
                f"{doc_label} PROGRAM KREATIVITAS MAHASISWA",
            ],
            forbidden=True,
            forbidden_scope="before_lampiran",
        ),
        SectionRule(
            name="HALAMAN PENGESAHAN",
            aliases=[
                "LEMBAR PENGESAHAN",
                "PENGESAHAN LAPORAN",
                "PENGESAHAN PKM",
                "PENGESAHAN USULAN",
            ],
            forbidden=True,
            forbidden_scope="before_lampiran",
        ),
    ]
    if forbid_ringkasan:
        sections.append(
            SectionRule(
                name="RINGKASAN",
                aliases=["ABSTRAK", "ABSTRACT"],
                forbidden=True,
                forbidden_scope="before_lampiran",
            )
        )
    return sections


def get_pkm_laporan_kemajuan_rules(schema_code: str) -> SchemaRules:
    """
    Aturan Laporan Kemajuan PKM 2026 untuk satu skema pendanaan.

    schema_code: kode pendek tanpa prefix — "K", "KC", "KI", "PI", "PM",
    "RE", "RSH", "VGK".
    """
    code = schema_code.upper().removeprefix("PKM-")
    if code not in _LAPORAN_SCHEMA_NAMES:
        raise ValueError(f"Skema tidak dikenal untuk laporan kemajuan: {schema_code!r}")
    bab3 = _KEMAJUAN_BAB3[code]
    # Toleransi variasi lapangan: judul BAB 3 skema lain lazim tertukar,
    # dan dokumen riset kerap menulis "METODE RISET" alih-alih "METODE PENELITIAN"
    bab3_variants = _bab3_field_variants(bab3)
    return SchemaRules(
        competition_code="PKM",
        schema_code=code,
        report_type_code="PROGRESS_REPORT",
        schema_name=_LAPORAN_SCHEMA_NAMES[code],
        year=2026,
        sections=[
            # --- SECTION WAJIB ---
            SectionRule(name="DAFTAR ISI", required=True, order=1),
            SectionRule(
                name="DAFTAR LAMPIRAN",
                aliases=["DAFTAR LAMPIRAN-LAMPIRAN"],
                required=True,
                order=4,
            ),
            _laporan_bab_rule(1, "PENDAHULUAN", order=5),
            _laporan_bab_rule(2, "TARGET LUARAN", order=6),
            _laporan_bab_rule(3, bab3, order=7, extra_aliases=bab3_variants),
            _laporan_bab_rule(4, "HASIL YANG DICAPAI", order=8),
            _laporan_bab_rule(5, "POTENSI HASIL", order=9),
            _laporan_bab_rule(
                6,
                "RENCANA TAHAPAN BERIKUTNYA",
                order=10,
                extra_aliases=("BAB 6. RENCANA TAHAP BERIKUTNYA", "BAB VI. RENCANA TAHAP BERIKUTNYA"),
            ),
            SectionRule(name="DAFTAR PUSTAKA", required=True, is_core=True, order=11),
            SectionRule(
                name="LAMPIRAN",
                aliases=["LAMPIRAN 1", "LAMPIRAN 1.", "LAMPIRAN-LAMPIRAN"],
                required=True,
                order=12,
            ),
            # --- SECTION OPSIONAL ---
            SectionRule(name="DAFTAR GAMBAR", required=False, order=2),
            SectionRule(name="DAFTAR TABEL", required=False, order=3),
            # --- SECTION TERLARANG ---
            *_laporan_forbidden_sections(
                f"PKM-{code}", "LAPORAN KEMAJUAN", forbid_ringkasan=True
            ),
        ],
    )


def get_pkm_laporan_akhir_rules(schema_code: str) -> SchemaRules:
    """
    Aturan Laporan Akhir PKM 2026 untuk satu skema pendanaan.

    Berbeda dari kemajuan: RINGKASAN wajib (bukan terlarang), 5 BAB
    (VGK 6 BAB) diakhiri PENUTUP.
    """
    code = schema_code.upper().removeprefix("PKM-")
    if code not in _LAPORAN_SCHEMA_NAMES:
        raise ValueError(f"Skema tidak dikenal untuk laporan akhir: {schema_code!r}")

    if code == "VGK":
        bab_rules = [
            _laporan_bab_rule(1, "PENDAHULUAN", order=6),
            _laporan_bab_rule(2, "GAGASAN", order=7),
            _laporan_bab_rule(3, "SKENARIO KONTEN", order=8),
            _laporan_bab_rule(4, "TAHAP PELAKSANAAN", order=9),
            _laporan_bab_rule(
                5,
                "HASIL YANG DICAPAI DAN POTENSI KHUSUS",
                order=10,
                extra_aliases=("BAB 5. HASIL YANG DICAPAI", "BAB V. HASIL YANG DICAPAI"),
            ),
            _laporan_bab_rule(
                6, "PENUTUP", order=11,
                extra_aliases=("BAB 6. KESIMPULAN DAN SARAN", "BAB VI. KESIMPULAN DAN SARAN"),
            ),
        ]
        dp_order, lamp_order = 12, 13
    else:
        bab4 = _AKHIR_BAB4.get(code, "HASIL YANG DICAPAI DAN POTENSI KHUSUS")
        bab_rules = [
            _laporan_bab_rule(1, "PENDAHULUAN", order=6),
            _laporan_bab_rule(2, _AKHIR_BAB2[code], order=7),
            _laporan_bab_rule(
                3,
                _KEMAJUAN_BAB3[code],
                order=8,
                extra_aliases=_bab3_field_variants(_KEMAJUAN_BAB3[code]),
            ),
            _laporan_bab_rule(
                4,
                bab4,
                order=9,
                # alias pendek: heading dokumen sering ditulis tanpa frasa potensi
                extra_aliases=("BAB 4. HASIL YANG DICAPAI", "BAB IV. HASIL YANG DICAPAI"),
            ),
            _laporan_bab_rule(
                5, "PENUTUP", order=10,
                extra_aliases=("BAB 5. KESIMPULAN DAN SARAN", "BAB V. KESIMPULAN DAN SARAN"),
            ),
        ]
        dp_order, lamp_order = 11, 12

    return SchemaRules(
        competition_code="PKM",
        schema_code=code,
        report_type_code="FINAL_REPORT",
        schema_name=_LAPORAN_SCHEMA_NAMES[code],
        year=2026,
        sections=[
            # --- SECTION WAJIB ---
            # RINGKASAN di awal berkas, tanpa nomor halaman (panduan §A)
            SectionRule(name="RINGKASAN", required=True, order=1),
            SectionRule(name="DAFTAR ISI", required=True, order=2),
            SectionRule(
                name="DAFTAR LAMPIRAN",
                aliases=["DAFTAR LAMPIRAN-LAMPIRAN"],
                required=True,
                order=5,
            ),
            *bab_rules,
            SectionRule(name="DAFTAR PUSTAKA", required=True, is_core=True, order=dp_order),
            SectionRule(
                name="LAMPIRAN",
                aliases=["LAMPIRAN 1", "LAMPIRAN 1.", "LAMPIRAN-LAMPIRAN"],
                required=True,
                order=lamp_order,
            ),
            # --- SECTION OPSIONAL ---
            SectionRule(name="DAFTAR GAMBAR", required=False, order=3),
            SectionRule(name="DAFTAR TABEL", required=False, order=4),
            # --- SECTION TERLARANG ---
            *_laporan_forbidden_sections(
                f"PKM-{code}", "LAPORAN AKHIR", forbid_ringkasan=False
            ),
        ],
    )


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