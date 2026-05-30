import Image from 'next/image';
import belajarGif from '@/assets/Animasi Belajar Membaca GIF (3).gif';

const CHECK_SCOPES = [
  {
    title: 'Struktur laporan',
    body: 'Urutan bagian, kelengkapan bab, dan komponen wajib.',
  },
  {
    title: 'Format naskah',
    body: 'Kesesuaian file, halaman, penomoran, dan tata letak.',
  },
  {
    title: 'Lampiran',
    body: 'Biodata, surat pendukung, dan dokumen pelengkap.',
  },
  {
    title: 'Referensi',
    body: 'Daftar pustaka dan catatan sitasi yang perlu dirapikan.',
  },
];

const RESULT_POINTS = [
  'Temuan dikelompokkan per bagian laporan.',
  'Catatan perbaikan ditulis singkat dan mudah ditindaklanjuti.',
  'Hasil pengecekan bisa dibaca ulang setelah proses selesai.',
];

export function CheckLandingHero() {
  return (
    <section className="relative min-w-0">
      <div className="relative z-10">
        <h1
          data-reveal
          data-reveal-delay="1"
          className="max-w-4xl font-display text-4xl font-bold leading-tight text-foreground sm:text-5xl lg:text-6xl"
        >
          Cek kesiapan laporan PKM sebelum{' '}
          <span className="text-gradient-brand">masuk tahap submit</span>.
        </h1>

        <p
          data-reveal
          data-reveal-delay="2"
          className="mt-5 max-w-2xl text-base leading-relaxed text-foreground-muted sm:text-lg"
        >
          Unggah dokumen, isi data pendukung, lalu dapatkan rangkuman masalah administrasi yang
          perlu dirapikan sebelum laporan dikirim ke sistem resmi.
        </p>

        <div data-reveal data-reveal-delay="3" className="mt-8 flex flex-wrap gap-3">
          <button
            type="button"
            onClick={() => {
              document.getElementById('form-section')?.scrollIntoView({ behavior: 'smooth' });
            }}
            className="btn-liquid btn-liquid-primary group relative inline-flex items-center justify-center overflow-hidden rounded-xl px-7 py-3.5 text-base font-semibold text-white transition"
          >
            <span className="relative z-10 flex items-center gap-2">
              Mulai pengecekan
              <svg
                xmlns="http://www.w3.org/2000/svg"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2.5"
                strokeLinecap="round"
                strokeLinejoin="round"
                className="h-4 w-4 transition-transform group-hover:translate-x-1"
              >
                <line x1="5" y1="12" x2="19" y2="12" />
                <polyline points="12 5 19 12 12 19" />
              </svg>
            </span>
            <span className="absolute inset-0 -translate-x-full bg-gradient-to-r from-transparent via-white/30 to-transparent transition-transform duration-700 group-hover:translate-x-full" />
          </button>
          <button
            type="button"
            onClick={() => {
              document.getElementById('flow-section')?.scrollIntoView({ behavior: 'smooth' });
            }}
            className="btn-liquid btn-liquid-ghost rounded-xl px-6 py-3.5 text-base font-semibold"
          >
            Lihat alur
          </button>
        </div>

      </div>

      <div data-reveal data-reveal-delay="3" className="relative mt-9">
        <div
          aria-hidden
          className="absolute inset-x-6 top-6 -z-10 h-48 rounded-full bg-gradient-to-br from-brand-200/70 via-white/40 to-amber-100/50 blur-3xl"
        />

        <div className="check-landing-hero-preview grid gap-5 rounded-[1.75rem] p-4 lg:grid-cols-[minmax(0,1fr)_280px] sm:p-5">
          <div className="min-w-0 rounded-3xl bg-white/55 p-4 backdrop-blur sm:p-5">
            <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.16em] text-foreground-subtle">
                  Yang akan dicek
                </p>
                <h2 className="mt-1 text-xl font-bold text-foreground">Cakupan pemeriksaan</h2>
              </div>
              <p className="max-w-sm text-sm leading-relaxed text-foreground-muted">
                Fokus pada hal yang paling sering membuat laporan perlu direvisi.
              </p>
            </div>

            <div className="mt-5 grid gap-3 sm:grid-cols-2">
              {CHECK_SCOPES.map((item) => (
                <div
                  key={item.title}
                  className="rounded-2xl border border-white/70 bg-white/55 p-4 transition hover:border-brand-200 hover:bg-white/75"
                >
                  <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-brand-100 text-brand-700">
                    <svg
                      xmlns="http://www.w3.org/2000/svg"
                      viewBox="0 0 24 24"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="2.4"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      className="h-4 w-4"
                    >
                      <polyline points="20 6 9 17 4 12" />
                    </svg>
                  </div>
                  <h3 className="mt-3 text-base font-bold text-foreground">{item.title}</h3>
                  <p className="mt-1 text-sm leading-relaxed text-foreground-muted">{item.body}</p>
                </div>
              ))}
            </div>
          </div>

          <div className="relative flex min-h-[260px] flex-col justify-between overflow-hidden rounded-3xl bg-gradient-to-br from-brand-50 via-white/65 to-amber-50 p-5">
            <div className="relative z-20">
              <p className="text-xs font-semibold uppercase tracking-[0.16em] text-brand-700">
                Output
              </p>
              <h2 className="mt-1 text-lg font-bold text-foreground">Ringkasan hasil</h2>
              <ul className="mt-4 space-y-3">
                {RESULT_POINTS.map((item) => (
                  <li key={item} className="flex gap-2 text-sm leading-relaxed text-foreground-muted">
                    <span className="mt-1 flex h-4 w-4 shrink-0 items-center justify-center rounded-full bg-brand-100 text-brand-700">
                      <svg
                        xmlns="http://www.w3.org/2000/svg"
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="3"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        className="h-2.5 w-2.5"
                      >
                        <polyline points="20 6 9 17 4 12" />
                      </svg>
                    </span>
                    <span>{item}</span>
                  </li>
                ))}
              </ul>
            </div>

            <Image
              src={belajarGif}
              alt="Ilustrasi mahasiswa menyiapkan laporan"
              unoptimized
              className="relative z-10 mx-auto mt-4 w-full max-w-[210px] object-contain"
            />
          </div>
        </div>
      </div>
    </section>
  );
}
