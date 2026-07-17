# Panduan Tambah Skema PKM Baru

> Disusun setelah penambahan **PKM-RE** & **PKM-RSH** (sesi 2026-05-28).
> Pakai dokumen ini sebagai cheat sheet untuk menambahkan PKM-K / PKM-PM / PKM-PI / PKM-KI / PKM-GFT atau skema lain di sesi mendatang.

---

## 1. Inventarisasi: Apa yang membedakan satu skema dari lainnya?

Sebelum coding, kumpulkan dulu fakta-fakta ini dari panduan PKM resmi:

| Aspek | Yang perlu kamu kumpulkan |
|---|---|
| **Struktur dokumen** | Nama BAB lengkap (mis. "BAB 3. METODE PENELITIAN"), jumlah BAB, aliases (romawi/arab/variasi titik), section opsional/terlarang |
| **Daftar luaran wajib** | List 4 luaran (`(label, regex)`). Kata kunci unik yang membedakan dari KC/VGK/RE |
| **Daftar lampiran wajib** | List `(nomor, [kata_kunci], "Label Tampil")`. Kalau identik dengan KC/RE → tinggal `_REQUIRED_LAMPIRAN_KC` saja, beda factory |
| **Budget rules** | Apakah identik dengan KC? Kalau ya, cukup clone dengan `schema_code` baru |
| **Schedule rules** | Hampir selalu identik (4 bulan, kolom No/Jadwal/Bulan/Penanggung Jawab) |
| **Similarity rules** | Hampir selalu maks 25% |
| **Sheet count rules** | Berapa min/max halaman inti? Cek schema_rules / panduan |

**Tip**: kalau sebagian besar identik dengan PKM-KC, ikuti pola "delegate ke helper KC dengan label berbeda" yang dipakai RE/RSH.

---

## 2. Daftar file yang perlu disentuh

Selalu sentuh ~6 file backend ini (urut dari paling fundamental ke yang paling tinggi):

```
backend/app/services/
├── schema_rules.py           # struktur section dokumen
├── budget_rules.py            # aturan anggaran (Belmawa/PT/Instansi)
├── schedule_rules.py          # aturan tabel jadwal
├── similarity_rules.py        # maks % similaritas
├── luaran_checker.py          # daftar luaran wajib + factory
├── lampiran_checker.py        # daftar lampiran wajib + factory
├── biodata_date_checker.py    # cuma tambah factory (label)
├── schedule_checker.py        # cuma tambah factory
├── similarity_checker.py      # cuma tambah factory
└── orchestrator.py            # routing + runner
```

Frontend **biasanya tidak perlu disentuh** — `frontend/src/features/check/form/checkFormConstants.ts` sudah pre-listed PKM-K, PKM-RE, PKM-RSH, PKM-PM, PKM-PI, PKM-KI, PKM-VGK, PKM-GFT, PKM-AI. Cek file ini dulu — kalau skema sudah ada di `SKEMA_OPTIONS`, frontend siap.

---

## 3. Template per file

Contoh di bawah pakai placeholder **`PKM-XX`** / **`xx`** / **`Nama Skema`**. Ganti sesuai skema baru. Lowercase `xx` dipakai di nama factory (`for_pkm_xx`).

### 3.1 `schema_rules.py` — struktur section

Kalau strukturnya BENAR-BENAR identik dengan skema yang sudah ada (mis. RE/RSH share `_build_pkm_riset_sections()`), bisa re-use helper. Kalau beda, bikin function baru:

