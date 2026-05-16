# Migration Plan — Pemisahan Per-Skema (Opsi 2 + Restruktur Folder)

> Dokumen ini **mandiri**. Bisa dikerjakan oleh sesi/akun baru tanpa konteks
> percakapan sebelumnya. Baca dari atas ke bawah. Jalankan Fase 1 sampai
> hijau & di-commit, baru Fase 2.
>
> Root kode: `backend/`  ·  Test: `cd backend && python -m pytest -q`
> Semua import saat ini absolute: `from app.services.<modul> import ...`

---

## 0. Ringkasan keputusan (sudah disepakati)

| Hal | Keputusan |
|---|---|
| Pendekatan | **Opsi 2**: `ai_format_checker` jadi pemilik PENUH format teks PKM-AI (judul/penulis/abstrak/caption **+ body**). `format_checker` untuk PKM-AI **hanya** `paper_size` + `margin`. |
| Hapus | `_body_start_index()` & `_is_caption_to_skip()` & `_parse_caption_label` cross-import — tidak ada lagi `if schema_code == "AI"` di engine generik. |
| Folder | 3 lapis: `core/` (infra) · `checkers/` (generik) · `schemas/pkm_kc/`, `schemas/pkm_ai/`. |
| Urutan | **Bertahap**: Fase 1 (perilaku) → commit → Fase 2 (folder). |

---

## 1. Latar belakang (kenapa refactor ini)

Aplikasi memeriksa dokumen `.docx` lomba PKM. Ada 2 skema aktif:
**PKM-KC** (proposal, pakai RAB) dan **PKM-AI** (artikel ilmiah, tanpa RAB).

`format_checker.py` adalah engine format generik (default = aturan PKM
Proposal: TNR 12, spasi 1.15, margin 4/3/3/3, justify). `ai_format_checker.py`
memvalidasi zona khusus PKM-AI (judul/penulis/abstrak/caption) dengan aturan
berbeda per-zona.

**Masalah yang memicu refactor:** untuk dokumen PKM-AI, `format_checker` dan
`ai_format_checker` sama-sama men-scan paragraf yang sama → **kontradiksi**
(mis. abstrak benar 11pt menurut `ai_format_checker`, tapi `format_checker`
vonis "harus 12pt"; caption panjang lolos di satu modul, gagal di modul lain).
Solusi tambal sulam saat ini (`_body_start_index`, `_is_caption_to_skip`,
cross-import `_parse_caption_label`) menaruh logika "hindari tabrakan" **di
dalam** engine generik → campur tanggung jawab. Refactor ini memisahkan
kepemilikan zona secara tegas per skema.

---

## 2. Spesifikasi aturan format PKM-AI (sumber kebenaran tunggal)

Ini hasil final yang sudah disepakati. Setelah refactor, **semua** ini
divalidasi oleh `ai_format_checker` (kecuali paper_size & margin).

| Zona | Font | Alignment | Spasi | Severity |
|---|---|---|---|---|
| Judul | TNR 12, **bold** | center | 1.0 | fail |
| Nama penulis & institusi | TNR 10 | center | 1.0 | fail |
| Isi Abstrak (ID) | TNR 11 | justify | 1.0 | fail |
| Isi Abstract (EN) | TNR 11 | justify | 1.0 | fail |
| Caption "Gambar N."/"Tabel N." | TNR 11 | center | 1.0 | **warning** |
| **Body** (Pendahuluan → akhir) | **TNR 12** | **justify** | **1.15** | fail |
| Ukuran kertas | A4 (21×29.7 cm) | — | — | fail · *tetap di `format_checker`* |
| Margin | kiri 4, kanan/atas/bawah 3 cm | — | — | fail · *tetap di `format_checker`* |

Catatan PKM-KC (tidak berubah): seluruh dokumen TNR 12, 1.15, justify,
margin 4/3/3/3, A4 — divalidasi `format_checker` penuh seperti sekarang.

### Format pesan (sudah berlaku, jangan diubah)
Semua finding pakai helper `app.services.message_format.format_finding(halaman, kesalahan, perbaikan)`
→ `"Halaman X — kesalahan — Perbaiki: perbaikan"` (atau `"Halaman -"` bila
tak ada halaman spesifik). **Dilarang** ada string penunjuk `paragraf #N`,
`global #N`, `Section #N`, `halaman fisik ~N` di pesan apa pun.

