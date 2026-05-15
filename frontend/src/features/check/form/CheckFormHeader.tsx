import Link from 'next/link';
import { CheckFormStepBar, CheckFormStepDot } from './CheckFormStepIndicator';

type Props = {
  tokenPreview: string;
};

export function CheckFormHeader({ tokenPreview }: Props) {
  return (
    <header className="mb-6">
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
              <rect x="3" y="11" width="18" height="11" rx="2" />
              <path d="M7 11V7a5 5 0 0 1 10 0v4" />
            </svg>
          </span>
          <div className="flex flex-col leading-tight">
            <span className="text-[10px] font-medium uppercase tracking-wide text-foreground-subtle">
              Token aktif
            </span>
            <span className="font-mono text-xs font-semibold text-foreground">{tokenPreview}</span>
          </div>
        </div>
      </div>

      <div className="mt-6 flex items-center gap-2">
        <CheckFormStepDot state="done" label="Token" />
        <CheckFormStepBar state="active" />
        <CheckFormStepDot state="active" label="Form" />
        <CheckFormStepBar state="todo" />
        <CheckFormStepDot state="todo" label="Hasil" />
      </div>
    </header>
  );
}
