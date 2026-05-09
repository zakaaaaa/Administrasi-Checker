'use client';

import { ChangeEvent, DragEvent, FormEvent, useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import type { CheckResults } from '@/features/check/types';

type Laporan = 'Proposal' | 'Laporan Kemajuan' | 'Laporan Akhir' | 'Artikel Ilmiah';
type SkemaCode = 'PKM-KC' | 'PKM-K' | 'PKM-KI' | 'PKM-PI' | 'PKM-RE';

const LAPORAN_OPTIONS: { value: Laporan; label: string; desc: string }[] = [
  { value: 'Proposal', label: 'Proposal', desc: 'Pengajuan awal kegiatan' },
  { value: 'Laporan Kemajuan', label: 'Laporan Kemajuan', desc: 'Update progress mid-term' },
  { value: 'Laporan Akhir', label: 'Laporan Akhir', desc: 'Hasil akhir kegiatan' },
  { value: 'Artikel Ilmiah', label: 'Artikel Ilmiah', desc: 'Publikasi karya tulis' },
];

const SKEMA_OPTIONS: { value: SkemaCode; label: string; desc: string }[] = [
  { value: 'PKM-KC', label: 'PKM-KC', desc: 'Karsa Cipta' },
  { value: 'PKM-K', label: 'PKM-K', desc: 'Kewirausahaan' },
  { value: 'PKM-KI', label: 'PKM-KI', desc: 'Karya Inovatif' },
  { value: 'PKM-PI', label: 'PKM-PI', desc: 'Penerapan IPTEK' },
  { value: 'PKM-RE', label: 'PKM-RE', desc: 'Riset Eksakta' },
];

const LAPORAN_TO_CODE: Record<Laporan, string> = {
  'Proposal': 'PROPOSAL',
  'Laporan Kemajuan': 'PROGRESS_REPORT',
  'Laporan Akhir': 'FINAL_REPORT',
  'Artikel Ilmiah': 'SCIENTIFIC_ARTICLE',
};

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';
const LAST_RESULT_STORAGE_KEY = 'last_check_result_v1';
const MAX_FILE_MB = 25;

function formatRupiah(value: string): string {
  const digits = value.replace(/\D/g, '');
  if (!digits) return '';
  return Number(digits).toLocaleString('id-ID');
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
}

export default function NewCheckFormPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const token = searchParams.get('token')?.trim() ?? '';

  const [laporan, setLaporan] = useState<Laporan>('Proposal');
  const [skema, setSkema] = useState<SkemaCode>('PKM-KC');
  const [danaBelmawa, setDanaBelmawa] = useState('');
  const [danaPt, setDanaPt] = useState('');
  const [file, setFile] = useState<File | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [errorMsg, setErrorMsg] = useState('');
  const [fileError, setFileError] = useState('');

  const totalDana = useMemo(() => {
    const belmawa = Number(danaBelmawa.replace(/\D/g, '') || 0);
    const pt = Number(danaPt.replace(/\D/g, '') || 0);
    return belmawa + pt;
  }, [danaBelmawa, danaPt]);

  const isFormReady = Boolean(token && file && !fileError);

  useEffect(() => {
    if (!token) {
      router.replace('/check/new');
    }
  }, [token, router]);

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
    const f = event.target.files?.[0] ?? null;
    handleFile(f);
  }

  function onDrop(event: DragEvent<HTMLLabelElement>) {
    event.preventDefault();
    setIsDragging(false);
    const f = event.dataTransfer.files?.[0] ?? null;
    handleFile(f);
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

    const fd = new FormData();
    fd.append('token', token);
    fd.append('competition', 'PKM');
    fd.append('report_type', LAPORAN_TO_CODE[laporan]);
    fd.append('schema_code', skema);
    fd.append('funding_belmawa', String(Number(danaBelmawa.replace(/\D/g, '') || 0)));
    fd.append('funding_pt', String(Number(danaPt.replace(/\D/g, '') || 0)));
    fd.append('funding_external', '0');
    fd.append('file', file);

    try {
      const res = await fetch(`${API_URL}/api/check`, { method: 'POST', body: fd });
      const data = await res.json();
      if (!res.ok) {
        const msg = data?.detail ?? `Error ${res.status}`;
        setErrorMsg(typeof msg === 'string' ? msg : JSON.stringify(msg));
        return;
      }
      const resultData = data as CheckResults;
      sessionStorage.setItem(LAST_RESULT_STORAGE_KEY, JSON.stringify(resultData));
      router.push('/check/new/result');
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      setErrorMsg(`Tidak bisa terhubung ke server: ${msg}`);
    } finally {
      setSubmitting(false);
    }
  }

  if (!token) return null;

  const tokenPreview = token.length > 14 ? `${token.slice(0, 8)}…${token.slice(-4)}` : token;

  return (
    <main className="relative mx-auto max-w-6xl px-4 pb-24 pt-8 sm:px-6">
      {/* HEADER */}
      <header className="mb-6">
        <Link
          href="/check/new"
          className="inline-flex items-center gap-1.5 text-sm font-medium text-foreground-muted transition hover:text-foreground"
        >
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" className="h-4 w-4">
            <line x1="19" y1="12" x2="5" y2="12" />
            <polyline points="12 19 5 12 12 5" />
          </svg>
          Kembali ke Beranda Input
        </Link>

        <div className="mt-4 flex flex-wrap items-end justify-between gap-4">
          <div>
            <p className="font-mono text-xs uppercase tracking-[0.18em] text-foreground-subtle">
              Langkah 2 dari 3 · Form Pengecekan
            </p>
            <h1 className="mt-2 text-3xl font-semibold tracking-tight text-foreground sm:text-4xl">
              Lengkapi data <span className="text-gradient-brand">laporan PKM</span>
            </h1>
            <p className="mt-2 max-w-2xl text-sm text-foreground-muted sm:text-base">
              Pilih jenis laporan, isi data pendanaan, dan unggah file <code className="rounded bg-brand-100/60 px-1.5 py-0.5 font-mono text-[0.85em]">.docx</code>.
              Pengecekan otomatis berjalan setelah submit.
            </p>
          </div>

          <div className="glass-surface-subtle flex items-center gap-2.5 rounded-full px-3.5 py-2">
            <span className="flex h-6 w-6 items-center justify-center rounded-full bg-brand-100">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" className="h-3.5 w-3.5 text-brand-600">
                <rect x="3" y="11" width="18" height="11" rx="2" />
                <path d="M7 11V7a5 5 0 0 1 10 0v4" />
              </svg>
            </span>
            <div className="flex flex-col leading-tight">
              <span className="text-[10px] font-medium uppercase tracking-wide text-foreground-subtle">Token aktif</span>
              <span className="font-mono text-xs font-semibold text-foreground">{tokenPreview}</span>
            </div>
          </div>
        </div>

        {/* Step bar */}
        <div className="mt-6 flex items-center gap-2">
          <StepDot state="done" label="Token" />
          <StepBar state="active" />
          <StepDot state="active" label="Form" />
          <StepBar state="todo" />
          <StepDot state="todo" label="Hasil" />
        </div>
      </header>

      <div className="grid gap-6 lg:grid-cols-[1fr_340px]">
        {/* FORM COLUMN */}
        <form onSubmit={onSubmit} className="space-y-5">
          {/* Section 1: Jenis Laporan */}
          <Section number={1} title="Jenis laporan" description="Pilih dokumen yang sedang Anda susun.">
            <div className="grid gap-3 sm:grid-cols-2">
              {LAPORAN_OPTIONS.map((opt) => (
                <SelectCard
                  key={opt.value}
                  active={laporan === opt.value}
                  onClick={() => setLaporan(opt.value)}
                  label={opt.label}
                  description={opt.desc}
                />
              ))}
            </div>
          </Section>

          {/* Section 2: Skema PKM */}
          <Section number={2} title="Skema PKM" description="Pilih satu skema sesuai usulan.">
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
              {SKEMA_OPTIONS.map((opt) => (
                <SelectCard
                  key={opt.value}
                  active={skema === opt.value}
                  onClick={() => setSkema(opt.value)}
                  label={opt.label}
                  description={opt.desc}
                  compact
                />
              ))}
            </div>
          </Section>

          {/* Section 3: Pendanaan */}
          <Section number={3} title="Pendanaan" description="Total dana yang diajukan dalam proposal.">
            <div className="grid gap-3 sm:grid-cols-2">
              <RupiahInput
                label="Dana Belmawa"
                hint="Sumber dari Direktorat Belmawa"
                value={danaBelmawa}
                onChange={(v) => setDanaBelmawa(formatRupiah(v))}
              />
              <RupiahInput
                label="Dana Perguruan Tinggi"
                hint="Pendamping dari kampus"
                value={danaPt}
                onChange={(v) => setDanaPt(formatRupiah(v))}
              />
            </div>
            <div className="mt-4 flex items-center justify-between rounded-2xl border border-brand-200/60 bg-brand-50/60 px-4 py-3">
              <span className="text-sm font-medium text-foreground-muted">Total dana</span>
              <span className="text-lg font-bold text-brand-700">
                Rp {totalDana.toLocaleString('id-ID')}
              </span>
            </div>
          </Section>

          {/* Section 4: Upload */}
          <Section number={4} title="Upload laporan" description="Hanya menerima file .docx, maksimal 25 MB.">
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
            {fileError && (
              <p className="mt-2 text-xs font-semibold text-red-600">{fileError}</p>
            )}
          </Section>

          {/* Submit */}
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
              disabled={submitting || !isFormReady}
              className="btn-liquid btn-liquid-primary w-full px-5 py-3.5 text-base font-semibold disabled:cursor-not-allowed disabled:opacity-50"
            >
              {submitting ? (
                <>
                  <svg className="h-4 w-4 animate-spin" viewBox="0 0 24 24" fill="none">
                    <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" opacity="0.25" />
                    <path d="M12 2a10 10 0 0 1 10 10" stroke="currentColor" strokeWidth="3" strokeLinecap="round" />
                  </svg>
                  Memproses laporan… (1–2 menit)
                </>
              ) : (
                <>
                  Submit & Mulai Pengecekan
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" className="h-4 w-4">
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

        {/* SIDEBAR */}
        <aside className="space-y-4 lg:sticky lg:top-6 lg:h-fit">
          <div className="glass-surface rounded-[1.5rem] p-5">
            <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-foreground-subtle">
              Ringkasan
            </p>
            <h2 className="mt-1 text-lg font-semibold text-foreground">Progress pengisian</h2>

            <ul className="mt-4 space-y-2.5">
              <ChecklistRow done label="Token diisi" value={tokenPreview} mono />
              <ChecklistRow done label="Jenis laporan" value={laporan} />
              <ChecklistRow done label="Skema PKM" value={skema} />
              <ChecklistRow
                done={totalDana > 0}
                label="Pendanaan"
                value={totalDana > 0 ? `Rp ${totalDana.toLocaleString('id-ID')}` : 'Opsional'}
                muted={totalDana === 0}
              />
              <ChecklistRow
                done={Boolean(file)}
                label="File laporan"
                value={file?.name ?? 'Belum dipilih'}
                truncate
              />
            </ul>
          </div>

          <div className="glass-surface-subtle rounded-[1.5rem] p-5">
            <div className="flex items-center gap-2">
              <span className="flex h-6 w-6 items-center justify-center rounded-full bg-brand-100">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" className="h-3.5 w-3.5 text-brand-600">
                  <circle cx="12" cy="12" r="10" />
                  <line x1="12" y1="16" x2="12" y2="12" />
                  <line x1="12" y1="8" x2="12.01" y2="8" />
                </svg>
              </span>
              <h3 className="text-sm font-semibold text-foreground">Tips singkat</h3>
            </div>
            <ul className="mt-3 space-y-2 text-xs text-foreground-muted">
              <li>• File <strong>harus .docx</strong> agar parser dapat membaca struktur dokumen.</li>
              <li>• Pastikan halaman <strong>Daftar Isi</strong> sudah ter-update sebelum unggah.</li>
              <li>• Proses memakan ~1–2 menit, jangan tutup tab browser.</li>
            </ul>
          </div>
        </aside>
      </div>
    </main>
  );
}

/* ---------- Sub-components ---------- */

function Section({
  number,
  title,
  description,
  children,
}: {
  number: number;
  title: string;
  description: string;
  children: React.ReactNode;
}) {
  return (
    <section className="glass-surface rounded-[1.5rem] p-5 sm:p-6">
      <div className="flex items-start gap-3">
        <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-brand-500 text-xs font-bold text-white shadow-sm">
          {number}
        </span>
        <div className="min-w-0">
          <h2 className="text-base font-semibold text-foreground sm:text-lg">{title}</h2>
          <p className="mt-0.5 text-xs text-foreground-muted sm:text-sm">{description}</p>
        </div>
      </div>
      <div className="mt-5">{children}</div>
    </section>
  );
}

function SelectCard({
  active,
  onClick,
  label,
  description,
  compact,
}: {
  active: boolean;
  onClick: () => void;
  label: string;
  description: string;
  compact?: boolean;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`relative flex flex-col items-start rounded-2xl border px-4 text-left transition ${
        compact ? 'py-3' : 'py-3.5'
      } ${
        active
          ? 'border-brand-500 bg-brand-50/80 shadow-[0_0_0_3px_rgba(249,115,22,0.12)]'
          : 'border-white/60 bg-white/40 hover:border-brand-200 hover:bg-white/65'
      }`}
    >
      <span className={`text-sm font-semibold ${active ? 'text-brand-700' : 'text-foreground'}`}>
        {label}
      </span>
      <span className="mt-0.5 text-xs text-foreground-muted">{description}</span>
      {active && (
        <span className="absolute right-3 top-3 flex h-5 w-5 items-center justify-center rounded-full bg-brand-500 text-white">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" className="h-3 w-3">
            <polyline points="20 6 9 17 4 12" />
          </svg>
        </span>
      )}
    </button>
  );
}