---

## 3. Arsitektur saat ini (sebelum refactor)

### 3.1 Daftar modul `backend/app/services/`
```
core/infra      : docx_parser, pdf_converter, style_resolver, message_format
rules/dataclass : schema_rules (SectionRule, SchemaRules, factories),
                  budget_rules
generik         : structure_checker, physical_sheet_counter, format_checker,
                  page_numbering_checker, reference_validator
PKM-AI           : ai_content_checker, ai_format_checker
PKM-KC           : budget_auditor, budget_table_parser
glue            : orchestrator
```

### 3.2 Registry orchestrator (sudah pola per-skema, KECUALI format)
`SCHEMA_REGISTRY: dict[(competition, report_type, schema_code) -> SchemaConfig]`

`SchemaConfig` fields:
`schema_rules_factory`, `modules`, `budget_rules_factory`,
`page_numbering_rules_factory`.

Module runner `_run_format` (INI sumber masalah — tidak per-skema):
```python
def _run_format(parser, schema, cfg) -> dict:
    return FormatChecker(parser, schema=schema).check().to_dict()
```
`FormatChecker.__init__(parser, rules=None, schema=None)` → `rules` default
`get_pkm_format_rules()` = `FormatRules()` untuk SEMUA skema.

`FormatChecker.check()` menjalankan sub-check (lokasi: `format_checker.py`
sekitar baris 292–298):
```
paper_size, margin, font_body, line_spacing, alignment(jika require_justify),
foreign_words_italic
```

Modul aktif: `PKM_KC_MODULES = ALL_MODULES`;
`PKM_AI_MODULES = (structure, physical_sheet, format, page_numbering,
reference, ai_content, ai_format)`.

### 3.3 Patch yang AKAN DIHAPUS di `format_checker.py`
- `_PKM_AI_PENDAHULUAN_RE` (module-level regex)
- `self._body_start_cache` di `__init__`
- method `_body_start_index()`
- fungsi module-level `_is_caption_to_skip()`
- import `from app.services.ai_format_checker import _parse_caption_label`
- semua guard `if para.index < body_start: continue` &
  `if _is_caption_to_skip(...): continue` di `_check_font_body`,
  `_check_line_spacing`, `_check_alignment`, `_check_foreign_words_italic`
- helper `_is_figure_table_caption_paragraph` / `_CAPTION_HEAD_RE` /
  `_MAX_CAPTION_PARAGRAPH_CHARS`: **tetap dipakai** oleh `_check_alignment`
  versi generik (PKM-KC) untuk skip caption. JANGAN dihapus. Hanya hentikan
  pemakaian gabungan `_is_caption_to_skip`; kembalikan ke
  `_is_figure_table_caption_paragraph` murni.

### 3.4 `ai_format_checker.py` — alur `check()`
```
check(): paragraphs = parser.paragraphs
  landmarks = _locate_landmarks(paragraphs)   # dict, termasuk "pendahuluan"
  title_para = _find_title_paragraph(...)
  _validate_title(title_para, result)
  _validate_title_page_spacing(paragraphs, title_para, landmarks, result)
  _validate_author_block(paragraphs, title_para, landmarks, result)
  _validate_abstract_block(... heading=landmarks["abstrak"] ...)   # ID
  _validate_abstract_block(... heading=landmarks["abstract"] ...)  # EN
  _validate_captions(paragraphs, result)
  _finalize(result)         # bangun messages via format_finding, set status
```
Konstanta sudah ada: `FONT_NAME="Times New Roman"`, `TITLE_FONT_SIZE=12.0`,
`AUTHOR_FONT_SIZE=10.0`, `ABSTRACT_FONT_SIZE=11.0`, `CAPTION_FONT_SIZE=11.0`,
`TITLE_PAGE_LINE_SPACING=1.0`, `ABSTRACT_LINE_SPACING=1.0`,
`TITLE_ALIGN/AUTHOR_ALIGN="center"`, `ABSTRACT_ALIGN="justify"`,
`CAPTION_ALIGN="center"`. `SIZE_TOL=0.5`, `SPACING_TOL=0.1`.
Helper: `_aggregate_font(p)`, `_size_matches`, `_spacing_matches`,
`_is_blank`, `_parse_caption_label`. `StyleResolver` tersedia via
`self.resolver`; alignment efektif: `self.resolver.resolve_paragraph_alignment(idx)`
(sudah style-chain aware, return 'left'/'center'/'right'/'justify' atau None).

