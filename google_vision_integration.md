# Integrasi Google Cloud Vision OCR — Instruksi Lengkap

> Untuk dikerjakan di session berikutnya. Baca dokumen ini dari atas sebelum mulai.
> Tujuan: pindahkan OCR dari CPU VPS ke Google Vision agar pengecekan cepat & bisa
> menangani ~10 dokumen bersamaan.

---

## 0. Konteks & keputusan yang sudah diambil

- **User setuju (2026-05-27)** gambar dokumen mahasiswa (biodata, TTD, foto) boleh
  di-upload ke cloud pihak ketiga.
- **Free tier**: 1.000 gambar/bulan pertama gratis → tahap awal **Rp 0**. Setelah itu
  **$1,50 / 1.000 gambar**.
- **Tips hemat WAJIB**: kirim **hanya gambar yang perlu OCR** (biodata + similarity),
  **JANGAN** seluruh PDF (tiap halaman PDF = 1 unit). Arsitektur sekarang sudah begitu:
  lampiran sudah text-only (0 OCR), biodata sudah di-scope, similarity maks 3 gambar.
- **Konsekuensi**: ganti engine OCR = hasil ekstraksi teks **pasti berbeda** dari easyocr.
  → **WAJIB re-validasi** semua checker OCR (lihat §6). Vision biasanya lebih akurat,
  jadi hasil kemungkinan membaik — tapi harus diukur, bukan diasumsikan.

---

## 1. Seam tunggal: `_run_ocr(images) -> list[str]`

Semua OCR di proyek ini mengalir lewat **satu** fungsi:

- **`backend/app/services/biodata_date_checker.py`**
  - `_run_ocr(images: list) -> list[str]` — input list PIL Image, output list teks
    (satu string per gambar, **urutan sama**). Ini titik injeksi utama.
  - `_best_rotation_text(img, reader)` — coba rotasi 0/90/180/270° (khusus easyocr).
  - `_downscale_for_ocr(img)` — turunkan sisi terpanjang ke ≤1500px.
  - `preload_ocr_model()` — preload singleton `_easyocr_reader`.
  - `_load_image_rels(zf)` — map rId → path `media/imageN.png`.
- **Konsumen `_run_ocr`** (semua import dari biodata_date_checker):
  - `similarity_checker.py` → `_run_ocr`, `_load_image_rels`
  - `lampiran_index.py` → `_run_ocr` (dengan cache per-rId `_ocr_cache` di `ocr_text_for_rids`)
  - `biodata_date_checker.py` sendiri (deteksi tanggal)
- **`backend/app/main.py`** lifespan → `preload_ocr_model()` saat startup.

**Karena semua lewat `_run_ocr`, cukup buat abstraksi engine di situ → ketiga konsumen
otomatis ikut tanpa diubah.**

---

## 2. Arsitektur: abstraksi `OcrEngine`

Buat file baru **`backend/app/services/ocr_engine.py`**:

```python
from __future__ import annotations
import io, os
from typing import Protocol


class OcrEngine(Protocol):
    def run(self, images: list) -> list[str]:
        """List PIL Image → list teks (satu string per gambar, urutan dipertahankan)."""
        ...


# --- EasyOCR: bungkus perilaku yang ADA SEKARANG (jangan ubah hasilnya) ---
class EasyOcrEngine:
    def run(self, images: list) -> list[str]:
        # Pindahkan ISI _run_ocr easyocr saat ini ke sini (atau panggil helper
        # _easyocr_run yang berisi body lama: singleton reader + _best_rotation_text).
        from app.services.biodata_date_checker import _easyocr_run
        return _easyocr_run(images)


# --- Google Vision ---
class GoogleVisionEngine:
    def __init__(self):
        from google.cloud import vision
        self._client = vision.ImageAnnotatorClient()
        self._vision = vision

    def run(self, images: list) -> list[str]:
        from concurrent.futures import ThreadPoolExecutor
        if not images:
            return []
        # Vision adalah I/O-bound → paralelkan. max_workers konservatif dulu.
        with ThreadPoolExecutor(max_workers=8) as ex:
            return list(ex.map(self._one, images))

    def _one(self, pil_img) -> str:
        buf = io.BytesIO()
        # Vision tidak butuh rotasi manual (deteksi orientasi sendiri).
        # Downscale opsional untuk hemat bandwidth — Vision terima gambar besar.
        pil_img.convert("RGB").save(buf, format="PNG")
        image = self._vision.Image(content=buf.getvalue())
        ctx = self._vision.ImageContext(language_hints=["id", "en"])
        resp = self._client.document_text_detection(image=image, image_context=ctx)
        if resp.error.message:
            return ""
        return resp.full_text_annotation.text or ""


_engine: OcrEngine | None = None

def get_ocr_engine() -> OcrEngine:
    global _engine
    if _engine is None:
        name = os.getenv("OCR_ENGINE", "easyocr").lower()
        _engine = GoogleVisionEngine() if name == "google_vision" else EasyOcrEngine()
    return _engine
```

### Refactor `_run_ocr` di biodata_date_checker.py
1. Rename body easyocr `_run_ocr` saat ini → `_easyocr_run(images)` (logika tetap **persis sama**: singleton reader, `_best_rotation_text`, downscale).
2. Ganti `_run_ocr` jadi tipis:
   ```python
   def _run_ocr(images: list) -> list[str]:
       from app.services.ocr_engine import get_ocr_engine
       return get_ocr_engine().run(images)
   ```
3. **Jangan ubah** signature `_run_ocr` (tetap `list -> list[str]`, urutan sama) agar
   similarity & lampiran_index tidak perlu disentuh.

