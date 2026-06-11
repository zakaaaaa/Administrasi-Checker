'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import { CheckResultsView } from '@/features/check/CheckResultsView';
import { exportCheckResultPdf } from '@/features/check/exportCheckResultPdf';
import type { CheckResults, ModuleResult } from '@/features/check/types';
import { API_URL } from './constants';

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
  results: Record<string, ModuleResult | undefined>;
};

type UploadsResponse = {
  uploads: UploadRecord[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
};

const REPORT_LABELS: Record<string, string> = {
  PROPOSAL: 'Proposal',
  PROGRESS_REPORT: 'Lap. Kemajuan',
  FINAL_REPORT: 'Lap. Akhir',
  SCIENTIFIC_ARTICLE: 'Artikel Ilmiah',
};

const STATUS_LABELS: Record<string, string> = {
  pass: 'Lulus',
  fail: 'Perlu Perbaikan',
  warning: 'Peringatan',
};

function fmtDate(iso: string | null): string {
  if (!iso) return '-';
  const d = new Date(iso);
  return d.toLocaleDateString('id-ID', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

function toCheckResult(record: UploadRecord): CheckResults {
  return {
    submission_id: record.submission_id,
    status: record.status,
    overall_status: record.overall_status ?? record.status,
    results: record.results as CheckResults['results'],
  };
}

function StatusBadge({ status }: { status: string | null }) {
  if (!status) return null;
  const map: Record<string, string> = {
    pass: 'bg-emerald-100 text-emerald-700 border-emerald-200',
    fail: 'bg-red-100 text-red-700 border-red-200',
    warning: 'bg-amber-100 text-amber-700 border-amber-200',
  };
  const cls = map[status] ?? 'bg-gray-100 text-gray-600 border-gray-200';
  return (
    <span className={`rounded-full border px-2.5 py-0.5 font-mono text-[11px] font-semibold ${cls}`}>
      {STATUS_LABELS[status] ?? status}
    </span>
  );
}

function FileIcon() {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      className="h-4 w-4"
    >
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
      <polyline points="14 2 14 8 20 8" />
    </svg>
  );
}

function DownloadIcon() {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      className="h-3.5 w-3.5"
    >
      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
      <polyline points="7 10 12 15 17 10" />
      <line x1="12" y1="15" x2="12" y2="3" />
    </svg>
  );
}

function SearchIcon() {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      className="h-4 w-4"
    >
      <circle cx="11" cy="11" r="8" />
      <line x1="21" y1="21" x2="16.65" y2="16.65" />
    </svg>
  );
}

function ChevronDownIcon({ open }: { open: boolean }) {
  return (
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
  );
}

function UploadHistoryItem({ record }: { record: UploadRecord }) {
  const [open, setOpen] = useState(false);
  const hasResults = record.status === 'completed' && Boolean(record.overall_status);
  const checkResult = useMemo(() => toCheckResult(record), [record]);

  function toggleOpen() {
    if (!hasResults) return;
    setOpen((current) => !current);
  }

  function handleDownload() {
    if (!hasResults) return;
    exportCheckResultPdf(checkResult, record.original_filename);
  }

  return (
    <div className="overflow-hidden rounded-2xl border border-border bg-surface-elevated">
      <div className="flex flex-col gap-3 px-4 py-3.5 sm:flex-row sm:items-center">
        <button
          type="button"
          onClick={toggleOpen}
          disabled={!hasResults}
          className={`flex min-w-0 flex-1 items-center gap-3 rounded-xl text-left transition ${
            hasResults ? 'hover:text-brand-700' : 'cursor-default'
          }`}
        >
          <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-brand-100 text-brand-600">
            <FileIcon />
          </span>
          <span className="min-w-0 flex-1">
            <span className="block truncate text-sm font-semibold text-foreground">
              {record.original_filename}
            </span>
            <span className="mt-0.5 block text-xs text-foreground-muted">
              {record.schema_code} · {REPORT_LABELS[record.report_type] ?? record.report_type} · {fmtDate(record.completed_at)}
            </span>
          </span>
        </button>

        <div className="flex shrink-0 flex-wrap items-center gap-2 sm:justify-end">
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
            <button
              type="button"
              onClick={handleDownload}
              className="inline-flex h-9 items-center gap-1.5 rounded-lg border border-brand-200 bg-brand-50 px-3 text-xs font-semibold text-brand-700 transition hover:bg-brand-100"
            >
              <DownloadIcon />
              Download
            </button>
          )}
          {hasResults && (
            <button
              type="button"
              onClick={toggleOpen}
              aria-label={open ? 'Tutup hasil pengecekan' : 'Buka hasil pengecekan'}
              aria-expanded={open}
              className="inline-flex h-9 w-9 items-center justify-center rounded-lg border border-border bg-surface text-foreground-muted transition hover:border-brand-300 hover:bg-brand-50 hover:text-brand-700"
            >
              <ChevronDownIcon open={open} />
            </button>
          )}
        </div>
      </div>

      {open && hasResults && (
        <div className="border-t border-border bg-surface px-4 py-5 sm:px-5">
          <CheckResultsView result={checkResult} />
        </div>
      )}
    </div>
  );
}

type Props = {
  adminId: string;
};