---

## 4. FASE 1 — Perubahan perilaku (Opsi 2). TANPA pindah folder.

Tujuan: PKM-AI tidak lagi double-check; `ai_format_checker` validasi body;
`format_checker` PKM-AI cuma paper+margin. Engine generik bebas dari
`if schema_code=="AI"`.

### Langkah 1.1 — Tambah konstanta body PKM-AI di `ai_format_checker.py`
Dekat blok konstanta lain:
```python
BODY_FONT_SIZE = 12.0
BODY_ALIGN = "justify"
BODY_LINE_SPACING = 1.15
```

### Langkah 1.2 — Tambah `_validate_body_block()` di `ai_format_checker.py`
Body = paragraf dari `landmarks["pendahuluan"]` (inklusif heading berikutnya,
gunakan paragraf SETELAH heading) sampai akhir dokumen, **kecuali**:
- paragraf kosong (`_is_blank`)
- heading (lihat `ParagraphInfo.is_heading`)
- caption (`_parse_caption_label(p.text) is not None`) — sudah ditangani
  `_validate_captions`
Cek per-paragraf (pola "mayoritas" seperti `_validate_abstract_block`):
- font size ≠ 12 → finding `fail` aspect `font_size`
- alignment (`resolver.resolve_paragraph_alignment`) ≠ "justify" →
  finding `fail` aspect `alignment`
- line_spacing ada & ≠ 1.15 (pakai toleransi; tamb. helper bila perlu,
  mis. `abs(ls-1.15) <= 0.05`) → finding `fail` aspect `line_spacing`
Pesan tetap "kesalahan only" (lihat pola: `message=f"Body ... pakai ukuran {s}pt"`),
`expected=` diisi nilai target (dipakai jadi "Perbaiki:" di `_finalize`).
Panggil `self._validate_body_block(paragraphs, landmarks, result)` di `check()`
**sebelum** `_finalize(result)`.

> Cek juga apakah PKM-AI butuh cek "kata asing wajib italic" di body. Bila ya,
> port logika `_check_foreign_words_italic` (lihat `format_checker.py` +
> konstanta `FOREIGN_WORDS`) ke sebuah `_validate_foreign_italic_body()`
> di `ai_format_checker`. Bila tidak diminta, lewati (catat sebagai
> keputusan terbuka §7).

### Langkah 1.3 — `format_checker.py`: bersihkan patch PKM-AI
- Hapus import `_parse_caption_label`.
- Hapus `_PKM_AI_PENDAHULUAN_RE`, `_is_caption_to_skip`, `_body_start_index`,
  `self._body_start_cache`.
- Di `_check_font_body`, `_check_line_spacing`, `_check_alignment`,
  `_check_foreign_words_italic`: buang `body_start`/`_is_caption_to_skip`
  guards. `_check_alignment` kembali skip caption pakai
  `_is_figure_table_caption_paragraph(text)` (versi generik, tetap ada).
- Tambah parameter pemilih sub-check:
  `def __init__(self, parser, rules=None, schema=None, enabled_checks: Optional[set[str]] = None)`
  simpan `self.enabled_checks = enabled_checks`. Di `check()`, bungkus tiap
  `result.checks[name] = ...` dengan `if self._enabled(name)` di mana
  `_enabled(n) = self.enabled_checks is None or n in self.enabled_checks`.
  (Default `None` = semua → PKM-KC tak berubah.)

