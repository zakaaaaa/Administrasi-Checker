# Backend Fix Documentation (May 2026)

Dokumentasi ini merangkum perbaikan engine checker backend untuk kasus output yang terlihat "halu" pada dokumen `.docx` real-world.

## Ringkasan Masalah

Pada beberapa dokumen nyata:

- section penting (mis. `DAFTAR PUSTAKA`, `BAB 4`, `LAMPIRAN`) ada di dokumen,
  tetapi engine melaporkan tidak ada.
- parsing RAB tidak stabil karena variasi bentuk tabel antar dokumen.
- balance check referensi memunculkan duplikasi temuan yang sama.

Penyebab utamanya adalah asumsi parser terlalu ketat pada style heading dan format tabel "ideal".

## Root Cause (Teknis)

1. **Ketergantungan pada style Heading**
   - Banyak dokumen menggunakan style `Normal` untuk judul section.
   - Deteksi section dengan `headings_only=True` gagal menemukan batas section nyata.

2. **False positive baris ToC (Daftar Isi)**
   - Baris seperti `BAB 1 .... 5` terbaca sebagai section asli jika tidak difilter.

3. **Parser RAB terlalu spesifik**
   - Variasi tabel Bab 4/Lampiran 2 (merged cell, kolom tambahan, label kategori berbeda)
     membuat parser salah identifikasi atau salah ekstraksi item.

4. **Duplikasi finding di validator referensi**
   - Sitasi yang sama muncul berulang memunculkan pesan fail ganda.

5. **Lokasi error sulit ditelusuri**
   - Output lama hanya menampilkan paragraf global.
   - Reviewer kesulitan mencari posisi error di dokumen hasil render.

6. **False positive pada format alignment**
   - Paragraf dengan alignment `inherit` (None) dianggap pelanggaran.
   - Ini bisa memicu warning/fail yang tidak merefleksikan kondisi nyata.

## Perbaikan yang Diterapkan

### 1) `app/services/docx_parser.py`

- `find_section_boundaries()` ditingkatkan dengan 2-pass strategy:
  - **Pass 1**: perilaku lama (sesuai parameter).
  - **Pass 2 fallback** (khusus `headings_only=True`):
    - cari kandidat section non-heading jika section belum ketemu.
    - skip baris ToC dengan heuristik:
      - tab + nomor halaman di akhir
      - dot leader + nomor halaman di akhir
- Tambahan helper:
  - `_looks_like_toc_entry()`
  - `_looks_like_heading_fallback()`

Dampak: batas section nyata tetap ketemu walau style judul bukan Heading.

### 2) `app/services/structure_checker.py`

- Tidak lagi memproses hanya `para.is_heading`.
- Menambahkan filter ToC dan kandidat heading fallback.
- Tetap menjaga akurasi dengan skip baris yang jelas bukan judul section.

Dampak: missing section palsu berkurang signifikan (termasuk `DAFTAR PUSTAKA`).

### 3) `app/services/budget_table_parser.py`

- Heuristik `is_bab4_rab_table()` diperluas:
  - support variasi kolom dan header nyata.
  - tetap membedakan dari Lampiran 2.
- `parse_bab4_table()`:
  - lebih toleran terhadap merged cells.
  - akumulasi nilai per kategori.
  - skip baris rekap sumber dana yang bukan kategori inti.
- `parse_lampiran2_table()`:
  - mendeteksi adanya kolom `No`.
  - deskripsi item dibaca dari kolom yang tepat (bukan angka urut).
  - dukung pola kategori seperti `1 | Belanja Bahan (maks. 60%)`.
  - deteksi `GRAND TOTAL`.
- Perbaikan deteksi subtotal/total agar tidak false-positive pada teks biasa yang mengandung kata "jumlah".

Dampak: parsing RAB jauh lebih stabil pada template dokumen real.

### 4) `app/services/budget_rules.py`

- Menambahkan alias kategori yang muncul di dokumen nyata:
  - `Belanja Bahan`, `Belanja Bahan (maks. 60%)`
  - `Belanja Sewa`, `Belanja Sewa (maks. 15%)`
  - `Perjalanan (maks. 30%)`
  - `Lain-lain (maks. 15%)`

Dampak: mapping kategori ke canonical lebih akurat.

### 5) `app/services/reference_validator.py`

- Menambahkan dedup untuk finding balance check:
  - dedup `in_text_not_in_references`
  - dedup `in_references_not_in_text`

Dampak: output referensi lebih bersih, tidak mengulang temuan yang sama.

### 6) `app/services/format_checker.py`

- Semua issue berbasis paragraf sekarang menyertakan lokasi:
  - `halaman fisik ~X, paragraf ke-N (global #Y)`
- Perbaikan anti-halu:
  - alignment `inherit` (`None`) tidak langsung dianggap pelanggaran.
  - hanya alignment explicit non-justify yang diflag.

Dampak: output format lebih akurat dan mudah ditelusuri reviewer.

### 7) Lokasi Debug Konsisten (`docx_parser.py`, `structure_checker.py`, `reference_validator.py`, `format_checker.py`)

- `DocxParser` ditambah API:
  - `estimate_physical_page(paragraph_index)`
  - `estimate_paragraph_index_in_page(paragraph_index)`
- Struktur, referensi, dan format menggunakan format lokasi seragam:
  - `halaman fisik ~X, paragraf ke-N (global #Y)`

Catatan:
- Nomor halaman adalah estimasi berbasis marker OOXML (`page break`/`section break`),
  bukan hasil layout engine visual 100% pixel-perfect.

## Status Verifikasi

Pengujian setelah perbaikan:

- `python -m pytest tests/test_budget_auditor.py -q` → **33 passed**
- `python -m pytest tests/test_budget_auditor.py tests/test_structure_checker.py tests/test_docx_parser.py -q` → **79 passed**
- `python -m pytest tests/test_format_checker.py tests/test_docx_parser.py -q` → **39 passed**
- `python -m pytest tests/test_format_checker.py tests/test_structure_checker.py tests/test_docx_parser.py tests/test_budget_auditor.py -q` → **95 passed**

## Catatan Penting

- Setelah parser dibetulkan, jika hasil masih `fail`, itu umumnya karena **isi dokumen memang tidak memenuhi aturan**, bukan karena section/tabel tidak terbaca.
- Contoh temuan valid yang tetap bisa fail:
  - mismatch sitasi vs daftar pustaka (author/year)
  - item RAB terlarang (`Konsumsi`, dll)
  - mismatch nilai antar Bab 4 dan Lampiran 2

## Rekomendasi Lanjutan

1. Tambah mode **strict / tolerant** untuk fase drafting:
   - sebagian fail non-kritis bisa diturunkan jadi warning.
2. Tambah endpoint debug internal untuk menampilkan:
   - section boundaries terdeteksi
   - tabel yang dipilih parser (Bab 4/Lampiran 2)
3. Tambah test fixture lebih banyak dari dokumen real agar regresi lebih cepat terdeteksi.