function RupiahInput({
  label,
  hint,
  value,
  onChange,
}: {
  label: string;
  hint: string;
  value: string;
  onChange: (v: string) => void;
}) {
  return (
    <label className="block">
      <span className="text-sm font-semibold text-foreground">{label}</span>
      <span className="mt-0.5 block text-xs text-foreground-muted">{hint}</span>
      <div className="relative mt-2">
        <span className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-sm font-semibold text-foreground-muted">
          Rp
        </span>
        <input
          type="text"
          inputMode="numeric"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder="0"
          className="glass-input w-full rounded-xl pl-10 pr-3 py-2.5 text-sm font-medium tabular-nums"
        />
      </div>
    </label>
  );
}

function StepDot({ state, label }: { state: 'done' | 'active' | 'todo'; label: string }) {
  const dot =
    state === 'done'
      ? 'bg-brand-500 text-white'
      : state === 'active'
        ? 'bg-white text-brand-600 ring-2 ring-brand-500'
        : 'bg-white/60 text-foreground-subtle ring-1 ring-white/70';
  const text = state === 'todo' ? 'text-foreground-subtle' : 'text-foreground';
  return (
    <div className="flex items-center gap-1.5">
      <span className={`flex h-5 w-5 items-center justify-center rounded-full text-[10px] font-bold ${dot}`}>
        {state === 'done' ? (
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" className="h-2.5 w-2.5">
            <polyline points="20 6 9 17 4 12" />
          </svg>
        ) : (
          ''
        )}
      </span>
      <span className={`text-xs font-medium ${text}`}>{label}</span>
    </div>
  );
}

