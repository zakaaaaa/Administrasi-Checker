"""
Test suite: pengecekan kata asing berbasis kamus `dictionary_english`.

Fokusnya perilaku penyaring nama diri (tiga lapis) dan batas wilayah pindai.
Tidak ada yang menyentuh jaringan: kamus di-inject lewat patch supaya isinya
terkendali dan test tetap jalan tanpa DATABASE_URL.

Cara jalankan:
    python3 -m unittest tests.test_foreign_words_dictionary -v
"""

import unittest
from unittest.mock import MagicMock, patch

from app.services import format_checker as fc
from app.services.docx_parser import ParagraphInfo, RunInfo
from app.services.english_dictionary import (
    EnglishDictionary,
    _normalize_fallback,
    MIN_WORD_LENGTH,
)
from app.services.format_checker import FormatChecker, FOREIGN_WORDS


# Kamus uji: memuat kata Inggris umum yang SENGAJA bukan bagian dari daftar
# kurasi FOREIGN_WORDS, supaya lapis 2 dan lapis 3 bisa diuji terpisah dari
# lapis 1. "smith"/"brown"/"health"/"organization" meniru isi kamus asli yang
# memang memuat nama orang dan kata pembentuk nama institusi.
TEST_WORDS = frozenset(
    {
        "machine", "learning", "framework", "dashboard", "software",
        "smith", "brown", "health", "organization", "world", "ministry",
        "texts", "mesh", "snack", "mix", "band", "json",
    }
)


def R(text, italic=None):
    return RunInfo(text=text, italic=italic)


def P(index, runs, heading=False, toc=False):
    if isinstance(runs, str):
        runs = [R(runs)]
    return ParagraphInfo(
        index=index,
        text="".join(r.text for r in runs),
        runs=runs,
        is_heading=heading,
        is_toc_entry=toc,
    )


def run_check(paragraphs, words=TEST_WORDS, **kwargs):
    """Jalankan sub-check kata asing atas daftar paragraf, kamus ter-patch."""
    parser = MagicMock()
    parser.paragraphs = paragraphs
    dictionary = EnglishDictionary(words=words, source="supabase")
    with patch.object(fc, "StyleResolver") as SR:
        SR.return_value.resolve_run_italic.return_value = None
        checker = FormatChecker(parser)
        with patch.object(
            FormatChecker, "_foreign_word_dictionary", return_value=dictionary
        ):
            return checker._check_foreign_words_italic(**kwargs)


def flagged_words(sec):
    """Himpunan kata yang dilaporkan, diambil dari teks issue."""
    out = set()
    for issue in sec.issues:
        inside = issue.issue.split('"')[1]
        for w in inside.split(", "):
            if not w.startswith("+"):
                out.add(w)
    return out


class TestDeteksiDasar(unittest.TestCase):
    def test_kata_inggris_tidak_miring_terdeteksi(self):
        sec = run_check([P(0, "Sistem ini memakai machine learning dan dashboard.")])
        self.assertEqual(sec.status, "fail")
        self.assertEqual(flagged_words(sec), {"machine", "learning", "dashboard"})

    def test_kata_yang_sudah_miring_lolos(self):
        sec = run_check([
            P(0, [R("Sistem memakai "), R("machine learning", italic=True), R(" untuk klasifikasi.")])
        ])
        self.assertEqual(sec.status, "pass")

    def test_kosakata_indonesia_tidak_terdeteksi(self):
        sec = run_check([
            P(0, "Purwarupa alat pendeteksi kebocoran gas menggunakan mikrokontroler."),
            P(1, "Pengujian dilakukan sebanyak lima kali ulangan pada suhu ruang."),
        ])
        self.assertEqual(sec.status, "pass")

    def test_vonis_per_kata_bukan_per_paragraf(self):
        """Regresi: dulu satu run italic mana pun meloloskan seluruh paragraf.

        Kasus nyata dari A410170082.docx — kata "texts" terpecah dua run,
        "text" miring dan "s" tidak, sehingga penulisannya cacat.
        """
        sec = run_check([
            P(0, [
                R("Use well-organized ", italic=True),
                R("text", italic=True),
                R("s"),
                R(" (Gunakan teks yang terorganisasi)"),
            ])
        ])
        self.assertEqual(sec.status, "fail")
        self.assertIn("texts", flagged_words(sec))


