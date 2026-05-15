import belajarGif from '@/assets/Animasi Belajar Membaca GIF (3).gif';

export function CheckLandingHero() {
  return (
    <section className="relative grid items-center gap-10 py-12 lg:grid-cols-2 lg:py-20">
      <div className="relative z-10">
        <div
          data-reveal
          className="check-landing-glass-badge inline-flex items-center gap-2 rounded-full px-4 py-1.5"
        >
          <span className="relative flex h-2 w-2">
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-orange-400 opacity-60" />
            <span className="relative inline-flex h-2 w-2 rounded-full bg-brand-500" />
          </span>
          <p className="font-mono text-xs uppercase tracking-[0.18em] text-foreground-subtle">
            Beranda Input
          </p>
        </div>

        <h1
          data-reveal
          data-reveal-delay="1"
          className="mt-5 text-4xl font-bold leading-tight tracking-tight text-foreground sm:text-5xl lg:text-6xl"
        >
          Siapkan data dulu, lalu masuk ke{' '}
          <span className="text-gradient-brand">form input PKM</span>.
        </h1>

        <p
          data-reveal
          data-reveal-delay="2"
          className="mt-5 max-w-xl text-base leading-relaxed text-foreground-muted sm:text-lg"
        >
          Halaman ini menjadi briefing singkat sebelum pengisian. Tujuannya agar user paham alur,
          syarat, dan dokumen yang dibutuhkan sehingga proses lebih cepat.
        </p>

        <div data-reveal data-reveal-delay="3" className="mt-8">
          <button
            type="button"
            onClick={() => {
              document.getElementById('form-section')?.scrollIntoView({ behavior: 'smooth' });
            }}
            className="btn-liquid btn-liquid-primary group relative inline-flex items-center justify-center overflow-hidden rounded-xl px-8 py-3.5 text-base font-semibold text-white transition"
          >
            <span className="relative z-10 flex items-center gap-2">
              Get Started
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
        </div>
      </div>

      <div
        data-reveal
        data-reveal-delay="2"
        className="relative flex items-center justify-center"
      >
        <div
          aria-hidden
          className="absolute inset-0 -z-10 mx-auto h-72 w-72 rounded-full bg-gradient-to-br from-orange-200/60 to-amber-100/40 blur-3xl"
        />

        <div className="check-landing-glass-badge check-landing-float-soft absolute left-0 top-6 z-20 flex items-center gap-2 rounded-2xl px-3 py-2 sm:left-4">
          <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-brand-100">
            <svg
              xmlns="http://www.w3.org/2000/svg"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2.5"
              strokeLinecap="round"
              strokeLinejoin="round"
              className="h-4 w-4 text-brand-500"
            >
              <polyline points="20 6 9 17 4 12" />
            </svg>
          </div>
          <div>
            <p className="text-xs font-semibold leading-tight text-foreground">Pengecekan Akurat</p>
            <p className="text-[10px] text-foreground-muted">100%</p>
          </div>
        </div>

        <div className="check-landing-glass-badge check-landing-float-soft delay-1 absolute right-0 top-1/3 z-20 flex items-center gap-2 rounded-2xl px-3 py-2 sm:right-2">
          <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-brand-100">
            <svg
              xmlns="http://www.w3.org/2000/svg"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2.5"
              strokeLinecap="round"
              strokeLinejoin="round"
              className="h-4 w-4 text-brand-500"
            >
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
              <polyline points="14 2 14 8 20 8" />
            </svg>
          </div>
          <div>
            <p className="text-xs font-semibold leading-tight text-foreground">Export Hasil</p>
            <p className="text-[10px] text-foreground-muted">.pdf</p>
          </div>
        </div>

        <div className="check-landing-glass-badge check-landing-float-soft delay-2 absolute bottom-8 left-2 z-20 flex items-center gap-2 rounded-2xl px-3 py-2 sm:left-8">
          <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-brand-100">
            <svg
              xmlns="http://www.w3.org/2000/svg"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2.5"
              strokeLinecap="round"
              strokeLinejoin="round"
              className="h-4 w-4 text-brand-500"
            >
              <circle cx="12" cy="12" r="10" />
              <polyline points="12 6 12 12 16 14" />
            </svg>
          </div>
          <div>
            <p className="text-xs font-semibold leading-tight text-foreground">Cepat</p>
            <p className="text-[10px] text-foreground-muted">~2 menit</p>
          </div>
        </div>

        <img
          src={belajarGif.src}
          alt="Ilustrasi tim membuat solusi"
          className="relative z-10 w-full max-w-lg object-contain"
        />
      </div>
    </section>
  );
}
