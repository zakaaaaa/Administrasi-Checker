# Blueprint: Optimasi Durasi Pengecekan Proposal (OCR Bottleneck)

> Dokumen ini lengkap dan mandiri. Tujuannya supaya bisa dieksekusi di **session baru tanpa konteks sebelumnya**. Mulai dari membaca bagian "TL;DR" lalu "Rencana Implementasi".

Dibuat: 2026-05-26 (Fase 0 selesai). Skema yang dioptimasi: **PKM-KC Proposal** (satu-satunya skema yang pakai OCR).

---

## TL;DR

Pengecekan PKM-KC lambat karena **OCR (easyocr CPU) memakan 80–98% waktu**. Dua pemborosan utama, terbukti dengan pengukuran:

1. **Duplikasi penuh**: `lampiran_checker` dan `biodata_date_checker` meng-OCR **gambar yang persis sama dua kali**, tanpa cache.
2. **Over-scan**: `lampiran_checker` meng-OCR SEMUA gambar lampiran walau dokumennya benar; `biodata_date_checker` meng-OCR semua gambar (termasuk justifikasi, susunan tim, screenshot Turnitin) padahal tanggal hanya ada di halaman biodata.
3. **Rotasi 4×**: tiap gambar dicoba orientasi 0/90/180/270° → ~10s/gambar, padahal gambar tegak cukup ~2.7s.

Solusi: **OCR tiap gambar maksimal 1× + cache dipakai bersama**, scoping gambar yang perlu di-OCR, tuning rotasi, downscale. Target: **867s → ~60–90s** (doc 40 gambar), **92s → ~15–20s** (doc 4 gambar). **Tanpa mengubah hasil pengecekan.**

⚠️ **Koreksi penting**: menjalankan easyocr di banyak thread paralel TIDAK memberi speedup linear (CPU-bound, torch sudah multi-thread internal, singleton reader belum tentu thread-safe). "Paralelisme" yang benar = **kurangi pekerjaan** (dedup + scoping), bukan OCR konkuren.

---

## Hasil Ukur Fase 0 (sudah dikerjakan)

Instrumentasi timing sudah ditambahkan di `orchestrator.py` (lihat bagian "Yang Sudah Ada di Kode").

**Dokumen A — "PKM KC NUKI OTISTA...docx"** (577KB, 4 gambar lampiran):

| Checker | Durasi |
|---|---:|
| biodata_date | 28.2s |
| lampiran | 27.3s |
| similarity | 18.2s |
| physical_sheet | 16.8s (docx→PDF LibreOffice, BUKAN OCR) |
| format / structure / lainnya | <1s |
| **TOTAL** | **92.0s** |

**Dokumen B — "pkm kc benar.docx"** (11MB, 40 gambar lampiran):

| Checker | Durasi |
|---|---:|
| lampiran | 429.5s (OCR 40 gambar) |
| biodata_date | 404.4s (OCR 40 gambar yang SAMA) |
| similarity | 16.1s |
| physical_sheet | 16.1s |
| lainnya | <1s |
| **TOTAL** | **867.2s (14.5 menit!)** |

OCR = 98% waktu. lampiran+biodata = 834s untuk OCR 40 gambar yang sama 2×. Per gambar ~10.7s (akibat 4 rotasi).

Catatan penting: Dokumen B "benar" (heading lampiran diketik rapi), tapi `lampiran` tetap OCR SEMUA 40 gambar → artinya ≥1 lampiran wajib gagal terdeteksi via teks lalu memicu OCR seluruh gambar. **Fase 1 harus buat lampiran hanya OCR gambar di sub-lampiran yang headingnya belum ketemu, bukan semua.**

---

## Konteks Lingkungan (penting, jangan ubah asumsi)

