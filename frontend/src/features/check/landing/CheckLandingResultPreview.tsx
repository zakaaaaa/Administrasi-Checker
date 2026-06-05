'use client';

import { useEffect, useState } from 'react';

type Phase = 'upload' | 'progress' | 'result';

// Durasi tiap fase (ms). Hasil ditahan lebih lama agar sempat dibaca.
const UPLOAD_MS = 2000;
const PROGRESS_MS = 3000;
const RESULT_MS = 5000;

type PreviewRow = {
  level: 'fail' | 'warn';
  page: string;
  text: string;
  mod: string;
};

const PREVIEW_ROWS: PreviewRow[] = [
  { level: 'fail', page: 'Hal 11', text: 'Margin tidak sesuai aturan PKM (kiri, kanan)', mod: 'Format Penulisan' },
  { level: 'fail', page: 'Hal 4', text: 'Lampiran biodata dosen pembimbing belum ditemukan', mod: 'Lampiran' },
  { level: 'warn', page: 'Hal 12', text: 'Ukuran huruf tidak 12 pt', mod: 'Format Penulisan' },
  { level: 'warn', page: '—', text: 'Urutan daftar pustaka belum alfabetis', mod: 'Daftar Pustaka' },
];

const PROGRESS_STAGES = [
  { label: 'Membaca struktur dokumen', at: 0 },
  { label: 'Memeriksa format & penomoran', at: 30 },
  { label: 'Memindai lampiran (OCR)', at: 55 },
  { label: 'Menyusun hasil', at: 92 },
];

function SeverityIcon({ fail, className = 'h-4 w-4' }: { fail: boolean; className?: string }) {
  const common = {
    viewBox: '0 0 24 24',
    fill: 'none',
    stroke: 'currentColor',
    strokeWidth: 2.2,
    strokeLinecap: 'round' as const,
    strokeLinejoin: 'round' as const,
  };
  return fail ? (
    <svg {...common} className={`${className} shrink-0 text-red-500`}>
      <circle cx="12" cy="12" r="9" />
      <line x1="15" y1="9" x2="9" y2="15" />
      <line x1="9" y1="9" x2="15" y2="15" />
    </svg>
  ) : (
    <svg {...common} className={`${className} shrink-0 text-amber-500`}>
      <path d="M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
      <line x1="12" y1="9" x2="12" y2="13" />
      <line x1="12" y1="17" x2="12.01" y2="17" />
    </svg>
  );
}

function Spinner({ className = 'h-4 w-4' }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" className={`${className} animate-spin text-brand-500`}>
      <circle cx="12" cy="12" r="9" stroke="currentColor" strokeWidth="3" opacity="0.2" />
      <path d="M21 12a9 9 0 0 0-9-9" stroke="currentColor" strokeWidth="3" strokeLinecap="round" />
    </svg>
  );
}

function CheckMark({ className = 'h-3 w-3' }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" className={className}>
      <polyline points="20 6 9 17 4 12" />
    </svg>
  );
}

function UploadPhase() {
  return (
    <div className="flex min-h-[260px] flex-col items-center justify-center rounded-xl border-2 border-dashed border-border bg-surface-sunken px-6 py-10 text-center">
      <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-brand-100 text-brand-600">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="h-6 w-6">
          <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
          <polyline points="17 8 12 3 7 8" />
          <line x1="12" y1="3" x2="12" y2="15" />
        </svg>
      </div>
      <p className="mt-3 flex items-center gap-2 text-sm font-medium text-foreground">
        <Spinner className="h-4 w-4" />
        Mengunggah Proposal-PKM-KC.docx…
      </p>
      <p className="mt-1 text-xs text-foreground-subtle">Format .docx · PKM-KC</p>
      <div className="mt-4 h-1.5 w-44 overflow-hidden rounded-full bg-surface-elevated">
        <div className="h-full w-2/3 animate-pulse rounded-full bg-brand-500" />
      </div>
    </div>
  );
}

