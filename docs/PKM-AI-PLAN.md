# Rencana Pengembangan PKM-AI — Handoff Document

> Dokumen ini dibuat untuk melanjutkan pengembangan setelah ganti akun/sesi Claude.
> Baca ini dulu sebelum mulai. Bahasa pengguna: Indonesia.

## 1. Konteks Project

**AdministrasiChecker** = sistem pengecekan administrasi/penulisan PKM.
Backend FastAPI (`backend/`), Frontend Next.js (`frontend/`).
Saat ini hanya skema **PKM-KC Proposal** yang aktif. Target: tambah dukungan **PKM-AI** (Artikel Ilmiah).

### Alur Backend
- `backend/app/main.py` — endpoint FastAPI. Catalog statis `COMPETITIONS`, `REPORT_TYPES`, `SCHEMAS`. Endpoint `POST /api/check` simpan file, verifikasi token, panggil `run_all_checks()`, simpan ke tabel `results`, balikan JSON ke frontend.
- `backend/app/services/orchestrator.py` — `run_all_checks(CheckRequest)`. **Hardcoded hanya menerima `("PKM","PROPOSAL","PKM-KC")`**. Menjalankan 6 checker berurutan: structure, physical_sheet, format, page_numbering, budget, reference. Tiap modul → `to_dict()`, lalu `overall_status` diagregasi.
- `backend/app/services/schema_rules.py` — `SchemaRules` + `SectionRule` (generic). Factory hardcoded `get_pkm_kc_proposal_rules()`.
- `backend/app/services/budget_rules.py` — `BudgetRules`, factory `get_pkm_kc_budget_rules()`.
- 6 checker: `structure_checker.py`, `physical_sheet_counter.py`, `format_checker.py`, `page_numbering_checker.py`, `budget_auditor.py`, `reference_validator.py`. Semua punya `.check()` → object dengan `.to_dict()`.
- Helper parser: `docx_parser.py` (ada `find_section_boundaries`, `estimate_physical_page`, `sections`, `paragraphs`, dll). **Catatan: file ini `M` (modified) di git SEBELUM sesi ini — itu pekerjaan user, jangan di-revert.**

### Alur Frontend
- `frontend/src/features/check/form/checkFormConstants.ts` — `SKEMA_LAPORAN_MAP` SUDAH memetakan `'PKM-AI': ['SCIENTIFIC_ARTICLE']`. `SKEMA_OPTIONS` sudah punya PKM-AI.
- `frontend/src/features/check/CheckFormView.tsx` — kirim `competition='PKM'`, `report_type=reportCode`, `schema_code=skema` ke `/api/check`.
- `frontend/src/features/check/CheckResultsView.tsx` — render hasil. **`modules` array di-hardcode** 6 modul (termasuk `budget`, `reference`). Kalau key tidak ada → status 'unknown', "Tidak ada catatan" (tidak crash tapi jelek).
- `frontend/src/features/check/exportCheckResultPdf.ts` — `MODULES` array juga hardcoded 6 modul. Sama, perlu dibuat dinamis.

## 2. Keputusan yang Sudah Disepakati User

1. **Arsitektur: Refactor ke registry/dispatch.** Buat registry skema; orchestrator pilih rules + checker-set per `(competition, report_type, schema_code)`. Jaga PKM-KC tidak regresi (ada test di `backend/tests/`).
2. **Cakupan iterasi pertama: core dulu** = `structure` + `physical_sheet` + `format` + `page_numbering`. **Skip `budget`**, **tunda `reference`** untuk PKM-AI (menyusul iterasi berikutnya).
3. **Tunda validator khas AI** (judul ≤20 kata, abstrak/abstract ≤250 kata, abstract EN italic, cek Lampiran similaritas) — iterasi berikutnya.
4. **Budget dihilangkan dari hasil PKM-AI.** Orchestrator balikan set modul dinamis (tanpa key `budget`/`reference`). Frontend `CheckResultsView.tsx` & `exportCheckResultPdf.ts` harus iterasi modul yang ADA di response, bukan list hardcoded.

## 3. Perbedaan PKM-AI vs PKM-KC (dari `PKM-AI-2026_fix.pdf`)

