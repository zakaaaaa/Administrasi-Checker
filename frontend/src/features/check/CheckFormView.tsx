'use client';

import type { ChangeEvent, DragEvent, FormEvent } from 'react';
import { useEffect, useRef, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import Link from 'next/link';
import type { CheckResults } from '@/features/check/types';
import {
  ALL_REPORTS,
  API_URL,
  LAST_RESULT_STORAGE_KEY,
  LAST_RESULT_META_KEY,
  MAX_FILE_MB,
  SKEMA_LAPORAN_MAP,
  SKEMA_OPTIONS,
  formatBytes,
  type ReportCode,
  type SkemaCode,
} from './form/checkFormConstants';
import { CheckFormSection } from './form/CheckFormSection';
import { CheckFormSelectCard } from './form/CheckFormSelectCard';
import { CheckProgressModal, PROGRESS_WAIT_CAP } from './CheckProgressModal';

export function CheckFormView() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const token = searchParams.get('token')?.trim() ?? '';

  const [skema, setSkema] = useState<SkemaCode>('PKM-KC');
  const [reportCode, setReportCode] = useState<ReportCode>('PROPOSAL');
  const [file, setFile] = useState<File | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [progress, setProgress] = useState(0);
  const progressTimer = useRef<ReturnType<typeof setInterval> | null>(null);
  const [errorMsg, setErrorMsg] = useState('');
  const [fileError, setFileError] = useState('');

  // Bersihkan interval simulasi saat unmount.
  useEffect(() => {
    return () => {
      if (progressTimer.current) clearInterval(progressTimer.current);
    };
  }, []);

  useEffect(() => {
    const validCodes = SKEMA_LAPORAN_MAP[skema];
    if (!validCodes.includes(reportCode)) {
      setReportCode(validCodes[0]);
    }
  }, [skema, reportCode]);

  useEffect(() => {
    if (!token) router.replace('/check/new');
  }, [token, router]);

  const availableReports = ALL_REPORTS.filter((r) => SKEMA_LAPORAN_MAP[skema].includes(r.code));
  const isFormReady = Boolean(token && file && !fileError);

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

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setErrorMsg('');
    if (!token) {
      setErrorMsg('Token wajib diisi dari halaman awal.');
      return;
    }
    if (!file) {
      setErrorMsg('File laporan belum diunggah.');
      return;
    }

    setSubmitting(true);
    setProgress(0);
    // Simulasi linear berbasis waktu: bar naik dengan laju tetap melewati tahap
    // proses (Unggah → Struktur → Format → OCR) selama ~SIM_DURATION_MS, lalu
    // PARKIR sedikit di bawah batas tunggu (tetap di tahap OCR) sampai respons
    // datang. Tahap "Menyusun hasil" baru jalan setelah respons (lihat success).
    // Backend nyata ~120–180 dtk → durasi disetel ke 180 dtk agar tiap tahap
    // mengalir merata sepanjang proses (≈43 dtk/tahap, OCR ≈51 dtk) dan bar
    // terus bergerak pelan, tidak melesat lalu nyangkut.
    const SIM_DURATION_MS = 180000;
    const TICK_MS = 150;
    const WAIT_HOLD = PROGRESS_WAIT_CAP - 1; // parkir di band OCR, bukan menyusun
    const stepPerTick = (PROGRESS_WAIT_CAP / SIM_DURATION_MS) * TICK_MS;
    if (progressTimer.current) clearInterval(progressTimer.current);
    progressTimer.current = setInterval(() => {
      setProgress((p) => Math.min(WAIT_HOLD, p + stepPerTick));
    }, TICK_MS);

    const stopTimer = () => {
      if (progressTimer.current) {
        clearInterval(progressTimer.current);
        progressTimer.current = null;
      }
    };

    const fd = new FormData();
    fd.append('token', token);
    fd.append('competition', 'PKM');
    fd.append('report_type', reportCode);
    fd.append('schema_code', skema);
    fd.append('file', file);

    try {
      const res = await fetch(`${API_URL}/api/check`, { method: 'POST', body: fd });
      const data = await res.json();
      if (!res.ok) {
        const msg = data?.detail ?? `Error ${res.status}`;
        setErrorMsg(typeof msg === 'string' ? msg : JSON.stringify(msg));
        stopTimer();
        setSubmitting(false);
        return;
      }
      sessionStorage.setItem(LAST_RESULT_STORAGE_KEY, JSON.stringify(data as CheckResults));
      const reportLabel = ALL_REPORTS.find((r) => r.code === reportCode)?.label ?? reportCode;
      sessionStorage.setItem(LAST_RESULT_META_KEY, JSON.stringify({ fileName: file.name, skema, reportLabel }));
      stopTimer();
      // Respons datang → jalankan tahap "Menyusun hasil" sebentar, lalu 100%.
      setProgress(PROGRESS_WAIT_CAP);
      await new Promise((r) => setTimeout(r, 450));
      setProgress(100);
      await new Promise((r) => setTimeout(r, 550));
      router.push('/check/new/result');
    } catch (err) {
      setErrorMsg(
        `Tidak bisa terhubung ke server: ${err instanceof Error ? err.message : String(err)}`,
      );
      stopTimer();
      setSubmitting(false);
    }
  }

  if (!token) return null;

  const tokenPreview = token.length > 14 ? `${token.slice(0, 8)}…${token.slice(-4)}` : token;

  return (
    <div className="relative min-h-screen">
      {submitting && <CheckProgressModal progress={progress} />}

      {/* Sticky header — mirip ReviewerCheckForm */}
      <header className="sticky top-0 z-10 border-b border-border bg-surface-elevated">
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
                Form Pengecekan
              </p>
              
            </div>
          </div>

          <Link
            href="/check/new"
            className="inline-flex items-center gap-1.5 rounded-xl border border-black/10 px-3 py-2 text-xs font-medium text-foreground-muted transition hover:border-brand-200 hover:text-foreground"
          >
            <svg
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2.5"
              strokeLinecap="round"
              strokeLinejoin="round"
              className="h-3.5 w-3.5"
            >
              <line x1="19" y1="12" x2="5" y2="12" />
              <polyline points="12 19 5 12 12 5" />
            </svg>
            Kembali
          </Link>
        </div>
      </header>

      <main className="mx-auto max-w-5xl px-4 pb-24 pt-8 sm:px-6">
        <div className="mb-6">
          <h1 className="text-2xl font-semibold tracking-tight text-foreground sm:text-3xl">
            Cek Dokumen PKM
          </h1>
          <p className="mt-1 text-sm text-foreground-muted">
            Pilih skema dan jenis laporan, lalu upload file{' '}
            <code className="rounded bg-brand-100/60 px-1.5 py-0.5 font-mono text-[0.85em]">.docx</code>.
          </p>
        </div>

        <form onSubmit={onSubmit} className="space-y-5">
          <CheckFormSection
            number={1}
            title="Skema PKM"
            description="Pilih satu skema sesuai usulan Anda."
          >
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
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
                : `Pilih dokumen yang sedang Anda susun untuk skema ${skema}.`
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
            title="Upload Laporan"
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
                    ? 'border-brand-500 bg-brand-50'
                    : 'border-border bg-surface-elevated hover:border-brand-300 hover:bg-surface-sunken'
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
              <div className="flex items-center gap-3 rounded-2xl border border-border bg-surface-sunken p-4">
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
                Lengkapi semua kolom wajib untuk melanjutkan
              </p>
            )}
          </div>
        </form>
      </main>
    </div>
  );
}