export function UploadHistoryPanel({ adminId }: Props) {
  const [records, setRecords] = useState<UploadRecord[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [search, setSearch] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const [total, setTotal] = useState(0);
  const [totalPages, setTotalPages] = useState(1);

  const fetchUploads = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const params = new URLSearchParams({
        admin_id: adminId,
        page: String(page),
        page_size: String(pageSize),
      });
      if (debouncedSearch.trim()) params.set('q', debouncedSearch.trim());

      const res = await fetch(`${API_URL}/api/admin/uploads?${params.toString()}`);
      const data = await res.json() as Partial<UploadsResponse> & { detail?: unknown };
      if (!res.ok) {
        setError(typeof data?.detail === 'string' ? data.detail : 'Gagal memuat data');
        return;
      }
      const nextTotal = typeof data.total === 'number' ? data.total : 0;
      const nextTotalPages = typeof data.total_pages === 'number' ? Math.max(1, data.total_pages) : 1;
      setRecords(Array.isArray(data.uploads) ? data.uploads : []);
      setTotal(nextTotal);
      setTotalPages(nextTotalPages);
      if (nextTotal > 0 && page > nextTotalPages) {
        setPage(nextTotalPages);
      }
    } catch (err) {
      setError(`Tidak bisa terhubung ke server: ${err instanceof Error ? err.message : String(err)}`);
    } finally {
      setLoading(false);
    }
  }, [adminId, debouncedSearch, page, pageSize]);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void fetchUploads();
    }, 0);
    return () => window.clearTimeout(timer);
  }, [fetchUploads]);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      setDebouncedSearch(search.trim());
      setPage(1);
    }, 350);
    return () => window.clearTimeout(timer);
  }, [search]);

  const startRecord = total === 0 ? 0 : (page - 1) * pageSize + 1;
  const endRecord = total === 0 ? 0 : Math.min(total, startRecord + records.length - 1);
  const canPrev = page > 1 && !loading;
  const canNext = page < totalPages && !loading;

  return (
    <div className="glass-surface rounded-[1.5rem] p-6 sm:p-8">
      <div className="mb-5 flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-foreground-subtle">Admin</p>
          <h2 className="mt-0.5 text-lg font-semibold text-foreground">Riwayat Upload</h2>
        </div>

        <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
          <label className="relative block min-w-0 sm:w-72">
            <span className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-foreground-subtle">
              <SearchIcon />
            </span>
            <input
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Cari dokumen..."
              className="glass-input h-10 w-full rounded-xl pl-9 pr-3 text-sm text-foreground placeholder:text-foreground-subtle"
            />
          </label>
          <select
            value={pageSize}
            onChange={(event) => {
              setPageSize(Number(event.target.value));
              setPage(1);
            }}
            className="glass-input h-10 rounded-xl px-3 text-sm font-medium text-foreground"
            aria-label="Jumlah dokumen per halaman"
          >
            <option value={10}>10 / halaman</option>
            <option value={20}>20 / halaman</option>
            <option value={50}>50 / halaman</option>
          </select>
          <button
            type="button"
            onClick={fetchUploads}
            disabled={loading}
            className="inline-flex h-10 items-center justify-center gap-1.5 rounded-xl border border-border px-3 text-xs font-medium text-foreground-muted transition hover:border-brand-200 hover:text-foreground disabled:opacity-50"
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" className={`h-3.5 w-3.5 ${loading ? 'animate-spin' : ''}`}>
              <polyline points="1 4 1 10 7 10" />
              <path d="M3.51 15a9 9 0 1 0 .49-3.51" />
            </svg>
            Refresh
          </button>
        </div>
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
      ) : records.length === 0 && !debouncedSearch ? (
        <div className="rounded-2xl border border-dashed border-border bg-surface py-14 text-center">
          <p className="text-sm font-semibold text-foreground-muted">Belum ada upload yang tercatat.</p>
        </div>
      ) : records.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-border bg-surface py-14 text-center">
          <p className="text-sm font-semibold text-foreground-muted">Tidak ada dokumen yang cocok.</p>
        </div>
      ) : (
        <div className="space-y-4">
          <div className="space-y-2">
            {records.map((record) => (
              <UploadHistoryItem key={record.submission_id} record={record} />
            ))}
          </div>

          <div className="flex flex-col gap-3 border-t border-border pt-4 sm:flex-row sm:items-center sm:justify-between">
            <p className="text-xs font-medium text-foreground-muted">
              Menampilkan {startRecord}-{endRecord} dari {total} dokumen
            </p>
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => setPage((current) => Math.max(1, current - 1))}
                disabled={!canPrev}
                className="inline-flex h-9 items-center rounded-lg border border-border px-3 text-xs font-semibold text-foreground-muted transition hover:border-brand-300 hover:bg-brand-50 hover:text-brand-700 disabled:cursor-not-allowed disabled:opacity-45"
              >
                Sebelumnya
              </button>
              <span className="min-w-20 rounded-lg bg-surface px-3 py-2 text-center font-mono text-xs font-semibold text-foreground">
                {page} / {totalPages}
              </span>
              <button
                type="button"
                onClick={() => setPage((current) => Math.min(totalPages, current + 1))}
                disabled={!canNext}
                className="inline-flex h-9 items-center rounded-lg border border-border px-3 text-xs font-semibold text-foreground-muted transition hover:border-brand-300 hover:bg-brand-50 hover:text-brand-700 disabled:cursor-not-allowed disabled:opacity-45"
              >
                Berikutnya
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
