# BLUEPRINT: Sistem Otomasi Pengecekan Administrasi Laporan Kemahasiswaan

## Versi 0.3 — Iterasi Ketiga (Hasil Rapat Koordinasi Tim IT)

> **Catatan Versi 0.3:** Iterasi ini memperluas cakupan sistem dari hanya PKM menjadi **multi-jenis lomba** (PKM, P2MW, PPK Ormawa, BIMA), memperbarui alur pemilihan pengguna menjadi tiga tingkat (Jenis Lomba → Jenis Laporan → Skema Spesifik), dan memperketat sejumlah modul pengecekan berdasarkan temuan lapangan: hitungan halaman fisik, validasi penomoran (Romawi vs Arab + posisi sudut halaman), audit RAB yang lebih ketat (dana PT wajib, integritas kolom kategori, cross-check Bab 4 ↔ Lampiran 2, rekomendasi relokasi), Harvard Style strict (tanpa "et al."/"dkk."), pengecekan keseimbangan sitasi, validasi OCR biodata terhadap PD Dikti, serta peningkatan kapasitas infrastruktur (40 analisa simultan + Cloud Storage).

---

## 1. RINGKASAN PROYEK

### 1.1 Tujuan
Membangun sistem web-based yang mampu melakukan pengecekan otomatis terhadap administrasi laporan kemahasiswaan lintas program (PKM, P2MW, PPK Ormawa, BIMA) yang meliputi: kelengkapan struktur, jumlah lembar fisik, format penulisan (termasuk penomoran halaman per zona), audit keuangan dengan cross-check Bab 4 dan Lampiran 2, validasi daftar pustaka Harvard style strict (tanpa "et al."/"dkk."), pengecekan keseimbangan sitasi, dan OCR biodata yang tervalidasi terhadap data PD Dikti.

### 1.2 Tech Stack
| Layer | Teknologi |
|-------|-----------|
| Frontend | Next.js (App Router), TypeScript, Tailwind CSS |
| Backend/API | Python, FastAPI |
| Database | Supabase (PostgreSQL + Auth) |
| **File Storage** | **Cloud Storage pihak ketiga (Cloudflare R2 / AWS S3 / Google Cloud Storage)** — file user TIDAK disimpan di server backend agar storage server tetap efisien |
| File Processing | python-docx, pypdf, regex, OCR (Tesseract/EasyOCR), LibreOffice (konversi DOCX → PDF untuk page counting) |
| Queue & Worker | Celery + Redis (untuk antrean pemrosesan async hingga 40 job paralel) |
| Deployment | (TBD — Vercel + Railway/Fly.io atau self-hosted via Docker) |

### 1.3 Pengguna Target
- **Mahasiswa** — upload laporan sebelum submit, mendapat feedback instan
- **Reviewer/Dosen** — melihat hasil pengecekan otomatis sebagai pre-screening
- **Admin Kemahasiswaan** — dashboard monitoring, rekap, dan manajemen antrean

### 1.4 Cakupan Jenis Lomba (Multi-Program)
Sistem mendukung empat jenis lomba/program:
1. **PKM** (Program Kreativitas Mahasiswa) — 10 skema (KC, AI, GFT, K, RE, RSH, PM, PI, KI, VGK)
2. **P2MW** (Program Pembinaan Mahasiswa Wirausaha)
3. **PPK Ormawa** (Penguatan Kapasitas Organisasi Kemahasiswaan)
4. **BIMA** (Sistem Informasi Penelitian dan Pengabdian — Kemdikbud)

> **Catatan iterasi:** Pada Versi 0.3 ini, aturan teknis yang sudah lengkap baru tersedia untuk PKM (KC, AI, GFT, K). Skema PKM lainnya serta P2MW, PPK Ormawa, dan BIMA akan diisi pada iterasi berikutnya melalui mekanisme konfigurasi `competition_schemas` (lihat §3).

---

## 2. ARSITEKTUR SISTEM

```
┌─────────────────────────────────────────────────────────────┐
│                    FRONTEND (Next.js)                        │
│  ┌──────────────┐  ┌──────────┐  ┌──────────────────────┐   │
│  │ 3-Step       │  │ Dashboard│  │  Hasil Pengecekan    │   │
│  │ Selector     │  │  & Rekap │  │  (Per Modul)         │   │
│  │ (Lomba→      │  │          │  │                      │   │
│  │  Laporan→    │  │          │  │                      │   │
│  │  Skema)      │  │          │  │                      │   │
│  └──────┬───────┘  └─────┬────┘  └──────────┬───────────┘   │
│         │                │                  │               │
└─────────┼────────────────┼──────────────────┼───────────────┘
          │                │                  │
     ┌────▼────────────────▼──────────────────▼────┐
     │           API GATEWAY (FastAPI)             │
     │                                             │
     │  GET  /api/competitions                     │
     │  GET  /api/competitions/{code}/report-types │
     │  GET  /api/schemas?competition=&report=     │
     │  POST /api/check                            │
     │  GET  /api/check/{id}                       │
     │  GET  /api/queue/status                     │
     └──────────────────┬──────────────────────────┘
                        │
     ┌──────────────────▼──────────────────────────┐
     │       QUEUE (Celery + Redis)                │
     │  - Antrean job analisa (kapasitas 40 paralel)│
     │  - Estimasi durasi ~2 menit per job         │
     │  - Pop-up notifikasi jika antrean penuh     │
     └──────────────────┬──────────────────────────┘
                        │
     ┌──────────────────▼──────────────────────────┐
     │           PROCESSING ENGINE                 │
     │                                             │
     │  ┌─────────────┐  ┌────────────────────┐    │
     │  │  Structure  │  │  Physical Sheet    │    │
     │  │  Checker    │  │  Counter (PDF)     │    │
     │  └─────────────┘  └────────────────────┘    │
     │  ┌─────────────┐  ┌────────────────────┐    │
     │  │  Format &   │  │  Budget Auditor    │    │
     │  │  Page-Num   │  │  (RAB + Lamp 2     │    │
     │  │  Checker    │  │   cross-check)     │    │
     │  └─────────────┘  └────────────────────┘    │
     │  ┌─────────────┐  ┌────────────────────┐    │
     │  │  Reference  │  │  OCR Biodata +     │    │
     │  │  Validator  │  │  PD Dikti Verify   │    │
     │  │  (Harvard   │  │                    │    │
     │  │   strict)   │  │                    │    │
     │  └─────────────┘  └────────────────────┘    │
     └──────────────────┬──────────────────────────┘
                        │
     ┌──────────────────▼──────────────────────────┐
     │     STORAGE LAYER                           │
     │  ┌──────────────┐  ┌────────────────────┐   │
     │  │  Supabase    │  │  Cloud Storage     │   │
     │  │  (PostgreSQL)│  │  (R2/S3/GCS)       │   │
     │  │  - users     │  │  - uploaded .docx  │   │
     │  │  - submissns │  │  - converted .pdf  │   │
     │  │  - results   │  │  - extracted imgs  │   │
     │  │  - schemas   │  │                    │   │
     │  └──────────────┘  └────────────────────┘   │
     └─────────────────────────────────────────────┘
```

**Catatan arsitektural penting (V0.3):**
- File mentah user (.docx) dan turunan PDF disimpan di **Cloud Storage pihak ketiga**, bukan di server FastAPI. Backend hanya menyimpan **referensi/URL** di tabel Supabase.
- Pemrosesan dilakukan asinkron via worker Celery. Frontend menampilkan estimasi waktu antrean dan posisi job.

---

## 3. DATABASE SCHEMA (Supabase/PostgreSQL)

### 3.1 Tabel `competitions` (BARU di V0.3)
Menyimpan daftar jenis lomba/program induk.

