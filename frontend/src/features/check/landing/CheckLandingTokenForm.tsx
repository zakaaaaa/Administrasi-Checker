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
    <aside id="form-section" className="space-y-4">
      <form
        onSubmit={onSubmit}
        data-reveal
        data-reveal-delay="1"
        className="check-landing-glass-card rounded-[1.5rem] p-6"
      >
        <h2 className="text-xl font-semibold text-foreground">Masukkan token dulu</h2>
        <p className="mt-2 text-base text-foreground-muted">
          Token wajib diisi sebelum masuk ke halaman pengecekan.
        </p>
        <input
          value={token}
          onChange={(e) => onTokenChange(e.target.value)}
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
        className="check-landing-glass-card rounded-[1.5rem] p-6"
      >
        <h2 className="text-xl font-semibold text-foreground">Syarat Minimum</h2>
        <ul className="mt-3 space-y-2.5 text-base text-foreground-muted">
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
