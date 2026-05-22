'use client';

import { useEffect, useState } from 'react';
import { API_URL } from './constants';

// ─── Types ────────────────────────────────────────────────────────────────────

type Msg = { level: string; text: string };
type ModuleResult = {
  status?: string;
  messages?: Msg[];
  message?: string;
};

type UploadRecord = {
  submission_id: string;
  original_filename: string;
  schema_code: string;
  report_type: string;
  status: string;
  completed_at: string | null;
  overall_status: string | null;
  fail_count: number;
  warn_count: number;
  results: Record<string, ModuleResult>;
};

// ─── Constants ────────────────────────────────────────────────────────────────

const MODULE_LABELS: Record<string, string> = {
  structure:      'Struktur Dokumen',
  physical_sheet: 'Lembar Fisik',
  format:         'Format Penulisan',
  page_numbering: 'Penomoran Halaman',
  budget:         'Anggaran',
  reference:      'Daftar Pustaka',
  luaran:         'Luaran',
  lampiran:       'Lampiran',
  biodata_date:   'Tanggal Biodata',
  ai_front_matter:'Front Matter',
};

const REPORT_LABELS: Record<string, string> = {
  PROPOSAL:           'Proposal',
  PROGRESS_REPORT:    'Lap. Kemajuan',
  FINAL_REPORT:       'Lap. Akhir',
  SCIENTIFIC_ARTICLE: 'Artikel Ilmiah',
};

// ─── Helpers ──────────────────────────────────────────────────────────────────

function getMessages(mod: ModuleResult): Msg[] {
  if (Array.isArray(mod.messages)) return mod.messages;
  if (typeof mod.message === 'string' && mod.message.trim())
    return [{ level: 'error', text: mod.message }];
  return [];
}

function isSummaryLine(text: string): boolean {
  return (
    /pelanggaran terdeteksi/.test(text) ||
    /^[a-z_]+: \d+ pelanggaran$/.test(text.trim()) ||
    /^[a-z_]+: OK$/.test(text.trim())
  );
}

function fmtDate(iso: string | null): string {
  if (!iso) return '—';
  const d = new Date(iso);
  return d.toLocaleDateString('id-ID', {
    day: '2-digit', month: 'short', year: 'numeric',
    hour: '2-digit', minute: '2-digit',
  });
}

// ─── Sub-components ───────────────────────────────────────────────────────────

function StatusBadge({ status }: { status: string | null }) {
  if (!status) return null;
  const map: Record<string, string> = {
    pass:    'bg-emerald-100 text-emerald-700 border-emerald-200',
    fail:    'bg-red-100 text-red-700 border-red-200',
    warning: 'bg-amber-100 text-amber-700 border-amber-200',
  };
  const label: Record<string, string> = { pass: 'Lulus', fail: 'Perlu Perbaikan', warning: 'Peringatan' };
  const cls = map[status] ?? 'bg-gray-100 text-gray-600 border-gray-200';
  return (
    <span className={`rounded-full border px-2.5 py-0.5 font-mono text-[11px] font-semibold ${cls}`}>
      {label[status] ?? status}
    </span>
  );
}

function ModuleSection({ modKey, mod }: { modKey: string; mod: ModuleResult }) {
  const msgs = getMessages(mod).filter(
    (m) => (m.level === 'fail' || m.level === 'error' || m.level === 'warning') && !isSummaryLine(m.text),
  );
  if (msgs.length === 0) return null;

  const failMsgs = msgs.filter((m) => m.level === 'fail' || m.level === 'error');
  const warnMsgs = msgs.filter((m) => m.level === 'warning');

  return (
    <div>
      <div className="mb-1.5 flex items-center gap-2">
        <span className="text-xs font-semibold uppercase tracking-wider text-foreground-subtle">
          {MODULE_LABELS[modKey] ?? modKey}
        </span>
        {failMsgs.length > 0 && (
          <span className="rounded bg-red-100 px-1.5 py-0.5 font-mono text-[10px] font-semibold text-red-700">
            {failMsgs.length} error
          </span>
        )}
        {warnMsgs.length > 0 && (
          <span className="rounded bg-amber-100 px-1.5 py-0.5 font-mono text-[10px] font-semibold text-amber-700">
            {warnMsgs.length} warn
          </span>
        )}
      </div>
      <ul className="space-y-1">
        {msgs.map((m, i) => {
          const isFail = m.level === 'fail' || m.level === 'error';
          // Strip leading [Lokasi] prefix for compact display
          const cleaned = m.text.replace(/^\[([^\]]+)\]\s*/, '').replace(/^\s*•\s*/, '').trim();
          return (
            <li
              key={i}
              className={`flex items-start gap-2 rounded-lg px-3 py-2 text-xs leading-relaxed ${
                isFail ? 'bg-red-50/70 text-red-800' : 'bg-amber-50/70 text-amber-800'
              }`}
            >
              <span className={`mt-0.5 h-1.5 w-1.5 shrink-0 rounded-full ${isFail ? 'bg-red-400' : 'bg-amber-400'}`} />
              {cleaned}
            </li>
          );
        })}
      </ul>
    </div>
  );
}