```python
def get_pkm_xx_proposal_rules() -> SchemaRules:
    """Aturan PKM-XX (Nama Skema) Proposal 2026."""
    return SchemaRules(
        competition_code="PKM",
        schema_code="XX",
        report_type_code="PROPOSAL",
        schema_name="Nama Skema",
        year=2026,
        sections=[
            SectionRule(name="DAFTAR ISI", required=True, order=1),
            SectionRule(name="DAFTAR LAMPIRAN",
                        aliases=["DAFTAR LAMPIRAN-LAMPIRAN"],
                        required=True, order=4),
            SectionRule(name="BAB 1. PENDAHULUAN",
                        aliases=["BAB I. PENDAHULUAN", "BAB 1 PENDAHULUAN",
                                 "BAB I PENDAHULUAN"],
                        required=True, is_core=True, order=5),
            # ... BAB 2-N ...
            SectionRule(name="DAFTAR PUSTAKA",
                        required=True, is_core=True, order=N+1),
            SectionRule(name="LAMPIRAN",
                        aliases=["LAMPIRAN 1", "LAMPIRAN 1.", "LAMPIRAN-LAMPIRAN"],
                        required=True, order=N+2),
            # Opsional
            SectionRule(name="DAFTAR GAMBAR", required=False, order=2),
            SectionRule(name="DAFTAR TABEL",  required=False, order=3),
            # Terlarang
            SectionRule(name="HALAMAN SAMPUL",
                        aliases=["COVER", "SAMPUL", "PROPOSAL PKM",
                                 "PROPOSAL PKM-XX",
                                 "PROPOSAL PROGRAM KREATIVITAS MAHASISWA"],
                        forbidden=True),
            SectionRule(name="HALAMAN PENGESAHAN",
                        aliases=["LEMBAR PENGESAHAN", "PENGESAHAN PROPOSAL",
                                 "PENGESAHAN PKM", "PENGESAHAN USULAN"],
                        forbidden=True),
            SectionRule(name="RINGKASAN",
                        aliases=["ABSTRAK", "ABSTRACT"], forbidden=True),
        ],
    )
```

**Catatan penting**:
- `order` HARUS mencerminkan urutan logis (Daftar Isi → BAB → Daftar Pustaka → Lampiran). Section opsional bisa di antara wajib.
- `aliases` — tambahkan SEMUA variasi yang mungkin (romawi `BAB I`, arab `BAB 1`, dengan/tanpa titik). Periksa beberapa proposal nyata sebelum finalisasi.
- Section `HALAMAN SAMPUL`, `HALAMAN PENGESAHAN`, `RINGKASAN` selalu **forbidden** untuk Proposal PKM (panduan 2026).

### 3.2 `budget_rules.py` — clone KC

Hampir selalu identik dengan KC (Belmawa min 80%, Instansi maks ~15%, dst.):

```python
def get_pkm_xx_budget_rules() -> BudgetRules:
    """Aturan anggaran PKM-XX 2026 — identik dengan PKM-KC."""
    rules = get_pkm_kc_budget_rules()
    rules.schema_code = "XX"
    return rules
```

### 3.3 `schedule_rules.py` & `similarity_rules.py` — clone KC

Pola sama: clone + ganti `schema_label`.

```python
def get_pkm_xx_schedule_rules() -> ScheduleTableRules:
    rules = get_pkm_kc_schedule_rules()
    rules.schema_label = "PKM-XX"
    return rules

def get_pkm_xx_similarity_rules() -> SimilarityRules:
    rules = get_pkm_kc_similarity_rules()
    rules.schema_label = "PKM-XX"
    return rules
```

### 3.4 `luaran_checker.py` — daftar luaran wajib

Setiap skema PKM punya 4 luaran wajib (Laporan Kemajuan + Laporan Akhir + dua spesifik). Bedanya hanya item ke-3 dan/atau ke-4:

| Skema | Luaran ke-3 | Luaran ke-4 |
|---|---|---|
| PKM-KC | Prototipe | Akun Media Sosial |
| PKM-VGK | Video YouTube | Akun Media Sosial |
| PKM-RE / RSH | Artikel Ilmiah | Akun Media Sosial |
| PKM-K | (TBD — cek panduan) | (TBD) |
| dst. | | |

Pola:

```python
_PKM_XX_REQUIRED: list[tuple[str, re.Pattern]] = [
    ("laporan kemajuan",  re.compile(r"laporan\s+kemajuan",    re.IGNORECASE)),
    ("laporan akhir",     re.compile(r"laporan\s+akhir",       re.IGNORECASE)),
    ("<luaran-3-label>",  re.compile(r"<regex-3>",             re.IGNORECASE)),
    ("akun media sosial", re.compile(r"akun\s+media\s+sosial", re.IGNORECASE)),
]

# Tambah factory di class LuaranChecker:
@classmethod
def for_pkm_xx(cls, parser: DocxParser) -> "LuaranChecker":
    return cls(parser, _PKM_XX_REQUIRED, "PKM-XX")
```

