'use client';

import type { ChangeEvent, DragEvent, FormEvent } from 'react';
import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import type { CheckResults } from '@/features/check/types';
import {
  ALL_REPORTS,
  API_URL,
  MAX_FILE_MB,
  SKEMA_LAPORAN_MAP,
  SKEMA_OPTIONS,
  formatBytes,
  type ReportCode,
  type SkemaCode,
} from '@/features/check/form/checkFormConstants';
import { CheckFormSection } from '@/features/check/form/CheckFormSection';
import { CheckFormSelectCard } from '@/features/check/form/CheckFormSelectCard';
import { supabase } from '@/lib/supabaseClient';
import { useReviewerSession } from './useReviewerSession';
import { REVIEWER_LAST_RESULT_STORAGE_KEY } from './constants';

export function ReviewerCheckFormView() {
  const router = useRouter();
  const session = useReviewerSession();

  const [skema, setSkema] = useState<SkemaCode>('PKM-KC');
  const [reportCode, setReportCode] = useState<ReportCode>('PROPOSAL');
  const [file, setFile] = useState<File | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [errorMsg, setErrorMsg] = useState('');
  const [fileError, setFileError] = useState('');

  useEffect(() => {
    const validCodes = SKEMA_LAPORAN_MAP[skema];
    if (!validCodes.includes(reportCode)) {
      setReportCode(validCodes[0]);
    }
  }, [skema, reportCode]);

  useEffect(() => {
    if (session.status === 'unauthenticated') {
      router.replace('/reviewer');
    }
  }, [session.status, router]);

  if (session.status === 'loading') {
    return (
      <main className="relative mx-auto max-w-6xl px-4 pb-24 pt-8 sm:px-6">
        <p className="text-sm text-foreground-muted">Memeriksa sesi…</p>
      </main>
    );
  }
  if (session.status === 'unauthenticated') return null;

  const availableReports = ALL_REPORTS.filter((r) => SKEMA_LAPORAN_MAP[skema].includes(r.code));
  const selectedReport = availableReports.find((r) => r.code === reportCode) ?? availableReports[0];
  const isFormReady = Boolean(file && !fileError);

  function handleFile(f: File | null) {
    setFileError('');
    setErrorMsg('');
    if (!f) {
      setFile(null);
      return;
    }
    if (!f.name.toLowerCase().endsWith('.docx')) {
      setFileError('Format harus .docx');
      setFile(null);
      return;
    }
    if (f.size > MAX_FILE_MB * 1024 * 1024) {
      setFileError(`Ukuran maksimal ${MAX_FILE_MB} MB`);
      setFile(null);
      return;
    }
    setFile(f);
  }

  function onFileInput(event: ChangeEvent<HTMLInputElement>) {
    handleFile(event.target.files?.[0] ?? null);
  }

  function onDrop(event: DragEvent<HTMLLabelElement>) {
    event.preventDefault();
    setIsDragging(false);
    handleFile(event.dataTransfer.files?.[0] ?? null);
  }

  async function handleSignOut() {
    await supabase.auth.signOut();
    router.replace('/reviewer');
  }

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setErrorMsg('');
    if (!session.session) {
      setErrorMsg('Sesi tidak valid. Silakan login ulang.');
      return;
    }
    if (!file) {
      setErrorMsg('File laporan belum diunggah.');
      return;
    }

    setSubmitting(true);
    const fd = new FormData();
    fd.append('competition', 'PKM');
    fd.append('report_type', reportCode);
    fd.append('schema_code', skema);
    fd.append('file', file);

    try {
      const res = await fetch(`${API_URL}/api/reviewer/check`, {
        method: 'POST',
        body: fd,
        headers: {
          Authorization: `Bearer ${session.session.access_token}`,
        },
      });
      const data = await res.json();
      if (!res.ok) {
        const msg = data?.detail ?? `Error ${res.status}`;
        setErrorMsg(typeof msg === 'string' ? msg : JSON.stringify(msg));
        return;
      }
      sessionStorage.setItem(REVIEWER_LAST_RESULT_STORAGE_KEY, JSON.stringify(data as CheckResults));
      router.push('/reviewer/check/result');
    } catch (err) {
      setErrorMsg(
        `Tidak bisa terhubung ke server: ${err instanceof Error ? err.message : String(err)}`,
      );
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="relative mx-auto max-w-6xl px-4 pb-24 pt-8 sm:px-6">
      <header className="mb-6">
        <Link
          href="/"
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
          Kembali ke Beranda
        </Link>

        <div className="mt-4 flex flex-wrap items-end justify-between gap-4">
          <div>
            <p className="font-mono text-xs uppercase tracking-[0.18em] text-foreground-subtle">
              Reviewer · Form Pengecekan
            </p>
            <h1 className="mt-2 text-3xl font-semibold tracking-tight text-foreground sm:text-4xl">
              Pengecekan <span className="text-gradient-brand">laporan PKM</span>
            </h1>
            <p className="mt-2 max-w-2xl text-sm text-foreground-muted sm:text-base">
              Pilih skema dan jenis laporan, lalu unggah file{' '}
              <code className="rounded bg-brand-100/60 px-1.5 py-0.5 font-mono text-[0.85em]">.docx</code>.
              Pengecekan otomatis berjalan setelah submit.
            </p>
          </div>

          <div className="glass-surface-subtle flex items-center gap-2.5 rounded-full px-3.5 py-2">
            <span className="flex h-6 w-6 items-center justify-center rounded-full bg-brand-100">
              <svg
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2.5"
                strokeLinecap="round"
                strokeLinejoin="round"
                className="h-3.5 w-3.5 text-brand-600"
              >
                <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
                <circle cx="12" cy="7" r="4" />
              </svg>
            </span>
            <div className="flex flex-col leading-tight">
              <span className="text-[10px] font-medium uppercase tracking-wide text-foreground-subtle">
                Login sebagai reviewer
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
        </div>
      </header>

      <div className="grid gap-6 lg:grid-cols-[1fr_340px]">
        <form onSubmit={onSubmit} className="space-y-5">
          <CheckFormSection
            number={1}
            title="Skema PKM"
            description="Pilih satu skema sesuai laporan yang ingin direview."
          >
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
              {SKEMA_OPTIONS.map((opt) => (
                <CheckFormSelectCard
                  key={opt.value}
                  active={skema === opt.value}
                  onClick={() => setSkema(opt.value)}
                  label={opt.label}
                  description={opt.desc}
                  compact
                />
              ))}
            </div>
          </CheckFormSection>

          <CheckFormSection
            number={2}
            title="Jenis Laporan"
            description={
              availableReports.length === 1
                ? `Skema ${skema} hanya memiliki satu jenis laporan.`
                : `Pilih dokumen yang sedang direview untuk skema ${skema}.`
            }
          >
            <div className={`grid gap-3 ${availableReports.length === 1 ? '' : 'sm:grid-cols-2'}`}>
              {availableReports.map((opt) => (
                <CheckFormSelectCard
                  key={opt.code}
                  active={reportCode === opt.code}
                  onClick={() => setReportCode(opt.code)}
                  label={opt.label}
                  description={opt.desc}
                />
              ))}
            </div>
            {availableReports.length === 1 && (
              <p className="mt-2 text-xs text-foreground-muted">
                Jenis laporan dipilih otomatis sesuai skema.
              </p>
            )}
          </CheckFormSection>

          <CheckFormSection
            number={3}
            title="Upload laporan"
            description="Hanya menerima file .docx, maksimal 25 MB."
          >
            {!file ? (
              <label
                onDragOver={(e) => {
                  e.preventDefault();
                  setIsDragging(true);
                }}
                onDragLeave={() => setIsDragging(false)}
                onDrop={onDrop}
                className={`group flex cursor-pointer flex-col items-center justify-center rounded-2xl border-2 border-dashed px-6 py-10 text-center transition ${
                  isDragging
                    ? 'border-brand-500 bg-brand-50/70'
                    : 'border-white/70 bg-white/40 hover:border-brand-300 hover:bg-white/60'
                }`}
              >
                <input type="file" accept=".docx" onChange={onFileInput} className="hidden" />
                <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-brand-100 text-brand-600 transition group-hover:scale-105">
                  <svg
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    className="h-6 w-6"
                  >
                    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                    <polyline points="17 8 12 3 7 8" />
                    <line x1="12" y1="3" x2="12" y2="15" />
                  </svg>
                </div>
                <p className="mt-3 text-base font-semibold text-foreground">
                  Klik untuk memilih atau seret file ke sini
                </p>
                <p className="mt-1 text-xs text-foreground-muted">
                  Format <span className="font-mono font-semibold">.docx</span> · maks {MAX_FILE_MB} MB
                </p>
              </label>
            ) : (
              <div className="flex items-center gap-3 rounded-2xl border border-brand-300/60 bg-white/70 p-4 backdrop-blur">
                <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-brand-100 text-brand-600">
                  <svg
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    className="h-5 w-5"
                  >
                    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                    <polyline points="14 2 14 8 20 8" />
                  </svg>
                </div>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-semibold text-foreground">{file.name}</p>
                  <p className="text-xs text-foreground-muted">{formatBytes(file.size)} · siap diunggah</p>
                </div>
                <button
                  type="button"
                  onClick={() => {
                    setFile(null);
                    setFileError('');
                  }}
                  className="shrink-0 rounded-full p-2 text-foreground-muted transition hover:bg-red-50 hover:text-red-600"
                  aria-label="Hapus file"
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
                    <line x1="18" y1="6" x2="6" y2="18" />
                    <line x1="6" y1="6" x2="18" y2="18" />
                  </svg>
                </button>
              </div>
            )}
            {fileError && <p className="mt-2 text-xs font-semibold text-red-600">{fileError}</p>}
          </CheckFormSection>

          <div className="glass-surface rounded-[1.5rem] p-5">
            {errorMsg && (
              <div className="mb-4 flex items-start gap-2.5 rounded-2xl border border-red-200 bg-red-50/80 p-3.5">
                <svg
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2.5"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  className="mt-0.5 h-4 w-4 shrink-0 text-red-600"
                >
                  <circle cx="12" cy="12" r="10" />
                  <line x1="12" y1="8" x2="12" y2="12" />
                  <line x1="12" y1="16" x2="12.01" y2="16" />
                </svg>
                <p className="text-sm font-medium text-red-700">{errorMsg}</p>
              </div>
            )}
            <button
              type="submit"
              disabled={submitting || !isFormReady}
              className="btn-liquid btn-liquid-primary w-full px-5 py-3.5 text-base font-semibold disabled:cursor-not-allowed disabled:opacity-50"
            >
              {submitting ? (
                <>
                  <svg className="h-4 w-4 animate-spin" viewBox="0 0 24 24" fill="none">
                    <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" opacity="0.25" />
                    <path
                      d="M12 2a10 10 0 0 1 10 10"
                      stroke="currentColor"
                      strokeWidth="3"
                      strokeLinecap="round"
                    />
                  </svg>
                  Memproses laporan… (1–2 menit)
                </>
              ) : (
                <>
                  Submit & Mulai Pengecekan
                  <svg
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
                </>
              )}
            </button>
            {!isFormReady && !submitting && (
              <p className="mt-2.5 text-center text-xs text-foreground-muted">
                Upload file untuk melanjutkan
              </p>
            )}
          </div>
        </form>

        <aside className="space-y-4">
          <div className="check-landing-glass-card rounded-[1.5rem] p-5">
            <h3 className="text-sm font-semibold uppercase tracking-wider text-foreground-subtle">
              Ringkasan
            </h3>
            <dl className="mt-3 space-y-3 text-sm">
              <div>
                <dt className="text-xs text-foreground-muted">Skema</dt>
                <dd className="font-semibold text-foreground">{skema}</dd>
              </div>
              <div>
                <dt className="text-xs text-foreground-muted">Jenis Laporan</dt>
                <dd className="font-semibold text-foreground">{selectedReport?.label}</dd>
              </div>
              <div>
                <dt className="text-xs text-foreground-muted">File</dt>
                <dd className="font-semibold text-foreground">
                  {file ? file.name : <span className="text-foreground-muted">Belum dipilih</span>}
                </dd>
              </div>
            </dl>
          </div>

          <div className="check-landing-glass-card rounded-[1.5rem] p-5">
            <h3 className="text-sm font-semibold uppercase tracking-wider text-foreground-subtle">
              Catatan Reviewer
            </h3>
            <p className="mt-2 text-sm text-foreground-muted">
              Sebagai reviewer, kamu bisa submit dokumen tanpa token. Hasil pengecekan akan
              tersimpan dan dapat di-export ke PDF.
            </p>
          </div>
        </aside>
      </div>
    </main>
  );
}
