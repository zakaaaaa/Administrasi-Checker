"""
SuratPernyataanChecker — validasi FORMAT "Surat Pernyataan Ketua Tim Pengusul".

Acuan format diambil dari template panduan resmi tiap skema (folder /panduan).
Format SAMA untuk semua skema (PKM-KC/VGK/RE/RSH/K/KI/PI/PM/GFT/AI), hanya
penyebutan skema di isi surat yang berbeda. Elemen wajib:

    1. Judul   : "SURAT PERNYATAAN KETUA TIM PENGUSUL"
    2. Field   : Nama Ketua Tim, Nomor Induk Mahasiswa, Program Studi,
                 Nama Dosen Pendamping, Perguruan Tinggi, Judul Proposal PKM
    3. Skema   : isi surat menyebut skema yang benar (mis. "PKM-KC")
    4. Materai : keterangan "Materai senilai Rp10.000"

Strategi (mirip BiodataDateChecker):
    1. Cari section LAMPIRAN, potong jadi segment per "Lampiran N ...".
    2. Pilih segment yang heading-nya = Surat Pernyataan Ketua (mengandung
       "pernyataan" + "ketua") — BUKAN "Sumber Tulisan" (khas PKM-AI).
    3. Korpus = teks paragraf segment + OCR gambar segment (surat biasanya
       hasil pindai bertanda tangan). Pakai cache OCR bersama (LampiranOcrIndex).
    4. Cek tiap elemen dengan pencocokan toleran (OCR sering tidak sempurna).

Severity: semua temuan = WARNING (periksa manual). Surat sering berupa scan,
OCR bisa meleset → hindari memvonis "gagal". Output digabung jadi SATU pesan
(konvensi "satu output per checker").
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

from app.services.docx_parser import DocxParser


# =============================================================================
# Elemen format wajib (uniform semua skema)
# =============================================================================

_TITLE_TOKENS = ["surat", "pernyataan", "ketua", "tim", "pengusul"]

# (label_tampil, token_subsequence_utama, token_alternatif_tunggal|None)
_REQUIRED_FIELDS: list[tuple[str, list[str], Optional[str]]] = [
    ("Nama Ketua Tim",          ["nama", "ketua", "tim"],        None),
    ("Nomor Induk Mahasiswa",   ["nomor", "induk", "mahasiswa"], "nim"),
    ("Program Studi",           ["program", "studi"],            None),
    ("Nama Dosen Pendamping",   ["nama", "dosen", "pendamping"], None),
    ("Perguruan Tinggi",        ["perguruan", "tinggi"],         None),
    ("Judul Proposal PKM",      ["judul", "proposal"],           None),
]

_LAMPIRAN_SECTION_RE = re.compile(r"^\s*LAMPIRAN\s*$", re.IGNORECASE)


# =============================================================================
# Data classes
# =============================================================================


@dataclass
class CheckMessage:
    level: str
    text: str


@dataclass
class SuratPernyataanResult:
    status: str
    messages: list[CheckMessage] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "messages": [{"level": m.level, "text": m.text} for m in self.messages],
        }


# =============================================================================
# SuratPernyataanChecker
# =============================================================================


class SuratPernyataanChecker:
    """
    Cara pakai:
        result = SuratPernyataanChecker.for_pkm_kc(parser).check(index=lampiran_index)
    """

    def __init__(self, parser: DocxParser, schema_label: str):
        self.parser = parser
        self.schema_label = schema_label
        # Kode skema untuk dicari di isi surat (mis. "PKM-KC" → "kc").
        self.schema_code = schema_label.split("-", 1)[-1].lower()

    # --- factory per skema (cocok dgn pola getattr(..., f"for_pkm_{s}")) -------

    @classmethod
    def for_pkm_kc(cls, parser: DocxParser) -> "SuratPernyataanChecker":
        return cls(parser, "PKM-KC")

    @classmethod
    def for_pkm_vgk(cls, parser: DocxParser) -> "SuratPernyataanChecker":
        return cls(parser, "PKM-VGK")

    @classmethod
    def for_pkm_re(cls, parser: DocxParser) -> "SuratPernyataanChecker":
        return cls(parser, "PKM-RE")

    @classmethod
    def for_pkm_rsh(cls, parser: DocxParser) -> "SuratPernyataanChecker":
        return cls(parser, "PKM-RSH")

    @classmethod
    def for_pkm_k(cls, parser: DocxParser) -> "SuratPernyataanChecker":
        return cls(parser, "PKM-K")

    @classmethod
    def for_pkm_ki(cls, parser: DocxParser) -> "SuratPernyataanChecker":
        return cls(parser, "PKM-KI")

    @classmethod
    def for_pkm_pi(cls, parser: DocxParser) -> "SuratPernyataanChecker":
        return cls(parser, "PKM-PI")

    @classmethod
    def for_pkm_pm(cls, parser: DocxParser) -> "SuratPernyataanChecker":
        return cls(parser, "PKM-PM")

    @classmethod
    def for_pkm_ai(cls, parser: DocxParser) -> "SuratPernyataanChecker":
        return cls(parser, "PKM-AI")

    @classmethod
    def for_pkm_gft(cls, parser: DocxParser) -> "SuratPernyataanChecker":
        return cls(parser, "PKM-GFT")

    # -------------------------------------------------------------------------
    # Public
    # -------------------------------------------------------------------------

    def check(self, index=None) -> SuratPernyataanResult:
        """`index` = LampiranOcrIndex bersama (opsional). Jika None, dibuat sendiri."""
        result = SuratPernyataanResult(status="pass")

        from app.services.lampiran_index import LampiranOcrIndex

        if index is None:
            index = LampiranOcrIndex(self.parser)

        seg_start = index.find_section_start()
        if seg_start is None:
            seg_start = self._find_lampiran_section_start()

        segs = index.segments(seg_start)
        surat_segs = [s for s in segs if _is_surat_pernyataan_segment(s)]

        if not surat_segs:
            result.status = "warning"
            result.messages.append(CheckMessage(
                level="warning",
                text=(
                    "Surat Pernyataan Ketua Tim Pengusul tidak terdeteksi pada "
                    "halaman lampiran — periksa manual format dan kelengkapannya."
                ),
            ))
            return result

        # Korpus: teks paragraf segment + OCR gambar segment (surat sering pindai).
        text_parts = [s.seg_text for s in surat_segs if (s.seg_text or "").strip()]
        rids: list[str] = []
        for s in surat_segs:
            rids.extend(s.image_rids)
        ocr_text = index.ocr_text_for_rids(rids) if rids else ""

        corpus = " ".join(text_parts) + " " + ocr_text
        nc = _norm(corpus)
        words = nc.split()

        # --- cek tiap elemen ---------------------------------------------------
        title_ok = _subseq(_TITLE_TOKENS, words)

        field_results: list[tuple[str, bool]] = []
        for label, tokens, alt in _REQUIRED_FIELDS:
            ok = _subseq(tokens, words) or (alt is not None and alt in words)
            field_results.append((label, ok))

        skema_ok = _schema_mentioned(nc, self.schema_code)
        materai_ok = "materai" in nc

        # Sinyal "isi surat terbaca": minimal satu elemen ISI (field/skema/materai)
        # terdeteksi. Kalau NOL → kemungkinan scan tak terbaca OCR → jangan
        # enumerasi semua (bising/menyesatkan), cukup minta periksa manual.
        content_detected = skema_ok or materai_ok or any(ok for _, ok in field_results)
        if not content_detected:
            result.status = "warning"
            result.messages.append(CheckMessage(
                level="warning",
                text=(
                    "Isi Surat Pernyataan Ketua tidak dapat dibaca otomatis "
                    "(kemungkinan hasil pindai/foto) — periksa manual: judul "
                    "\"SURAT PERNYATAAN KETUA TIM PENGUSUL\", data ketua, "
                    f"penyebutan {self.schema_label}, dan Materai senilai Rp10.000."
                ),
            ))
            return result

        missing: list[str] = []
        if not title_ok:
            missing.append('Judul "SURAT PERNYATAAN KETUA TIM PENGUSUL"')
        for label, ok in field_results:
            if not ok:
                missing.append(f'Isian "{label}"')
        if not skema_ok:
            missing.append(f'Penyebutan skema "{self.schema_label}" pada isi surat')
        if not materai_ok:
            missing.append('Keterangan "Materai senilai Rp10.000"')

        if missing:
            result.status = "warning"
            lines = "\n".join(f"- {m}" for m in missing)
            result.messages.append(CheckMessage(
                level="warning",
                text=(
                    "Format Surat Pernyataan Ketua tidak lengkap/tidak terbaca. "
                    "Bagian berikut tidak terdeteksi (periksa manual):\n" + lines
                ),
            ))
        else:
            result.messages.append(CheckMessage(
                level="pass",
                text=(
                    f"Format Surat Pernyataan Ketua {self.schema_label} sesuai: "
                    "judul, data ketua, skema, dan materai terdeteksi."
                ),
            ))
        return result

    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------

    def _find_lampiran_section_start(self) -> Optional[int]:
        for p in self.parser.paragraphs:
            if _LAMPIRAN_SECTION_RE.match(p.text.strip()):
                return p.index
        return None


# =============================================================================
# Helpers: deteksi & pencocokan toleran
# =============================================================================


def _is_surat_pernyataan_segment(seg) -> bool:
    """
    True bila segment ini = Surat Pernyataan Ketua. Pakai heading dulu (paling
    andal), fallback ke awal teks segment. Harus mengandung "pernyataan" + "ketua"
    agar lampiran "Surat Pernyataan Sumber Tulisan" (PKM-AI) tidak ikut terpilih.
    """
    h = (getattr(seg, "heading_text", "") or "").lower()
    if not h.strip():
        h = (getattr(seg, "seg_text", "") or "")[:160].lower()
    return "pernyataan" in h and "ketua" in h


def _norm(text: str) -> str:
    """Lowercase, ganti semua non-alfanumerik jadi spasi tunggal (toleran OCR)."""
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def _subseq(tokens: list[str], words: list[str]) -> bool:
    """True bila `tokens` muncul sebagai subsequence (urut, boleh berjarak) di
    `words`. Toleran terhadap kata/noise OCR yang menyelip antar kata label."""
    if not tokens:
        return False
    it = iter(words)
    return all(any(w == tok for w in it) for tok in tokens)


def _schema_mentioned(nc: str, code: str) -> bool:
    """True bila isi surat menyebut "PKM-<code>" (mis. PKM-KC). `nc` = teks
    ter-normalisasi (hyphen sudah jadi spasi). Word-boundary mencegah "pkm k"
    keliru cocok di "pkm kc"/"pkm ki"."""
    if not code:
        return False
    return re.search(rf"\bpkm\s*{re.escape(code)}\b", nc) is not None
