'use client';

import Link from 'next/link';
import { useMemo, useSyncExternalStore } from 'react';
import { CheckResultReport } from '@/features/check/CheckResultReport';
import type { CheckResults } from '@/features/check/types';
import { LAST_RESULT_STORAGE_KEY, LAST_RESULT_META_KEY } from '@/features/check/form/checkFormConstants';
import { ExportCheckResultButton } from '@/features/check/ExportCheckResultButton';

type ResultMeta = { fileName: string; skema: string; reportLabel: string };

function subscribeToStorage(onChange: () => void) {
  window.addEventListener('storage', onChange);
  return () => window.removeEventListener('storage', onChange);
}

function useStoredResult<T>(key: string): T | null {
  // Server and initial hydration both see null; read browser storage afterwards.
  const raw = useSyncExternalStore(subscribeToStorage, () => {
    try { return sessionStorage.getItem(key); } catch { return null; }
  }, () => null);
  return useMemo(() => {
    if (!raw) return null;
    try { return JSON.parse(raw) as T; } catch { return null; }
  }, [raw]);
}

export function CheckResultPageView() {
  const result = useStoredResult<CheckResults>(LAST_RESULT_STORAGE_KEY);
  const meta = useStoredResult<ResultMeta>(LAST_RESULT_META_KEY);

  return (
    <div className="relative min-h-screen">
      {/* Header */}
      <header className="sticky top-0 z-10 border-b border-border bg-surface-elevated print:hidden">
        <div className="mx-auto flex max-w-5xl items-center justify-between px-4 py-3 sm:px-6">
          <div className="flex items-center gap-3">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src="https://wryvhzvzeuadzbpelbdz.supabase.co/storage/v1/object/public/web/logopkm.png"
              alt="Logo PKM"
              className="h-8 w-auto object-contain"
            />
            <div>
              <p className="font-mono text-[10px] uppercase tracking-widest text-foreground-subtle">
                Hasil Pengecekan
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            {result && (
              <ExportCheckResultButton
                result={result}
                sourceFileName={meta?.fileName}
                schemaLabel={meta?.skema}
                reportLabel={meta?.reportLabel}
              />
            )}
            <Link
              href="/check/new"
              className="inline-flex items-center gap-1.5 rounded-xl border border-brand-300 bg-brand-50 px-3 py-2 text-xs font-semibold text-brand-700 transition hover:bg-brand-100"
            >
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" className="h-3.5 w-3.5">
                <polyline points="1 4 1 10 7 10" />
                <path d="M3.51 15a9 9 0 1 0 .49-3.51" />
              </svg>
              Cek Dokumen Lain
            </Link>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-5xl px-4 pb-24 pt-8 sm:px-6">
        {result ? (
          <CheckResultReport
            result={result}
            sourceFileName={meta?.fileName}
            schemaLabel={meta?.skema}
            reportLabel={meta?.reportLabel}
          />
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
    </div>
  );
}