- Backend FastAPI di `backend/app/`, dijalankan dari `backend/` dengan `.venv` aktif, uvicorn port 8000.
- **OCR engine**: pytesseract DICOBA dulu tapi **tesseract binary tidak terinstall** di macOS 13 (Tier 3 brew) → SELALU fallback ke **easyocr** (CPU, tanpa GPU). Model ~500MB.
- easyocr reader = singleton `_easyocr_reader` di `biodata_date_checker.py`, di-**preload saat startup** via `lifespan` di `main.py` (~5–8s). Jadi saat request, model sudah warm.
- `run_all_checks` dipanggil **sinkron** di endpoint `/api/check` dan `/api/reviewer/check` (`main.py`), memblok response sampai selesai.

---

## Arsitektur OCR Saat Ini (peta kode)

### `backend/app/services/biodata_date_checker.py`
- **Mesin OCR bersama** (diimpor checker lain):
  - `_run_ocr(images: list) -> list[str]`: coba pytesseract → fallback easyocr. Per gambar panggil `_best_rotation_text`, lalu `_fix_ocr_months`.
  - `_best_rotation_text(img, reader)`: coba rotasi `[0, 90, 180, 270]`, pilih skor tertinggi (jumlah kata alfabet >3 huruf), **early-stop jika skor ≥ 15** (`_ROTATION_SCORE_THRESHOLD`). ← sumber lambat untuk gambar "tipis".
  - `_load_image_rels(zf)`, `_collect_image_rids_after(body, start_idx, paragraphs)`: helper OOXML.
- **Logika checker**:
  - `_find_lampiran_section_start()`: cari paragraf yang teksnya == "LAMPIRAN" (regex `_LAMPIRAN_SECTION_RE`). NB: TIDAK pakai filter `is_heading` (beda dgn lampiran_checker) → bisa ketipu baris Daftar Isi.
  - `_collect_lampiran_text(start_idx)`: teks paragraf mulai start_idx.
  - `_ocr_lampiran_images(start_idx)`: OCR **semua** gambar di section lampiran.
  - `check()`: gabung teks+OCR → `_extract_dates` (regex "Kota, DD Bulan YYYY", `_strip_birthdate_lines` buang tanggal lahir) → validasi rentang **9 Mar 2026 – 9 Apr 2026**.

### `backend/app/services/lampiran_checker.py`
- 6 lampiran wajib di `_REQUIRED_LAMPIRAN` (nomor, keywords, label):
  1. jadwal kegiatan, 2. biodata ketua+anggota, 3. biodata dosen pendamping, 4. justifikasi anggaran, 5. susunan tim pengusul+pembagian, 6. surat pernyataan ketua.
- `_find_lampiran_section_start()`: heading "LAMPIRAN" **dengan** filter `is_heading`.
- `_collect_text_from_lampiran(start_idx)` + `_lampiran_found_in_text(num, keywords, corpus)`: cocokkan "Lampiran N" diikuti SEMUA keyword dalam window 200 char (nomor diabaikan, dokumen lapangan sering beda penomoran).
- `check()`: cek via teks dulu → yang `missing_via_text` baru picu `_ocr_lampiran_images()` yang **OCR SEMUA gambar** lampiran (bukan hanya yang relevan).
- Punya salinan helper `_load_image_rels`, `_collect_image_rids_after` sendiri (duplikat dgn biodata_date).

### `backend/app/services/similarity_checker.py`
- Sudah relatif efisien: `_find_similarity_range()` → (start,end) heading lampiran similaritas (kemunculan TERAKHIR di body). `_collect_image_rids_in_range`. `_ocr_extract`: OCR hanya `max_images_to_scan=3` gambar pertama, **di-crop bagian atas** (`crop_top_ratio=0.35`), berhenti begitu persen ketemu. Regex di-anchor ke "Overall Similarity". Aturan di `similarity_rules.py`.
- Impor `_load_image_rels, _run_ocr` dari biodata_date.

### `backend/app/services/orchestrator.py`
- `_run_pkm_kc(parser)`: jalankan 11 checker **berurutan**. Urutan OCR: (8) lampiran → (9) biodata_date → (11) similarity. Sudah ada instrumentasi `_log_timing`.

---

## Keputusan yang Sudah Diambil (jangan ubah tanpa konfirmasi user)