```sql
CREATE TABLE competitions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code VARCHAR(20) NOT NULL UNIQUE,         -- 'PKM', 'P2MW', 'PPK_ORMAWA', 'BIMA'
    name VARCHAR(200) NOT NULL,               -- 'Program Kreativitas Mahasiswa', dst.
    description TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

**Seed awal:**
```sql
INSERT INTO competitions (code, name) VALUES
('PKM',         'Program Kreativitas Mahasiswa'),
('P2MW',        'Program Pembinaan Mahasiswa Wirausaha'),
('PPK_ORMAWA',  'Penguatan Kapasitas Ormawa'),
('BIMA',        'Sistem Informasi Penelitian & Pengabdian (Kemdikbud)');
```

### 3.2 Tabel `report_types` (BARU di V0.3)
Menyimpan jenis laporan per kompetisi (relasi banyak-ke-banyak).

```sql
CREATE TABLE report_types (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    competition_id UUID REFERENCES competitions(id) ON DELETE CASCADE,
    code VARCHAR(30) NOT NULL,                -- 'PROPOSAL', 'PROGRESS_REPORT', 'FINAL_REPORT', 'SCIENTIFIC_ARTICLE'
    name VARCHAR(100) NOT NULL,               -- 'Proposal', 'Laporan Kemajuan', 'Laporan Akhir', 'Artikel Ilmiah'
    UNIQUE(competition_id, code)
);
```

**Contoh isi untuk PKM:**
| competition | code | name |
|-------------|------|------|
| PKM | PROPOSAL | Proposal |
| PKM | PROGRESS_REPORT | Laporan Kemajuan |
| PKM | FINAL_REPORT | Laporan Akhir |
| PKM | SCIENTIFIC_ARTICLE | Artikel Ilmiah |

### 3.3 Tabel `competition_schemas` (rename dari `pkm_schemas`, di-generalisasi)
Menyimpan konfigurasi aturan untuk setiap **skema spesifik** dari setiap kompetisi.

```sql
CREATE TABLE competition_schemas (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    competition_id UUID REFERENCES competitions(id),
    schema_code VARCHAR(20) NOT NULL,         -- 'KC', 'AI', 'GFT', 'K' (untuk PKM); kosong/'-' untuk lomba single-skema
    schema_name VARCHAR(100) NOT NULL,        -- 'Karsa Cipta', dst.
    year INTEGER NOT NULL DEFAULT 2026,
    
    -- Mapping ke jenis laporan yang berlaku untuk skema ini
    applicable_report_types JSONB NOT NULL,   -- ['PROPOSAL', 'PROGRESS_REPORT', 'FINAL_REPORT'] atau ['SCIENTIFIC_ARTICLE']
    
    -- Aturan struktur per jenis laporan (key = report_type_code)
    structure_rules JSONB NOT NULL,
    
    -- Aturan halaman inti
    min_core_pages INTEGER,                   -- NULL jika tidak ada batas minimum
    max_core_pages INTEGER NOT NULL,          -- 10 untuk 8-bidang, 15 untuk GFT/AI
    
    -- Aturan format (font dasar)
    font_name VARCHAR(50) NOT NULL DEFAULT 'Times New Roman',
    font_size INTEGER NOT NULL DEFAULT 12,
    line_spacing FLOAT NOT NULL DEFAULT 1.15,
    margin_left_cm FLOAT NOT NULL DEFAULT 4.0,
    margin_right_cm FLOAT NOT NULL DEFAULT 3.0,
    margin_top_cm FLOAT NOT NULL DEFAULT 3.0,
    margin_bottom_cm FLOAT NOT NULL DEFAULT 3.0,
    paper_size VARCHAR(10) NOT NULL DEFAULT 'A4',
    
    -- Aturan penomoran halaman per zona
    page_numbering_rules JSONB NOT NULL,
    
    -- Aturan anggaran
    budget_rules JSONB NOT NULL,
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    UNIQUE(competition_id, schema_code, year)
);
```

**Contoh `page_numbering_rules` (berlaku untuk semua skema PKM dengan struktur lengkap):**
```json
{
    "front_matter": {
        "applies_to_sections": ["DAFTAR ISI", "DAFTAR GAMBAR", "DAFTAR TABEL", "DAFTAR LAMPIRAN"],
        "numeral_type": "roman_lower",
        "examples": ["i", "ii", "iii", "iv"],
        "position": "bottom_right",
        "font_name": "Times New Roman",
        "font_size": 12
    },
    "core_matter": {
        "applies_to_sections_from": "BAB 1",
        "applies_to_sections_until": "LAMPIRAN",
        "numeral_type": "arabic",
        "examples": ["1", "2", "3"],
        "position": "top_right",
        "font_name": "Times New Roman",
        "font_size": 12
    }
}
```

**Contoh `budget_rules` PKM-KC (V0.3 — diperketat):**
```json
{
    "funding_type": "pendanaan",
    "funding_sources": {
        "belmawa": {
            "min": 6000000,
            "max": 8000000,
            "mandatory": true,
            "validation": "Dana Belmawa wajib berada di rentang Rp6.000.000 — Rp8.000.000"
        },
        "university": {
            "min": 500,
            "max": 2000000,
            "mandatory": true,
            "validation": "Dana PT WAJIB > Rp0 (minimal Rp500) dan tidak boleh melebihi Rp2.000.000",
            "zero_value_is_error": true
        },
        "external": {
            "min": 0,
            "max": 1000000,
            "mandatory": false
        }
    },
    "categories": [
        {"name": "Bahan habis pakai", "max_percentage": 60, "must_exist_in_table": true},
        {"name": "Sewa dan jasa",     "max_percentage": 15, "must_exist_in_table": true},
        {"name": "Transportasi lokal","max_percentage": 30, "must_exist_in_table": true},
        {"name": "Lain-lain",         "max_percentage": 15, "must_exist_in_table": true}
    ],
    "table_integrity": {
        "all_categories_required": true,
        "reject_if_category_column_deleted": true,
        "note": "Sistem MENOLAK dokumen jika kolom kategori (Bahan Habis Pakai, Sewa, dst) dihapus, meskipun nilainya kosong/Rp0"
    },
    "cross_check": {
        "bab4_vs_lampiran2": {
            "enabled": true,
            "tolerance_rupiah": 0,
            "note": "Total di Bab 4 (Biaya & Jadwal) wajib SAMA dengan total rincian di Lampiran 2 (Justifikasi Anggaran)"
        }
    },
    "single_item_relocation_advisory": {
        "threshold": 1000000,
        "level": "warning",
        "action": "advisory_only",
        "message": "Item transaksi tunggal di atas Rp1.000.000 sebaiknya dipecah/direlokasi ke beberapa item agar lebih realistis. Ini bukan error, hanya saran."
    },
    "composition": {
        "operational_min_percentage": 80,
        "administration_max_percentage": 20
    },
    "restrictions": {
        "social_media_ads_max": 500000,
        "lab_rental_max": 1000000,
        "item_purchase_max": 1000000,
        "internet_quota_max_per_month": 100000,
        "license_max_duration_months": 6
    },
    "prohibited_items": [
        "Honorarium",
        "Konsumsi",
        "Hadiah",
        "Sewa komputer/laptop/printer/ponsel/kamera",
        "Pembelian penyimpanan data",
        "Biaya seminar/publikasi jurnal"
    ]
}
```

### 3.4 Tabel `user_profiles`
```sql
CREATE TABLE user_profiles (
    id UUID PRIMARY KEY REFERENCES auth.users(id),
    full_name VARCHAR(200),
    nim VARCHAR(30),                    -- untuk validasi PD Dikti
    university VARCHAR(200),
    role VARCHAR(20) DEFAULT 'student', -- student, reviewer, admin
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

### 3.5 Tabel `check_submissions` (diperbarui)
```sql
CREATE TABLE check_submissions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES auth.users(id),
    
    -- 3-tier selection (V0.3)
    competition_id UUID REFERENCES competitions(id),
    report_type_id UUID REFERENCES report_types(id),
    schema_id       UUID REFERENCES competition_schemas(id),
    
    -- File di Cloud Storage (BUKAN di server)
    storage_provider VARCHAR(20) NOT NULL,    -- 'r2', 's3', 'gcs'
    storage_bucket   VARCHAR(100) NOT NULL,
    storage_key      TEXT NOT NULL,           -- path di bucket
    storage_url      TEXT,                    -- signed URL (cached, regenerate jika expired)
    original_filename TEXT NOT NULL,
    file_size_bytes  BIGINT,
    
    -- Budget calculator input
    total_funding BIGINT,
    funding_belmawa BIGINT,
    funding_pt BIGINT,
    funding_external BIGINT,
    
    -- Queue tracking
    queue_position INTEGER,                   -- posisi dalam antrean saat masuk
    queued_at TIMESTAMPTZ DEFAULT NOW(),
    started_at TIMESTAMPTZ,
    
    status VARCHAR(20) DEFAULT 'queued',      -- queued, processing, completed, failed, queue_full_rejected
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);
```

### 3.6 Tabel `check_results`
```sql
CREATE TABLE check_results (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    submission_id UUID REFERENCES check_submissions(id) ON DELETE CASCADE,
    
    overall_score FLOAT,
    overall_status VARCHAR(20),              -- 'pass', 'warning', 'fail'
    
    structure_result   JSONB,
    page_count_result  JSONB,                -- berbasis hitungan LEMBAR FISIK
    format_result      JSONB,                -- termasuk validasi penomoran per zona
    budget_result      JSONB,                -- termasuk cross-check Bab 4 ↔ Lamp 2
    reference_result   JSONB,                -- Harvard strict + balance check
    biodata_ocr_result JSONB,                -- Nama/NIM/Tahun/TTD + saran KTP
    
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

### 3.7 Tabel `queue_metrics` (BARU di V0.3)
Untuk monitoring antrean.

```sql
CREATE TABLE queue_metrics (
    id BIGSERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ DEFAULT NOW(),
    active_jobs INTEGER NOT NULL,            -- yang sedang diproses (≤ 40)
    queued_jobs INTEGER NOT NULL,            -- yang menunggu
    avg_processing_time_seconds INTEGER,
    rejected_count_last_hour INTEGER         -- ditolak karena queue full
);
```


---

## 4. MODUL PROCESSING ENGINE (Detail — Direvisi V0.3)

### 4.1 Module: Structure Checker
**Input:** File .docx + skema + jenis laporan
**Output:** List sections yang ditemukan, hilang, salah urutan, atau tidak diizinkan (red flag)

**Logika:**
1. Parse .docx menggunakan `python-docx`.
2. Identifikasi heading/section berdasarkan style heading, pola regex (`^BAB \d+\.`, `^DAFTAR`, `^LAMPIRAN`, `^RINGKASAN`), dan teks UPPERCASE bold.
3. Bandingkan dengan `structure_rules` dari `competition_schemas` (key = report_type_code).
4. Cek red flags per skema (mis. PKM-KC proposal: tidak boleh ada halaman sampul/pengesahan/abstrak).

**Output JSON contoh** — sama seperti V0.2, tetap berlaku.

---

### 4.2 Module: Physical Sheet Counter (DIREVISI V0.3)
**Input:** File .docx (akan dikonversi ke PDF)
**Output:** Jumlah **lembar fisik** bagian inti + status validitas penomoran

**Perubahan utama V0.3 — Hitungan Lembar Fisik (bukan Nomor Halaman):**
Pengecekan halaman **TIDAK** boleh hanya mengandalkan nomor halaman yang tertera di dokumen. Sistem harus menghitung **jumlah lembar fisik** hasil render PDF, lalu **mencocokkannya** dengan nomor halaman yang tertera. Tujuan: mendeteksi kesalahan penomoran seperti:
- Nomor halaman duplikat (mis. dua halaman bernomor "5")
- Nomor halaman meloncat (mis. setelah "7" langsung "9")
- Nomor halaman tidak urut (mis. "8" sebelum "7")
- Hilangnya nomor halaman pada lembar tertentu

**Logika:**
1. Konversi `.docx` → `.pdf` menggunakan LibreOffice headless (`soffice --headless --convert-to pdf`).
2. Hitung total lembar PDF (`physical_sheet_count`) menggunakan `pypdf`.
3. Identifikasi lembar awal & akhir bagian inti (BAB 1 sampai akhir Lampiran) berdasarkan pencocokan teks.
4. Untuk setiap lembar, ekstrak nomor halaman yang tertera (di pojok kanan atas atau bawah, sesuai zona).
5. Bandingkan **urutan nomor tertera** vs **urutan lembar fisik**. Deteksi:
   - `duplicate_numbers`: nomor yang muncul lebih dari 1 kali
   - `skipped_numbers`: gap dalam urutan
   - `out_of_order`: nomor mundur
   - `missing_numbers`: lembar tanpa nomor yang seharusnya bernomor
6. Bandingkan `core_physical_sheets` dengan aturan skema:
   - **Skema GFT & AI:** minimal 8 dan maksimal 15 lembar
   - **Skema 8 bidang lainnya (KC, K, RE, RSH, PM, PI, KI, VGK):** maksimal 10 lembar (tanpa batas minimum)

**Output JSON:**
```json
{
    "status": "fail",
    "method": "pdf_physical_sheet_count",
    "total_physical_sheets": 12,
    "core_physical_sheets": 11,
    "rule": {
        "schema": "PKM-KC",
        "min_sheets": null,
        "max_sheets": 10
    },
    "page_numbering_issues": {
        "duplicate_numbers": [{"number": "5", "found_on_sheets": [6, 7]}],
        "skipped_numbers": [{"after": "7", "next": "9"}],
        "out_of_order": [],
        "missing_numbers": [{"sheet_index": 9, "expected": "8 atau 9"}]
    },
    "messages": [
        {"level": "fail", "text": "Bagian inti 11 lembar fisik — melebihi batas 10 lembar untuk PKM-KC"},
        {"level": "fail", "text": "Nomor halaman '5' duplikat (muncul di lembar fisik ke-6 dan ke-7)"},
        {"level": "fail", "text": "Nomor halaman meloncat dari '7' langsung ke '9' — kemungkinan salah set page numbering"}
    ]
}
```

---

### 4.3 Module: Format & Page-Numbering Checker (DIREVISI V0.3)
**Input:** File .docx
**Output:** Daftar ketidaksesuaian format

**Yang dicek:**
1. **Font seluruh dokumen:** Times New Roman 12pt
   - Deteksi font lain (Arial, Calibri, dll) → fail
   - Deteksi ukuran font berbeda di body teks → fail
   - **Nomor halaman juga wajib Times New Roman 12pt** (V0.3 — cek baru)
   - Deteksi bahasa asing yang tidak italic
2. **Margin:** Kiri 4 cm, Kanan/Atas/Bawah 3 cm (toleransi ±0.05 cm)
3. **Kertas:** A4 (width 11906 DXA, height 16838 DXA)
4. **Spasi baris:** 1.15
5. **Perataan:** Justify (rata kiri-kanan)
6. **Penomoran halaman per zona (DIPERKUAT V0.3):**

   | Zona | Jenis Numeral | Posisi | Font |
   |------|---------------|--------|------|
   | Bagian Awal (Daftar Isi, Daftar Gambar, Daftar Tabel, Daftar Lampiran) | **Romawi kecil** (i, ii, iii, …) | **Pojok kanan bawah** | Times New Roman 12pt |
   | Bagian Inti (BAB 1 s.d. Lampiran) | **Angka Arab** (1, 2, 3, …) | **Pojok kanan atas** | Times New Roman 12pt |

   Sistem memvalidasi tiga aspek sekaligus per lembar: jenis numeral, posisi sudut, dan format font nomor halamannya.

**Pendekatan teknis untuk validasi posisi & format nomor halaman:**
- Parse `headerN.xml` dan `footerN.xml` di dalam paket `.docx` (struktur OOXML).
- Pada `<w:sectPr>`, identifikasi `<w:pgNumType w:fmt="..."/>` (`decimal`, `lowerRoman`, dll) per section.
- Pada `<w:p>` di header/footer, periksa alignment (`<w:jc w:val="right"/>`) dan run properties (`<w:rFonts w:ascii="Times New Roman"/>`, `<w:sz w:val="24"/>` → 24 half-points = 12pt).
- Untuk validasi posisi (atas vs bawah): jika nomor di header → "top", di footer → "bottom".
- Untuk validasi alignment kanan: alignment harus `right`.

**Deteksi Bahasa Asing Italic:**
- Maintain dictionary kata-kata asing umum dalam konteks akademik.
- Detect kata/frasa non-Indonesia (English, Latin, dll) yang tidak di-italic.

**Output JSON:**
```json
{
    "status": "fail",
    "checks": {
        "font_body": {
            "status": "warning",
            "issues": [
                {"paragraph": 15, "text_preview": "Rotating Biological...", "issue": "Bahasa asing tidak italic"},
                {"paragraph": 42, "text_preview": "Data menunjukkan...", "issue": "Font bukan TNR", "found": "Arial"}
            ]
        },
        "page_number_format": {
            "status": "fail",
            "issues": [
                {"sheet": 3, "issue": "Font nomor halaman bukan Times New Roman", "found": "Calibri 11pt"},
                {"sheet": 5, "issue": "Ukuran nomor halaman bukan 12pt", "found": "10pt"}
            ]
        },
        "page_numbering_zones": {
            "status": "fail",
            "front_matter": {
                "status": "fail",
                "expected": {"numeral": "roman_lower", "position": "bottom_right"},
                "found":    {"numeral": "arabic",      "position": "bottom_right"},
                "message": "Daftar Isi seharusnya pakai romawi kecil (i, ii, iii), bukan angka arab"
            },
            "core_matter": {
                "status": "fail",
                "expected": {"numeral": "arabic", "position": "top_right"},
                "found":    {"numeral": "arabic", "position": "bottom_center"},
                "message": "Bagian inti (BAB 1 dst) seharusnya nomor halaman di pojok kanan ATAS, bukan tengah bawah"
            }
        },
        "margin": {"status": "pass", "left_cm": 4.0, "right_cm": 3.0, "top_cm": 3.0, "bottom_cm": 3.0},
        "paper_size": {"status": "pass", "detected": "A4"},
        "line_spacing": {"status": "pass", "detected": 1.15},
        "alignment": {"status": "pass"}
    }
}
```

---

### 4.4 Module: Budget Auditor (DIPERKUAT V0.3)
**Input:** File .docx (untuk extract tabel RAB Bab 4 + tabel rincian Lampiran 2) + total dana Belmawa/PT/Eksternal yang diinput user + skema
**Output:** Validasi alokasi anggaran + cross-check Bab 4 vs Lampiran 2 + rekomendasi relokasi

**Logika V0.3 (5 lapis pengecekan):**

**Lapis 1 — Validasi Sumber Dana (DIPERKETAT):**
1. **Dana PT (Perguruan Tinggi):** WAJIB > Rp0 (minimal Rp500), maksimal Rp2.000.000.
   - Jika user input Rp0 → **FAIL** dengan pesan: *"Dana PT wajib minimal Rp500. Tidak diperkenankan Rp0."*
   - Jika > Rp2.000.000 → **FAIL** dengan pesan: *"Dana PT melebihi batas Rp2.000.000."*
2. **Dana Belmawa:** WAJIB di rentang Rp6.000.000 — Rp8.000.000.
   - Di luar rentang → **FAIL**.
3. **Dana Eksternal:** opsional, maksimal Rp1.000.000 jika ada.

**Lapis 2 — Integritas Tabel RAB:**
- Sistem extract tabel RAB dari .docx (deteksi tabel berdasarkan header "Jenis Pengeluaran" / "Kategori").
- Wajib mendeteksi keberadaan **semua kolom kategori** sesuai skema:
  - Bahan habis pakai
  - Sewa dan jasa
  - Transportasi lokal
  - Lain-lain
- Jika ada kolom kategori yang **dihapus oleh user** (meskipun nilainya kosong/Rp0) → **FAIL** dengan pesan: *"Kolom '[nama kategori]' dihapus dari tabel RAB. Kolom kategori wajib utuh meskipun nilainya Rp0."*

**Lapis 3 — Validasi Alokasi per Kategori:**
- Hitung persentase tiap kategori terhadap total dana.
- Bandingkan dengan `max_percentage` per kategori di `budget_rules`.
- Cek komposisi operasional ≥ 80%, administrasi ≤ 20%.

**Lapis 4 — Cross-Check Bab 4 ↔ Lampiran 2 (BARU V0.3):**
- Ekstrak total nilai per kategori dari **Bab 4 (Biaya & Jadwal Kegiatan)**.
- Ekstrak total nilai per kategori dari **Lampiran 2 (Justifikasi Anggaran / rincian)**.
- Bandingkan keduanya. Toleransi: Rp0 (harus identik).
- Jika tidak sinkron → **FAIL** dengan detail per kategori.

**Lapis 5 — Rekomendasi Relokasi (BARU V0.3, level: warning/saran):**
- Scan setiap baris item transaksi di Lampiran 2.
- Jika ada item tunggal dengan nilai > Rp1.000.000 → **WARNING (saran, bukan error mati)**.
- Berikan notifikasi: *"Item '[nama item]' senilai Rp[X] disarankan dipecah/direlokasi menjadi beberapa item untuk realisme dan akuntabilitas. Saran ini bukan error — proposal tetap bisa lolos validasi."*

**Lapis 6 — Item Terlarang & Restriksi Khusus:** (lanjutan dari V0.2)
- Scan deskripsi item terhadap `prohibited_items` (honorarium, konsumsi, sewa laptop, dll).
- Cek restriksi spesifik (ads medsos ≤ Rp500rb, sewa lab ≤ Rp1jt, kuota internet ≤ Rp100rb/bulan, dll).

**Output JSON:**
```json
{
    "status": "fail",
    "funding_validation": {
        "belmawa": {"input": 6000000, "min": 6000000, "max": 8000000, "status": "pass"},
        "university": {
            "input": 0,
            "min": 500,
            "max": 2000000,
            "status": "fail",
            "message": "Dana PT wajib minimal Rp500. Tidak diperkenankan Rp0."
        },
        "external": {"input": 0, "min": 0, "max": 1000000, "status": "pass"}
    },
    "table_integrity": {
        "status": "fail",
        "missing_categories": ["Lain-lain"],
        "message": "Kolom kategori 'Lain-lain' dihapus dari tabel RAB. Kolom kategori wajib utuh meskipun bernilai Rp0."
    },
    "categories": [
        {"name": "Bahan habis pakai", "max_pct": 60, "actual_pct": 56.25, "status": "pass"},
        {"name": "Sewa dan jasa",     "max_pct": 15, "actual_pct": 18.75, "status": "fail", "excess_rp": 300000},
        {"name": "Transportasi lokal","max_pct": 30, "actual_pct": 12.5,  "status": "pass"},
        {"name": "Lain-lain",         "max_pct": 15, "actual_pct": null,  "status": "fail", "reason": "kolom dihapus"}
    ],
    "cross_check_bab4_vs_lampiran2": {
        "status": "fail",
        "discrepancies": [
            {"category": "Bahan habis pakai", "bab4": 4500000, "lampiran2": 4750000, "delta_rp": 250000},
            {"category": "Transportasi lokal", "bab4": 1000000, "lampiran2": 1000000, "delta_rp": 0}
        ],
        "message": "Total Bab 4 tidak sama dengan total Lampiran 2 — kemungkinan ada revisi yang belum disinkronkan."
    },
    "relocation_advisory": {
        "status": "warning",
        "items_above_threshold": [
            {
                "category": "Bahan habis pakai",
                "item": "Modul mikrokontroler ESP32 + sensor",
                "amount": 1450000,
                "advisory": "Item tunggal di atas Rp1.000.000 disarankan dipecah menjadi beberapa item untuk akuntabilitas. Bukan error."
            }
        ]
    },
    "prohibited_items_found": [],
    "restriction_checks": [
        {"item": "Ads media sosial", "max": 500000, "found": 300000, "status": "pass"}
    ]
}
```

---

### 4.5 Module: Reference Validator (DIPERKUAT V0.3 — Strict Harvard)

**Input:** Teks Daftar Pustaka + body teks dokumen
**Output:** Validasi format per entry + analisis sitasi + rekomendasi kualitas referensi

**Yang dicek (V0.3):**

**A. Format Strict Harvard:**
1. **Buku:** Nama belakang, Inisial. (Tahun) *Judul Buku*. Edisi. Tempat: Penerbit.
2. **Jurnal:** Nama belakang, Inisial. (Tahun) 'Judul Artikel', *Nama Jurnal*, Volume(Issue), pp. x-y.
3. **Prosiding, Skripsi/Tesis, Website, Media Sosial:** lihat aturan V0.2 (tidak berubah).

**B. LARANGAN STRICT (BARU V0.3):**
- **TIDAK BOLEH menggunakan "et al."** di Daftar Pustaka.
- **TIDAK BOLEH menggunakan "dkk."** di Daftar Pustaka.
- Semua nama penulis WAJIB ditulis lengkap (Nama belakang + Inisial), berapa pun jumlah penulisnya.
- Jika terdeteksi → **FAIL** dengan pesan eksplisit: *"Daftar Pustaka memuat 'et al.' / 'dkk.' yang dilarang oleh aturan Harvard strict. Tulis semua nama penulis lengkap."*

**C. Pengecekan Keseimbangan Sitasi (BARU V0.3 — Mencegah Referensi Bodong):**
Sistem melakukan dua arah pengecekan:

1. **In-text → Daftar Pustaka:**
   - Scan body teks untuk pola sitasi: `(Nama, Tahun)`, `Nama (Tahun)`, `(Nama1 dan Nama2, Tahun)`.
   - Setiap sitasi yang ditemukan di teks **WAJIB** ada padanannya di Daftar Pustaka.
   - Jika ada sitasi di teks tapi tidak ada di Daftar Pustaka → **FAIL** (referensi tidak lengkap).

2. **Daftar Pustaka → In-text:**
   - Setiap entry di Daftar Pustaka **WAJIB** dirujuk minimal sekali di body teks.
   - Jika ada entry yang tidak pernah disitasi di teks → **FAIL** (referensi bodong / unused reference).

Hasil ditampilkan dalam dua list: `in_text_not_in_references` dan `in_references_not_in_text`.

**D. Urutan Alfabetis:** entry dalam Daftar Pustaka harus alfabetis berdasarkan nama belakang penulis pertama.

**E. Italic pada Judul:** judul buku/jurnal harus italic.

**F. Rekomendasi Kualitas (BARU V0.3 — Saran, Bukan Error):**
- Hitung jumlah referensi mutakhir (terbit < 10 tahun terakhir, yaitu ≥ 2017 untuk tahun acuan 2026).
- Jika **jumlah referensi mutakhir < 8** → tampilkan **SARAN (warning, bukan fail)**: *"Anda memiliki [X] referensi mutakhir (<10 tahun). Untuk scoring maksimal, disarankan menambah referensi mutakhir agar mencapai minimal 8 entri."*

**Pendekatan teknis:**
- Regex patterns per tipe sumber (sudah ada sebagian di V0.2).
- Parse nama penulis, tahun, judul, venue.
- Untuk balance check: tokenize body teks, ekstrak `(Nama, Tahun)` dengan regex, normalisasi (lowercase, strip) lalu cocokkan dengan key entry Daftar Pustaka.

**Output JSON:**
```json
{
    "status": "fail",
    "total_entries": 15,
    "valid_entries": 11,
    "format_issues": [
        {
            "entry_index": 3,
            "text_preview": "Rahmadi et al. (2022) ...",
            "severity": "fail",
            "issue": "Mengandung 'et al.' — Harvard strict melarang. Tulis semua penulis lengkap."
        },
        {
            "entry_index": 7,
            "text_preview": "WHO (2021) Living guidance...",
            "severity": "warning",
            "issue": "Judul tidak italic"
        }
    ],
    "alphabetical_order": {
        "status": "fail",
        "out_of_order": [{"index": 5, "current": "Syukri", "should_be_after": "Sulichantini"}]
    },
    "citation_balance": {
        "status": "fail",
        "in_text_not_in_references": [
            {"citation": "(Johnson, 2020)", "found_at_paragraph": 12,
             "message": "Sitasi ada di teks tapi tidak ditemukan di Daftar Pustaka."}
        ],
        "in_references_not_in_text": [
            {"reference": "Ikawati, Z. (2018) ...",
             "message": "Referensi bodong: ada di Daftar Pustaka tapi tidak dirujuk di body teks."}
        ]
    },
    "quality_recommendation": {
        "level": "warning",
        "recent_references_count": 5,
        "recent_threshold_years": 10,
        "minimum_recommended": 8,
        "message": "Hanya 5 referensi mutakhir (<10 tahun). Disarankan menambah hingga ≥8 untuk scoring maksimal. Bukan error mati."
    }
}
```

---

### 4.6 Module: OCR Biodata + PD Dikti Verifier (DIREVISI V0.3)

**Input:** File .docx — bagian Lampiran Biodata (ketua + anggota + dosen pendamping); akses lookup ke API/dataset PD Dikti
**Output:** Validasi Nama, NIM/NIDN, Tahun, deteksi tanda tangan crop, saran KTP

**Fokus Validasi V0.3:**
1. **Nama:** harus identik dengan record di PD Dikti (case-insensitive, abaikan ekstra spasi).
2. **NIM (mahasiswa) / NIDN (dosen):** wajib ada dan tervalidasi di PD Dikti.
3. **Tahun:** semua tanggal/tahun yang tertera di biodata wajib **2027** (sesuai siklus pendanaan PKM 2026 yang berlangsung hingga 2027). Tahun selain 2027 → flag.
4. **Tanda tangan hasil cropping:** deteksi tanda tangan yang tampak hasil potongan/edit lokal (bukan scan TTD basah asli).

**Logika:**
1. Identifikasi section Lampiran Biodata (per anggota).
2. Ekstrak teks biodata (Nama lengkap, NIM/NIDN, tempat & tanggal lahir, dst.).
3. Lookup ke PD Dikti via API/dataset (untuk validasi Nama–NIM matching).
4. Untuk tanda tangan:
   - Ekstrak gambar TTD dari .docx (`document.xml.rels` + `/word/media/`).
   - Jalankan analisis edge/contour & deteksi artefak crop:
     - Tepi terlalu lurus/sempurna (rectangular hard edge)
     - Background warna solid yang berbeda dari kertas asli
     - Resolusi yang tidak konsisten antar TTD anggota
   - Output `crop_suspicion_score` (0–1).
5. Untuk tanggal:
   - Jika teks tertanam → parse langsung.
   - Jika dalam gambar (scan TTD basah) → OCR (Tesseract/EasyOCR), parse tahun.
   - Cocokkan dengan tahun acuan **2027**.

**Saran KTP (BARU V0.3):**
- Jika nama di PD Dikti adalah **singkatan** (mengandung titik dalam nama, contoh: `"M. Ibnu"`, `"A. Rahman"`, `"Moh. Iqbal"`) → tampilkan **saran (bukan error)**: *"Nama di PD Dikti tertulis singkat ('[nama]'). Disarankan melampirkan KTP di lampiran terakhir untuk klarifikasi identitas."*

**Output JSON:**
```json
{
    "status": "warning",
    "biodata_entries": [
        {
            "role": "Ketua",
            "name_in_doc": "Muhammad Ibnu Pratama",
            "nim_in_doc": "2114321023",
            "pd_dikti_lookup": {
                "found": true,
                "name_pd_dikti": "M. Ibnu Pratama",
                "name_match": true,
                "name_is_abbreviated": true
            },
            "year_check": {"detected": "2027", "expected": "2027", "status": "pass"},
            "signature_check": {
                "image_extracted": true,
                "crop_suspicion_score": 0.18,
                "status": "pass"
            },
            "ktp_advisory": {
                "level": "info",
                "message": "Nama di PD Dikti berupa singkatan ('M. Ibnu Pratama'). Disarankan melampirkan KTP di lampiran terakhir."
            }
        },
        {
            "role": "Anggota 1",
            "name_in_doc": "Siti Nurhaliza",
            "nim_in_doc": "2114321099",
            "pd_dikti_lookup": {
                "found": false,
                "message": "NIM tidak ditemukan di PD Dikti — periksa kembali."
            },
            "year_check": {"detected": "2026", "expected": "2027", "status": "fail",
                           "message": "Tahun di biodata seharusnya 2027, terdeteksi 2026."},
            "signature_check": {
                "image_extracted": true,
                "crop_suspicion_score": 0.84,
                "status": "fail",
                "message": "Tanda tangan terdeteksi hasil cropping (tepi terlalu rapi, background tidak natural)."
            }
        }
    ]
}
```


---

## 5. API ENDPOINTS (FastAPI — Direvisi V0.3)

```
POST   /api/auth/register                     — Registrasi user
POST   /api/auth/login                        — Login user

GET    /api/competitions                      — List jenis lomba (PKM, P2MW, PPK Ormawa, BIMA)
GET    /api/competitions/{code}/report-types  — List jenis laporan untuk kompetisi tertentu
GET    /api/schemas?competition=&report=      — List skema spesifik untuk kombinasi kompetisi+laporan
GET    /api/schemas/{id}                      — Detail aturan skema

POST   /api/check                             — Submit job pengecekan (multipart):
                                                 - competition_id
                                                 - report_type_id
                                                 - schema_id
                                                 - file (.docx)
                                                 - funding_belmawa, funding_pt, funding_external
                                                Sistem upload file ke Cloud Storage → enqueue job
                                                Response 503 jika antrean penuh (>40 active jobs)
GET    /api/check/{submission_id}             — Status & hasil
GET    /api/check/history                     — Riwayat user

GET    /api/queue/status                      — Status antrean global (active, queued, ETA)
POST   /api/budget-calculator                 — Standalone kalkulator (tanpa upload)

GET    /api/admin/dashboard                   — Rekap statistik (admin only)
GET    /api/admin/queue-metrics               — Metrik antrean historis
```

**Response saat antrean penuh (V0.3):**
```json
HTTP 503 Service Unavailable
{
    "error": "queue_full",
    "active_jobs": 40,
    "queued_jobs": 12,
    "message": "Antrean pemrosesan saat ini penuh. Silakan coba lagi dalam ~5 menit.",
    "retry_after_seconds": 300
}
```

Frontend menangkap response ini dan menampilkan **pop-up notifikasi**: *"Antrean penuh, silakan coba lagi sebentar."*

---

## 6. ALUR KERJA (User Flow)

### 6.1 Flow Utama: Cek Laporan (DIREVISI V0.3 — 3-Step Selector)

```
1. User login / register
2. STEP 1 — User pilih JENIS LOMBA:
   ○ PKM
   ○ P2MW
   ○ PPK Ormawa
   ○ BIMA
3. STEP 2 — User pilih JENIS LAPORAN (tergantung Lomba):
   PKM → ○ Proposal  ○ Laporan Kemajuan  ○ Laporan Akhir  ○ Artikel Ilmiah
   P2MW → (sesuai konfigurasi P2MW)
   PPK Ormawa → (sesuai konfigurasi PPK Ormawa)
   BIMA → (sesuai konfigurasi BIMA)
4. STEP 3 — User pilih SKEMA SPESIFIK (tergantung Lomba+Laporan):
   PKM + Proposal → KC, K, RE, RSH, PM, PI, KI, GFT, VGK
   PKM + Laporan Kemajuan → KC, K, RE, RSH, PM, PI, KI, VGK (GFT dan AI tidak punya lapkem)
   PKM + Laporan Akhir → KC, K, RE, RSH, PM, PI, KI, VGK
   PKM + Artikel Ilmiah → AI saja
5. User upload file .docx
6. User input total pendanaan: Belmawa / PT / Eksternal
7. Frontend submit POST /api/check
   - Backend upload file ke Cloud Storage → simpan referensi di DB
   - Backend enqueue Celery job
   - Jika antrean ≥ 40 active → response 503 → frontend pop-up "Antrean penuh"
8. Worker memproses (durasi ~2 menit/job):
   a. Structure Checker
   b. Physical Sheet Counter (PDF)
   c. Format & Page-Numbering Checker
   d. Budget Auditor (incl. cross-check Bab 4 ↔ Lampiran 2)
   e. Reference Validator (strict Harvard + balance + recency)
   f. OCR Biodata + PD Dikti Verifier
9. User mendapat notifikasi (atau polling otomatis) → buka halaman hasil
10. User download laporan PDF (opsional)
```

### 6.2 Flow Kalkulator Anggaran (Standalone)
Sama seperti V0.2, dengan tambahan validasi Dana PT minimal Rp500 dan rentang Belmawa Rp6jt–Rp8jt.

---

## 7. FRONTEND PAGES (Next.js)

### 7.1 Halaman Utama
| Route | Deskripsi |
|-------|-----------|
| `/` | Landing page |
| `/login` | Login / Register |
| `/dashboard` | Riwayat check user |
| `/check/new` | **3-Step selector** (Lomba → Laporan → Skema) + form upload + form pendanaan |
| `/check/[id]` | Hasil pengecekan detail |
| `/calculator` | Kalkulator anggaran |
| `/admin` | Dashboard admin |
| `/admin/queue` | Monitoring antrean |

### 7.2 Komponen `/check/new` — 3-Step Selector
Wizard 3 langkah:
- Langkah 1: kartu pilihan jenis lomba (4 opsi).
- Langkah 2: setelah lomba dipilih, fetch `/api/competitions/{code}/report-types`, render opsi laporan.
- Langkah 3: setelah laporan dipilih, fetch `/api/schemas?competition=...&report=...`, render skema yang valid.
- Setelah ketiga dipilih → tampilkan form upload + input pendanaan.

### 7.3 Komponen Hasil Pengecekan (`/check/[id]`)
Card/accordion per modul:
1. **Struktur Dokumen**
2. **Jumlah Lembar Fisik & Penomoran** (V0.3: termasuk deteksi nomor duplikat/loncat)
3. **Format Penulisan** (V0.3: termasuk validasi penomoran per zona dan font nomor halaman)
4. **Audit Keuangan** (V0.3: termasuk cross-check Bab 4 ↔ Lamp 2 + advisory relokasi)
5. **Daftar Pustaka** (V0.3: balance check + recency advisory)
6. **Biodata & PD Dikti** (V0.3: ganti Date Scanner; saran KTP)

Setiap modul: ✅ Pass | ⚠️ Warning | ❌ Fail

### 7.4 Pop-up Antrean Penuh (V0.3)
Ketika POST `/api/check` mengembalikan HTTP 503 dengan `error: "queue_full"`, frontend menampilkan modal:
- Judul: *"Antrean Pemrosesan Penuh"*
- Body: *"Saat ini ada 40 analisa berjalan dan 12 dalam antrean. Estimasi tunggu ~5 menit. Silakan coba lagi nanti."*
- Tombol: "Coba Lagi" (disable selama countdown `retry_after_seconds`).


---

## 8. KONFIGURASI SKEMA (V0.3 — Penyesuaian Aturan)

> Bagian ini mempertahankan detail per-skema dari V0.2 dengan pembaruan:
> - Aturan halaman: GFT & AI = 8–15 lembar fisik; 8 bidang lainnya (KC, K, RE, RSH, PM, PI, KI, VGK) = maks 10 lembar fisik (tanpa minimum).
> - Aturan dana: PT minimal Rp500, maks Rp2 juta; Belmawa Rp6–8 juta.
> - Aturan penomoran: zona awal romawi pojok kanan bawah; zona inti arab pojok kanan atas; nomor halaman wajib TNR 12pt.
> - Aturan referensi: strict Harvard (no "et al."/"dkk."), balance check, advisory ≥8 referensi mutakhir.

### 8.1 PKM-KC — Aturan Struktur Proposal
| No | Section | Wajib |
|----|---------|-------|
| 1 | DAFTAR ISI | Ya |
| 2 | DAFTAR GAMBAR | Tidak |
| 3 | DAFTAR TABEL | Tidak |
| 4 | DAFTAR LAMPIRAN | Ya |
| 5 | BAB 1. PENDAHULUAN | Ya (inti) |
| 6 | BAB 2. TINJAUAN PUSTAKA | Ya (inti) |
| 7 | BAB 3. TAHAP PELAKSANAAN | Ya (inti) |
| 8 | BAB 4. BIAYA DAN JADWAL KEGIATAN | Ya (inti) |
| 9 | DAFTAR PUSTAKA | Ya (inti) |
| 10 | LAMPIRAN | Ya |

**Aturan Halaman Inti:** Maksimal **10 lembar fisik**, tanpa batas minimum.

**Red Flags (Langsung Tidak Lolos Tahap 1):**
- Halaman sampul, halaman pengesahan, ringkasan/abstrak
- Tanda tangan hasil crop (deteksi via `crop_suspicion_score > 0.7`)
- Kolom kategori RAB dihapus
- Dana PT = Rp0
- Daftar Pustaka mengandung "et al." atau "dkk."

### 8.2 PKM-KC — Laporan Kemajuan & Laporan Akhir
Tetap seperti V0.2 (struktur sama). Aturan halaman & dana tetap mengikuti pembaruan §8 di atas.

### 8.3 PKM-KC — Aturan Anggaran (Direvisi V0.3)

**Sumber Dana:**
| Sumber | Range | Validasi |
|--------|-------|----------|
| Belmawa | Rp6.000.000 — Rp8.000.000 | Wajib di rentang ini |
| Perguruan Tinggi (wajib) | **Rp500 — Rp2.000.000** | **Wajib > Rp0; minimal Rp500; maksimal Rp2 juta** |
| Institusi Lain (opsional) | Maks Rp1.000.000 | Boleh kosong |

**Kategori (semua wajib ada di tabel, kolom tidak boleh dihapus):**
| Kategori | Maks % | Jika total Rp8jt → Maks Rp |
|----------|--------|-----------------------------|
| Bahan habis pakai | 60% | Rp4.800.000 |
| Sewa dan jasa | 15% | Rp1.200.000 |
| Transportasi lokal | 30% | Rp2.400.000 |
| Lain-lain | 15% | Rp1.200.000 |

**Validasi tambahan V0.3:**
- Cross-check Bab 4 ↔ Lampiran 2 (toleransi Rp0).
- Advisory: item tunggal > Rp1.000.000 → saran dipecah/relokasi.

### 8.4 PKM-AI — Aturan Struktur Artikel Ilmiah
PKM-AI = PKM Insentif (artikel ilmiah dari kegiatan akademik selesai). **Tidak ada halaman sampul, halaman pengesahan, dan daftar isi pada berkas naskah.**

| No | Section | Wajib | Catatan |
|----|---------|-------|---------|
| 1 | JUDUL + PENULIS + ABSTRAK + ABSTRACT | Ya (inti) | Halaman 1, semua dalam 1 halaman, jarak baris 1.0 |
| 2 | 1. Pendahuluan | Ya (inti) | |
| 3 | 2. Metode | Ya (inti) | |
| 4 | 3. Hasil dan Pembahasan | Ya (inti) | |
| 5 | 4. Kesimpulan | Ya (inti) | |
| 6 | 5. Ucapan Terima Kasih | Ya (inti) | |
| 7 | 6. Kontribusi Penulis | Ya (inti) | |
| 8 | 7. Daftar Pustaka | Ya (inti) | Min 10 rujukan, ≤5 tahun, Harvard strict |
| 9 | LAMPIRAN | Ya | Biodata, Kontribusi, Surat Pernyataan, Sumber Tulisan, Uji Similaritas (maks 25%) |

**Aturan Halaman Inti V0.3:** **Minimal 8 dan maksimal 15 lembar fisik** (Judul s.d. Daftar Pustaka).

**Format Khusus PKM-AI:**
- Halaman judul: TNR 12pt (judul, kapital, tebal); TNR 10pt (nama penulis & alamat institusi); TNR 11pt (abstrak/abstract & kata kunci); spasi 1.0.
- Penomoran halaman: angka arab pojok kanan atas dimulai dari halaman judul, **TNR 12pt**.
- Keterangan tabel/gambar: TNR 11pt, satu spasi.

**Red Flags:** halaman sampul, halaman pengesahan, daftar isi, TTD crop, "et al."/"dkk." di Daftar Pustaka.

**Catatan:** PKM-AI hanya punya satu jenis laporan: **Artikel Ilmiah**. Modul Budget Auditor di-skip.

### 8.5 PKM-GFT — Aturan Struktur Gagasan Futuristik Tertulis
PKM-GFT = PKM Insentif. **Tidak ada halaman sampul dan halaman pengesahan.**

| No | Section | Wajib | Catatan |
|----|---------|-------|---------|
| 1 | DAFTAR ISI | Ya | Romawi kecil pojok kanan bawah |
| 2 | BAB 1. PENDAHULUAN | Ya (inti) | |
| 3 | BAB 2. GAGASAN | Ya (inti) | |
| 4 | BAB 3. KESIMPULAN | Ya (inti) | |
| 5 | DAFTAR PUSTAKA | Ya (inti) | Harvard strict |
| 6 | LAMPIRAN | Ya | Biodata, Kontribusi, Surat Pernyataan, Uji Similaritas (maks 25%) |

**Aturan Halaman Inti V0.3:** **Minimal 8 dan maksimal 15 lembar fisik** (BAB 1 s.d. Daftar Pustaka).

**Format Khusus:**
- Penomoran zona awal: romawi kecil pojok kanan bawah, TNR 12pt.
- Penomoran zona inti & lampiran: angka arab pojok kanan atas, TNR 12pt, dimulai dari BAB 1.
- Judul: maks 20 kata, kapital, hindari singkatan.

**Red Flags:** halaman sampul, halaman pengesahan, ringkasan/abstrak, TTD crop, "et al."/"dkk."

**Catatan:** PKM-GFT hanya punya satu jenis laporan: **Proposal Gagasan**. Modul Budget Auditor di-skip.

### 8.6 PKM-K — Aturan Struktur Kewirausahaan
PKM-K = PKM Pendanaan. Struktur Proposal/Lapkem/Lapakhir mengikuti V0.2 (lihat §8.7 V0.2).

**Aturan Halaman Inti V0.3:** Maksimal **10 lembar fisik**, tanpa batas minimum.

**Aturan Anggaran:** Identik dengan PKM-KC (Belmawa Rp6–8 juta, PT Rp500–Rp2 juta, Eksternal maks Rp1 juta; kategori BHP 60%, Sewa 15%, Transport 30%, Lain-lain 15%).

**Tambahan PKM-K:** Wajib publikasi/promosi di media sosial dengan jadwal ads tertentu (lihat `social_media_requirements` di V0.2 §8.7).

### 8.7 Ringkasan Perbandingan Antar-Skema (V0.3)

| Aspek | PKM-KC | PKM-AI | PKM-GFT | PKM-K |
|-------|--------|--------|---------|-------|
| **Tipe** | Pendanaan | Insentif | Insentif | Pendanaan |
| **Jenis Laporan** | Proposal, Lapkem, Lapakhir | Artikel Ilmiah | Proposal Gagasan | Proposal, Lapkem, Lapakhir |
| **Lembar Fisik Inti** | Maks 10 | **8–15** | **8–15** | Maks 10 |
| **Zona Awal** | Romawi kecil, kanan bawah, TNR 12 | — | Romawi kecil, kanan bawah, TNR 12 | Romawi kecil, kanan bawah, TNR 12 |
| **Zona Inti** | Arab, kanan atas, TNR 12 | Arab, kanan atas, TNR 12 | Arab, kanan atas, TNR 12 | Arab, kanan atas, TNR 12 |
| **Dana Belmawa** | Rp6–8jt | Insentif Rp1,5jt | — | Rp6–8jt |
| **Dana PT (wajib)** | **Rp500–Rp2jt** | — | — | **Rp500–Rp2jt** |
| **Dana Eksternal** | Maks Rp1jt | — | — | Maks Rp1jt |
| **Cross-check Bab4 ↔ Lamp2** | Ya | — | — | Ya |
| **Advisory item >Rp1jt** | Ya | — | — | Ya |
| **Harvard Strict (no et al./dkk.)** | Ya | Ya | Ya | Ya |
| **Balance Check Sitasi** | Ya | Ya | Ya | Ya |
| **Advisory ≥8 ref mutakhir** | Ya | Ya | Ya | Ya |
| **Uji Similaritas** | Maks 25% | Maks 25% | Maks 25% | Maks 25% |
| **Media Sosial Wajib** | Tidak | Tidak | Tidak | Ya |


---

## 9. INFRASTRUKTUR & SKALABILITAS (BARU/DIPERKUAT V0.3)

### 9.1 Kapasitas Pemrosesan
| Parameter | Spesifikasi |
|-----------|-------------|
| Kapasitas paralel | **40 analisa simultan** |
| Estimasi durasi per analisa | **~2 menit** (target rata-rata) |
| Throughput teoritis | ~20 job/menit; ~1.200 job/jam pada beban penuh |
| Backend antrean | Celery + Redis |
| Worker scaling | Horizontal (tambah worker container saat load tinggi) |

### 9.2 Manajemen Antrean
- Setiap submission masuk antrean Celery dengan prioritas FIFO.
- API `/api/queue/status` mengembalikan jumlah `active_jobs`, `queued_jobs`, dan estimasi ETA.
- Jika `active_jobs >= 40`, endpoint `/api/check` mengembalikan **HTTP 503 + payload `queue_full`**.
- Frontend menangkap response ini dan menampilkan **pop-up notifikasi**: *"Antrean penuh, silakan coba lagi nanti."* + tombol "Coba Lagi" yang disabled selama countdown `retry_after_seconds`.

### 9.3 Penyimpanan File (Cloud Storage Pihak Ketiga)
- File `.docx` user, hasil konversi PDF, dan gambar yang di-extract **TIDAK** disimpan di server FastAPI.
- Disimpan di **Cloud Storage** (Cloudflare R2 / AWS S3 / Google Cloud Storage).
- Backend hanya menyimpan referensi (`storage_provider`, `storage_bucket`, `storage_key`) di tabel `check_submissions`.
- Akses file via **signed URL** (TTL 15 menit, regenerate jika expired).
- Setelah job selesai dan hasil di-render, file mentah bisa di-archive ke storage class yang lebih murah (mis. R2 Infrequent Access) atau dihapus sesuai kebijakan retensi (mis. 30 hari).

**Manfaat arsitektural:**
- Server backend tetap ramping; storage server tidak membengkak.
- Memudahkan scaling horizontal worker (file diakses semua worker dari satu sumber).
- Resiliensi: file tidak hilang jika container backend di-redeploy.

### 9.4 Monitoring
- Logging structured (JSON) untuk setiap job: `submission_id`, `start_time`, `end_time`, `duration`, `modules_status`, `error`.
- Metrik antrean disimpan di `queue_metrics` (tiap 1 menit).
- Dashboard admin `/admin/queue` menampilkan grafik real-time + alert saat `rejected_count_last_hour > 10`.

---

## 10. FOLDER STRUCTURE

```
pkm-checker/
├── frontend/                              # Next.js
│   ├── src/
│   │   ├── app/
│   │   │   ├── page.tsx
│   │   │   ├── login/
│   │   │   ├── dashboard/
│   │   │   ├── check/
│   │   │   │   ├── new/                   # 3-step selector
│   │   │   │   └── [id]/
│   │   │   ├── calculator/
│   │   │   └── admin/
│   │   │       └── queue/                 # NEW: monitoring antrean
│   │   ├── components/
│   │   │   ├── ui/
│   │   │   ├── CompetitionSelector.tsx    # NEW
│   │   │   ├── ReportTypeSelector.tsx     # NEW
│   │   │   ├── SchemaSelector.tsx         # NEW
│   │   │   ├── QueueFullModal.tsx         # NEW
│   │   │   ├── CheckResultCard.tsx
│   │   │   ├── PageNumberingChart.tsx     # NEW
│   │   │   ├── BudgetCrossCheckTable.tsx  # NEW
│   │   │   ├── ReferenceBalanceTable.tsx  # NEW
│   │   │   └── FileUploader.tsx
│   │   ├── lib/
│   │   │   ├── supabase.ts
│   │   │   └── api.ts
│   │   └── types/
│   ├── tailwind.config.ts
│   └── package.json
│
├── backend/                               # FastAPI
│   ├── app/
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── routers/
│   │   │   ├── auth.py
│   │   │   ├── competitions.py            # NEW
│   │   │   ├── schemas.py
│   │   │   ├── check.py
│   │   │   ├── queue.py                   # NEW
│   │   │   ├── calculator.py
│   │   │   └── admin.py
│   │   ├── services/
│   │   │   ├── docx_parser.py
│   │   │   ├── pdf_converter.py           # NEW: LibreOffice headless
│   │   │   ├── structure_checker.py
│   │   │   ├── physical_sheet_counter.py  # RENAMED: dari page_counter.py
│   │   │   ├── format_checker.py
│   │   │   ├── page_numbering_checker.py  # NEW: validasi zona romawi/arab + posisi
│   │   │   ├── budget_auditor.py          # diperbarui: cross-check & advisory
│   │   │   ├── reference_validator.py     # diperbarui: strict + balance + recency
│   │   │   ├── biodata_ocr_pddikti.py     # RENAMED & EXPANDED
│   │   │   └── cloud_storage.py           # NEW: abstraksi R2/S3/GCS
│   │   ├── workers/
│   │   │   ├── celery_app.py              # NEW
│   │   │   └── tasks.py                   # NEW: task definitions
│   │   ├── models/
│   │   │   ├── schemas.py
│   │   │   └── database.py
│   │   └── utils/
│   │       ├── ocr.py
│   │       ├── pddikti_client.py          # NEW
│   │       ├── foreign_words.py
│   │       └── harvard_patterns.py
│   ├── tests/
│   │   ├── test_structure.py
│   │   ├── test_physical_sheets.py        # NEW
│   │   ├── test_page_numbering.py         # NEW
│   │   ├── test_budget_crosscheck.py      # NEW
│   │   ├── test_reference_strict.py       # NEW
│   │   ├── test_biodata_pddikti.py        # NEW
│   │   └── sample_docs/
│   ├── requirements.txt
│   └── Dockerfile
│
├── docs/
│   ├── blueprint.md                        # Dokumen ini (V0.3)
│   └── panduan/
│       ├── PKM-KC-2026.pdf
│       ├── PKM-AI-2026.pdf
│       ├── PKM-GFT-2026.pdf
│       ├── PKM-K-2026.pdf
│       └── ...
│
├── docker-compose.yml                      # FastAPI + Redis + Celery worker
└── README.md
```

---

## 11. PRIORITAS PENGEMBANGAN (Roadmap V0.3)

### Phase 1 — MVP (4–6 minggu)
- [ ] Setup project (Next.js + FastAPI + Supabase + Redis + Cloud Storage)
- [ ] Schema database baru: `competitions`, `report_types`, `competition_schemas`
- [ ] Implementasi PKM-KC sebagai skema pertama
- [ ] **Frontend 3-step selector (Lomba → Laporan → Skema)**
- [ ] Module: Structure Checker
- [ ] Module: **Physical Sheet Counter** (PDF-based)
- [ ] Module: **Format & Page-Numbering Checker** (validasi zona romawi/arab)
- [ ] Module: Budget Calculator standalone (validasi Dana PT min Rp500)
- [ ] Setup Celery + Redis, queue dasar
- [ ] Cloud Storage integration (R2 atau S3)
- [ ] Auth (Supabase Auth)

### Phase 2 — Full Features (4–6 minggu)
- [ ] Module: **Budget Auditor** (extract tabel + integritas kolom + cross-check Bab 4 ↔ Lamp 2 + advisory relokasi)
- [ ] Module: **Reference Validator strict Harvard** (no et al./dkk. + balance check + recency advisory)
- [ ] Module: **OCR Biodata + PD Dikti Verifier** (Nama, NIM/NIDN, Tahun 2027, deteksi TTD crop, saran KTP)
- [ ] Pop-up "Antrean Penuh" + endpoint `/api/queue/status`
- [ ] Tambah skema PKM-AI, PKM-GFT, PKM-K
- [ ] Download laporan hasil (PDF)

### Phase 3 — Scaling (4–6 minggu)
- [ ] Tambah 6 skema PKM tersisa (RE, RSH, PM, PI, KI, VGK)
- [ ] Tambah konfigurasi P2MW, PPK Ormawa, BIMA
- [ ] Dashboard admin + monitoring antrean (`/admin/queue`)
- [ ] Stress test 40 job paralel (target ~2 menit/job)
- [ ] Performance optimization (PDF conversion caching, OCR batch)

---

## 12. RISIKO & MITIGASI (Direvisi V0.3)

| Risiko | Dampak | Mitigasi |
|--------|--------|----------|
| Pagination .docx tidak akurat | Hitungan halaman salah | Konversi ke PDF via LibreOffice headless, hitung lembar fisik dengan pypdf |
| Penomoran halaman tidak terdeteksi posisinya | Validasi zona gagal | Parse OOXML `headerN.xml`/`footerN.xml`, cek alignment + position |
| Tabel RAB format tidak standar | Budget auditor gagal parse | Multiple pattern matcher, fallback ke manual input, deteksi kolom kategori hilang |
| Cross-check Bab 4 ↔ Lamp 2 sering tidak match | Banyak false-fail | Toleransi Rp0 dengan pesan jelas; user diminta sinkronkan revisi |
| OCR tanggal/TTD gagal (gambar blur) | False negative | Confidence score, minta user verifikasi manual |
| Regex Harvard terlalu strict/loose | False positive/negative | Iterasi pattern berdasarkan sampel real, test suite per tipe sumber |
| API PD Dikti rate-limited | Validasi nama/NIM gagal | Caching hasil lookup di Redis (TTL 24 jam) |
| Variasi penulisan heading | Structure checker miss | Fuzzy matching + normalisasi |
| Antrean penuh saat puncak | Job ditolak | Pop-up notifikasi + UI ETA; horizontal scaling worker |
| Cloud Storage outage | File tidak terbaca | Multi-region replication; fallback retry; monitoring |
| Deteksi TTD crop false-positive | TTD asli dianggap crop | Threshold `crop_suspicion_score`, izinkan reviewer override manual |

---

## 13. CATATAN UNTUK ITERASI SELANJUTNYA

1. **Skema PKM yang masih perlu dilengkapi** — 6 skema:
   - PKM-RE (Riset Eksakta)
   - PKM-RSH (Riset Sosial Humaniora)
   - PKM-PM (Pengabdian kepada Masyarakat)
   - PKM-PI (Penerapan Iptek)
   - PKM-KI (Karya Inovatif)
   - PKM-VGK (Video Gagasan Konstruktif)

2. **Kompetisi non-PKM yang perlu dikonfigurasi:**
   - **P2MW** — Program Pembinaan Mahasiswa Wirausaha (struktur, jenis laporan, aturan dana)
   - **PPK Ormawa** — Penguatan Kapasitas Ormawa (struktur, jenis laporan)
   - **BIMA** — sistem Kemdikbud (banyak sub-skema penelitian/pengabdian dosen)

3. **Catatan implementasi V0.3:**
   - **Physical Sheet Counter** wajib pakai konversi PDF — `python-docx` saja tidak akurat untuk pagination.
   - **Page-Numbering Zone Checker** butuh parsing OOXML manual (header/footer XML) karena `python-docx` belum expose page number XML utuh.
   - **Cross-check Bab 4 ↔ Lampiran 2** sensitif terhadap format tabel — siapkan multiple parsers (tabel berhalaman, tabel dengan merge cell, dll).
   - **PD Dikti integration** masih perlu klarifikasi sumber: API resmi vs scraping vs dataset internal kemahasiswaan.

4. **Data yang perlu dikumpulkan:**
   - Sampel .docx laporan real (per skema, minimal 5 sampel) untuk testing.
   - Snapshot dataset PD Dikti per universitas (atau MoU akses API).
   - Daftar kata asing umum dalam konteks PKM.
   - Deadline pengumpulan per tahap (untuk validasi tanggal).

5. **Keputusan yang belum final:**
   - Provider Cloud Storage utama (R2 vs S3 vs GCS — tergantung biaya & latensi).
   - Strategi retensi file (30 hari? 90 hari? policy per role?).
   - Apakah laporan hasil di-render PDF atau .docx dengan tracked changes?
   - Apakah PD Dikti lookup dilakukan real-time per submission, atau batch sync harian?
