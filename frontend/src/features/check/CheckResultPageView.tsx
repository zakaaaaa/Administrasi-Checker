'use client';

import Link from 'next/link';
import { useEffect, useState } from 'react';
import { CheckResultsView } from '@/features/check/CheckResultsView';
import type { CheckResults } from '@/features/check/types';
import { LAST_RESULT_STORAGE_KEY } from '@/features/check/form/checkFormConstants';
import { exportCheckResultPdf } from '@/features/check/exportCheckResultPdf';
import {
  CheckFormStepBar,
  CheckFormStepDot,
} from '@/features/check/form/CheckFormStepIndicator';


export function CheckResultPageView() {
  const [result] = useState<CheckResults | null>(() => {
    if (typeof window === 'undefined') return null;
    const raw = sessionStorage.getItem(LAST_RESULT_STORAGE_KEY);
    if (!raw) return null;
    try {
      return JSON.parse(raw) as CheckResults;
    } catch {
      return null;
    }
  });

  const [scrolled, setScrolled] = useState(false);
  useEffect(() => {
    const handler = () => setScrolled(window.scrollY > 8);
    window.addEventListener('scroll', handler, { passive: true });
    return () => window.removeEventListener('scroll', handler);
  }, []);

  return (
    <>
      {/* Full-width sticky header */}
      <header
        className={`sticky top-0 z-10 w-full print:hidden transition-all duration-200 ${
          scrolled
            ? 'bg-white shadow-sm border-b border-black/8'
            : 'bg-white/70 backdrop-blur-lg'
        }`}
      >
        <div className="px-4 py-4 sm:px-6">
          <div className="flex items-center justify-between">
            <Link
              href="/check/new"
              className="inline-flex items-center gap-1.5 text-sm font-medium text-foreground-muted transition hover:text-foreground"
            >
              <svg
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2.5"
                strokeLinecap="round"
                strokeLinejoin="round"
                className="h-4 w-4"
              >
                <line x1="19" y1="12" x2="5" y2="12" />
                <polyline points="12 19 5 12 12 5" />
              </svg>
              Kembali ke Form
            </Link>

            <button
              type="button"
              onClick={() => result && exportCheckResultPdf(result)}
              disabled={!result}
              className="inline-flex items-center gap-1.5 rounded-xl bg-foreground px-3.5 py-2 text-sm font-semibold text-background transition hover:opacity-80 disabled:cursor-not-allowed disabled:opacity-40 print:hidden"
            >
              <svg
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
                className="h-4 w-4"
              >
                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                <polyline points="7 10 12 15 17 10" />
                <line x1="12" y1="15" x2="12" y2="3" />
              </svg>
              Export PDF
            </button>
          </div>

          <div className="mt-4">
            <p className="font-mono text-xs uppercase tracking-[0.18em] text-foreground-subtle">
              Langkah 3 dari 3 · Hasil Pengecekan
            </p>
            <h1 className="mt-2 text-3xl font-semibold tracking-tight text-foreground sm:text-4xl">
              Hasil{' '}
              <span className="font-display text-gradient-brand">pengecekan dokumen</span>
            </h1>
            <p className="mt-2 max-w-2xl text-sm text-foreground-muted sm:text-base">
              Tinjau setiap modul di bawah dan perbaiki temuan sebelum submit ke Simbelmawa.
            </p>
          </div>

          <div className="mt-5 flex items-center gap-2">
            <CheckFormStepDot state="done" label="Token" />
            <CheckFormStepBar state="active" />
            <CheckFormStepDot state="done" label="Form" />
            <CheckFormStepBar state="active" />
            <CheckFormStepDot state="active" label="Hasil" />
          </div>
        </div>
      </header>

      {/* Page content */}
      <main className="mx-auto max-w-[1890px] px-4 pb-24 pt-6 sm:px-6">
        {result ? (
          <CheckResultsView result={result} />
        ) : (
          <div className="rounded-2xl border border-amber-200 bg-amber-50/80 p-5">
            <p className="text-sm font-semibold text-amber-800">Hasil belum tersedia.</p>
            <p className="mt-1 text-sm text-amber-700">
              Silakan submit dokumen terlebih dahulu melalui halaman form.
            </p>
            <Link
              href="/check/new"
              className="mt-3 inline-flex text-sm font-semibold text-amber-800 underline underline-offset-2"
            >
              Kembali ke Form →
            </Link>
          </div>
        )}
      </main>
    </>
  );
}