### Langkah 1.4 — Registry-driven format scope di `orchestrator.py`
Tambah field di `SchemaConfig`:
```python
format_rules_factory: Optional[Callable[[], FormatRules]] = None
format_checks: Optional[tuple[str, ...]] = None   # None = semua sub-check
```
Import `FormatRules` dari `app.services.format_checker`.
Ubah `_run_format`:
```python
def _run_format(parser, schema, cfg) -> dict:
    rules = cfg.format_rules_factory() if cfg.format_rules_factory else None
    checks = set(cfg.format_checks) if cfg.format_checks else None
    return FormatChecker(parser, rules=rules, schema=schema,
                         enabled_checks=checks).check().to_dict()
```
Di `SCHEMA_REGISTRY`:
- PKM-KC: biarkan (`format_rules_factory=None`, `format_checks=None`).
- PKM-AI: `format_checks=("paper_size", "margin")`. (Body/font/spasi/
  alignment/foreign PKM-AI sekarang dari `ai_format_checker`.)

### Langkah 1.5 — Pesan "pass" `ai_format_checker._finalize`
Perbarui teks pass agar menyebut body juga, mis.:
"... judul TNR 12 bold center, penulis TNR 10 center, abstrak/abstract
TNR 11 justify (semua 1,0 spasi), body TNR 12 justify 1,15, caption TNR 11
rata tengah."

### Langkah 1.6 — Test Fase 1
- Update `tests/test_format_checker.py`: hapus/aktifkan-skip kelas
  `TestBodyStartIndex` & `TestIsCaptionToSkip` (fungsi yang ditest sudah
  dihapus → ganti dengan test `enabled_checks` membatasi sub-check;
  dan test PKM-KC tetap jalan penuh).
- Tambah test baru `tests/test_ai_format_checker.py` (bila belum ada):
  body 11pt → fail; body 12pt justify 1.15 → tidak ada finding body;
  caption tetap warning; tidak ada string `paragraf #`/`Section #`.
- Jalankan: `cd backend && python -m pytest -q` → **harus semua hijau**.
- **Commit Fase 1** sebelum lanjut (mis. branch `refactor/per-schema-phase1`).

### Acceptance Fase 1
- Dokumen PKM-AI body 11pt: muncul finding dari section AI-format, **tidak**
  ada lagi finding "font_body harus 12pt" dari section format generik.
- Dokumen PKM-AI: section `format` hanya berisi paper_size + margin.
- Dokumen PKM-KC: hasil identik dengan sebelum refactor (regresi nol).

---

## 5. FASE 2 — Restruktur folder (`core/ checkers/ schemas/`)

Hanya pindah file + perbaiki import. **Tanpa** perubahan logika. Lakukan
setelah Fase 1 hijau & ter-commit.

### 5.1 Target struktur
```
backend/app/services/
  __init__.py
  orchestrator.py
  core/
    __init__.py
    docx_parser.py
    pdf_converter.py
    style_resolver.py
    message_format.py
    base_rules.py          # eks-schema_rules.py: SectionRule, SchemaRules,
                            #   FormatRules (pindahkan dataclass FormatRules
                            #   dari format_checker.py ke sini)
  checkers/
    __init__.py
    structure_checker.py
    physical_sheet_counter.py
    format_checker.py        # tetap engine generik (paper/margin/font/...)
    page_numbering_checker.py
    reference_validator.py
  schemas/
    __init__.py
    pkm_kc/
      __init__.py
      rules.py               # get_pkm_kc_proposal_rules,
                              #   get_pkm_kc_budget_rules, page-num KC factory
      budget_auditor.py
      budget_rules.py
      budget_table_parser.py
    pkm_ai/
      __init__.py
      rules.py               # get_pkm_ai_article_rules,
                              #   get_pkm_ai_page_numbering_rules,
                              #   get_pkm_ai_format_rules (jika dibuat)
      ai_content_checker.py
      ai_format_checker.py
```

