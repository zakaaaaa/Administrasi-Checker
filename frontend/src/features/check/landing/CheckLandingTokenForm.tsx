'use client';

import type { FormEvent } from 'react';

type Props = {
  token: string;
  onTokenChange: (value: string) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
};

function CheckIcon() {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2.5"
      strokeLinecap="round"
      strokeLinejoin="round"
      className="mt-0.5 h-4 w-4 shrink-0 text-brand-500"
    >
      <polyline points="20 6 9 17 4 12" />
    </svg>
  );
}

const REQUIREMENTS = [
  'Token aktif dari admin.',
  'File laporan format .word atau .docx.',
];

export function CheckLandingTokenForm({ token, onTokenChange, onSubmit }: Props) {
  return (
    <section id="mulai" className="relative scroll-mt-20 px-4 py-16 sm:px-6 sm:py-20">
      <div
        data-reveal
        className="check-landing-glass-card mx-auto max-w-3xl rounded-3xl p-6 sm:p-9"
      >
        <div className="grid gap-8 md:grid-cols-[minmax(0,1fr)_minmax(0,1fr)] md:items-center">
          {/* Kiri: ajakan + syarat */}
          <div>
            <p className="font-mono text-xs uppercase tracking-[0.18em] text-brand-700">
              Mulai sekarang
            </p>
            <h2 className="mt-2 font-display text-2xl font-bold leading-tight text-foreground sm:text-3xl">
              Siap mengecek laporanmu?
            </h2>
            <p className="mt-3 text-sm leading-relaxed text-foreground-muted">
              Masukkan token dari admin untuk membuka sesi input. Yang perlu kamu siapkan:
            </p>
            <ul className="mt-4 space-y-2.5 text-sm leading-relaxed text-foreground-muted">
              {REQUIREMENTS.map((item) => (
                <li key={item} className="flex items-start gap-2">
                  <CheckIcon />
                  {item}
                </li>
              ))}
            </ul>
          </div>

          {/* Kanan: form token */}
          <form onSubmit={onSubmit} className="rounded-2xl border border-border bg-surface-sunken p-5">
            <label
              htmlFor="check-token"
              className="block text-sm font-semibold text-foreground"
            >
              Token aktif
            </label>
            <input
              id="check-token"
              value={token}
              onChange={(e) => onTokenChange(e.target.value)}
              placeholder="Contoh: PKM-2026-ABCD12"
              className="glass-input mt-2 w-full rounded-xl px-4 py-3 text-base font-medium text-foreground placeholder:text-foreground-subtle"
            />
            <button
              type="submit"
              disabled={!token.trim()}
              className="btn-liquid btn-liquid-primary mt-4 inline-flex w-full items-center justify-center gap-2 rounded-xl px-4 py-3.5 text-base font-semibold text-white transition disabled:cursor-not-allowed disabled:opacity-50"
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
        </div>
      </div>
    </section>
  );
}
