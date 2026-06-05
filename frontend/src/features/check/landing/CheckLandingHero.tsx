'use client';

import { CheckLandingDecor } from './CheckLandingDecor';

type Props = {
  onStart: () => void;
};

export function CheckLandingHero({ onStart }: Props) {
  return (
    <section id="top" className="relative overflow-hidden">
      <CheckLandingDecor />

      <div className="mx-auto max-w-3xl px-4 pb-16 pt-16 text-center sm:px-6 sm:pb-20 sm:pt-24">
        <h1
          data-reveal
          data-reveal-delay="1"
          className="mt-6 font-display text-4xl font-bold leading-[1.08] text-foreground sm:text-5xl lg:text-6xl"
        >
          Berhenti memeriksa laporan PKM{' '}
          <span className="text-gradient-brand">baris demi baris</span>.
        </h1>

        <p
          data-reveal
          data-reveal-delay="2"
          className="mx-auto mt-6 max-w-xl text-base leading-relaxed text-foreground-muted sm:text-lg"
        >
          Pengecekan administrasi manual butuh waktu, tenaga, dan ketelitian penuh dan tetap
          rawan terlewat. Serahkan ke PKM Checker Kelas PKM: hasil lengkap dan konsisten dalam
          hitungan menit.
        </p>

        <div
          data-reveal
          data-reveal-delay="3"
          className="mt-9 flex flex-wrap items-center justify-center gap-3"
        >
          <button
            type="button"
            onClick={onStart}
            className="btn-liquid btn-liquid-primary group inline-flex items-center justify-center gap-2 rounded-xl px-7 py-3.5 text-base font-semibold text-white"
          >
            Mulai Pengecekan
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
          </button>
          <a
            href="#flow-section"
            className="btn-liquid btn-liquid-ghost rounded-xl px-6 py-3.5 text-base font-semibold"
          >
            Lihat cara kerja
          </a>
        </div>

      </div>
    </section>
  );
}