### Update preload (main.py)
- `preload_ocr_model()` hanya relevan untuk easyocr. Buat engine-aware:
  - jika `OCR_ENGINE=google_vision` → cukup instansiasi client (`get_ocr_engine()`), murah.
  - jika easyocr → preload reader seperti sekarang.

---

## 3. Dependencies & kredensial

```bash
# di backend/.venv
pip install google-cloud-vision
```

Kredensial (service account):
1. Buat project di Google Cloud Console, aktifkan **Cloud Vision API**.
2. Buat **Service Account** → unduh JSON key.
3. Set env (di VPS / .env):
   ```bash
   export GOOGLE_APPLICATION_CREDENTIALS=/path/ke/service-account.json
   export OCR_ENGINE=google_vision
   ```
4. JANGAN commit JSON key. Tambah ke `.gitignore`.

Catatan billing: Vision tetap butuh billing account aktif walau di free tier
(1.000 unit/bulan pertama gratis, sisanya ditagih).

---

## 4. Detail teknis penting

- **Fitur**: pakai `document_text_detection` (bukan `text_detection`) — lebih bagus
  untuk dokumen padat & paragraf. 1 gambar = 1 unit.
- **language_hints `["id", "en"]`** — selaras dengan easyocr (`Reader(["id","en"])`).
- **Rotasi**: Vision deteksi orientasi otomatis → **jangan** pakai `_best_rotation_text`
  di path Vision (hemat 4× pemanggilan). Path easyocr tetap pakai.
- **Format gambar**: kirim PNG (lossless) dari PIL. Bisa downscale ≤2000px untuk hemat
  bandwidth tanpa kehilangan teks; jangan terlalu kecil (tanggal/angka bisa hilang).
- **Cache per-rId** di `lampiran_index.ocr_text_for_rids` tetap berfungsi (meng-cache hasil
  `_run_ocr` per rId) — tidak perlu diubah.

---

## 5. Paralelisasi & konkurensi

- Di dalam satu dokumen: `GoogleVisionEngine.run` sudah paralelkan gambar via
  `ThreadPoolExecutor`. Satu dokumen (~15–20 gambar) → OCR kelar ~2–4 detik.
- Antar dokumen (10 sekaligus): beban berat ada di sisi Google, **bukan** CPU VPS.
  Tapi `/api/check` masih sinkron & memblok → tetap perlu **queue/worker** (lihat §8)
  agar 10 request tidak saling menunggu di level HTTP.
- Kuota Vision default ~1.800 request/menit (bisa dinaikkan). 10 dok × 20 gambar = 200
  request burst → aman.

---

## 6. Re-validasi WAJIB (jangan skip)

Ganti engine = hasil beda. Bandingkan terhadap baseline easyocr pada dokumen uji:

| Checker | Dokumen uji | Baseline easyocr | Harus dicek |
|---|---|---|---|
| biodata_date | `pkm kc full nuki.docx` | **7 tanggal pass** | jumlah & nilai tanggal sama? |
| similarity | `pkm kc full nuki.docx` | **20%** | persen terdeteksi sama? |
| lampiran | (text-only) | tak OCR | tak terpengaruh |

Cara: jalankan `run_all_checks` dengan `OCR_ENGINE=easyocr` lalu `=google_vision`,
bandingkan `results["biodata_date"]` & `results["similarity"]` (status + messages).
Kalau Vision menemukan tanggal yang easyocr lewatkan, itu peningkatan — verifikasi manual
beberapa untuk memastikan benar, lalu update ekspektasi.

---

## 7. Biaya & monitoring

- Rumus: `biaya = (jumlah_dok × gambar_per_dok − 1000) × $0,0015` (kalau <0 → gratis).
- ~20 gambar/dok → ~$0,03 (~Rp 480)/dokumen setelah free tier.
- 10 dok/bulan = gratis; 100 dok = ~Rp 24.000; 1.000 dok = ~Rp 456.000.
- Pasang **budget alert** di Google Cloud Billing untuk jaga-jaga.

---

## 8. Queue/worker (terpisah — prasyarat produksi konkuren)

Independen dari Vision, tapi perlu untuk "10 dokumen sekaligus":
- `/api/check` & `/api/reviewer/check` di `main.py` sekarang **sinkron & memblok**.
- Tambah **Redis + RQ/Celery**: upload → enqueue → worker proses → frontend polling status.
- Dengan OCR di Vision, worker jadi ringan (tinggal orkestrasi + HTTP call), jadi
  beberapa worker di VPS 4 vCPU sudah cukup.

---

## 9. Rollback & keamanan

- Default `OCR_ENGINE=easyocr` → tanpa set env, perilaku lama (aman, tidak ada panggilan
  cloud). Set `=google_vision` hanya saat siap.
- Karena seam tunggal `_run_ocr`, rollback = unset env var. Tidak ada perubahan di checker.
- Pastikan ada fallback: jika Vision error/timeout di `_one`, kembalikan `""` (jangan
  crash) — checker sudah toleran teks kosong.

---

## Checklist eksekusi
- [ ] `pip install google-cloud-vision`, set kredensial + `OCR_ENGINE`
- [ ] Buat `ocr_engine.py` (Protocol + EasyOcrEngine + GoogleVisionEngine + factory)
- [ ] Refactor `_run_ocr` → `get_ocr_engine().run`; pindahkan body easyocr ke `_easyocr_run`
- [ ] Engine-aware `preload_ocr_model` di lifespan
- [ ] Uji 1 dokumen, ukur durasi + bandingkan biodata(7 tanggal)/similarity(20%) vs easyocr
- [ ] Pasang budget alert billing
- [ ] (Opsional, terpisah) queue + worker untuk konkurensi request
