'use client';

import Link from 'next/link';
import { useState } from 'react';
import { CheckResultsView } from '@/features/check/CheckResultsView';
import type { CheckResults } from '@/features/check/types';
import { LAST_RESULT_STORAGE_KEY } from '@/features/check/form/checkFormConstants';
import { exportCheckResultPdf } from '@/features/check/exportCheckResultPdf';

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

  return (
    <main className="relative mx-auto max-w-6xl px-4 pb-20 pt-10 sm:px-6">
      <section className="glass-surface-elevated relative overflow-hidden rounded-[2rem] p-6 sm:p-10 print:hidden">
        <h1 className="max-w-4xl text-4xl font-semibold tracking-tight text-foreground sm:text-6xl">
          Output <span className="font-display text-gradient-brand">hasil pengecekan</span>
        </h1>
        <p className="mt-3 text-base text-foreground-muted">
          Halaman ini khusus untuk melihat hasil dan export PDF.
        </p>
      </section>

      <section className="mt-6 space-y-6">
        <div className="flex flex-wrap gap-3 print:hidden">
          <button
            type="button"
            onClick={() => result && exportCheckResultPdf(result)}
            disabled={!result}
            className="btn-liquid btn-liquid-primary px-5 py-3 text-base font-semibold disabled:opacity-50"
          >
            Export PDF
          </button>
          <Link href="/check/new" className="btn-liquid btn-liquid-ghost px-5 py-3 text-base">
            Kembali ke Beranda Input
          </Link>
        </div>

        {result ? (
          <CheckResultsView result={result} />
        ) : (
          <section className="rounded-2xl border border-amber-300 bg-amber-50 p-4 text-base font-semibold text-amber-800">
            Hasil belum tersedia. Silakan submit dokumen dulu dari halaman form.
          </section>
        )}
      </section>
    </main>
  );
}