class TestMiringSebagian(unittest.TestCase):
    """Kata yang terpecah run dilaporkan beda dari kata yang belum dimiringkan.

    Di layar kata seperti "texts" terlihat miring — yang tegak cuma huruf
    terakhirnya. Pesan "tidak dicetak miring" bikin penulis mengira checker
    salah, jadi kondisinya dipisah.
    """

    PARA_SEBAGIAN = [R("Memakai "), R("machin", italic=True), R("e"), R(" terbaru.")]

    def test_dilaporkan_sebagai_miring_sebagian(self):
        sec = run_check([P(0, self.PARA_SEBAGIAN)])
        self.assertEqual(len(sec.issues), 1)
        self.assertIn("miring sebagian", sec.issues[0].issue)
        self.assertEqual(sec.issues[0].found, "italic sebagian")
        self.assertEqual(sec.issues[0].expected, "italic penuh")

    def test_kata_polos_tetap_pakai_pesan_lama(self):
        sec = run_check([P(0, "Memakai machine terbaru.")])
        self.assertEqual(len(sec.issues), 1)
        self.assertIn("tidak dicetak miring", sec.issues[0].issue)
        self.assertNotIn("sebagian", sec.issues[0].issue)
        self.assertEqual(sec.issues[0].found, "tidak italic")

    def test_dua_kondisi_dilaporkan_terpisah(self):
        """Satu paragraf bisa memuat keduanya sekaligus."""
        sec = run_check([
            P(0, [R("Memakai "), R("machin", italic=True), R("e"), R(" dan dashboard.")])
        ])
        self.assertEqual(len(sec.issues), 2)
        pesan = sorted(i.issue for i in sec.issues)
        self.assertIn("dashboard", pesan[1])          # "tidak dicetak miring"
        self.assertIn("miring sebagian", pesan[0])
        self.assertEqual(sec.detail["flagged_words_count"], 2)

    def test_kata_miring_penuh_lintas_run_tetap_lolos(self):
        """Terpecah run bukan pelanggaran selama semua potongannya miring."""
        sec = run_check([
            P(0, [R("Memakai "), R("machin", italic=True), R("e", italic=True), R(" terbaru.")])
        ])
        self.assertEqual(sec.status, "pass", flagged_words(sec))


class TestPenyaringNamaDiri(unittest.TestCase):
    """Tiga lapis: daftar kurasi → konsistensi dokumen → aturan kapital."""

    def test_lapis3_nama_orang_dan_institusi_dilewati(self):
        sec = run_check([
            P(0, "Menurut Smith dan Brown, World Health Organization mencatat hal serupa."),
        ])
        self.assertEqual(sec.status, "pass", flagged_words(sec))

    def test_lapis1_daftar_kurasi_menang_atas_aturan_kapital(self):
        """"Machine Learning" berkapital di tengah kalimat tetap divonis."""
        sec = run_check([
            P(0, "Kami menerapkan Machine Learning pada tahap klasifikasi citra."),
        ])
        self.assertEqual(sec.status, "fail")
        self.assertEqual(flagged_words(sec), {"Machine", "Learning"})

    def test_lapis2_pernah_muncul_huruf_kecil_di_dokumen(self):
        """"Framework" berkapital divonis karena "framework" ada di paragraf lain."""
        sec = run_check([
            P(0, "Adapun Framework yang dipakai sudah teruji."),
            P(1, "Pemilihan framework dilakukan pada tahap awal."),
        ])
        self.assertEqual(len(sec.issues), 2)
        self.assertEqual(flagged_words(sec), {"Framework", "framework"})

    def test_lapis2_tidak_aktif_kalau_selalu_berkapital(self):
        """Tanpa kemunculan huruf kecil, kata berkapital tetap dianggap nama diri."""
        sec = run_check([
            P(0, "Adapun Ministry of Health menerbitkan pedoman tersebut."),
            P(1, "Pedoman itu dipakai sebagai acuan kegiatan."),
        ])
        self.assertEqual(sec.status, "pass", flagged_words(sec))

    def test_kata_di_awal_kalimat_tetap_divonis(self):
        """Kapital di awal kalimat bukan petunjuk nama diri."""
        sec = run_check([P(0, "Software tersebut dipasang di komputer mitra.")])
        self.assertEqual(sec.status, "fail")
        self.assertIn("Software", flagged_words(sec))