### 5.2 Tabel pemindahan (path lama → baru)
| Lama `app/services/` | Baru |
|---|---|
| docx_parser.py | core/docx_parser.py |
| pdf_converter.py | core/pdf_converter.py |
| style_resolver.py | core/style_resolver.py |
| message_format.py | core/message_format.py |
| schema_rules.py | core/base_rules.py (dataclass+SectionRule) **+** factory KC/AI dipecah ke schemas/*/rules.py |
| (FormatRules di format_checker.py) | core/base_rules.py |
| structure_checker.py | checkers/structure_checker.py |
| physical_sheet_counter.py | checkers/physical_sheet_counter.py |
| format_checker.py | checkers/format_checker.py |
| page_numbering_checker.py | checkers/page_numbering_checker.py |
| reference_validator.py | checkers/reference_validator.py |
| budget_rules.py | schemas/pkm_kc/budget_rules.py |
| budget_auditor.py | schemas/pkm_kc/budget_auditor.py |
| budget_table_parser.py | schemas/pkm_kc/budget_table_parser.py |
| ai_content_checker.py | schemas/pkm_ai/ai_content_checker.py |
| ai_format_checker.py | schemas/pkm_ai/ai_format_checker.py |
| orchestrator.py | tetap di app/services/orchestrator.py |

> `schema_rules.py` dipecah: dataclass `SectionRule`, `SchemaRules` →
> `core/base_rules.py`. `get_pkm_kc_proposal_rules` →
> `schemas/pkm_kc/rules.py`. `get_pkm_ai_article_rules` →
> `schemas/pkm_ai/rules.py`. Page-numbering & budget rules factory ikut
> ke folder skema masing-masing. `FormatRules` + `get_pkm_format_rules`
> pindah dari `format_checker.py` ke `core/base_rules.py` (checker import
> dari sana).

### 5.3 Prosedur eksekusi (disarankan `git mv` agar history terjaga)
1. Buat folder + `__init__.py` kosong tiap paket baru.
2. `git mv` tiap file sesuai tabel.
3. Pecah `schema_rules.py` & `FormatRules` sesuai §5.2 (manual edit).
4. Update SEMUA import. Peta penggantian (regex, hati-hati urutan —
   yang spesifik dulu):
   ```
   app.services.docx_parser            -> app.services.core.docx_parser
   app.services.pdf_converter          -> app.services.core.pdf_converter
   app.services.style_resolver         -> app.services.core.style_resolver
   app.services.message_format         -> app.services.core.message_format
   app.services.schema_rules           -> app.services.core.base_rules
       (lalu pindahkan import factory KC/AI ke
        app.services.schemas.pkm_kc.rules / .pkm_ai.rules)
   app.services.structure_checker      -> app.services.checkers.structure_checker
   app.services.physical_sheet_counter -> app.services.checkers.physical_sheet_counter
   app.services.format_checker         -> app.services.checkers.format_checker
   app.services.page_numbering_checker -> app.services.checkers.page_numbering_checker
   app.services.reference_validator    -> app.services.checkers.reference_validator
   app.services.budget_rules           -> app.services.schemas.pkm_kc.budget_rules
   app.services.budget_auditor         -> app.services.schemas.pkm_kc.budget_auditor
   app.services.budget_table_parser    -> app.services.schemas.pkm_kc.budget_table_parser
   app.services.ai_content_checker     -> app.services.schemas.pkm_ai.ai_content_checker
   app.services.ai_format_checker      -> app.services.schemas.pkm_ai.ai_format_checker
   ```
   File yang mengandung `app.services` (≈21 di `app/` + `tests/`). Temukan:
   `grep -rl "app\.services\." backend/app backend/tests`
   Terapkan substitusi (mis. dengan editor/`sed -i`), lalu **verifikasi
   manual** file orchestrator & semua `tests/test_*.py`.
5. Cek tidak ada import yang tersisa lama:
   `grep -rn "app\.services\.\(docx_parser\|format_checker\|ai_format_checker\|schema_rules\|budget_\|structure_checker\|physical_sheet_counter\|page_numbering_checker\|reference_validator\|style_resolver\|message_format\|pdf_converter\|ai_content_checker\)" backend` → harus kosong.
6. Cek API/entrypoint lain: `grep -rn "app\.services" backend/app/main.py`
   (dan FastAPI routers) — update juga.
7. `cd backend && python -c "import app.services.orchestrator"` → tidak error
   (deteksi circular import / path salah).
8. `cd backend && python -m pytest -q` → semua hijau.

### 5.4 Risiko circular import
- `core/` tidak boleh import `checkers/` atau `schemas/`.
- `checkers/` boleh import `core/`. **Tidak boleh** import `schemas/`.
- `schemas/` boleh import `core/` + `checkers/`.
- `orchestrator` boleh import semua.
- Pastikan `format_checker` (di `checkers/`) **tidak** lagi import apa pun
  dari `schemas/pkm_ai/ai_format_checker` (sudah dihapus di Fase 1 — ini
  alasan Fase 1 wajib duluan).

---

## 6. Verifikasi akhir (kedua fase)
```
cd backend
python -m pytest -q                       # semua hijau
python -c "import app.services.orchestrator"   # tak ada error import
grep -rn "paragraf #\|global #\|Section #\|halaman fisik ~" app/ ; # kosong
grep -rn "_body_start_index\|_is_caption_to_skip" app/ ;           # kosong
```
Uji manual via endpoint/CLI dengan 1 dokumen PKM-AI & 1 PKM-KC:
- PKM-AI: section "format" hanya paper_size+margin; semua aturan teks dari
  section AI-format; tidak ada vonis font 12 di abstrak/caption.
- PKM-KC: identik dengan sebelum refactor.

---

## 7. Keputusan terbuka / asumsi (konfirmasi ke pemilik produk)
1. **Foreign-words italic** untuk body PKM-AI: diport ke `ai_format_checker`
   atau di-drop? (Default dokumen: port; severity `warning`.)
2. Toleransi line spacing body PKM-AI: pakai ±0.05 (asumsi, samakan dgn
   `FormatRules.line_spacing_tolerance`).
3. Body PKM-AI mulai dari heading PENDAHULUAN — apakah teks sebelum
   PENDAHULUAN tapi setelah abstrak/keywords (mis. kata kunci tambahan)
   perlu aturan? Asumsi: tidak; hanya zona ber-nama yang punya aturan.
4. Nama folder final (`core`/`checkers`/`schemas`) — dikonfirmasi OK.
5. Apakah ada skema lain menyusul (PKM-K, P2MW)? Struktur `schemas/<kode>/`
   sudah mengakomodasi; tambah factory + entry registry saja.

---

## 8. Catatan commit & rollback
- Kerjakan di branch terpisah; **jangan** ke `main` langsung.
- Commit granular: (a) Fase 1 perilaku, (b) Fase 1 test, (c) Fase 2 git mv,
  (d) Fase 2 import rewrite. Memudahkan `git revert` per fase.
- Sebelum mulai: pastikan working tree bersih / commit perubahan sesi
  sebelumnya (cek `git status`). Ada perubahan belum di-commit pada
  `format_checker.py`, `ai_format_checker.py`, `style_resolver.py`,
  `reference_validator.py`, `page_numbering_checker.py`,
  `message_format.py`, `tests/test_format_checker.py` (refactor pesan +
  fix kontradiksi sesi sebelumnya) — commit dulu sebagai baseline Fase 0.
- Co-author trailer commit:
  `Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>`

---

## 9. Checklist eksekusi (centang saat dikerjakan)

**Fase 0**
- [ ] Commit baseline (semua perubahan sesi sebelumnya), test hijau.

**Fase 1 — perilaku**
- [ ] 1.1 Konstanta body di `ai_format_checker.py`
- [ ] 1.2 `_validate_body_block()` + dipanggil di `check()`
- [ ] 1.3 Bersihkan patch PKM-AI di `format_checker.py` + param `enabled_checks`
- [ ] 1.4 `SchemaConfig.format_rules_factory`/`format_checks` + `_run_format` + registry
- [ ] 1.5 Update pesan "pass" `_finalize`
- [ ] 1.6 Update/tambah test; `pytest -q` hijau
- [ ] Commit Fase 1

**Fase 2 — folder**
- [ ] 5.1/5.2 Buat folder + `__init__.py`, `git mv` semua file
- [ ] 5.3.3 Pecah `schema_rules.py` & pindah `FormatRules` ke `core/base_rules.py`
- [ ] 5.3.4 Rewrite semua import (app + tests + main.py)
- [ ] 5.3.5–7 Grep sisa import lama = kosong; import smoke test OK
- [ ] 5.3.8 `pytest -q` hijau
- [ ] Commit Fase 2
- [ ] §6 Verifikasi akhir + uji manual 2 dokumen
