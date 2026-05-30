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
      className="mt-1 h-4 w-4 shrink-0 text-brand-500"
    >
      <polyline points="20 6 9 17 4 12" />
    </svg>
  );
}

export function CheckLandingTokenForm({ token, onTokenChange, onSubmit }: Props) {
  return (
    <aside id="form-section" className="space-y-4 lg:sticky lg:top-6">
      <form
        onSubmit={onSubmit}
        data-reveal
        data-reveal-delay="1"
        className="check-landing-glass-card rounded-[1.5rem] p-5 sm:p-6"
      >
        <div className="flex items-start justify-between gap-3">
          <div>
            <p className="font-mono text-xs uppercase tracking-[0.18em] text-brand-700">
              Akses pengecekan
            </p>
            <h2 className="mt-2 text-2xl font-bold text-foreground">Masukkan token</h2>
          </div>
          <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-brand-100 text-brand-700">
            <svg
              xmlns="http://www.w3.org/2000/svg"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2.3"
              strokeLinecap="round"
              strokeLinejoin="round"
              className="h-5 w-5"
            >
              <path d="M15 7h.01" />
              <path d="M10.4 21.2 3 13.8 13.8 3H21v7.2L10.4 21.2Z" />
            </svg>
          </div>
        </div>

        <p className="mt-3 text-sm leading-relaxed text-foreground-muted sm:text-base">
          Token dari admin membuka sesi input dan menghubungkan hasil cek ke riwayat unggahan.
        </p>

        <label htmlFor="check-token" className="mt-5 block text-sm font-semibold text-foreground">
          Token aktif
        </label>
        <input
          id="check-token"
          value={token}
          onChange={(e) => onTokenChange(e.target.value)}
          placeholder="Contoh: PKM-2026-ABCD12"
          className="mt-2 w-full rounded-2xl border border-white/70 bg-white/75 px-4 py-3 text-base font-semibold text-foreground shadow-inner shadow-white/40 backdrop-blur transition placeholder:text-foreground-subtle focus:border-brand-300 focus:bg-white focus:outline-none focus:ring-4 focus:ring-brand-200/45"
        />
        <button
          type="submit"
          disabled={!token.trim()}
          className="btn-liquid btn-liquid-primary mt-4 inline-flex w-full items-center justify-center gap-2 rounded-xl px-4 py-3.5 text-base font-semibold text-white transition disabled:cursor-not-allowed disabled:opacity-50 disabled:shadow-none"
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
        className="check-landing-glass-card rounded-[1.5rem] p-5 sm:p-6"
      >
        <h2 className="text-lg font-bold text-foreground">Sebelum mulai</h2>
        <ul className="mt-3 space-y-2.5 text-sm leading-relaxed text-foreground-muted sm:text-base">
          <li className="flex items-start gap-2">
            <CheckIcon />
            Token aktif dari admin.
          </li>
          <li className="flex items-start gap-2">
            <CheckIcon />
            Data dana Belmawa dan Perguruan Tinggi.
          </li>
          <li className="flex items-start gap-2">
            <CheckIcon />
            File laporan format `.doc`, `.docx`, atau `.pdf`.
          </li>
        </ul>
      </div>
    </aside>
  );
}
