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
    # OCR scan multiple gambar lampiran similaritas — overview Turnitin tidak
    # selalu di gambar PERTAMA (kadang last page report). 20 cukup untuk cover
    # semua kasus normal, dan OCR Vision paralel via ThreadPoolExecutor.
    max_images_to_scan: int = 20
    crop_top_ratio: float = 0.35     # OCR cukup bagian atas gambar (tempat "XX% Overall Similarity")


def get_pkm_kc_similarity_rules() -> SimilarityRules:
    """Aturan similaritas PKM-KC 2026 — maksimal 25%."""
    return SimilarityRules(schema_label="PKM-KC", max_percent=25)


def get_pkm_vgk_similarity_rules() -> SimilarityRules:
    """Aturan similaritas PKM-VGK — sama dengan PKM-KC."""
    rules = get_pkm_kc_similarity_rules()
    rules.schema_label = "PKM-VGK"
    return rules


def get_pkm_re_similarity_rules() -> SimilarityRules:
    """Aturan similaritas PKM-RE — sama dengan PKM-KC (maks 25%)."""
    rules = get_pkm_kc_similarity_rules()
    rules.schema_label = "PKM-RE"
    return rules


def get_pkm_rsh_similarity_rules() -> SimilarityRules:
    """Aturan similaritas PKM-RSH — sama dengan PKM-KC (maks 25%)."""
    rules = get_pkm_kc_similarity_rules()
    rules.schema_label = "PKM-RSH"
    return rules


def get_pkm_k_similarity_rules() -> SimilarityRules:
    """Aturan similaritas PKM-K — sama dengan PKM-KC (maks 25%)."""
    rules = get_pkm_kc_similarity_rules()
    rules.schema_label = "PKM-K"
    return rules


def get_pkm_ki_similarity_rules() -> SimilarityRules:
    """Aturan similaritas PKM-KI — sama dengan PKM-KC (maks 25%)."""
    rules = get_pkm_kc_similarity_rules()
    rules.schema_label = "PKM-KI"
    return rules


def get_pkm_pi_similarity_rules() -> SimilarityRules:
    """Aturan similaritas PKM-PI — sama dengan PKM-KC (maks 25%)."""
    rules = get_pkm_kc_similarity_rules()
    rules.schema_label = "PKM-PI"
    return rules


def get_pkm_pm_similarity_rules() -> SimilarityRules:
    """Aturan similaritas PKM-PM — sama dengan PKM-KC (maks 25%)."""
    rules = get_pkm_kc_similarity_rules()
    rules.schema_label = "PKM-PM"
    return rules


def get_pkm_ai_similarity_rules() -> SimilarityRules:
    """Aturan similaritas PKM-AI — sama dengan PKM-KC (maks 25%)."""
    rules = get_pkm_kc_similarity_rules()
    rules.schema_label = "PKM-AI"
    return rules


def get_pkm_gft_similarity_rules() -> SimilarityRules:
    """Aturan similaritas PKM-GFT — sama dengan PKM-KC (maks 25%)."""
    rules = get_pkm_kc_similarity_rules()
    rules.schema_label = "PKM-GFT"
    return rules
