"""
ScheduleChecker — validasi tabel "Jadwal Kegiatan" (BAB 4) PKM-KC/PKM-VGK.

Yang dicek (acuan: format tabel.docx):
1. Struktur & penulisan header kolom — wajib persis: No, Jadwal Kegiatan,
   Bulan, Penanggung Jawab. Tidak boleh sinonim (mis. "PIC" untuk Penanggung
   Jawab, "Jenis Kegiatan" untuk Jadwal Kegiatan).
2. Rentang bulan ≤ max_months (default 4).
3. Tiap baris kegiatan punya Penanggung Jawab terisi.

Catatan deteksi:
- Tabel jadwal dilokasi lewat tanda-tangan header ("BULAN"/"KEGIATAN"),
  bukan urutan dokumen — meniru is_bab4_rab_table di budget_table_parser.
  Anchor sengaja TIDAK memakai "Penanggung Jawab" supaya tabel tetap ketemu
  meski label kolomnya yang justru salah tulis (itu yang sedang dicek).
- Merged cell membuat python-docx menduplikasi teks sel ke beberapa kolom
  grid; header dinormalkan dengan dedup nilai berurutan yang sama.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

from app.services.docx_parser import DocxParser, TableInfo
from app.services.schedule_rules import (
    ScheduleTableRules,
    get_pkm_kc_schedule_rules,
    get_pkm_vgk_schedule_rules,
)


@dataclass
class CheckMessage:
    level: str
    text: str


@dataclass
class ScheduleCheckResult:
    status: str
    messages: list[CheckMessage] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "messages": [{"level": m.level, "text": m.text} for m in self.messages],
        }


def _norm(s: str) -> str:
    """Normalkan teks header: trim, rapatkan spasi, lowercase."""
    return re.sub(r"\s+", " ", (s or "").strip()).lower()


def _dedup_consecutive(cells: list[str]) -> list[str]:
    """Buang sel kosong & gabungkan nilai berurutan yang sama (artefak merged cell)."""
    out: list[str] = []
    for c in cells:
        t = (c or "").strip()
        if not t:
            continue
        if out and _norm(out[-1]) == _norm(t):
            continue
        out.append(t)
    return out


class ScheduleChecker:
    """
    Validasi tabel jadwal kegiatan.

    Cara pakai:
        checker = ScheduleChecker.for_pkm_kc(parser)
        result  = checker.check()
    """

    def __init__(self, parser: DocxParser, rules: ScheduleTableRules):
        self.parser = parser
        self.rules = rules

    # --- factory ---

    @classmethod
    def for_pkm_kc(cls, parser: DocxParser) -> "ScheduleChecker":
        return cls(parser, get_pkm_kc_schedule_rules())

    @classmethod
    def for_pkm_vgk(cls, parser: DocxParser) -> "ScheduleChecker":
        return cls(parser, get_pkm_vgk_schedule_rules())

    # --- public ---

    def check(self) -> ScheduleCheckResult:
        result = ScheduleCheckResult(status="pass")
        label = self.rules.schema_label

        table = self._find_schedule_table()
        if table is None:
            result.status = "warning"
            result.messages.append(CheckMessage(
                level="warning",
                text=(
                    f"Tabel jadwal kegiatan {label} tidak terdeteksi otomatis — "
                    f"periksa manual. Format wajib: "
                    f"{', '.join(self.rules.expected_headers)}."
                ),
            ))
            return result

        grid = self._build_grid(table)

        issues: list[CheckMessage] = []
        issues += self._check_headers(table, grid)
        issues += self._check_months(table, grid)
        if self.rules.require_pic_filled:
            issues += self._check_pic_filled(table, grid)

        if issues:
            result.messages.extend(issues)
            result.status = "fail" if any(i.level == "fail" for i in issues) else "warning"
        else:
            result.messages.append(CheckMessage(
                level="pass",
                text=(
                    f"Tabel jadwal kegiatan {label} sesuai format "
                    f"({', '.join(self.rules.expected_headers)}, tepat {self.rules.required_months} bulan)."
                ),
            ))
        return result

    # -------------------------------------------------------------------------
    # Lokasi tabel
    # -------------------------------------------------------------------------

    # Header yang mengindikasikan tabel RAB/biodata (bukan jadwal) → dikecualikan.
    _NON_SCHEDULE_HINTS = ("sumber dana", "volume", "harga", "pengeluaran", "nim", "nama /")

    def _find_schedule_table(self) -> Optional[TableInfo]:
        for tbl in self.parser.tables:
            blob = _norm(" ".join(tbl.header_texts or []))
            if not blob:
                continue
            if any(h in blob for h in self._NON_SCHEDULE_HINTS):
                continue
            if "bulan" in blob or "kegiatan" in blob:
                return tbl
        return None

    @staticmethod
    def _build_grid(table: TableInfo) -> dict[tuple[int, int], str]:
        grid: dict[tuple[int, int], str] = {}
        for c in table.cells:
            grid[(c.row, c.col)] = (c.text or "").replace("\n", " ").strip()
        return grid

    def _row_cells(self, table: TableInfo, grid: dict, r: int) -> list[str]:
        return [grid.get((r, c), "") for c in range(table.cols)]

    # -------------------------------------------------------------------------
    # 1. Header kolom (strict)
    # -------------------------------------------------------------------------

    def _check_headers(self, table: TableInfo, grid: dict) -> list[CheckMessage]:
        out: list[CheckMessage] = []
        logical = _dedup_consecutive(self._row_cells(table, grid, 0))
        expected = self.rules.expected_headers
        expected_norm = {_norm(e) for e in expected}
        logical_norm = {_norm(g) for g in logical}
        expected_join = ", ".join(expected)

        # Header yang ditulis tapi tidak termasuk header resmi (mis. "PIC")
        for got in logical:
            if _norm(got) not in expected_norm:
                out.append(CheckMessage(
                    level="fail",
                    text=(
                        f"Penulisan header kolom \"{got}\" pada tabel jadwal tidak sesuai. "
                        f"Header wajib ditulis persis: {expected_join}."
                    ),
                ))
        # Header resmi yang hilang (mis. "Penanggung Jawab" karena ditulis "PIC")
        for exp in expected:
            if _norm(exp) not in logical_norm:
                out.append(CheckMessage(
                    level="fail",
                    text=(
                        f"Kolom \"{exp}\" tidak ditemukan di tabel jadwal kegiatan. "
                        f"Header wajib: {expected_join}."
                    ),
                ))
        return out

    # -------------------------------------------------------------------------
    # 2. Rentang bulan
    # -------------------------------------------------------------------------

    _INT_RE = re.compile(r"^\d{1,2}$")

    def _check_months(self, table: TableInfo, grid: dict) -> list[CheckMessage]:
        months = self._collect_month_numbers(table, grid)
        if not months:
            # Angka bulan tidak terbaca — jangan false-positive, biar header check yg bicara.
            return []
        count = len(months)
        req = self.rules.required_months
        if count != req:
            month_list = ", ".join(str(m) for m in months)
            return [CheckMessage(
                level="fail",
                text=(
                    f"Jumlah bulan pada tabel jadwal {count} (bulan {month_list}) — "
                    f"wajib tepat {req} bulan."
                ),
            )]
        return []

    def _collect_month_numbers(self, table: TableInfo, grid: dict) -> list[int]:
        """
        Kumpulkan angka bulan distinct dari band header (2 baris pertama), di kolom
        antara "Jadwal Kegiatan" (kolom 1) dan kolom Penanggung Jawab (kolom terakhir).

        Hanya baris header yang di-scan, jadi nomor urut di kolom "No" (kolom 0) dan
        angka di baris data tidak ikut terhitung. Tahan terhadap jumlah bulan berapa
        pun (2, 3, 4, 5, ...).
        """
        last = table.cols - 1  # kolom Penanggung Jawab (dikecualikan)
        nums: set[int] = set()
        for r in range(min(2, table.rows)):
            for c in range(2, last):
                v = grid.get((r, c), "").strip()
                if self._INT_RE.match(v):
                    nums.add(int(v))
        return sorted(nums)

    # -------------------------------------------------------------------------
    # 3. Penanggung jawab terisi
    # -------------------------------------------------------------------------

    def _check_pic_filled(self, table: TableInfo, grid: dict) -> list[CheckMessage]:
        out: list[CheckMessage] = []
        last = table.cols - 1
        for r in range(table.rows):
            no = grid.get((r, 0), "").strip()
            if not no.isdigit():          # hanya baris kegiatan (kolom No berisi angka)
                continue
            pic = grid.get((r, last), "").strip() or grid.get((r, last - 1), "").strip()
            if not pic:
                kegiatan = grid.get((r, 1), "").strip()
                snippet = f" (\"{kegiatan[:40]}\")" if kegiatan else ""
                out.append(CheckMessage(
                    level=self.rules.pic_severity,
                    text=f"Penanggung Jawab kosong pada kegiatan nomor {no}{snippet}.",
                ))
        return out
