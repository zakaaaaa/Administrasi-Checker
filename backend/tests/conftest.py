"""Konfigurasi pytest untuk seluruh test backend.

Satu-satunya tugasnya: memastikan test tidak menghubungi Supabase.

Pengecekan kata asing memuat tabel `dictionary_english` (361 ribu kata) saat
sub-check pertama kali jalan. Tanpa penguncian ini, test seperti
test_format_checker yang memanggil FormatChecker.check() ikut menembak
jaringan — hasilnya jadi bergantung pada koneksi dan isi tabel yang bisa
berubah sewaktu-waktu.

Dengan ENGLISH_DICTIONARY_SOURCE=fallback, yang dipakai adalah daftar kurasi
FOREIGN_WORDS di dalam kode. Test yang perlu kamus tertentu meng-inject
sendiri lewat patch (lihat tests/test_foreign_words_dictionary.py).
"""

import os

os.environ.setdefault("ENGLISH_DICTIONARY_SOURCE", "fallback")