function StepBar({ state }: { state: 'active' | 'todo' }) {
  return (
    <span
      className={`h-0.5 flex-1 max-w-[60px] rounded-full ${
        state === 'active' ? 'bg-brand-300' : 'bg-white/60'
      }`}
    />
  );
}

function ChecklistRow({
  done,
  label,
  value,
  muted,
  truncate,
  mono,
}: {
  done: boolean;
  label: string;
  value: string;
  muted?: boolean;
  truncate?: boolean;
  mono?: boolean;
}) {
  return (
    <li className="flex items-start gap-2.5">
      <span
        className={`mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded-full ${
          done ? 'bg-brand-500 text-white' : 'border border-foreground-subtle/30 bg-transparent'
        }`}
      >
        {done && (
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3.5" strokeLinecap="round" strokeLinejoin="round" className="h-2.5 w-2.5">
            <polyline points="20 6 9 17 4 12" />
          </svg>
        )}
      </span>
      <div className="min-w-0 flex-1">
        <p className="text-[11px] font-medium uppercase tracking-wide text-foreground-subtle">
          {label}
        </p>
        <p
          className={`text-sm font-semibold ${muted ? 'text-foreground-muted' : 'text-foreground'} ${
            truncate ? 'truncate' : ''
          } ${mono ? 'font-mono' : ''}`}
        >
          {value}
        </p>
      </div>
    </li>
  );
}