1. **Scope biodata_date** setelah dibatasi = **biodata + surat pernyataan** (BUKAN biodata saja). Tetap validasi tanggal di Surat Pernyataan Ketua seperti sekarang. Jadi yang TIDAK perlu di-OCR untuk tanggal: justifikasi anggaran, susunan tim, jadwal, screenshot similaritas.
2. Optimasi **tidak boleh mengubah hasil pengecekan** (status & messages tiap checker harus identik untuk dokumen contoh).

---

## Rencana Implementasi

### FASE 1 — Hilangkan duplikasi & batasi scope (gain terbesar, risiko rendah)

**Inti: buat satu sumber kebenaran untuk section lampiran + cache OCR per gambar.**

Buat modul baru `backend/app/services/lampiran_index.py` berisi class `LampiranOcrIndex`:

Tanggung jawab:
1. `find_section_start()` — cari heading "LAMPIRAN" di **body** (pakai `is_heading`, ambil kemunculan setelah Daftar Isi). Jika tak ketemu → mode aman (lihat fallback).
2. **Segmentasi** section lampiran jadi daftar `LampiranSegment` berdasarkan heading "Lampiran N ...":
   - tiap segment: `heading_text`, `start_para_idx`, `end_para_idx`, `image_rids: list[str]`.
3. **Cache OCR**: `ocr_text_for_rids(rids: list[str]) -> str` yang meng-OCR tiap rId **maksimal sekali**, simpan di `dict[str, str]` (key = rId), gabung hasil. Reuse antar pemanggilan/antar checker.
4. Loader gambar: `_image_by_rid(rid) -> PIL.Image` (buka zip sekali, simpan `rel_map`).
5. Util: `identify_segment(keywords) -> segment | None` (cocokkan heading via teks; jika heading kosong/gambar, opsional OCR heading-nya saja).

Lalu sambungkan ke checker (semua memakai instance index yang SAMA, dibuat sekali di orchestrator dan diteruskan):

