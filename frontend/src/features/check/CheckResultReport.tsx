import { CheckResultsView } from './CheckResultsView';
import type { CheckResults } from './types';

export type CheckResultReportProps = {
  result: CheckResults;
  sourceFileName?: string;
  schemaLabel?: string;
  reportLabel?: string;
  exportMode?: boolean;
};

/** The screen and downloaded report share their content and presentation. */
export function CheckResultReport({
  result, sourceFileName, schemaLabel, reportLabel, exportMode = false,
}: CheckResultReportProps) {
  const subtitle = [schemaLabel, reportLabel].filter(Boolean).join(' · ');

  return (
    <div data-check-result-report>
      <div className="mb-6" data-pdf-keep data-pdf-heading>
        <p className="font-mono text-xs uppercase tracking-[0.18em] text-foreground-subtle">
          Hasil Pengecekan
        </p>
        <h1 className={`mt-1.5 break-words font-semibold tracking-tight text-foreground ${exportMode ? 'text-3xl' : 'text-2xl sm:text-3xl'}`}>
          <span className="font-display text-gradient-brand">{sourceFileName ?? 'Dokumen'}</span>
        </h1>
        {subtitle && <p className="mt-1 text-sm text-foreground-muted">{subtitle}</p>}
      </div>
      <CheckResultsView result={result} exportMode={exportMode} />
    </div>
  );
}
