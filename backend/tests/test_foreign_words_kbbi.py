"""
Test suite: FOREIGN_WORDS tidak boleh memuat lema KBBI.

Latar belakang
--------------
Kata serapan yang sudah jadi lema KBBI BUKAN kata asing, jadi tidak wajib
dicetak miring. Memasukkannya ke FOREIGN_WORDS bikin false positive — kasus
yang memicu perbaikan ini: "sensor" ter-flag di dokumen PKM-KC, padahal KBBI V
punya lema "sensor" homograf ke-2 dengan makna persis teknis:
"elemen yang mengubah sinyal fisik menjadi sinyal elektronik".

Metode verifikasi (2026-09-07)
------------------------------
Seluruh 526 entri FOREIGN_WORDS dicocokkan dengan dataset KBBI V
(186.588 lema, ekstraksi resmi dari laman KBBI). Ketemu 43 entri yang ada
di KBBI, lalu dipilah pakai kolom `kelas` milik KBBI sendiri:

- 25 entri ditandai KBBI kelas "Ungkapan; Latin" (ad hoc, in situ, status quo,
  curriculum vitae, dst.) → TETAP di FOREIGN_WORDS. KBBI mendaftarkannya
  justru sebagai ungkapan asing, jadi tetap wajib italic.
- 18 entri tanpa penanda bahasa asing → serapan penuh, DIHAPUS.

Dataset KBBI tidak ikut di-vendor ke repo (21 MB, dan lisensinya melarang
penggunaan komersial). Hasil verifikasinya dibekukan jadi konstanta di bawah,
supaya daftar ini tidak diam-diam kembali menyusup saat FOREIGN_WORDS ditambah.

Cara jalankan:
    python3 -m unittest tests.test_foreign_words_kbbi -v
"""

import unittest

from app.services.format_checker import FOREIGN_WORDS


# Lema KBBI V yang pernah salah masuk FOREIGN_WORDS — tidak boleh balik lagi.
# Format: kata -> alasan singkat (makna KBBI-nya).
KBBI_LEMMAS_MUST_NOT_BE_FOREIGN = {
    "antigen": "Nomina; Kimia — zat yang merangsang pembentukan antibodi",
    "antiviral": "Adjektiva — bersifat menyembuhkan penyakit akibat virus",
    "biogas": "Nomina — gas dari kotoran ternak",
    "in vitro": "Adverbia; Kedokteran — dalam lingkungan buatan",
    "in vivo": "Adverbia; Kedokteran — di dalam makhluk hidup",
    "input": "Nomina — masukan",
    "metaverse": "Nomina — metamesta",
    "modal": "Nomina — uang pokok untuk berdagang",
    "modus operandi": "modus operasi",
    "monitoring": "Nomina; Cakapan — pemantauan",
    "monomer": "Nomina — kelompok kecil molekul",
    "nanomaterial": "Nomina; Nanoteknologi",
    "pivot": "Nomina/Verba — putaran; poros; inti",
    "pro bono": "Nomina; Hukum — bantuan hukum cuma-cuma",
    "sensor": "Nomina — elemen pengubah sinyal fisik jadi sinyal elektronik",
    "server": "Nomina — peladen",
    "stem": "Nomina; Pendidikan — sains, teknologi, teknik, matematika",
    "versus": "Partikel — (me)lawan",
}

# Ungkapan Latin yang KBBI sendiri tandai kelas "Ungkapan; Latin".
# Ada di KBBI, tapi justru sebagai ungkapan asing → tetap wajib italic.
KBBI_LATIN_STAY_FOREIGN = {
    "a fortiori", "a posteriori", "ad hoc", "ad infinitum", "ad libitum",
    "circa", "curriculum vitae", "de facto", "de jure", "et cetera",
    "ex officio", "ex situ", "exempli gratia", "ibid", "id est",
    "in situ", "in toto", "inter alia", "ipso facto", "mutatis mutandis",
    "per se", "prima facie", "status quo", "sui generis", "vice versa",
}


class TestKbbiLemmasExcluded(unittest.TestCase):
    def test_no_kbbi_lemma_in_foreign_words(self):
        """Tidak satu pun lema KBBI serapan boleh ada di FOREIGN_WORDS."""
        leaked = sorted(
            w for w in KBBI_LEMMAS_MUST_NOT_BE_FOREIGN if w in FOREIGN_WORDS
        )
        self.assertEqual(
            leaked, [],
            "Kata berikut ada di KBBI (bukan kata asing) tapi masih di "
            "FOREIGN_WORDS sehingga akan memicu false positive italic:\n"
            + "\n".join(
                f"  - {w}: {KBBI_LEMMAS_MUST_NOT_BE_FOREIGN[w]}" for w in leaked
            ),
        )

    def test_sensor_specifically_excluded(self):
        """Regresi kasus lapangan: "sensor" di laporan PKM-KC ter-flag asing."""
        self.assertNotIn("sensor", FOREIGN_WORDS)

    def test_homograph_words_excluded(self):
        """Homograf yang makna Indonesianya jauh lebih lazim di dokumen PKM.

        "modal" (modal usaha) dan "pivot" (putaran) akan jauh lebih sering
        muncul dalam makna Indonesia ketimbang makna teknis Inggrisnya.
        """
        for word in ("modal", "pivot", "stem"):
            self.assertNotIn(word, FOREIGN_WORDS)


class TestLatinExpressionsRetained(unittest.TestCase):
    def test_latin_expressions_still_foreign(self):
        """Ungkapan Latin bertanda KBBI tetap wajib italic — jangan ikut terhapus."""
        missing = sorted(w for w in KBBI_LATIN_STAY_FOREIGN if w not in FOREIGN_WORDS)
        self.assertEqual(
            missing, [],
            "Ungkapan Latin berikut hilang dari FOREIGN_WORDS padahal KBBI "
            f"menandainya kelas 'Ungkapan; Latin': {missing}",
        )

    def test_two_groups_do_not_overlap(self):
        self.assertEqual(
            set(KBBI_LEMMAS_MUST_NOT_BE_FOREIGN) & KBBI_LATIN_STAY_FOREIGN, set()
        )


class TestForeignWordsIntegrity(unittest.TestCase):
    def test_common_english_terms_still_detected(self):
        """Kata Inggris yang memang bukan lema KBBI harus tetap terdeteksi."""
        for word in (
            "software", "framework", "dashboard", "startup", "output",
            "browser", "machine learning", "blockchain", "actuator",
        ):
            self.assertIn(word, FOREIGN_WORDS)

    def test_all_entries_lowercase_and_stripped(self):
        """Matching-nya case-insensitive; entri disimpan lowercase & rapi."""
        for word in FOREIGN_WORDS:
            self.assertEqual(word, word.lower().strip(), f"entri tidak rapi: {word!r}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