**Catatan regex**:
- Pakai `\s+` antar kata untuk toleran terhadap spasi ganda.
- `re.IGNORECASE` selalu.
- Substring biasanya OK (mis. `"similar"` match `"similaritas"`).

### 3.5 `lampiran_checker.py` — daftar lampiran wajib

Lampiran wajib BISA SAMA persis dengan KC (7 item: jadwal, biodata ketua/anggota, biodata dosen, justifikasi, susunan tim, surat pernyataan, uji similaritas) — kalau iya, langsung reuse list KC:

```python
# Tambah factory saja:
@classmethod
def for_pkm_xx(cls, parser: DocxParser) -> "LampiranChecker":
    return cls(parser, _REQUIRED_LAMPIRAN_KC, "PKM-XX")
```

Kalau beda struktur (mis. PKM-VGK gabung biodata jadi 1 lampiran), buat list baru:

```python
_REQUIRED_LAMPIRAN_XX: list[tuple[int, list[str], str]] = [
    (1, ["biodata", "ketua", "dosen"],
        "Biodata Ketua dan Anggota, serta Dosen Pendamping"),
    (2, ["justifikasi", "anggaran"],
        "Justifikasi Anggaran Kegiatan"),
    # dst.
]
```

**Kata kunci**: pilih 2-4 kata yang HARUS muncul di window 200 char setelah anchor "Lampiran N". Jangan kata umum seperti "kegiatan" sendirian — terlalu generic.

### 3.6 `biodata_date_checker.py`, `schedule_checker.py`, `similarity_checker.py` — factory tipis

3 file ini cuma butuh factory baru (label-only):

```python
# biodata_date_checker.py
@classmethod
def for_pkm_xx(cls, parser: DocxParser) -> "BiodataDateChecker":
    return cls(parser, "PKM-XX")

# schedule_checker.py (import rules baru dulu)
from app.services.schedule_rules import (
    ..., get_pkm_xx_schedule_rules,
)
@classmethod
def for_pkm_xx(cls, parser: DocxParser) -> "ScheduleChecker":
    return cls(parser, get_pkm_xx_schedule_rules())

# similarity_checker.py (import rules baru dulu)
from app.services.similarity_rules import (
    ..., get_pkm_xx_similarity_rules,
)
@classmethod
def for_pkm_xx(cls, parser: DocxParser) -> "SimilarityChecker":
    return cls(parser, get_pkm_xx_similarity_rules())
```

### 3.7 `orchestrator.py` — runner + routing

Tambah import schema & budget rules:

```python
from app.services.schema_rules import (
    ..., get_pkm_xx_proposal_rules,
)
from app.services.budget_rules import (
    ..., get_pkm_xx_budget_rules,
)
```

Tambah runner (1-liner) yang delegate ke shared helper:

```python
def _run_pkm_xx(parser: DocxParser) -> dict[str, Any]:
    """PKM-XX runner — pipeline sama dengan PKM-KC."""
    return _run_pkm_kc_like(
        parser,
        schema=get_pkm_xx_proposal_rules(),
        budget_rules=get_pkm_xx_budget_rules(),
        schema_suffix="xx",       # harus lowercase, match nama factory
        log_label="PKM-XX",
    )
```

> **Kunci**: `schema_suffix` dipakai `getattr(LuaranChecker, f"for_pkm_{s}")` di helper. **Suffix HARUS match nama factory** yang kamu bikin di 3.4–3.6. Salah ketik → AttributeError saat runtime.

Tambah routing di `run_all_checks()`:

```python
if key == ("PKM", "PROPOSAL", "PKM-KC"):
    return _run_pkm_kc(parser)
# ...
elif key == ("PKM", "PROPOSAL", "PKM-XX"):
    return _run_pkm_xx(parser)
# ...
```

Update juga pesan error `UnsupportedSchemaError` agar daftar skema yang tersedia menyebut PKM-XX.

---

## 4. Frontend (biasanya skip)

