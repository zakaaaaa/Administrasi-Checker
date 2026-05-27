"""
SimilarityRules — konfigurasi pengecekan hasil uji similaritas (Turnitin) PKM-KC.

Persentase "Overall Similarity" pada Lampiran "Hasil Uji Periksa Similaritas"
tidak boleh LEBIH dari max_percent. Tepat di max_percent masih lolos
(mis. 25% lolos, 26% gagal).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class SimilarityRules:
    schema_label: str
    max_percent: int = 25            # > max_percent → fail; tepat max_percent masih lolos
    max_images_to_scan: int = 3      # OCR hanya beberapa gambar pertama lampiran similaritas
    crop_top_ratio: float = 0.35     # OCR cukup bagian atas gambar (tempat "XX% Overall Similarity")


def get_pkm_kc_similarity_rules() -> SimilarityRules:
    """Aturan similaritas PKM-KC 2026 — maksimal 25%."""
    return SimilarityRules(schema_label="PKM-KC", max_percent=25)


def get_pkm_vgk_similarity_rules() -> SimilarityRules:
    """Aturan similaritas PKM-VGK — sama dengan PKM-KC."""
    rules = get_pkm_kc_similarity_rules()
    rules.schema_label = "PKM-VGK"
    return rules
