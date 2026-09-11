# Frontend Administrasi Checker

Frontend ini dibangun dengan Next.js (App Router) untuk alur pengecekan dokumen PKM:

- input token
- isi form pengecekan
- lihat output di halaman hasil
- export hasil ke PDF

## Menjalankan Project

Jalankan dari folder `frontend`:

```bash
npm install
npm run dev
```

Lalu buka [http://localhost:3000](http://localhost:3000).

## Alur Halaman (Terbaru)

### 1) Beranda Input Token

Path: `/check/new`

- User wajib memasukkan token terlebih dulu.
- Setelah klik lanjut, user diarahkan ke form dengan query token:
  - `/check/new/form?token=PKM-2026-XXXXXX`

### 2) Form Pengecekan

Path: `/check/new/form`

- Form berisi input lomba, jenis laporan (dropdown), skema, dana, dan upload file `.docx`.
- Jika path form diakses tanpa token, route akan otomatis redirect ke:
  - `/check/new`
- Setelah submit sukses, data hasil disimpan sementara di `sessionStorage`, lalu redirect ke:
  - `/check/new/result`

### 3) Halaman Output Hasil

Path: `/check/new/result`

- Menampilkan ringkasan hasil pengecekan per modul.
- Tombol **Export PDF** akan langsung mengunduh file PDF tanpa dialog print browser.
- Tombol kembali diarahkan ke beranda input token (`/check/new`).

## Export PDF

PDF dibuat di server Next.js dengan `puppeteer-core` dan browser yang dibundel
oleh `@sparticuz/chromium`. Tombol mengirim hasil ke `POST /export/pdf`, lalu
langsung mengunduh respons PDF tanpa dialog cetak.

Perilaku:

- Nama file: `hasil-pengecekan-{nama_dokumen}.pdf` (fallback: submission ID).
- Konten menggunakan `CheckResultReport` yang sama dengan interface, dengan semua detail terbuka.
- Teks tetap dapat diseleksi, disalin, dan dicari; bukan tangkapan layar.
- Data hanya digunakan selama rendering, tidak disimpan sebagai dokumen server.

Renderer membuka halaman lokal `/export/report` pada `http://127.0.0.1:3000`.
Jika menjalankan Next.js pada port lain, set `PDF_RENDER_ORIGIN` ke alamat lokal
tersebut, misalnya `http://127.0.0.1:3105`. Jangan arahkan variabel ini ke layanan lain.
Node.js minimal 22.17 diperlukan; browser diekstrak ke direktori sementara yang
harus dapat ditulis oleh akun layanan. Tidak perlu menginstal Chrome terpisah.
Endpoint dibatasi dua rendering bersamaan, payload 2 MiB, dan 4.000 pesan.

## Perubahan UI yang Sudah Diterapkan

- Font utama menggunakan **Plus Jakarta Sans** + **Poppins**.
- Ukuran dan ketebalan teks diperbesar untuk keterbacaan.
- Pilihan jenis laporan di form diubah menjadi dropdown.
- Label step (Step 01, Step 02, dst) dihapus.
- Panel log aktivitas dihapus.

## Struktur File yang Ditambahkan/Diubah

- `src/app/check/new/page.tsx`  
  Halaman awal input token.
- `src/app/check/new/form/page.tsx`  
  Halaman form dengan guard token dan submit ke backend.
- `src/app/check/new/result/page.tsx`  
  Halaman output hasil + tombol export PDF.
- `src/features/check/types.ts`  
  Type hasil pengecekan.
- `src/features/check/CheckResultsView.tsx`  
  Komponen presentasi hasil pengecekan.
- `src/app/layout.tsx`  
  Konfigurasi font global dan atribut `data-scroll-behavior`.
- `tailwind.config.ts`  
  Update konfigurasi font family.

## Catatan Integrasi Backend

Frontend menggunakan:

- `NEXT_PUBLIC_API_URL` (default `http://localhost:8000`)

Endpoint utama:

- `POST /api/check`
- `POST /api/admin/login`
- `POST /api/admin/tokens`

Pastikan backend aktif sebelum pengujian flow frontend.
