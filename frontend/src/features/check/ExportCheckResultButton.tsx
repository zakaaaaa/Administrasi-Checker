'use client';

import { useRef, useState } from 'react';
import type { CheckResultReportProps } from './CheckResultReport';
import { exportCheckResultPdf } from './exportCheckResultPdf';

type Props = Omit<CheckResultReportProps, 'exportMode'> & {
  label?: string;
  className?: string;
};

export function ExportCheckResultButton({
  result, sourceFileName, schemaLabel, reportLabel, label = 'Export PDF',
  className = 'inline-flex items-center gap-1.5 rounded-xl bg-brand-600 px-3 py-2 text-xs font-semibold text-white shadow-sm transition hover:bg-brand-700 print:hidden',
}: Props) {
  const busy = useRef(false);
  const [exporting, setExporting] = useState(false);
  const [error, setError] = useState('');

  async function download() {
    if (busy.current) return;
    busy.current = true;
    setExporting(true);
    setError('');
    try {
      await exportCheckResultPdf(result, sourceFileName, { schemaLabel, reportLabel });
    } catch {
      setError('PDF gagal dibuat. Silakan coba ekspor kembali.');
    } finally {
      busy.current = false;
      setExporting(false);
    }
  }

  return (
    <div className="relative">
      <button
        type="button"
        onClick={download}
        disabled={exporting}
        aria-busy={exporting}
        title="Unduh hasil pengecekan sebagai PDF"
        className={`${className} disabled:cursor-wait disabled:opacity-60`}
      >
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="h-3.5 w-3.5">
          <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
          <polyline points="7 10 12 15 17 10" />
          <line x1="12" y1="15" x2="12" y2="3" />
        </svg>
        <span aria-live="polite">{exporting ? 'Membuat PDF…' : label}</span>
      </button>
      {error && (
        <p role="alert" className="absolute right-0 top-full z-20 mt-2 w-64 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-800 shadow-sm">
          {error}
        </p>
      )}
    </div>
  );
}
