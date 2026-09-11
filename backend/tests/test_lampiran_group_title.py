"""
Judul kelompok lampiran tanpa nomor.

Kasus nyata (LapKem PKM-RE Julian): bukti-bukti dikelompokkan di bawah satu
judul tanpa nomor, lalu tiap bukti diberi nomor sendiri:

    LAMPIRAN
    Bukti Pendukung kegiatan
    Lampiran 1. Sosial Media
    Lampiran 2. Bukti Perekaman Sinyal EEG
    ...
    Penggunaan Dana
    Lampiran 9. Rincian Pengeluaran Dana Belmawa

Kata kunci hanya dicari 200 karakter SETELAH "Lampiran N", jadi judul
kelompok yang berada di atas "Lampiran 1" tidak terbaca → "Tidak ditemukan
Lampiran 2 Bukti-Bukti Pendukung Kegiatan" padahal bagiannya ada.

Cara jalankan:
    python3 -m unittest tests.test_lampiran_group_title -v
"""
import unittest
from dataclasses import dataclass
from typing import Optional

from app.services.lampiran_checker import LampiranChecker


@dataclass
class _Para:
    index: int
    text: str
    is_heading: bool = False
    style_name: Optional[str] = None
    is_toc_entry: bool = False


class _StubParser:
    def __init__(self, texts):
        self.paragraphs = [
            _Para(i, t, is_heading=h, style_name=s, is_toc_entry=toc)
            for i, (t, h, s, toc) in enumerate(texts)
        ]


class _StubIndex:
    """Index OCR tiruan: tidak ada gambar → korpus OCR kosong."""

    def rids_in_range(self, *a, **k):
        return []

    def ocr_text_for_rids(self, rids):
        return ""


def H(text):
    return (text, True, "Heading 1", False)


def TOC(text):
    return (text, False, "table of figures", True)


def L(text):
    return (text, False, "Lampiran", False)


def N(text):
    return (text, False, "Normal", False)


_DAFTAR = [
    H("DAFTAR LAMPIRAN"),
    TOC("Lampiran 1. Sosial Media\t11"),
    TOC("Lampiran 2. Bukti Perekaman Sinyal EEG\t11"),
    TOC("Lampiran 3. Bukti Penggunaan Dana\t17"),
    H("BAB 1. PENDAHULUAN"),
    N("isi"),
    H("DAFTAR PUSTAKA"),
]


def _check(texts):
    c = LampiranChecker.for_pkm_laporan(_StubParser(texts), "RE", "PROGRESS_REPORT")
    return c.check(index=_StubIndex())


def _texts(result):
    return [m.text for m in result.messages]


class TestGroupTitle(unittest.TestCase):
    def test_group_title_over_numbered_lampiran_passes(self):
        r = _check(_DAFTAR + [
            H("LAMPIRAN"),
            L("Bukti Pendukung kegiatan"),
            L("Lampiran 1. Sosial Media"),
            L("Lampiran 2. Bukti Perekaman Sinyal EEG"),
            L("Penggunaan Dana"),
            L("Lampiran 3. Bukti Penggunaan Dana"),
        ])
        self.assertEqual(r.status, "pass", _texts(r))

    def test_group_lampiran_missing_from_daftar_is_reported_as_daftar_issue(self):
        # Lampiran di bawah judul kelompok (4, 5) tidak ada di Daftar Lampiran:
        # bagiannya ADA di badan lampiran — yang kurang daftarnya.
        r = _check(_DAFTAR + [
            H("LAMPIRAN"),
            L("Bukti Pendukung kegiatan"),
            L("Lampiran 4. Foto Kegiatan"),
            L("Lampiran 5. Logbook"),
            L("Penggunaan Dana"),
            L("Lampiran 3. Bukti Penggunaan Dana"),
        ])
        texts = _texts(r)
        self.assertEqual(r.status, "fail")
        self.assertTrue(any("Kesalahan kelengkapan Daftar Lampiran" in t for t in texts), texts)
        self.assertFalse(any("Tidak ditemukan Lampiran 2" in t for t in texts), texts)

    def test_keywords_inside_long_sentence_are_not_a_title(self):
        # Kalimat isi yang kebetulan menyebut kata kunci bukan judul kelompok.
        r = _check(_DAFTAR + [
            H("LAMPIRAN"),
            N(
                "Seluruh bukti pendukung pelaksanaan kegiatan telah diserahkan "
                "kepada dosen pendamping pada akhir bulan kedua pelaksanaan."
            ),
            L("Lampiran 1. Bukti Penggunaan Dana"),
        ])
        self.assertIn(
            'Tidak ditemukan Lampiran 2 "Bukti-Bukti Pendukung Kegiatan" pada halaman lampiran',
            _texts(r),
        )

    def test_numbered_title_still_matches_as_before(self):
        r = _check(_DAFTAR[:1] + [
            TOC("Lampiran 1. Penggunaan Dana\t11"),
            TOC("Lampiran 2. Bukti-Bukti Pendukung Kegiatan\t12"),
        ] + _DAFTAR[4:] + [
            H("LAMPIRAN"),
            L("Lampiran 1. Penggunaan Dana"),
            L("Lampiran 2. Bukti-Bukti Pendukung Kegiatan"),
        ])
        self.assertEqual(r.status, "pass", _texts(r))


if __name__ == "__main__":
    unittest.main()