class TestPengecualian(unittest.TestCase):
    def test_akronim_huruf_besar_dilewati(self):
        """WHO/JSON/API tegak itu benar — termasuk yang ada di daftar kurasi."""
        sec = run_check([P(0, "Data dikirim dalam bentuk JSON melalui API ke WHO.")])
        self.assertEqual(sec.status, "pass", flagged_words(sec))

    def test_sitasi_berkurung_tahun_dilewati(self):
        sec = run_check([P(0, "Hal ini sudah dibuktikan sebelumnya (Smith, 2020).")])
        self.assertEqual(sec.status, "pass", flagged_words(sec))

    def test_sitasi_naratif_and_dilewati(self):
        """Regresi lapangan (Lapkem PKM-RSH): "and" di antara nama penulis
        sitasi naratif dulu divonis kata asing tidak miring."""
        sec = run_check([
            P(0, "Proses kognitif mengacu pada Anderson and Krathwohl (2001), serta "
                 "Hidayati, Notosudjono, and Sunaryo (2023) dan Chin & Todd (1995)."),
        ], words=TEST_WORDS | {"and"})
        self.assertEqual(sec.status, "pass", flagged_words(sec))

    def test_and_di_luar_sitasi_tetap_divonis(self):
        sec = run_check(
            [P(0, "Tahap ini meliputi planning and controlling (2021) di mitra.")],
            words=TEST_WORDS | {"and"},
        )
        self.assertIn("and", flagged_words(sec))

    def test_nama_domain_dilewati(self):
        """Regresi: "Sumber: Dikemas.com" dulu menyumbang kata "com"."""
        sec = run_check([
            P(0, "Gambar 2. Snack Drive. Sumber: Dikemas.com, 2019."),
            P(1, "Diakses dari https://freepik.com/vector dan www.yougov.com."),
        ])
        self.assertNotIn("com", flagged_words(sec))

    def test_angka_romawi_berdiri_sendiri_dilewati(self):
        """Nomor halaman depan "iii" yang diketik sebagai teks body."""
        sec = run_check([P(0, "iii"), P(1, "ii. Tahap pelaksanaan kegiatan.")])
        self.assertEqual(sec.status, "pass", flagged_words(sec))

    def test_kata_mirip_romawi_di_tengah_kalimat_tetap_divonis(self):
        """"mix" cocok pola angka Romawi, tapi di tengah kalimat itu kata Inggris."""
        sec = run_check([P(0, "Bahan tersebut diaduk memakai mix otomatis.")])
        self.assertIn("mix", flagged_words(sec))

    def test_heading_dan_entri_daftar_isi_dilewati(self):
        sec = run_check([
            P(0, "BAB 2. TINJAUAN PUSTAKA machine learning", heading=True),
            P(1, "Machine learning dashboard\t5", toc=True),
        ])
        self.assertEqual(sec.status, "pass", flagged_words(sec))