function AccordionItem({ record }: { record: UploadRecord }) {
  const [open, setOpen] = useState(false);

  const hasResults = record.status === 'completed' && record.overall_status;
  const moduleKeys = Object.keys(record.results).filter((k) => {
    const msgs = getMessages(record.results[k]);
    return msgs.some((m) => m.level === 'fail' || m.level === 'error' || m.level === 'warning') &&
           msgs.some((m) => !isSummaryLine(m.text));
  });

  return (
    <div className="overflow-hidden rounded-2xl border border-white/50 bg-white/50 backdrop-blur">
      {/* Row header */}
      <button
        type="button"
        onClick={() => hasResults && setOpen((o) => !o)}
        className={`flex w-full items-center gap-3 px-4 py-3.5 text-left transition ${
          hasResults ? 'hover:bg-white/60' : 'cursor-default'
        }`}
      >
        {/* Icon */}
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-brand-100 text-brand-600">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="h-4 w-4">
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
            <polyline points="14 2 14 8 20 8" />
          </svg>
        </div>

        {/* Main info */}
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-semibold text-foreground">{record.original_filename}</p>
          <p className="mt-0.5 text-xs text-foreground-muted">
            {record.schema_code} · {REPORT_LABELS[record.report_type] ?? record.report_type} · {fmtDate(record.completed_at)}
          </p>
        </div>

        {/* Counts + status */}
        <div className="flex shrink-0 items-center gap-2">
          {record.fail_count > 0 && (
            <span className="rounded-full bg-red-100 px-2 py-0.5 font-mono text-[11px] font-semibold text-red-700">
              {record.fail_count} error
            </span>
          )}
          {record.warn_count > 0 && (
            <span className="rounded-full bg-amber-100 px-2 py-0.5 font-mono text-[11px] font-semibold text-amber-700">
              {record.warn_count} warn
            </span>
          )}
          <StatusBadge status={record.overall_status} />

          {hasResults && (
            <svg
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2.5"
              strokeLinecap="round"
              strokeLinejoin="round"
              className={`h-4 w-4 shrink-0 text-foreground-muted transition-transform ${open ? 'rotate-180' : ''}`}
            >
              <polyline points="6 9 12 15 18 9" />
            </svg>
          )}
        </div>
      </button>

      {/* Accordion body */}
      {open && hasResults && (
        <div className="border-t border-white/50 bg-white/30 px-4 pb-5 pt-4">
          {moduleKeys.length === 0 ? (
            <p className="text-center text-sm text-emerald-700">Semua modul lulus — tidak ada kesalahan.</p>
          ) : (
            <div className="space-y-5">
              {moduleKeys.map((k) => (
                <ModuleSection key={k} modKey={k} mod={record.results[k]} />
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ─── Main component ───────────────────────────────────────────────────────────

type Props = {
  adminId: string;
};

export function UploadHistoryPanel({ adminId }: Props) {
  const [records, setRecords] = useState<UploadRecord[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  async function fetchUploads() {
    setLoading(true);
    setError('');
    try {
      const res = await fetch(`${API_URL}/api/admin/uploads?admin_id=${encodeURIComponent(adminId)}`);
      const data = await res.json();
      if (!res.ok) {
        setError(typeof data?.detail === 'string' ? data.detail : 'Gagal memuat data');
        return;
      }
      setRecords(data.uploads as UploadRecord[]);
    } catch (err) {
      setError(`Tidak bisa terhubung ke server: ${err instanceof Error ? err.message : String(err)}`);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void fetchUploads();
  }, [adminId]);

  return (
    <div className="glass-surface rounded-[1.5rem] p-6 sm:p-8">
      <div className="mb-5 flex items-center justify-between">
        <div>
          <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-foreground-subtle">Admin</p>
          <h2 className="mt-0.5 text-lg font-semibold text-foreground">Riwayat Upload</h2>
        </div>
        <button
          type="button"
          onClick={fetchUploads}
          disabled={loading}
          className="inline-flex items-center gap-1.5 rounded-xl border border-black/10 px-3 py-2 text-xs font-medium text-foreground-muted transition hover:border-brand-200 hover:text-foreground disabled:opacity-50"
        >
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" className={`h-3.5 w-3.5 ${loading ? 'animate-spin' : ''}`}>
            <polyline points="1 4 1 10 7 10" />
            <path d="M3.51 15a9 9 0 1 0 .49-3.51" />
          </svg>
          Refresh
        </button>
      </div>

      {error && (
        <div className="mb-4 rounded-2xl border border-red-200 bg-red-50/80 p-3.5 text-sm font-medium text-red-700">
          {error}
        </div>
      )}

      {loading && records.length === 0 ? (
        <div className="flex items-center justify-center py-16">
          <svg className="h-6 w-6 animate-spin text-brand-500" viewBox="0 0 24 24" fill="none">
            <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" opacity="0.25" />
            <path d="M12 2a10 10 0 0 1 10 10" stroke="currentColor" strokeWidth="3" strokeLinecap="round" />
          </svg>
        </div>
      ) : records.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-white/60 bg-white/40 py-14 text-center">
          <p className="text-sm font-semibold text-foreground-muted">Belum ada upload yang tercatat.</p>
        </div>
      ) : (
        <div className="space-y-2">
          {records.map((r) => (
            <AccordionItem key={r.submission_id} record={r} />
          ))}
        </div>
      )}
    </div>
  );
}
