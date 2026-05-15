import type { ReportOption } from './checkFormConstants';

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
          <svg
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="3.5"
            strokeLinecap="round"
            strokeLinejoin="round"
            className="h-2.5 w-2.5"
          >
            <polyline points="20 6 9 17 4 12" />
          </svg>
        )}
      </span>
      <div className="min-w-0 flex-1">
        <p className="text-[11px] font-medium uppercase tracking-wide text-foreground-subtle">{label}</p>
        <p
          className={`text-sm font-semibold ${muted ? 'text-foreground-muted' : 'text-foreground'} ${truncate ? 'truncate' : ''} ${mono ? 'font-mono' : ''}`}
        >
          {value}
        </p>
      </div>
    </li>
  );
}

type Props = {
  tokenPreview: string;
  skema: string;
  selectedReport: ReportOption;
  file: File | null;
};

export function CheckFormSidebar({ tokenPreview, skema, selectedReport, file }: Props) {
  return (
    <aside className="space-y-4 lg:sticky lg:top-6 lg:h-fit">
      <div className="glass-surface rounded-[1.5rem] p-5">
        <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-foreground-subtle">Ringkasan</p>
        <h2 className="mt-1 text-lg font-semibold text-foreground">Progress pengisian</h2>
        <ul className="mt-4 space-y-2.5">
          <ChecklistRow done label="Token diisi" value={tokenPreview} mono />
          <ChecklistRow done label="Skema PKM" value={skema} />
          <ChecklistRow done label="Jenis Laporan" value={selectedReport.label} />
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
            <svg
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2.5"
              strokeLinecap="round"
              strokeLinejoin="round"
              className="h-3.5 w-3.5 text-brand-600"
            >
              <circle cx="12" cy="12" r="10" />
              <line x1="12" y1="16" x2="12" y2="12" />
              <line x1="12" y1="8" x2="12.01" y2="8" />
            </svg>
          </span>
          <h3 className="text-sm font-semibold text-foreground">Tips singkat</h3>
        </div>
        <ul className="mt-3 space-y-2 text-xs text-foreground-muted">
          <li>
            • File <strong>harus .docx</strong> agar parser dapat membaca struktur dokumen.
          </li>
          <li>• Pastikan halaman <strong>Daftar Isi</strong> sudah ter-update sebelum unggah.</li>
          <li>• Data pendanaan dibaca otomatis dari isi dokumen.</li>
          <li>• Proses memakan ~1–2 menit, jangan tutup tab browser.</li>
        </ul>
      </div>
    </aside>
  );
}