| Aspek | PKM-KC | PKM-AI |
|---|---|---|
| Jenis dokumen | Proposal | Artikel Ilmiah (`SCIENTIFIC_ARTICLE`) |
| Pembiayaan | Ada (Belmawa/PT/eksternal) | **Tidak ada** (insentif Rp1.5jt, bukan RAB) |
| DAFTAR ISI | Wajib | **DILARANG** |
| Abstrak/Ringkasan | Dilarang | **WAJIB** (ID + EN) |
| Halaman sampul & pengesahan | Dilarang | Dilarang (sama) |
| Struktur inti | BAB 1–4 + Daftar Pustaka | Judul → Penulis/Institusi → Abstrak (ID) → Abstract (EN) → Kata kunci → Pendahuluan → Metode → Hasil dan Pembahasan → Kesimpulan → Ucapan Terima Kasih → Kontribusi Penulis → Daftar Pustaka |
| Lampiran | Lampiran 1.. | Lampiran 1 Biodata; 2 Kontribusi; 3 Surat Pernyataan Ketua; 4 Surat Pernyataan Sumber Tulisan; 5 Hasil Uji Similaritas (indeks 25%) |
| Penomoran halaman | Zona awal romawi-bawah + zona inti arab-atas | **Semua angka arab, kanan ATAS, mulai halaman judul** (TIDAK ada zona romawi) |
| Lembar fisik (inti) | maks 10 (anchor "BAB 1"..akhir) | **8–15 halaman**, inti = Judul s/d Daftar Pustaka (anchor BUKAN "BAB 1") |
| Font body | TNR 12 / 1,15 spasi | TNR 12 / 1,15 spasi (sama). Tambahan: halaman judul 1,0 spasi; Abstrak/Abstract TNR **11**; nama penulis TNR **10**; caption gambar/tabel TNR 11; Abstract EN **italic** |
| Margin | kiri 4cm, kanan/atas/bawah 3cm | sama |
| Kertas | A4 satu kolom | sama |
| Daftar Pustaka | Harvard strict, min ~8 mutakhir <10thn | Harvard, **min 10 rujukan**, mutakhir **maks 5 tahun** |
| Judul | — | ≤20 kata, huruf kapital, tanpa singkatan |

Sumber teks panduan lengkap sudah diekstrak (28 halaman PDF). Poin kunci:
- Hal 5–6: "Tidak ada halaman sampul dan halaman pengesahan, serta daftar isi". Penomoran arab dari halaman judul, sudut kanan atas.
- Hal 6: Format penulisan (TNR 12, 1,15 spasi, A4, margin kiri 4 / lainnya 3, inti 8–15 hal).
- Hal 6–10: Sistematika isi (Judul, Penulis, Abstrak/Abstract, Pendahuluan, Metode, Hasil dan Pembahasan, Kesimpulan, Ucapan Terima Kasih, Kontribusi Penulis, Daftar Pustaka).
- Hal 11: Daftar Pustaka Harvard, min 10 rujukan, maks 5 tahun ke belakang. Lampiran 1–5.
- Hal 18–28: Format rujukan Harvard detail + contoh.

## 4. Rencana Implementasi Konkret

### Backend

**A. `schema_rules.py`**
- Tambah field opsional ke `SchemaRules` untuk mendukung skema non-BAB, mis.:
  - `section_titles_titlecase: bool = False` — jika True, StructureChecker boleh menganggap paragraf pendek yang match nama section sebagai heading walau bukan ALL-CAPS (PKM-AI: "Pendahuluan", "Metode", dll Title Case/bold, bukan "BAB 1").
