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
    row_index: int = -1       # indeks baris dalam tabel (0-based), untuk estimasi halaman
    table_index: int = -1     # indeks tabel di DocxParser.tables (0-based)


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
    # Rekap Sumber Dana (blok di bagian bawah tabel Bab 4)
    rekap_belmawa_rp: Optional[int] = None
    rekap_university_rp: Optional[int] = None
    rekap_external_rp: Optional[int] = None
    rekap_total_rp: Optional[int] = None
    rekap_rows: dict = field(default_factory=dict)  # source_key -> row_index (estimasi halaman)


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
    if table.cols < 3 or table.cols > 7:
        return False
    header_blob = " ".join(h.upper() for h in table.header_texts)
    has_jenis = "JENIS" in header_blob or "URAIAN" in header_blob or "PENGELUARAN" in header_blob
    has_biaya = (
        "BIAYA" in header_blob
        or "TOTAL" in header_blob
        or "JUMLAH" in header_blob
        or "DANA" in header_blob
    )
    has_volume = "VOLUME" in header_blob
    # Tabel Bab 4 biasanya memuat kolom sumber dana (sebagian template),
    # atau minimal tidak memakai kolom volume seperti Lampiran 2.
    has_sumber_dana = "SUMBER DANA" in header_blob
    # Tabel Bab 4 bisa memanjang karena rekap sumber dana.
    if table.rows > 30:
        return False
    return has_jenis and has_biaya and (has_sumber_dana or not has_volume)


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

# Pola sumber dana di blok "Rekap Sumber Dana" tabel Bab 4.
_REKAP_SOURCE_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("belmawa",    re.compile(r"belmawa", re.IGNORECASE)),
    ("university", re.compile(r"perguruan\s+tinggi", re.IGNORECASE)),
    ("external",   re.compile(r"instansi\s+lain|institusi\s+lain", re.IGNORECASE)),
    ("total",      re.compile(r"^\s*(?:jumlah|total)\s*$", re.IGNORECASE)),
]


def _match_rekap_source(row_cells) -> Optional[str]:
    """Tentukan baris rekap ini untuk sumber dana yang mana (belmawa/university/external/total)."""
    for c in row_cells:
        text = c.text.strip()
        if not text:
            continue
        for key, pat in _REKAP_SOURCE_PATTERNS:
            if pat.search(text):
                return key
    return None


def _is_total_label(text: str) -> bool:
    """
    Deteksi label total/subtotal secara presisi.
    Hindari false-positive pada kalimat biasa yang kebetulan mengandung kata "jumlah".
    """
    t = re.sub(r"\s+", " ", text.strip().upper())
    if not t:
        return False
    if t == "JUMLAH":
        return True
    if t.startswith("SUB TOTAL") or t.startswith("SUBTOTAL"):
        return True
    if t.startswith("TOTAL") or t.startswith("GRAND TOTAL"):
        return True
    return False


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

    # Asumsi umum: kolom kedua = nama kategori, kolom terakhir = nilai.
    # Namun tabel dengan merged cell bisa punya jumlah cell efektif < table.cols.
    name_col = 1
    cat_totals: dict[str, int] = {}

    for r_idx in range(1, table.rows):
        row_cells = sorted(
            (c for c in table.cells if c.row == r_idx),
            key=lambda c: c.col,
        )
        if len(row_cells) < 2:
            continue
        safe_name_col = name_col if len(row_cells) > name_col else 0
        value_cell = row_cells[-1]
        name_text = row_cells[safe_name_col].text.strip()
        value_text = value_cell.text.strip()
        if not name_text:
            continue

        value_int = parse_indonesian_number(value_text)
        upper_name = name_text.upper()
        is_grand_total = _is_total_label(upper_name)
        if "REKAP SUMBER DANA" in upper_name:
            # Blok rekap di bawah tabel: simpan nominal per sumber dana.
            source_key = _match_rekap_source(row_cells)
            if source_key is not None and value_int is not None:
                if source_key == "belmawa":
                    result.rekap_belmawa_rp = value_int
                elif source_key == "university":
                    result.rekap_university_rp = value_int
                elif source_key == "external":
                    result.rekap_external_rp = value_int
                elif source_key == "total":
                    result.rekap_total_rp = value_int
                result.rekap_rows[source_key] = r_idx
            continue

        if is_grand_total:
            if value_int is not None:
                result.grand_total_rp = value_int
        else:
            if value_int is None:
                continue
            cat_totals[name_text] = cat_totals.get(name_text, 0) + value_int

    result.categories = [
        BudgetCategoryTotal(category_name=name, total_rp=total)
        for name, total in cat_totals.items()
    ]

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

    # Banyak dokumen memakai kolom pertama "No", jadi deskripsi ada di kolom kedua.
    first_header = (table.header_texts[0].strip().upper() if table.header_texts else "")
    has_number_col = first_header in ("NO", "NOMOR")
    desc_col = 1 if has_number_col and table.cols >= 2 else 0
    volume_col = desc_col + 1 if table.cols > desc_col + 1 else None
    price_col = desc_col + 2 if table.cols > desc_col + 2 else None
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

        number_cell_text = row_cells[0].text.strip() if row_cells else ""
        first_cell_text = row_cells[desc_col].text.strip() if len(row_cells) > desc_col else ""
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

        # Pola umum dokumen real:
        # "1 | Belanja Bahan (maks. 60%) | ... | 5.160.000"
        # treat sebagai header kategori (bukan item).
        if (
            has_number_col
            and re.match(r"^\d+$", number_cell_text)
            and first_cell_text
        ):
            vol_text = row_cells[volume_col].text.strip() if volume_col is not None else ""
            price_text = row_cells[price_col].text.strip() if price_col is not None else ""
            value_int = parse_indonesian_number(last_cell_text)
            if value_int is not None and not vol_text and not price_text:
                current_category = first_cell_text
                continue

        # 2. Cek SUB TOTAL atau TOTAL
        first_upper = first_cell_text.upper()
        if _is_total_label(first_upper):
            value_int = parse_indonesian_number(last_cell_text)
            # Kalau "TOTAL" di akhir tabel = grand total
            if (
                "TOTAL 1+2+3+4" in first_upper
                or first_upper.startswith("TOTAL")
                or "GRAND TOTAL" in first_upper
            ):
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
                table_index=table.index,
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