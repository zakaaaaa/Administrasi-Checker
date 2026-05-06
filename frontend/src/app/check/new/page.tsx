'use client';

import { FormEvent, useEffect, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import belajarGif from '@/assets/Animasi Belajar Membaca GIF (3).gif';

export default function NewCheckPage() {
  const [token, setToken] = useState('');
  const router = useRouter();

  function handleContinue(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!token.trim()) return;
    router.push(`/check/new/form?token=${encodeURIComponent(token.trim())}`);
  }

  // Intersection observer untuk fade-in saat scroll
  const observerRef = useRef<IntersectionObserver | null>(null);
  useEffect(() => {
    observerRef.current = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            entry.target.classList.add('reveal-in');
            observerRef.current?.unobserve(entry.target);
          }
        });
      },
      { threshold: 0.12, rootMargin: '0px 0px -40px 0px' }
    );
    document
      .querySelectorAll('[data-reveal]')
      .forEach((el) => observerRef.current?.observe(el));
    return () => observerRef.current?.disconnect();
  }, []);

  return (
    <main className="relative mx-auto max-w-7xl px-4 pb-20 pt-10 sm:px-6">
      {/* Style untuk reveal animation, dot pattern, floating badge, dan glass */}
      <style>{`
        [data-reveal] {
          opacity: 0;
          transform: translateY(24px);
          transition: opacity 0.8s cubic-bezier(0.22, 1, 0.36, 1),
                      transform 0.8s cubic-bezier(0.22, 1, 0.36, 1);
        }
        [data-reveal].reveal-in {
          opacity: 1;
          transform: translateY(0);
        }
        [data-reveal-delay="1"] { transition-delay: 0.08s; }
        [data-reveal-delay="2"] { transition-delay: 0.16s; }
        [data-reveal-delay="3"] { transition-delay: 0.24s; }
        [data-reveal-delay="4"] { transition-delay: 0.32s; }

        .dot-pattern {
          background-image: radial-gradient(
            circle,
            rgba(249, 115, 22, 0.18) 1px,
            transparent 1px
          );
          background-size: 22px 22px;
          mask-image: radial-gradient(ellipse at center, black 40%, transparent 75%);
          -webkit-mask-image: radial-gradient(ellipse at center, black 40%, transparent 75%);
        }

        @keyframes float-y {
          0%, 100% { transform: translateY(0); }
          50% { transform: translateY(-10px); }
        }
        .float-soft { animation: float-y 5s ease-in-out infinite; }
        .float-soft.delay-1 { animation-delay: 0.8s; }
        .float-soft.delay-2 { animation-delay: 1.6s; }

        .glass-card {
          background: rgba(255, 255, 255, 0.55);
          backdrop-filter: blur(18px) saturate(140%);
          -webkit-backdrop-filter: blur(18px) saturate(140%);
          border: 1px solid rgba(255, 255, 255, 0.6);
          box-shadow:
            0 1px 0 rgba(255, 255, 255, 0.8) inset,
            0 20px 50px -20px rgba(249, 115, 22, 0.15),
            0 8px 24px -12px rgba(15, 23, 42, 0.08);
        }
        .glass-badge {
          background: rgba(255, 255, 255, 0.75);
          backdrop-filter: blur(14px) saturate(140%);
          -webkit-backdrop-filter: blur(14px) saturate(140%);
          border: 1px solid rgba(255, 255, 255, 0.8);
          box-shadow: 0 8px 24px -10px rgba(15, 23, 42, 0.12);
        }
        .blob {
          position: absolute;
          border-radius: 9999px;
          filter: blur(60px);
          opacity: 0.55;
          pointer-events: none;
        }
      `}</style>

      {/* Background dot pattern */}
      <div
        aria-hidden
        className="dot-pattern pointer-events-none absolute inset-0 -z-10"
      />

      {/* Soft gradient blobs */}
      <div
        aria-hidden
        className="blob -z-10 left-[-80px] top-[40px] h-72 w-72 bg-orange-300/40"
      />
      <div
        aria-hidden
        className="blob -z-10 right-[-60px] top-[200px] h-80 w-80 bg-amber-200/40"
      />

      {/* Decorative dots */}
      <div
        aria-hidden
        className="pointer-events-none absolute left-4 top-6 flex flex-col gap-3"
      >
        <span className="block h-3 w-3 rounded-full bg-orange-400/80" />
        <span className="ml-6 block h-2 w-2 rounded-full bg-orange-300/70" />
        <span className="block h-1.5 w-1.5 rounded-full bg-orange-300/60" />
      </div>
      <div
        aria-hidden
        className="pointer-events-none absolute bottom-10 right-8 flex flex-col items-end gap-3"
      >
        <span className="block h-2 w-2 rounded-full bg-orange-300/70" />
        <span className="mr-6 block h-3 w-3 rounded-full bg-orange-400/80" />
        <span className="block h-1.5 w-1.5 rounded-full bg-orange-300/60" />
      </div>

      {/* HERO SECTION */}
      <section className="relative grid items-center gap-10 py-12 lg:grid-cols-2 lg:py-20">
        {/* Kolom kiri: teks + CTA */}
        <div className="relative z-10">
          {/* Eyebrow badge */}
          <div
            data-reveal
            className="glass-badge inline-flex items-center gap-2 rounded-full px-4 py-1.5"
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
            Halaman ini menjadi briefing singkat sebelum pengisian. Tujuannya agar user paham
            alur, syarat, dan dokumen yang dibutuhkan sehingga proses lebih cepat.
          </p>

          {/* Tombol Get Started */}
          <div data-reveal data-reveal-delay="3" className="mt-8">
            <button
              type="button"
              onClick={() => {
                const el = document.getElementById('form-section');
                el?.scrollIntoView({ behavior: 'smooth' });
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
              {/* Shimmer */}
              <span className="absolute inset-0 -translate-x-full bg-gradient-to-r from-transparent via-white/30 to-transparent transition-transform duration-700 group-hover:translate-x-full" />
            </button>
          </div>

        
        </div>

        {/* Kolom kanan: GIF + floating badges */}
        <div
          data-reveal
          data-reveal-delay="2"
          className="relative flex items-center justify-center"
        >
          <div
            aria-hidden
            className="absolute inset-0 -z-10 mx-auto h-72 w-72 rounded-full bg-gradient-to-br from-orange-200/60 to-amber-100/40 blur-3xl"
          />

          {/* Floating badge — kiri atas */}
          <div className="glass-badge float-soft absolute left-0 top-6 z-20 flex items-center gap-2 rounded-2xl px-3 py-2 sm:left-4">
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

          {/* Floating badge — kanan tengah */}
          <div className="glass-badge float-soft delay-1 absolute right-0 top-1/3 z-20 flex items-center gap-2 rounded-2xl px-3 py-2 sm:right-2">
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

          {/* Floating badge — kiri bawah */}
          <div className="glass-badge float-soft delay-2 absolute bottom-8 left-2 z-20 flex items-center gap-2 rounded-2xl px-3 py-2 sm:left-8">
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

      {/* FLOW SECTION */}
      <section
        id="flow-section"
        className="mt-6 grid gap-6 lg:grid-cols-[1fr_360px]"
      >
        <div data-reveal className="glass-card rounded-[1.75rem] p-6 sm:p-8">
          <div className="flex items-center gap-2">
            <span className="h-1.5 w-8 rounded-full bg-brand-500" />
            <p className="font-mono text-sm uppercase tracking-[0.2em] text-foreground-subtle">
              Alur Pengisian
            </p>
          </div>
          <div className="mt-5 grid gap-3 sm:grid-cols-2">
            {[
              'Input token',
              'Pilih jenis laporan (Proposal aktif)',
              'Pilih skema PKM',
              'Pilih lomba (PKM aktif)',
              'Input dana (Belmawa + PT)',
              'Upload laporan',
              'Submit / Proses',
            ].map((item, idx) => (
              <div
                key={item}
                className="group flex items-center gap-3 rounded-2xl border border-white/60 bg-white/50 p-4 backdrop-blur-md transition hover:border-orange-200 hover:bg-white/80"
              >
                <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-brand-100 text-sm font-bold text-brand-600 transition group-hover:bg-brand-500 group-hover:text-white">
                  {idx + 1}
                </div>
                <p className="text-base font-semibold text-foreground">{item}</p>
              </div>
            ))}
          </div>
        </div>

        <aside id="form-section" className="space-y-4">
          <form
            onSubmit={handleContinue}
            data-reveal
            data-reveal-delay="1"
            className="glass-card rounded-[1.5rem] p-6"
          >
            <h2 className="text-xl font-semibold text-foreground">Masukkan token dulu</h2>
            <p className="mt-2 text-base text-foreground-muted">
              Token wajib diisi sebelum masuk ke halaman pengecekan.
            </p>
            <input
              value={token}
              onChange={(event) => setToken(event.target.value)}
              placeholder="Contoh: PKM-2026-ABCD12"
              className="mt-4 w-full rounded-2xl border border-white/70 bg-white/70 px-4 py-3 text-base font-medium backdrop-blur transition focus:border-orange-300 focus:bg-white focus:outline-none focus:ring-4 focus:ring-orange-100"
            />
            <button
              type="submit"
              disabled={!token.trim()}
              className="btn-liquid btn-liquid-primary mt-4 inline-flex w-full items-center justify-center gap-2 rounded-xl px-4 py-3 text-base font-semibold text-white transition disabled:cursor-not-allowed disabled:opacity-50 disabled:shadow-none"
            >
              Lanjut ke Form Pengecekan
              <svg
                xmlns="http://www.w3.org/2000/svg"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2.5"
                strokeLinecap="round"
                strokeLinejoin="round"
                className="h-4 w-4"
              >
                <line x1="5" y1="12" x2="19" y2="12" />
                <polyline points="12 5 19 12 12 19" />
              </svg>
            </button>
          </form>

          <div
            data-reveal
            data-reveal-delay="2"
            className="glass-card rounded-[1.5rem] p-6"
          >
            <h2 className="text-xl font-semibold text-foreground">Syarat Minimum</h2>
            <ul className="mt-3 space-y-2.5 text-base text-foreground-muted">
              <li className="flex items-start gap-2">
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2.5"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  className="mt-1 h-4 w-4 shrink-0 text-brand-500"
                >
                  <polyline points="20 6 9 17 4 12" />
                </svg>
                Token aktif dari admin.
              </li>
              <li className="flex items-start gap-2">
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2.5"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  className="mt-1 h-4 w-4 shrink-0 text-brand-500"
                >
                  <polyline points="20 6 9 17 4 12" />
                </svg>
                Data dana Belmawa dan Perguruan Tinggi.
              </li>
              <li className="flex items-start gap-2">
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2.5"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  className="mt-1 h-4 w-4 shrink-0 text-brand-500"
                >
                  <polyline points="20 6 9 17 4 12" />
                </svg>
                File laporan format `.doc`, `.docx`, atau `.pdf`.
              </li>
            </ul>
          </div>
        </aside>
      </section>
    </main>
  );
}