Cek `frontend/src/features/check/form/checkFormConstants.ts`:
- `SkemaCode` type — pastikan `'PKM-XX'` ada
- `SKEMA_LAPORAN_MAP` — petakan ke `THREE_REPORTS` (untuk Proposal/Progress/Final) atau report-code lain
- `SKEMA_OPTIONS` — entry dropdown dengan `{ value, label, desc }`

Kalau ketiga sudah ada → frontend siap. Kalau belum, tambah baris singkat di 3 tempat tsb.

---

## 5. Testing — 3 step pasca-implementasi

1. **Syntax check**:
   ```bash
   cd backend
   ./.venv/bin/python -m py_compile \
     app/services/orchestrator.py app/services/schema_rules.py \
     app/services/budget_rules.py app/services/luaran_checker.py \
     app/services/lampiran_checker.py app/services/biodata_date_checker.py \
     app/services/schedule_checker.py app/services/similarity_checker.py \
     app/services/similarity_rules.py app/services/schedule_rules.py
   ```

2. **Regression test suite**:
   ```bash
   ./.venv/bin/python -m pytest tests/ -q --ignore=tests/test_physical_sheet_counter.py
   ```
   (Skip `test_physical_sheet_counter` karena ada 1 test gagal pre-existing yang tidak terkait.)

3. **Smoke test routing** pakai dokumen contoh apa saja:
   ```python
   from app.services.orchestrator import CheckRequest, run_all_checks
   req = CheckRequest(
       docx_path='/path/to/contoh.docx',
       competition='PKM', report_type='PROPOSAL', schema_code='PKM-XX',
   )
   r = run_all_checks(req)
   print(f'overall={r["overall_status"]} modules={[k for k in r if not k.startswith("_") and k != "overall_status"]}')
   ```

   Pastikan: tidak crash, 11 modul muncul di hasil, `overall_status` salah satu dari pass/warning/fail/error.

---

## 6. Pitfalls & gotchas

### 6.1 Heading-style misuse di luaran
Banyak proposal yang style item luaran (`1) Laporan kemajuan`, dst) pakai **Heading 2** — sama dengan label "Luaran yang Diharapkan". Logika `_is_next_section()` di `luaran_checker.py` sudah dibuat **TIDAK** stop di `is_heading=True` saja — andalkan pola struktural (`_NEXT_HEADING_RE`: BAB X / X.Y / ALL CAPS). **Jangan ubah ini balik**.

### 6.2 Daftar Lampiran di TOC field (SDT)
Word generate Daftar Lampiran pakai field code TOC di dalam `<w:sdt>`. python-docx **tidak** enumerate isi SDT sebagai paragraph. Fungsi `_collect_daftar_lampiran_text()` di `lampiran_checker.py` punya fallback XML extraction. Pastikan saat ekstrak SDT, **pisahkan `<w:t>` dengan spasi** (bukan concat langsung) — kalau tidak, "Pendamping11Lampiran 2." membuat `\bLampiran` regex meleset karena tidak ada word boundary antara digit dan huruf.

### 6.3 Page mapping akurasi
Format checker akurasi tinggi karena pakai PDF text search (LibreOffice render). 3 hal kritikal di `_pdf_page_for_text()`:
- **`last_occurrence=True`** untuk hindari false-match dari entry TOC di halaman depan
- **Whitespace normalize** (collapse `\s+` → single space) di kedua sisi — LibreOffice render menghasilkan multi-space pada justified layout
- **Fallback graceful** ke `estimate_physical_page` (output `~N`) kalau LibreOffice tidak tersedia di server

### 6.4 OCR (Google Vision only)
Tidak ada lagi easyocr / pytesseract. Pastikan VPS punya:
- `GOOGLE_APPLICATION_CREDENTIALS` env → path service-account JSON
- `pip install google-cloud-vision`
- Project Google Cloud yang aktif (billing + Vision API enabled)

File JSON service-account **wajib** di `.gitignore` (pola `*service-account*.json`, `*-credentials*.json`, `ocr-checker-*.json`, hex-suffix pattern).