class TestBatasWilayahPindai(unittest.TestCase):
    def test_berhenti_di_daftar_pustaka(self):
        """Judul artikel & nama jurnal berbahasa Inggris bukan pelanggaran."""
        paras = [
            P(0, "Sistem memakai machine learning."),
            P(1, "DAFTAR PUSTAKA", heading=True),
            P(2, "Smith, J. Deep learning for medical image analysis. Medical Systems."),
        ]
        sec = run_check(paras)
        self.assertEqual(len(sec.issues), 1)
        self.assertEqual(sec.issues[0].location, "Paragraf #0")

    def test_entri_daftar_isi_bukan_batas_daftar_pustaka(self):
        """"DAFTAR PUSTAKA......12" di halaman awal tidak boleh menghentikan pindai."""
        paras = [
            P(0, "DAFTAR PUSTAKA\t12", toc=True),
            P(1, "Sistem memakai machine learning."),
        ]
        sec = run_check(paras)
        self.assertEqual(len(sec.issues), 1)

    def test_berhenti_di_lampiran(self):
        paras = [
            P(0, "Sistem memakai machine learning."),
            P(1, "LAMPIRAN", heading=True),
            P(2, "Biodata: software engineer di dashboard mitra."),
        ]
        sec = run_check(paras, lampiran_idx=1)
        self.assertEqual(len(sec.issues), 1)

    def test_front_matter_dilewati(self):
        paras = [
            P(0, "Halaman sampul memuat software mitra."),
            P(1, "Sistem memakai machine learning."),
        ]
        sec = run_check(paras, start_para_idx=1)
        self.assertEqual(len(sec.issues), 1)
        self.assertEqual(sec.issues[0].location, "Paragraf #1")


class TestPelaporan(unittest.TestCase):
    def test_detail_menyebut_asal_kamus(self):
        sec = run_check([P(0, "Teks biasa saja tanpa kata asing.")])
        self.assertEqual(sec.detail["dictionary_source"], "supabase")
        self.assertEqual(sec.detail["dictionary_size"], len(TEST_WORDS))

    def test_daftar_kata_dipangkas_saat_terlalu_banyak(self):
        teks = "machine learning framework dashboard software mesh band snack"
        sec = run_check([P(0, teks)])
        self.assertIn("lainnya", sec.issues[0].issue)


class TestFallbackKamus(unittest.TestCase):
    """Kalau Supabase tidak bisa dihubungi, pengecekan tetap jalan."""

    def test_frasa_kurasi_dipecah_jadi_kata_tunggal(self):
        words = _normalize_fallback({"machine learning", "real-time", "a/b testing"})
        self.assertIn("machine", words)
        self.assertIn("learning", words)
        self.assertIn("real", words)
        self.assertIn("time", words)
        self.assertIn("testing", words)

    def test_kata_terlalu_pendek_dibuang(self):
        """Kata 1-2 huruf terlalu sering bertabrakan dengan singkatan Indonesia."""
        words = _normalize_fallback({"a/b testing", "id est", "ci/cd"})
        self.assertNotIn("a", words)
        self.assertNotIn("b", words)
        self.assertNotIn("id", words)
        for w in words:
            self.assertGreaterEqual(len(w), MIN_WORD_LENGTH)

    def test_fallback_dari_foreign_words_tidak_kosong(self):
        words = _normalize_fallback(FOREIGN_WORDS)
        self.assertGreater(len(words), 300)
        self.assertIn("software", words)
        self.assertIn("dashboard", words)


class TestKataIndonesiaDiKamus(unittest.TestCase):
    """REGRESI lapangan: "Kelima unsur tersebut" divonis kata asing karena
    "kelima" (ke- + lima, bukan lema KBBI tersendiri) ada di tabel kamus."""

    def test_kata_indonesia_dibuang_saat_muat_dari_db(self):
        import sys
        import types
        from app.services import english_dictionary as ed

        cur = MagicMock()
        cur.fetchall.return_value = [{"word": "Kelima"}, {"word": "framework"}]
        ctx = MagicMock()
        ctx.__enter__.return_value = cur
        fake_db = types.ModuleType("app.db")
        fake_db.get_cursor = lambda: ctx
        with patch.dict(sys.modules, {"app.db": fake_db}):
            words = ed._fetch_from_db()
        self.assertIn("framework", words)
        self.assertNotIn("kelima", words)
        self.assertIn("kelima", ed.NOT_ENGLISH)


if __name__ == "__main__":
    unittest.main(verbosity=2)