- Tambah `get_pkm_ai_article_rules()`:
  - `competition_code="PKM"`, `schema_code="AI"`, `report_type_code="SCIENTIFIC_ARTICLE"`, `schema_name="Artikel Ilmiah"`.
  - Required + order: Pendahuluan, Metode, Hasil dan Pembahasan, Kesimpulan, Daftar Pustaka, Lampiran. (Abstrak/Abstract/Kata kunci/Judul/Penulis — penanganan teks bebas, ditunda jadi validator khas AI; untuk iterasi 1 boleh dimasukkan sebagai required section sederhana ATAU optional. Putuskan: minimal required = Pendahuluan, Metode, Hasil dan Pembahasan, Kesimpulan, Daftar Pustaka.)
  - Optional: Ucapan Terima Kasih, Kontribusi Penulis, Abstrak, Abstract.
  - Forbidden: DAFTAR ISI, HALAMAN SAMPUL, HALAMAN PENGESAHAN. (Catatan: di PKM-KC "RINGKASAN/ABSTRAK" forbidden — di PKM-AI JANGAN forbidden abstrak.)
  - `section_titles_titlecase=True`.
  - Aliases untuk variasi: "BAB I PENDAHULUAN" vs "PENDAHULUAN", "HASIL DAN PEMBAHASAN" vs "HASIL & PEMBAHASAN", dll.

**B. `structure_checker.py`**
- Di `_identify_sections`, gate saat ini: `if not para.is_heading and not _looks_like_heading_candidate(text): continue`.
- Tambah cabang: jika `self.rules` punya `section_titles_titlecase=True`, izinkan juga paragraf pendek (mis. `len(text) <= 80`) yang `_heading_matches_rule` cocok, walau bukan all-caps. JANGAN ubah perilaku default (PKM-KC tetap pakai logika lama → no regresi).

**C. `physical_sheet_counter.py`**
- `SHEET_COUNT_RULES` sudah punya `("PKM","AI"): (8,15)` ✔.
- Masalah: `_locate_core_range` pakai `CORE_START_PATTERNS` = regex "BAB 1". PKM-AI tidak ada "BAB 1"; inti mulai dari halaman judul (hal fisik 1).
- Solusi: buat anchor inti schema-driven. Tambah konsep di `SchemaRules` (mis. `core_start_mode: 'bab1' | 'first_page'`). PKM-AI: `core_first = 1` (halaman judul), `core_last = ` halaman sebelum heading "LAMPIRAN" (atau halaman terakhir bila lampiran tak terdeteksi). Hati-hati: jangan regresi KC.

**D. `page_numbering_checker.py`**
- PKM-KC: 2 zona (front_matter romawi-bawah, core_matter arab-atas). PKM-AI: 1 zona (semua arab, atas, kanan), tanpa DAFTAR ISI/BAB.
- `_identify_section_zones` pakai boundary "DAFTAR ISI" & "BAB 1" — PKM-AI tidak punya keduanya.
- Solusi: buat `PageNumberingRules` schema-driven. Tambah factory `get_pkm_ai_page_numbering_rules()` mode single-zone: semua section dianggap `core_matter` (arab/top/right TNR12). Sesuaikan `_identify_section_zones` agar bila skema single-zone → semua section = core_matter. Putuskan via flag pada SchemaRules atau dispatch di registry.

**E. `format_checker.py`**
- Default `FormatRules()` sudah cocok untuk PKM-AI body (TNR12, margin sama, 1.15, justify). Perbedaan abstrak-11/penulis-10/judul-1.0 = validator khas AI → DITUNDA. Iterasi 1: pakai FormatChecker apa adanya. (Konsekuensi: halaman judul 1,0 spasi mungkin muncul sebagai *warning* line_spacing — dapat diterima sementara, atau relaksasi ringan kalau perlu.)

**F. `orchestrator.py` — REFACTOR REGISTRY (inti pekerjaan)**
- Bangun registry, mis.:
  ```python
  SCHEMA_REGISTRY: dict[tuple[str,str,str], SchemaConfig]
  ```
  key `(competition, report_type, schema_code)`, value berisi: factory `schema_rules`, optional `budget_rules`, dan daftar modul yang dijalankan.
- PKM-KC: jalankan 6 modul (seperti sekarang). PKM-AI: jalankan `structure, physical_sheet, format, page_numbering` saja (tanpa budget & reference).
- `run_all_checks` jadi generic: loop modul terdaftar, bungkus tiap modul dgn try/except `_module_error_payload` (pertahankan pola lama), `results[<key>]`, agregasi `overall_status` hanya dari modul yang dijalankan.
- Buang validasi hardcoded `!= ("PKM","PROPOSAL","PKM-KC")`; ganti: kalau key tak ada di registry → `UnsupportedSchemaError`.
- `schema_code` dari frontend = `"PKM-KC"`/`"PKM-AI"` (lihat `CheckFormView`), sedangkan `SchemaRules.schema_code`="KC"/"AI". Registry pakai kunci sesuai yang dikirim frontend (`"PKM-AI"`).