### 6.5 Similarity not detected → masuk Lampiran
Logika di `_move_similarity_undetected_to_lampiran()` (orchestrator): kalau SimilarityChecker tidak bisa baca % dari OCR, pesan dipindah ke section Lampiran sebagai `Tidak ditemukan "Uji similaritas" pada halaman lampiran`. Helper ini auto-running di runner KC-like — jadi RE/RSH dapat behavior ini gratis.

### 6.6 In-text citation `et al.` / `dkk.`
**DIPERBOLEHKAN di sitasi in-text** (Harvard standar). Dilarang **hanya di Daftar Pustaka**. Validasi DP via `_dp_has_et_al` / `_dp_has_dkk` di `reference_validator.py`. **Jangan** tambahkan "et al" balik ke `FOREIGN_WORDS` di `format_checker.py` — kontradiksi.

### 6.7 Layout tabel Vision (TTL)
Regex `_TTL_RE` di `biodata_date_checker.py` pakai `[\s\S]{0,300}?` (lazy, lintas newline) — gap longgar agar match ke layout tabel Vision yang taruh label kolom dulu (mengandung digit) baru value-nya. **Tidak boleh dipersempit** ke `[^\d]*` (yang lama) — akan miss tanggal lahir di output Vision dan tanggal lahir lolos ke validasi.

---

## 7. Polish lain dari sesi ini (referensi cepat)

Daftar improvement lain yang sudah masuk — kalau di sesi mendatang kamu lihat hal seperti ini, ini sudah ada:

| Area | Status |
|---|---|
| OCR | Full Google Vision, ada `.env` + fallback graceful |
| Lampiran kelengkapan | 3-stage (Daftar absent → body text + OCR fallback → cross-mismatch) |
| Luaran false-positive | Sudah aman vs heading-style items |
| Page numbering | PDF render via LibreOffice, accurate dengan `last_occurrence` + whitespace normalize |
| Foreign words dict | 526 entry (AI/ML/UI/medis/Latin/bisnis/dll) |
| Reference DP | `dkk.`/`et al.` strict di DP, allowed di in-text |
| Frontend mapping | `case 'lampiran'` & `case 'structure'` di `CheckResultsView.tsx` punya pesan custom |

---

## 8. Checklist final untuk skema baru

Centang saat sudah dikerjakan:

- [ ] Kumpulkan fakta panduan (§1)
- [ ] `schema_rules.py`: section rules (§3.1)
- [ ] `budget_rules.py`: clone KC (§3.2)
- [ ] `schedule_rules.py`: clone KC (§3.3)
- [ ] `similarity_rules.py`: clone KC (§3.3)
- [ ] `luaran_checker.py`: `_PKM_XX_REQUIRED` + factory (§3.4)
- [ ] `lampiran_checker.py`: factory (§3.5)
- [ ] `biodata_date_checker.py`: factory (§3.6)
- [ ] `schedule_checker.py`: import + factory (§3.6)
- [ ] `similarity_checker.py`: import + factory (§3.6)
- [ ] `orchestrator.py`: import schema/budget + runner 1-liner + routing + error message (§3.7)
- [ ] Frontend constants — cek dropdown (§4)
- [ ] Syntax check + pytest + smoke test (§5)

---

## 9. Contoh referensi (kerja nyata sesi ini)

Untuk lihat implementasi konkret PKM-RE & PKM-RSH, baca di file berikut (semua sudah committed):

- `backend/app/services/schema_rules.py` — `_build_pkm_riset_sections()`, `get_pkm_re_proposal_rules()`, `get_pkm_rsh_proposal_rules()`
- `backend/app/services/luaran_checker.py` — `_PKM_RISET_REQUIRED`, `for_pkm_re`/`for_pkm_rsh`
- `backend/app/services/lampiran_checker.py` — `for_pkm_re`/`for_pkm_rsh` (reuse `_REQUIRED_LAMPIRAN_KC`)
- `backend/app/services/orchestrator.py` — `_run_pkm_kc_like()` helper, `_run_pkm_re()`, `_run_pkm_rsh()`
- `backend/app/services/{schedule,similarity}_rules.py` — clone pattern

Selamat coding, dan jangan lupa test tiap step. 🚀
