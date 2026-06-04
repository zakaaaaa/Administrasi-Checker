"""
ScheduleChecker — validasi tabel "Jadwal Kegiatan" (BAB 4) PKM-KC/PKM-VGK.

Yang dicek:
1. Rentang bulan — wajib tepat required_months bulan.
2. Tiap baris kegiatan punya Penanggung Jawab terisi.

Nama kolom bebas, tidak divalidasi.

Catatan deteksi:
- Tabel jadwal dilokasi lewat tanda-tangan header ("BULAN"/"KEGIATAN").
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
    get_pkm_re_schedule_rules,
    get_pkm_rsh_schedule_rules,
    get_pkm_k_schedule_rules,
    get_pkm_ki_schedule_rules,
    get_pkm_pi_schedule_rules,
    get_pkm_pm_schedule_rules,
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

    @classmethod
    def for_pkm_re(cls, parser: DocxParser) -> "ScheduleChecker":
        return cls(parser, get_pkm_re_schedule_rules())

    @classmethod
    def for_pkm_rsh(cls, parser: DocxParser) -> "ScheduleChecker":
        return cls(parser, get_pkm_rsh_schedule_rules())

    @classmethod
    def for_pkm_k(cls, parser: DocxParser) -> "ScheduleChecker":
        return cls(parser, get_pkm_k_schedule_rules())

    @classmethod
    def for_pkm_ki(cls, parser: DocxParser) -> "ScheduleChecker":
        return cls(parser, get_pkm_ki_schedule_rules())

    @classmethod
    def for_pkm_pi(cls, parser: DocxParser) -> "ScheduleChecker":
        return cls(parser, get_pkm_pi_schedule_rules())

    @classmethod
    def for_pkm_pm(cls, parser: DocxParser) -> "ScheduleChecker":
        return cls(parser, get_pkm_pm_schedule_rules())

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
                    f"periksa manual."
                ),
            ))
            return result

        grid = self._build_grid(table)

        issues: list[CheckMessage] = []
        issues += self._check_pic_header(table, grid)
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
                    f"Tabel jadwal kegiatan {label} sesuai "
                    f"(tepat {self.rules.required_months} bulan, Penanggung Jawab terisi)."
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
    # 1. Nama kolom Penanggung Jawab
    # -------------------------------------------------------------------------

    def _check_pic_header(self, table: TableInfo, grid: dict) -> list[CheckMessage]:
        """Kolom terakhir wajib bernama 'Penanggung Jawab' (nama kolom lain bebas)."""
        last = table.cols - 1
        header_cells = _dedup_consecutive(self._row_cells(table, grid, 0))
        last_header = _norm(header_cells[-1]) if header_cells else ""
        if last_header == "penanggung jawab":
            return []
        written = header_cells[-1] if header_cells else "(tidak terbaca)"
        return [CheckMessage(
            level="fail",
            text=(
                f"Kesalahan format Tabel Jadwal Kegiatan, Kolom Penanggung Jawab "
                f"tidak boleh ditulis \"{written}\""
            ),
        )]

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
