"""
Kamus kata Inggris — sumber data untuk deteksi kata asing yang tidak italic.

Sumber utama: tabel `dictionary_english` di Supabase.

    Table "public.dictionary_english"
     Column |  Type
    --------+--------
     id     | bigint
     word   | text

Karakteristik dataset (diverifikasi 2026-09-08, 361.423 baris):
- Satu kata per baris, huruf kecil semua, tanpa spasi/tanda hubung/angka.
  Artinya frasa seperti "machine learning" TIDAK ada sebagai satu entri —
  pencocokan berlangsung per kata ("machine", lalu "learning").
- Sudah dibersihkan dari lema KBBI. Kata serapan yang sudah jadi kata
  Indonesia tidak ada di sini: data, sensor, server, monitor, modal, input,
  media, video, format, total, final, objek, ide, radio, energi, sistem,
  analisis. Sementara kata yang memang masih asing tetap ada: software,
  hardware, output, dashboard, startup.
  Pemilahan ini persis mengikuti KBBI — "input" dibuang, "output" bertahan —
  sama dengan hasil verifikasi di tests/test_foreign_words_kbbi.py.

Karena penyaringan KBBI sudah dilakukan di sisi dataset, checker TIDAK perlu
menyaring ulang. Uji lapangan pada empat paragraf PKM berbahasa Indonesia
(171 token: teknologi informasi, metode pelaksanaan, luaran, anggaran)
menghasilkan 0 kecocokan — tidak ada false positive dari kosakata Indonesia.

Kegagalan koneksi TIDAK membatalkan pengecekan dokumen: pemanggil menyediakan
daftar cadangan (FOREIGN_WORDS di format_checker) yang dipakai kalau DB tidak
bisa dihubungi. Cakupannya lebih sempit, tapi pengecekan tetap berjalan.
"""

from __future__ import annotations

import logging
import os
import threading
from dataclasses import dataclass
from typing import Iterable, Optional

logger = logging.getLogger(__name__)


# Nama tabel bisa di-override lewat env kalau nanti dataset dipindah/diganti.
TABLE_NAME = os.getenv("ENGLISH_DICTIONARY_TABLE", "dictionary_english")

# Set ENGLISH_DICTIONARY_SOURCE=fallback untuk memaksa pakai daftar kurasi saja
# (dipakai test supaya tidak menyentuh jaringan).
_SOURCE_ENV = "ENGLISH_DICTIONARY_SOURCE"

# Kata sependek 1-2 huruf terlalu sering bertabrakan dengan singkatan, satuan,
# dan penomoran dalam dokumen Indonesia ("in", "or", "no", "id"). Ambang ini
# membuang bagian ekor kamus yang risikonya jauh lebih besar dari manfaatnya.
MIN_WORD_LENGTH = 3

# Kata Indonesia yang tetap lolos ke tabel. Tabel dibersihkan terhadap LEMA
# KBBI, sedangkan bentuk turunan seperti "kelima" (ke- + lima) bukan lema
# tersendiri — ia tertinggal dan membuat "Kelima unsur tersebut" divonis kata
# asing. Tambah entri di sini (huruf kecil) setiap ada temuan serupa.
NOT_ENGLISH = frozenset({"kelima"})


@dataclass(frozen=True)
class EnglishDictionary:
    """Kamus siap pakai beserta asal-usulnya (untuk pelaporan)."""

    words: frozenset[str]
    source: str  # "supabase" | "fallback"
    error: Optional[str] = None

    @property
    def is_fallback(self) -> bool:
        return self.source == "fallback"

    def __contains__(self, word: str) -> bool:
        return word.lower() in self.words


# Cache proses. Kamus 361k kata ±15 MB — dimuat sekali, dipakai semua request.
_cache: Optional[EnglishDictionary] = None
_lock = threading.Lock()


def _fetch_from_db() -> frozenset[str]:
    """Ambil seluruh kolom `word`. Import app.db ditunda supaya modul ini tetap
    bisa di-import di lingkungan tanpa DATABASE_URL (app.db raise saat import)."""
    from app.db import get_cursor  # noqa: PLC0415 — sengaja lazy

    with get_cursor() as cur:
        cur.execute(f"SELECT word FROM {TABLE_NAME}")  # noqa: S608 — nama tabel dari env, bukan input user
        rows = cur.fetchall()

    words = set()
    for row in rows:
        raw = row["word"] if isinstance(row, dict) else row[0]
        if not raw:
            continue
        w = raw.strip().lower()
        if len(w) >= MIN_WORD_LENGTH and w.isalpha():
            words.add(w)
    return frozenset(words - NOT_ENGLISH)


def _normalize_fallback(fallback: Iterable[str]) -> frozenset[str]:
    """Daftar kurasi memuat frasa ("machine learning"); pecah jadi kata tunggal
    supaya bentuknya seragam dengan isi tabel."""
    words = set()
    for entry in fallback:
        for token in entry.lower().replace("-", " ").replace("/", " ").split():
            token = token.strip(".,()")
            if len(token) >= MIN_WORD_LENGTH and token.isalpha():
                words.add(token)
    return frozenset(words)


def get_english_dictionary(
    fallback: Iterable[str] = (), force_reload: bool = False
) -> EnglishDictionary:
    """
    Kamus Inggris dari Supabase, di-cache per proses.

    Kalau query gagal (DB mati, DATABASE_URL kosong, tabel tidak ada), yang
    dikembalikan adalah `fallback` dengan source="fallback" — bukan exception,
    supaya satu dokumen tidak gagal dicek gara-gara database.
    """
    global _cache

    if os.getenv(_SOURCE_ENV, "").lower() == "fallback":
        return EnglishDictionary(
            words=_normalize_fallback(fallback),
            source="fallback",
            error=f"{_SOURCE_ENV}=fallback",
        )

    with _lock:
        if _cache is not None and not force_reload:
            return _cache

        try:
            words = _fetch_from_db()
            if not words:
                raise RuntimeError(f"tabel {TABLE_NAME} kosong")
            _cache = EnglishDictionary(words=words, source="supabase")
            logger.info("Kamus Inggris dimuat: %d kata dari %s", len(words), TABLE_NAME)
        except Exception as e:
            logger.warning(
                "Gagal memuat %s (%s) — pakai daftar kurasi bawaan", TABLE_NAME, e
            )
            _cache = EnglishDictionary(
                words=_normalize_fallback(fallback),
                source="fallback",
                error=str(e),
            )
        return _cache


def reset_cache() -> None:
    """Kosongkan cache (dipakai test dan saat dataset di-update)."""
    global _cache
    with _lock:
        _cache = None
