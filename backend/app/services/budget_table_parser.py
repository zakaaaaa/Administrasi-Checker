"""
BudgetTableParser — helper untuk parse tabel anggaran (RAB Bab 4 & Justifikasi Lampiran 2).

Tugas:
1. Identifikasi tabel RAB Bab 4 (struktur sederhana: No, Jenis, Biaya)
2. Identifikasi tabel Justifikasi Lampiran 2 (struktur dengan sub-kategori + items)
3. Ekstrak total per kategori dari kedua tabel
4. Parse format angka Indonesia (titik ribuan, koma desimal): "4.400.000,00" → 4400000

Modul ini stateless — hanya fungsi-fungsi pure yang menerima TableInfo dari
DocxParser.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

from app.services.docx_parser import TableInfo


# ============================================================================
# Helper: parse angka format Indonesia
# ============================================================================


_NUMBER_RE = re.compile(r"[\d.,]+")


def parse_indonesian_number(text: str) -> Optional[int]:
    """
    Parse format angka Indonesia ke int.
    "4.400.000,00" → 4400000
    "Rp 4.400.000" → 4400000
    "4,400,000.00" (US format) → 4400000 (auto-detect)
    "11.320.000,00" → 11320000

    Strategi:
    - Buang prefix "Rp" dan whitespace
    - Match cluster digits + . + ,
    - Indonesian: titik = ribuan separator, koma = desimal
    - US (fallback): koma = ribuan, titik = desimal

    Return None kalau tidak bisa parse.
    """
    if not text:
        return None

    # Bersihkan: buang Rp, whitespace, kurung, dan karakter di luar [0-9.,]
    cleaned = text.strip()
    cleaned = re.sub(r"[Rr][Pp]\.?", "", cleaned)
    cleaned = cleaned.strip()

    m = _NUMBER_RE.search(cleaned)
    if not m:
        return None
    num = m.group(0)

    has_comma = "," in num
    has_dot = "." in num

    if has_comma and has_dot:
        # Cek pola: kalau koma muncul SETELAH titik terakhir → koma = desimal
        # (format Indonesia)
        last_dot = num.rfind(".")
        last_comma = num.rfind(",")
        if last_comma > last_dot:
            # Indonesian: hapus titik (ribuan), ganti koma dengan titik (desimal)
            int_part = num[:last_comma].replace(".", "")
            return _safe_int(int_part)
        else:
            # US format: hapus koma (ribuan), titik = desimal
            int_part = num[:last_dot].replace(",", "")
            return _safe_int(int_part)
    elif has_comma:
        # Hanya koma — bisa ribuan (1,200) atau desimal (1,5)
        # Indonesian: koma desimal kalau hanya 1-2 digit setelah koma terakhir
        comma_parts = num.split(",")
        if len(comma_parts) == 2 and len(comma_parts[1]) <= 2:
            # Decimal — ambil int part saja
            return _safe_int(comma_parts[0])
        else:
            # Ribuan separator
            return _safe_int(num.replace(",", ""))
    elif has_dot:
        # Hanya titik — Indonesian: ribuan; US: desimal
        # Heuristik: kalau pattern X.YYY.ZZZ → ribuan
        dot_parts = num.split(".")
        # Indonesian thousands: setiap segment selain pertama harus 3 digit
        if len(dot_parts) >= 2 and all(len(p) == 3 for p in dot_parts[1:]):
            return _safe_int(num.replace(".", ""))
        # Single dot dengan 1-2 digit: probably US decimal
        if len(dot_parts) == 2 and len(dot_parts[1]) <= 2:
            return _safe_int(dot_parts[0])
        # Default: hapus titik
        return _safe_int(num.replace(".", ""))
    else:
        return _safe_int(num)


def _safe_int(s: str) -> Optional[int]:
    try:
        return int(s)
    except (ValueError, TypeError):
        return None


# ============================================================================
# Hasil parsing tabel
# ============================================================================


@dataclass
class BudgetItem:
    """Satu item transaksi di tabel anggaran."""
    description: str        # nama item, mis. "Hard Disk External"
    category: Optional[str] = None  # kategori parent (kalau di Lampiran 2)
    volume: Optional[str] = None
    unit_price: Optional[int] = None
    total_rp: Optional[int] = None
    row_index: int = -1


@dataclass
class BudgetCategoryTotal:
    """Total per kategori dari tabel."""
    category_name: str          # apa yang tertulis di tabel
    total_rp: Optional[int] = None
    matched_canonical: Optional[str] = None  # nama canonical setelah alias matching


@dataclass
class Bab4ParseResult:
    """Hasil parsing tabel RAB Bab 4."""
    found: bool = False
    table_index: int = -1
    categories: list[BudgetCategoryTotal] = field(default_factory=list)
    grand_total_rp: Optional[int] = None
    raw_header: list[str] = field(default_factory=list)


@dataclass
class Lampiran2ParseResult:
    """Hasil parsing tabel Justifikasi Anggaran Lampiran 2."""
    found: bool = False
    table_index: int = -1
    categories: list[BudgetCategoryTotal] = field(default_factory=list)
    items: list[BudgetItem] = field(default_factory=list)
    grand_total_rp: Optional[int] = None


# ============================================================================
# Identifikasi tabel
# ============================================================================


def is_bab4_rab_table(table: TableInfo) -> bool:
    """
    Heuristik: tabel RAB Bab 4 punya:
    - 3 kolom (No, Jenis Pengeluaran, Biaya/Total)
    - Header berisi kata "Jenis Pengeluaran" atau "Pengeluaran" + "Biaya" atau "Total"
    - 4-6 baris (4 kategori + optional jumlah)
    """
    if table.cols < 3 or table.cols > 4:
        return False
    header_blob = " ".join(h.upper() for h in table.header_texts)
    has_jenis = "JENIS" in header_blob or "URAIAN" in header_blob or "PENGELUARAN" in header_blob
    has_biaya = "BIAYA" in header_blob or "TOTAL" in header_blob or "JUMLAH" in header_blob
    # Reject yang terlalu besar (kemungkinan tabel jadwal atau Justifikasi)
    if table.rows > 10:
        return False
    return has_jenis and has_biaya


def is_lampiran2_table(table: TableInfo) -> bool:
    """
    Heuristik: tabel Lampiran 2 (Justifikasi Anggaran) punya:
    - 4 kolom (Item, Volume, Harga Satuan, Nilai)
    - Header punya "Volume" + ("Harga Satuan" atau "Nilai" atau "Satuan")
    - Banyak baris (>= 10)
    """
    if table.cols < 4 or table.cols > 5:
        return False
    header_blob = " ".join(h.upper() for h in table.header_texts)
    has_volume = "VOLUME" in header_blob
    has_harga = "HARGA" in header_blob or "SATUAN" in header_blob or "NILAI" in header_blob
    if table.rows < 8:
        return False
    return has_volume and has_harga


# ============================================================================
# Parser tabel RAB Bab 4
# ============================================================================


_SUBTOTAL_KEYWORDS = ("SUB TOTAL", "SUBTOTAL", "JUMLAH", "TOTAL")


def parse_bab4_table(table: TableInfo) -> Bab4ParseResult:
    """
    Parse tabel RAB Bab 4 → kategori + total per kategori.
    Asumsi struktur:
        R0: Header (No | Jenis Pengeluaran | Biaya)
        R1..N-1: Kategori dengan total
        Rlast (optional): "Jumlah" atau "Total" dengan grand total
    """
    result = Bab4ParseResult(
        found=True,
        table_index=table.index,
        raw_header=list(table.header_texts),
    )

    # Asumsi: kolom kedua = nama kategori, kolom terakhir = nilai
    name_col = 1
    value_col = table.cols - 1

    for r_idx in range(1, table.rows):
        row_cells = sorted(
            (c for c in table.cells if c.row == r_idx),
            key=lambda c: c.col,
        )
        if len(row_cells) < table.cols:
            continue
        name_text = row_cells[name_col].text.strip()
        value_text = row_cells[value_col].text.strip()
        if not name_text:
            continue

        value_int = parse_indonesian_number(value_text)
        is_grand_total = any(kw in name_text.upper() for kw in _SUBTOTAL_KEYWORDS)

        if is_grand_total:
            if value_int is not None:
                result.grand_total_rp = value_int
        else:
            result.categories.append(
                BudgetCategoryTotal(
                    category_name=name_text,
                    total_rp=value_int,
                )
            )

    return result


# ============================================================================
# Parser tabel Lampiran 2
# ============================================================================


# Pattern untuk header kategori di Lampiran 2: "1. Jenis Perlengkapan", "2. Bahan Habis"
_CATEGORY_HEADER_RE = re.compile(r"^\s*(\d+)\.\s*(.+)$")


def parse_lampiran2_table(table: TableInfo) -> Lampiran2ParseResult:
    """
    Parse tabel Justifikasi Anggaran (Lampiran 2).

    Struktur tipikal:
        R0: Header utama (atau header kategori 1)
        R1-Rk: items kategori 1
        Rk+1: SUB TOTAL kategori 1
        Rk+2: Header kategori 2
        ...
        Rlast: TOTAL grand total
    """
    result = Lampiran2ParseResult(
        found=True,
        table_index=table.index,
    )
    if table.cols < 4:
        return result

    name_col = 0
    volume_col = 1 if table.cols >= 3 else None
    price_col = 2 if table.cols >= 4 else None
    value_col = table.cols - 1  # kolom terakhir = total

    current_category: Optional[str] = None
    pending_items: list[BudgetItem] = []

    for r_idx in range(table.rows):
        row_cells = sorted(
            (c for c in table.cells if c.row == r_idx),
            key=lambda c: c.col,
        )
        if len(row_cells) < table.cols:
            continue

        first_cell_text = row_cells[name_col].text.strip()
        last_cell_text = row_cells[value_col].text.strip()

        # 1. Cek header kategori (mis. "1. Jenis Perlengkapan")
        cat_match = _CATEGORY_HEADER_RE.match(first_cell_text)
        if cat_match:
            # Sebelum mulai kategori baru, asumsikan header
            # Cek juga apakah ini benar header (bukan item dengan numbering)
            # Heuristik: kalau 4 cell pertama mostly "Volume / Harga Satuan / Nilai" → header
            row_blob = " ".join(c.text.strip().upper() for c in row_cells[1:])
            if "VOLUME" in row_blob and ("HARGA" in row_blob or "NILAI" in row_blob):
                current_category = cat_match.group(2).strip()
                continue

        # 2. Cek SUB TOTAL atau TOTAL
        first_upper = first_cell_text.upper()
        if any(kw in first_upper for kw in _SUBTOTAL_KEYWORDS):
            value_int = parse_indonesian_number(last_cell_text)
            # Kalau "TOTAL" di akhir tabel = grand total
            if "TOTAL 1+2+3+4" in first_upper or first_upper.startswith("TOTAL"):
                if value_int is not None:
                    result.grand_total_rp = value_int
            else:
                # SUB TOTAL kategori — tambah ke result.categories
                if current_category is not None and value_int is not None:
                    result.categories.append(
                        BudgetCategoryTotal(
                            category_name=current_category,
                            total_rp=value_int,
                        )
                    )
                # Reset items pending tapi tetap simpan
                result.items.extend(pending_items)
                pending_items = []
            continue

        # 3. Skip baris kosong dan baris terbilang
        if not first_cell_text or "Terbilang" in first_cell_text:
            continue

        # 4. Cek baris header tabel umum (Volume + Harga ...)
        first_upper = first_cell_text.upper()
        if first_upper in ("JENIS PERLENGKAPAN", "BAHAN HABIS",
                           "PERJALANAN", "LAIN-LAIN"):
            current_category = first_cell_text
            continue

        # 5. Item baris — extract value, volume, harga, deskripsi
        # Bersihkan prefix "- " kalau ada (style dokumen real)
        desc = first_cell_text.lstrip("-").strip()
        volume = row_cells[volume_col].text.strip() if volume_col else None
        unit_price = (
            parse_indonesian_number(row_cells[price_col].text)
            if price_col else None
        )
        total = parse_indonesian_number(last_cell_text)

        # Skip kalau total kosong (mungkin baris filler)
        if total is None and unit_price is None:
            continue

        pending_items.append(
            BudgetItem(
                description=desc,
                category=current_category,
                volume=volume,
                unit_price=unit_price,
                total_rp=total,
                row_index=r_idx,
            )
        )

    # Flush pending items kalau tabel tidak punya SUB TOTAL terakhir
    if pending_items:
        result.items.extend(pending_items)

    return result


# ============================================================================
# Match alias kategori
# ============================================================================


def match_category_to_canonical(
    category_name: str, categories: list  # list[BudgetCategory]
) -> Optional[str]:
    """
    Match nama kategori dari tabel ke canonical name di BudgetRules.categories.
    Pencocokan: case-insensitive, normalisasi whitespace, cek name + aliases.

    Return canonical name kalau ketemu, None kalau tidak.
    """
    norm = _normalize_category_text(category_name)
    for cat in categories:
        candidates = [cat.name] + list(cat.aliases)
        for cand in candidates:
            if _normalize_category_text(cand) == norm:
                return cat.name
            # Partial match — kalau target startswith canonical
            if norm.startswith(_normalize_category_text(cand)):
                return cat.name
    return None


def _normalize_category_text(text: str) -> str:
    """Normalisasi: lowercase, collapse whitespace, normalize dashes."""
    t = text.lower().strip()
    # Normalize en-dash, em-dash → simple dash
    t = t.replace("\u2013", "-").replace("\u2014", "-")
    # Collapse whitespace
    t = re.sub(r"\s+", " ", t)
    # Strip surrounding dashes
    t = t.strip("- ")
    return t