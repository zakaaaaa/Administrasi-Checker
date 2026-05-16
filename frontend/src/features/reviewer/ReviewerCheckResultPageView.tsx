'use client';

import Link from 'next/link';
import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { CheckResultsView } from '@/features/check/CheckResultsView';
import { exportCheckResultPdf } from '@/features/check/exportCheckResultPdf';
import type { CheckResults } from '@/features/check/types';
import { supabase } from '@/lib/supabaseClient';
import { useReviewerSession } from './useReviewerSession';
import { REVIEWER_LAST_RESULT_STORAGE_KEY } from './constants';

export function ReviewerCheckResultPageView() {
  const router = useRouter();
  const session = useReviewerSession();
  const [result] = useState<CheckResults | null>(() => {
    if (typeof window === 'undefined') return null;
    const raw = sessionStorage.getItem(REVIEWER_LAST_RESULT_STORAGE_KEY);
    if (!raw) return null;
    try {
      return JSON.parse(raw) as CheckResults;
    } catch {
      return null;
    }
  });

  useEffect(() => {
    if (session.status === 'unauthenticated') {
      router.replace('/reviewer');
    }
  }, [session.status, router]);

  async function handleSignOut() {
    await supabase.auth.signOut();
    router.replace('/reviewer');
  }

  if (session.status === 'loading') {
    return (
      <main className="relative mx-auto max-w-6xl px-4 pb-20 pt-10 sm:px-6">
        <p className="text-sm text-foreground-muted">Memeriksa sesi…</p>
      </main>
    );
  }
  if (session.status === 'unauthenticated') return null;

  return (
    <main className="relative mx-auto max-w-6xl px-4 pb-20 pt-10 sm:px-6">
      <section className="glass-surface-elevated relative overflow-hidden rounded-[2rem] p-6 sm:p-10 print:hidden">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="font-mono text-xs uppercase tracking-[0.2em] text-foreground-subtle">
              Reviewer · Hasil
            </p>
            <h1 className="mt-2 max-w-4xl text-4xl font-semibold tracking-tight text-foreground sm:text-6xl">
              Output <span className="font-display text-gradient-brand">hasil pengecekan</span>
            </h1>
            <p className="mt-3 text-base text-foreground-muted">
              Halaman ini khusus untuk melihat hasil dan export PDF.
            </p>
          </div>
          {session.email && (
            <div className="glass-surface-subtle flex items-center gap-2.5 rounded-full px-3.5 py-2">
              <div className="flex flex-col leading-tight">
                <span className="text-[10px] font-medium uppercase tracking-wide text-foreground-subtle">
                  Reviewer
                </span>
                <span className="font-mono text-xs font-semibold text-foreground">{session.email}</span>
              </div>
              <button
                type="button"
                onClick={handleSignOut}
                className="ml-2 rounded-full bg-white/60 px-2.5 py-1 text-[11px] font-semibold text-foreground-muted transition hover:bg-white hover:text-red-600"
              >
                Logout
              </button>
            </div>
          )}
        </div>
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
          <Link href="/reviewer/check" className="btn-liquid btn-liquid-ghost px-5 py-3 text-base">
            Pengecekan Baru
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
