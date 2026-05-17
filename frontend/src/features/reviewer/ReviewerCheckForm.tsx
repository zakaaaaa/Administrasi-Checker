'use client';

import type { ChangeEvent, DragEvent, FormEvent } from 'react';
import { useEffect, useState } from 'react';
import { CheckResultsView } from '@/features/check/CheckResultsView';
import type { CheckResults } from '@/features/check/types';
import { exportCheckResultPdf } from '@/features/check/exportCheckResultPdf';
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

type Props = {
  adminId: string;
  adminUsername: string;
  onLogout: () => void;
};

type ViewState = 'form' | 'submitting' | 'result';

export function ReviewerCheckForm({ adminId, adminUsername, onLogout }: Props) {
  const [skema, setSkema] = useState<SkemaCode>('PKM-KC');
  const [reportCode, setReportCode] = useState<ReportCode>('PROPOSAL');
  const [file, setFile] = useState<File | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [fileError, setFileError] = useState('');
  const [errorMsg, setErrorMsg] = useState('');
  const [view, setView] = useState<ViewState>('form');
  const [result, setResult] = useState<CheckResults | null>(null);

  useEffect(() => {
    const validCodes = SKEMA_LAPORAN_MAP[skema];
    if (!validCodes.includes(reportCode)) {
      setReportCode(validCodes[0]);
    }
  }, [skema, reportCode]);

  const availableReports = ALL_REPORTS.filter((r) => SKEMA_LAPORAN_MAP[skema].includes(r.code));
  const selectedReport = availableReports.find((r) => r.code === reportCode) ?? availableReports[0];
  const isFormReady = Boolean(file && !fileError);

  function handleFile(f: File | null) {
    setFileError('');
    setErrorMsg('');
    if (!f) { setFile(null); return; }
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
    if (!file) { setErrorMsg('File laporan belum diunggah.'); return; }

    setView('submitting');
    const fd = new FormData();
    fd.append('admin_id', adminId);
    fd.append('competition', 'PKM');
    fd.append('report_type', reportCode);
    fd.append('schema_code', skema);
    fd.append('file', file);

    try {
      const res = await fetch(`${API_URL}/api/reviewer/check`, { method: 'POST', body: fd });
      const data = await res.json();
      if (!res.ok) {
        if (res.status === 401) {
          onLogout();
          return;
        }
        const msg = data?.detail ?? `Error ${res.status}`;
        setErrorMsg(typeof msg === 'string' ? msg : JSON.stringify(msg));
        setView('form');
        return;
      }
      setResult(data as CheckResults);
      setView('result');
    } catch (err) {
      setErrorMsg(`Tidak bisa terhubung ke server: ${err instanceof Error ? err.message : String(err)}`);
      setView('form');
    }
  }

  function handleReset() {
    setFile(null);
    setFileError('');
    setErrorMsg('');
    setResult(null);
    setView('form');
  }

  return (
    <div className="relative min-h-screen">
      {/* Header */}
      <header className="sticky top-0 z-10 border-b border-black/8 bg-white/80 backdrop-blur-lg print:hidden">
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
                Reviewer Mode
              </p>
              <p className="text-sm font-semibold text-foreground">{adminUsername}</p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            {view === 'result' && result && (
              <button
                type="button"
                onClick={() => exportCheckResultPdf(result)}
                className="inline-flex items-center gap-1.5 rounded-xl bg-foreground px-3 py-2 text-xs font-semibold text-background transition hover:opacity-80 print:hidden"
              >
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="h-3.5 w-3.5">
                  <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                  <polyline points="7 10 12 15 17 10" />
                  <line x1="12" y1="15" x2="12" y2="3" />
                </svg>
                Export PDF
              </button>
            )}
            {view === 'result' && (
              <button
                type="button"
                onClick={handleReset}
                className="inline-flex items-center gap-1.5 rounded-xl border border-brand-300 bg-brand-50 px-3 py-2 text-xs font-semibold text-brand-700 transition hover:bg-brand-100"
              >
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" className="h-3.5 w-3.5">
                  <polyline points="1 4 1 10 7 10" />
                  <path d="M3.51 15a9 9 0 1 0 .49-3.51" />
                </svg>
                Cek Dokumen Lain
              </button>
            )}
            <button
              type="button"
              onClick={onLogout}
              className="rounded-xl border border-black/10 px-3 py-2 text-xs font-medium text-foreground-muted transition hover:border-red-200 hover:text-red-600"
            >
              Keluar
            </button>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-5xl px-4 pb-24 pt-8 sm:px-6">
        {view === 'submitting' && (
          <div className="flex flex-col items-center justify-center py-32 text-center">
            <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-brand-100">
              <svg className="h-6 w-6 animate-spin text-brand-600" viewBox="0 0 24 24" fill="none">
                <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" opacity="0.25" />
                <path d="M12 2a10 10 0 0 1 10 10" stroke="currentColor" strokeWidth="3" strokeLinecap="round" />
              </svg>
            </div>
            <p className="mt-4 text-base font-semibold text-foreground">Memproses dokumen…</p>
            <p className="mt-1 text-sm text-foreground-muted">Biasanya membutuhkan 1–2 menit</p>
          </div>
        )}

        {view === 'result' && result && (
          <div>
            <div className="mb-6">
              <p className="font-mono text-xs uppercase tracking-[0.18em] text-foreground-subtle">
                Hasil Pengecekan
              </p>
              <h1 className="mt-1.5 text-2xl font-semibold tracking-tight text-foreground sm:text-3xl">
                <span className="font-display text-gradient-brand">{file?.name ?? 'Dokumen'}</span>
              </h1>
              <p className="mt-1 text-sm text-foreground-muted">
                {skema} · {selectedReport.label}
              </p>
            </div>
            <CheckResultsView result={result} />
          </div>
        )}

        {view === 'form' && (
          <div>
            <div className="mb-6">
              <p className="font-mono text-xs uppercase tracking-[0.18em] text-foreground-subtle">
                Pengecekan Reviewer
              </p>
              <h1 className="mt-1.5 text-2xl font-semibold tracking-tight text-foreground sm:text-3xl">
                Cek Dokumen PKM
              </h1>
              <p className="mt-1 text-sm text-foreground-muted">
                Upload dokumen dan pilih skema untuk mulai pengecekan.
              </p>
            </div>

            <form onSubmit={onSubmit} className="space-y-5">
              <CheckFormSection number={1} title="Skema PKM" description="Pilih satu skema sesuai usulan.">
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
                    : `Pilih dokumen yang ingin dicek untuk skema ${skema}.`
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

              <CheckFormSection number={3} title="Upload Dokumen" description="Hanya menerima file .docx, maksimal 25 MB.">
                {!file ? (
                  <label
                    onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
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
                      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="h-6 w-6">
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
                      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="h-5 w-5">
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
                      onClick={() => { setFile(null); setFileError(''); }}
                      className="shrink-0 rounded-full p-2 text-foreground-muted transition hover:bg-red-50 hover:text-red-600"
                      aria-label="Hapus file"
                    >
                      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" className="h-4 w-4">
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
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" className="mt-0.5 h-4 w-4 shrink-0 text-red-600">
                      <circle cx="12" cy="12" r="10" />
                      <line x1="12" y1="8" x2="12" y2="12" />
                      <line x1="12" y1="16" x2="12.01" y2="16" />
                    </svg>
                    <p className="text-sm font-medium text-red-700">{errorMsg}</p>
                  </div>
                )}
                <button
                  type="submit"
                  disabled={!isFormReady}
                  className="btn-liquid btn-liquid-primary w-full px-5 py-3.5 text-base font-semibold disabled:cursor-not-allowed disabled:opacity-50"
                >
                  Mulai Pengecekan
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" className="h-4 w-4">
                    <line x1="5" y1="12" x2="19" y2="12" />
                    <polyline points="12 5 19 12 12 19" />
                  </svg>
                </button>
                {!isFormReady && (
                  <p className="mt-2.5 text-center text-xs text-foreground-muted">
                    Upload dokumen untuk melanjutkan
                  </p>
                )}
              </div>
            </form>
          </div>
        )}
      </main>
    </div>
  );
}
