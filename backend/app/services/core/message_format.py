"""
Helper format pesan finding standar untuk semua checker.

Format:
    "Halaman X — kesalahan — Perbaiki: perbaikan"

Untuk finding yang tidak punya halaman spesifik (dokumen-wide, mis. total RAB
salah, judul tidak ditemukan), pakai placeholder "Halaman -".
"""
from __future__ import annotations

from typing import Optional


def format_finding(
    halaman: Optional[int],
    kesalahan: str,
    perbaikan: str,
) -> str:
    """
    Bangun pesan 3-bagian standar.

    Args:
        halaman: nomor halaman fisik (1-based). None → "Halaman -".
        kesalahan: deskripsi apa yang salah (tanpa kata "Perbaiki").
        perbaikan: deskripsi singkat cara memperbaiki / nilai yang seharusnya.

    Returns:
        "Halaman X — kesalahan — Perbaiki: perbaikan"
        atau "Halaman - — kesalahan — Perbaiki: perbaikan"
    """
    halaman_str = f"Halaman {halaman}" if halaman is not None else "Halaman -"
    return f"{halaman_str} — {kesalahan} — Perbaiki: {perbaikan}"