function ProgressPhase({ progress }: { progress: number }) {
  let activeIdx = 0;
  for (let i = 0; i < PROGRESS_STAGES.length; i++) {
    if (progress >= PROGRESS_STAGES[i].at) activeIdx = i;
  }
  return (
    <div className="flex min-h-[260px] flex-col justify-center px-1">
      <div className="flex items-baseline justify-between">
        <p className="text-sm font-medium text-foreground">Memeriksa dokumen…</p>
        <span className="font-display text-2xl font-bold tabular-nums text-brand-600">{progress}%</span>
      </div>
      <div className="mt-3 h-2 w-full overflow-hidden rounded-full bg-surface-sunken">
        <div className="h-full rounded-full bg-brand-500 transition-[width] duration-150 ease-out" style={{ width: `${progress}%` }} />
      </div>
      <ul className="mt-5 space-y-2.5">
        {PROGRESS_STAGES.map((stage, i) => {
          const done = i < activeIdx;
          const active = i === activeIdx;
          return (
            <li key={stage.label} className="flex items-center gap-3">
              <span
                className={`flex h-5 w-5 shrink-0 items-center justify-center rounded-full ${
                  done ? 'bg-brand-500 text-white' : active ? 'bg-brand-50' : 'bg-surface-sunken'
                }`}
              >
                {done ? <CheckMark /> : active ? <Spinner className="h-3.5 w-3.5" /> : null}
              </span>
              <span className={`text-sm ${done || active ? 'text-foreground' : 'text-foreground-subtle'} ${active ? 'font-medium' : ''}`}>
                {stage.label}
              </span>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

function ResultPhase() {
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-2.5">
        <span className="rounded-lg border border-red-200 bg-red-50 px-3 py-1.5 text-sm font-semibold text-red-700">
          2 harus diperbaiki
        </span>
        <span className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-1.5 text-sm font-semibold text-amber-700">
          2 perlu diperhatikan
        </span>
      </div>
      <div className="space-y-2">
        {PREVIEW_ROWS.map((row, i) => {
          const isFail = row.level === 'fail';
          const rowCls = isFail ? 'border-red-100 border-l-red-400 bg-red-50/60' : 'border-amber-100 border-l-amber-400 bg-amber-50/60';
          const textCls = isFail ? 'text-red-900' : 'text-amber-900';
          const tagCls = isFail ? 'bg-red-100 text-red-700' : 'bg-amber-100 text-amber-700';
          const pageCls = isFail ? 'text-red-400' : 'text-amber-400';
          return (
            <div key={i} className={`flex items-center gap-3 rounded-xl border border-l-4 px-3.5 py-2.5 ${rowCls}`}>
              <SeverityIcon fail={isFail} />
              {row.page !== '—' && (
                <span className={`w-14 shrink-0 font-mono text-xs font-medium ${pageCls}`}>{row.page}</span>
              )}
              <p className={`flex-1 text-sm font-medium leading-snug ${textCls}`}>{row.text}</p>
              <span className={`hidden shrink-0 rounded px-2 py-0.5 font-mono text-[10px] font-semibold sm:inline ${tagCls}`}>
                {row.mod}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

export function CheckLandingResultPreview() {
  const [phase, setPhase] = useState<Phase>('upload');
  const [progress, setProgress] = useState(0);

  useEffect(() => {
    let cancelled = false;
    const timers: ReturnType<typeof setTimeout>[] = [];
    let progressInterval: ReturnType<typeof setInterval> | null = null;

    const clearProgress = () => {
      if (progressInterval) {
        clearInterval(progressInterval);
        progressInterval = null;
      }
    };

    function runCycle() {
      if (cancelled) return;
      setPhase('upload');
      setProgress(0);

      timers.push(
        setTimeout(() => {
          if (cancelled) return;
          setPhase('progress');
          const start = Date.now();
          progressInterval = setInterval(() => {
            const pct = Math.min(100, Math.round(((Date.now() - start) / PROGRESS_MS) * 100));
            setProgress(pct);
            if (pct >= 100) clearProgress();
          }, 60);

          timers.push(
            setTimeout(() => {
              if (cancelled) return;
              clearProgress();
              setProgress(100);
              setPhase('result');
              timers.push(setTimeout(runCycle, RESULT_MS));
            }, PROGRESS_MS),
          );
        }, UPLOAD_MS),
      );
    }

    runCycle();

    return () => {
      cancelled = true;
      timers.forEach(clearTimeout);
      clearProgress();
    };
  }, []);

  const statusLabel =
    phase === 'upload' ? 'Mengunggah…' : phase === 'progress' ? 'Memeriksa…' : 'Selesai dicek';
  const statusDone = phase === 'result';

  return (
    <section id="preview" className="relative px-4 py-16 sm:px-6 sm:py-20">
      <div className="mx-auto max-w-5xl">
        <div className="mx-auto max-w-2xl text-center">
          <h2
            data-reveal
            data-reveal-delay="1"
            className="mt-3 font-display text-2xl font-bold leading-tight text-foreground sm:text-3xl"
          >
            Temuan yang jelas, langsung bisa ditindaklanjuti.
          </h2>
          <p
            data-reveal
            data-reveal-delay="2"
            className="mx-auto mt-3 max-w-xl text-sm leading-relaxed text-foreground-muted sm:text-base"
          >
            Setiap masalah dikelompokkan per bagian laporan dan ditandai lokasinya, lengkap dengan
            tingkat prioritas — mana yang wajib diperbaiki, mana yang sekadar perlu diperhatikan.
          </p>
        </div>

        <div
          data-reveal
          data-reveal-delay="3"
          className="check-landing-glass-card mx-auto mt-10 max-w-3xl overflow-hidden rounded-2xl"
        >
          {/* Window chrome */}
          <div className="flex items-center gap-3 border-b border-border bg-surface-sunken px-4 py-3">
            <div className="flex gap-1.5">
              <span className="h-3 w-3 rounded-full bg-red-300" />
              <span className="h-3 w-3 rounded-full bg-amber-300" />
              <span className="h-3 w-3 rounded-full bg-emerald-300" />
            </div>
            <span className="font-mono text-xs text-foreground-muted">Proposal-PKM-KC.docx</span>
            <span
              className={`ml-auto inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-[11px] font-semibold ${
                statusDone ? 'bg-emerald-100 text-emerald-700' : 'bg-brand-100 text-brand-700'
              }`}
            >
              <span className={`h-1.5 w-1.5 rounded-full ${statusDone ? 'bg-emerald-500' : 'bg-brand-500 animate-pulse'}`} />
              {statusLabel}
            </span>
          </div>

          {/* Body — konten berganti per fase (fade saat berganti) */}
          <div className="min-h-[320px] p-5 sm:p-6">
            <div key={phase} className="animate-fade-up">
              {phase === 'upload' && <UploadPhase />}
              {phase === 'progress' && <ProgressPhase progress={progress} />}
              {phase === 'result' && <ResultPhase />}
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