- **LampiranChecker**:
  - Cek via teks seperti sekarang (cepat).
  - Untuk lampiran yang `missing_via_text`: OCR **hanya gambar di segment yang headingnya belum teridentifikasi**, dan **berhenti sebelum segment similaritas** (saran user #2). Pakai `index.ocr_text_for_rids`.
  - Hapus fallback "OCR seluruh dokumen" saat heading LAMPIRAN tak ketemu → ganti: kalau section tak ketemu, jangan OCR (atau batasi 40% akhir dokumen), supaya tidak meledak.
- **BiodataDateChecker**:
  - Ambil teks dari segment **biodata + surat pernyataan** saja.
  - OCR **hanya gambar di segment biodata + surat pernyataan** via `index.ocr_text_for_rids` (reuse cache milik lampiran → kemungkinan 0 OCR tambahan).
  - Sisanya identik: `_strip_birthdate_lines` → `_extract_dates` → validasi rentang.
- **SimilarityChecker**:
  - Pakai segment similaritas dari index untuk dapat range. OCR cropped tetap (1–3 gambar). NB: hasil crop BEDA dari OCR full-image, jadi **jangan reuse cache full-image untuk crop** (atau key cache = `(rid, crop_ratio)`).

**Verifikasi Fase 1**: jalankan `_bench_timing.py` di doc A & B, pastikan `results["lampiran"]`, `results["biodata_date"]`, `results["similarity"]` (status + messages + jumlah tanggal/persen) IDENTIK dengan baseline. Bandingkan waktu.

Estimasi: dedup saja doc B 867s→~460s; + scoping lampiran (hanya OCR segment yang perlu) bisa jauh lebih rendah.

### FASE 2 — Buat tiap OCR lebih murah

Edit `_run_ocr` / `_best_rotation_text` di `biodata_date_checker.py`:

1. **Rotasi 0° dulu (short-circuit)**: hitung skor 0°. Jika skor ≥ ambang rendah (mis. 3) ATAU teks 0° sudah mengandung pola tanggal (`_DATE_RE`) / persen (untuk similarity), langsung return. Hanya jika 0° nyaris kosong (skor < 3) baru coba 90/180/270°. Pertahankan early-stop skor≥15 yang lama.
   - Risiko: scan miring asli. Mitigasi: rotasi tetap dijalankan saat 0° kosong.
2. **Downscale sebelum OCR**: jika `max(w,h) > MAX_DIM` (mulai konservatif: 2000px), resize jaga rasio. Waktu easyocr ∝ jumlah piksel.
   - Risiko: teks kecil jadi tak terbaca. Mitigasi: MAX_DIM konservatif, verifikasi semua tanggal/persen masih terdeteksi di doc contoh.

Estimasi: ~3–4× per gambar (10.7s → ~2.7s).

### FASE 3 — Overlap (gain kecil, opsional)

Di `orchestrator._run_pkm_kc`: jalankan grup OCR (lampiran/biodata/similarity berbasis index) di **satu** thread, sementara checker non-OCR + `physical_sheet` (docx→PDF, subprocess) jalan di main thread; lalu join. Wall-clock ≈ max(OCR, sisanya). Karena OCR dominan, hemat ≈ waktu physical_sheet (~16s) "gratis".
- Catatan: cukup SATU thread OCR (hormati singleton reader). Jangan banyak thread OCR.
- Dependensi: `format` butuh `structure_result` + pdf_texts dari `physical_sheet` → urutkan di jalur non-OCR.

---

## Korektnes & Cara Verifikasi (WAJIB tiap fase)

1. Simpan baseline output dulu (status + messages) untuk doc A & B dari kondisi sekarang.
2. Setelah tiap fase, jalankan ulang dan **diff** output ketiga checker OCR. Harus identik:
   - lampiran: status + daftar lampiran yang missing.
   - biodata_date: status + jumlah tanggal terdeteksi + tanggal invalid. (Baseline NUKI: 7 kemunculan, semua valid → pass.)
   - similarity: persen terdeteksi + status.
3. Bandingkan waktu via `results["_timings"]`.

---

## Yang Sudah Ada di Kode (jangan ulang)

- `orchestrator.py`:
  - `_log_timing(key, t0, sink)` + flag `_TIMING_ENABLED` (env `CHECK_TIMING`, default ON; set `CHECK_TIMING=0` untuk matikan).
  - `_run_pkm_kc` sudah di-instrument tiap step; hasil di `results["_timings"]` (dict per checker + "total"). main.py TIDAK meneruskan `_timings` ke frontend (aman).
- `backend/_bench_timing.py` — skrip benchmark **SEMENTARA**. Preload OCR lalu `run_all_checks`, print ringkasan terurut.
  - Pakai: `PYTHONPATH=backend backend/.venv/bin/python backend/_bench_timing.py "<path.docx>" [runs]`
  - **HAPUS** setelah optimasi selesai. Instrumentasi `_log_timing` boleh tetap (gated env).

## Dokumen Contoh untuk Uji

Di root repo:
- `PKM KC  NUKI OTISTA_evp_KP_030426.docx` (577KB, 4 gambar) — cepat, untuk iterasi.
- `pkm kc benar.docx` (11MB, 40 gambar) — stress test, lambat (~14 menit baseline). Pakai sesekali / di background.

## File yang Akan Disentuh

- BARU: `backend/app/services/lampiran_index.py`
- EDIT: `lampiran_checker.py`, `biodata_date_checker.py`, `similarity_checker.py`, `orchestrator.py`
- HAPUS nanti: `backend/_bench_timing.py`

## Definition of Done

- [ ] Fase 1: tidak ada gambar di-OCR >1×; lampiran hanya OCR segment yang perlu; biodata hanya biodata+surat pernyataan; hasil pengecekan identik baseline.
- [ ] Fase 2: rotasi 0°-dulu + downscale; hasil identik; per-gambar turun ~3–4×.
- [ ] Fase 3 (opsional): overlap physical_sheet dgn OCR.
- [ ] Doc B turun dari 867s ke target ~60–90s; Doc A dari 92s ke ~15–20s.
- [ ] `_bench_timing.py` dihapus; memory `ocr-optimization` di-update.