**G. `main.py`**
- `REPORT_TYPES["PKM"]`: set `SCIENTIFIC_ARTICLE` → `active: True`.
- `SCHEMAS[("PKM","PROPOSAL")]` tidak punya PKM-AI. Tambah entri katalog untuk `("PKM","SCIENTIFIC_ARTICLE")` = `[{"code":"PKM-AI","name":"Artikel Ilmiah","active":True}]`. (Cek apakah frontend benar2 fetch `/api/schemas` atau pakai konstanta lokal — `checkFormConstants.ts` pakai konstanta lokal, tapi tetap rapikan katalog backend agar konsisten.)
- **`POST /api/check` penyimpanan hasil**: saat ini INSERT ke tabel `results` 6 kolom (`structure_result`...`reference_result`) + `overall_status`, dan response `results` susun manual 6 key. Harus dibuat dinamis:
  - Untuk modul yang tidak dijalankan (PKM-AI: budget, reference) → simpan `NULL` di kolomnya (atau payload `{"status":"skipped"}` — putuskan; NULL lebih bersih).
  - Response JSON `results` hanya berisi key modul yang dijalankan.
  - **VERIFIKASI dulu skema tabel `results`** (apakah kolom NOT NULL?). Belum sempat dicek — file SQL/migration belum ditemukan; `db.py` belum sempat dibaca (tool call di-interrupt). Cek: cari `CREATE TABLE results` di repo / Supabase. Kalau kolom NOT NULL, opsi: simpan payload `{"status":"skipped","messages":[...]}` daripada NULL.

### Frontend

**H. `CheckResultsView.tsx` & `exportCheckResultPdf.ts`**
- Ubah dari iterasi `modules` hardcoded → iterasi key yang benar-benar ada di `result.results` (atau filter modul yang `result.results[key]` truthy). Pertahankan label mapping (struktur, physical_sheet, dst). Jadi PKM-AI tampil 4 kartu saja, PKM-KC tetap 6.
- `types.ts` `CheckResults.results` saat ini object dengan 6 key wajib → ubah jadi `Partial`/index signature agar key opsional.

### Testing
- Jalankan test eksisting `backend/tests/` (pytest) untuk pastikan PKM-KC tidak regresi setelah refactor orchestrator.
- Idealnya buat dokumen DOCX PKM-AI dummy untuk uji manual (lihat `backend/tests/build_dummy_docx.py` sebagai contoh pembuatan dummy).

## 5. Hal yang BELUM Diverifikasi (lakukan di sesi lanjutan)
1. Skema tabel `results` (NOT NULL? lokasi DDL/migration?). `backend/app/db.py` belum dibaca (interrupted).
2. Apakah frontend memang panggil `/api/schemas` & `/api/competitions/{}/report-types` atau murni konstanta lokal `checkFormConstants.ts`. (CheckFormView terlihat pakai konstanta lokal saja.)
3. Helper di `docx_parser.py` versi terkini (file modified oleh user) — cek `find_section_boundaries`, `estimate_physical_page`, signature `sections`.

## 6. Cara Membaca Panduan PKM-AI
PDF tidak bisa dibaca tool Read langsung (perlu poppler). Gunakan pypdf yang sudah ada di venv:
```
cd backend && .venv/bin/python -c "from pypdf import PdfReader; r=PdfReader('../PKM-AI-2026_fix.pdf'); [print(p.extract_text()) for p in r.pages]"
```

## 7. Status Saat Ini
- Eksplorasi & analisis selesai. **Belum ada perubahan kode** di sesi ini.
- Langkah berikut: mulai dari (F) refactor registry orchestrator + (A) schema_rules PKM-AI, lalu B/C/D, lalu G & frontend H. Verifikasi poin §5 lebih dulu.
