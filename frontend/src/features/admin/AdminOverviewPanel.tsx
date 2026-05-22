'use client';

import { useEffect, useState } from 'react';
import { API_URL } from './constants';

// ─── Types ────────────────────────────────────────────────────────────────────

type OverviewData = {
  total_tokens: number;
  tokens_used: number;
  tokens_unused: number;
  total_submissions: number;
  submissions_today: number;
  pass_count: number;
  fail_count: number;
  warning_count: number;
  avg_processing_seconds: number | null;
  by_schema: { schema_code: string; count: number }[];
  recent: {
    original_filename: string;
    schema_code: string;
    report_type: string;
    completed_at: string | null;
    overall_status: string | null;
  }[];
};

// ─── Helpers ──────────────────────────────────────────────────────────────────

const REPORT_LABELS: Record<string, string> = {
  PROPOSAL:           'Proposal',
  PROGRESS_REPORT:    'Lap. Kemajuan',
  FINAL_REPORT:       'Lap. Akhir',
  SCIENTIFIC_ARTICLE: 'Artikel Ilmiah',
};

function fmtDate(iso: string | null) {
  if (!iso) return '—';
  return new Date(iso).toLocaleDateString('id-ID', {
    day: '2-digit', month: 'short', year: 'numeric',
    hour: '2-digit', minute: '2-digit',
  });
}

function pct(part: number, total: number) {
  if (!total) return 0;
  return Math.round((part / total) * 100);
}

function fmtDuration(seconds: number | null): string {
  if (seconds === null) return '—';
  if (seconds < 60) return `${seconds} detik`;
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return s > 0 ? `${m} mnt ${s} dtk` : `${m} menit`;
}

// ─── Sub-components ───────────────────────────────────────────────────────────

function KpiCard({
  label,
  value,
  sub,
  color,
  icon,
}: {
  label: string;
  value: string | number;
  sub?: string;
  color: 'brand' | 'emerald' | 'red' | 'amber' | 'sky' | 'violet';
  icon: React.ReactNode;
}) {
  const bg: Record<string, string> = {
    brand:   'bg-brand-100/70 text-brand-600',
    emerald: 'bg-emerald-100 text-emerald-600',
    red:     'bg-red-100 text-red-600',
    amber:   'bg-amber-100 text-amber-600',
    sky:     'bg-sky-100 text-sky-600',
    violet:  'bg-violet-100 text-violet-600',
  };
  return (
    <div className="glass-surface rounded-2xl p-5">
      <div className="flex items-start gap-3">
        <div className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-xl ${bg[color]}`}>
          {icon}
        </div>
        <div className="min-w-0 flex-1">
          <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-foreground-subtle">{label}</p>
          <p className="mt-0.5 text-2xl font-semibold tracking-tight text-foreground">{value}</p>
          {sub && <p className="mt-0.5 text-xs text-foreground-muted">{sub}</p>}
        </div>
      </div>
    </div>
  );
}


function SchemaBar({ items }: { items: { schema_code: string; count: number }[] }) {
  if (!items.length) return <p className="text-sm text-foreground-muted">Belum ada data.</p>;
  const max = Math.max(...items.map((i) => i.count));
  return (
    <div className="space-y-2.5">
      {items.map((item) => (
        <div key={item.schema_code} className="flex items-center gap-3">
          <span className="w-20 shrink-0 font-mono text-xs font-semibold text-foreground">
            {item.schema_code}
          </span>
          <div className="flex-1 overflow-hidden rounded-full bg-white/50" style={{ height: 10 }}>
            <div
              className="h-full rounded-full bg-brand-400 transition-all"
              style={{ width: `${pct(item.count, max)}%` }}
            />
          </div>
          <span className="w-6 shrink-0 text-right font-mono text-xs text-foreground-muted">
            {item.count}
          </span>
        </div>
      ))}
    </div>
  );
}

function StatusDot({ status }: { status: string | null }) {
  const map: Record<string, string> = {
    pass:    'bg-emerald-400',
    fail:    'bg-red-400',
    warning: 'bg-amber-400',
  };
  return (
    <span className={`inline-block h-2 w-2 rounded-full ${map[status ?? ''] ?? 'bg-gray-300'}`} />
  );
}

// ─── Main ─────────────────────────────────────────────────────────────────────

export function AdminOverviewPanel({ adminId }: { adminId: string }) {
  const [data, setData] = useState<OverviewData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  async function fetchData() {
    setLoading(true);
    setError('');
    try {
      const res = await fetch(`${API_URL}/api/admin/overview?admin_id=${encodeURIComponent(adminId)}`);
      const json = await res.json();
      if (!res.ok) {
        setError(typeof json?.detail === 'string' ? json.detail : 'Gagal memuat data');
        return;
      }
      setData(json as OverviewData);
    } catch (err) {
      setError(`Tidak bisa terhubung ke server: ${err instanceof Error ? err.message : String(err)}`);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { void fetchData(); }, [adminId]);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-foreground-subtle">Admin</p>
          <h2 className="mt-0.5 text-lg font-semibold text-foreground">Overview</h2>
        </div>
        <button
          type="button"
          onClick={fetchData}
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
        <div className="rounded-2xl border border-red-200 bg-red-50/80 p-3.5 text-sm font-medium text-red-700">
          {error}
        </div>
      )}

      {loading && !data ? (
        <div className="flex items-center justify-center py-20">
          <svg className="h-6 w-6 animate-spin text-brand-500" viewBox="0 0 24 24" fill="none">
            <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" opacity="0.25" />
            <path d="M12 2a10 10 0 0 1 10 10" stroke="currentColor" strokeWidth="3" strokeLinecap="round" />
          </svg>
        </div>
      ) : data && (
        <>
          {/* ── KPI Grid ── */}
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <KpiCard
              label="Total Token"
              value={data.total_tokens}
              sub={`${data.tokens_used} terpakai · ${data.tokens_unused} sisa`}
              color="brand"
              icon={
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" className="h-5 w-5">
                  <circle cx="8" cy="15" r="4" /><path d="m10.85 12.15 7.4-7.4" /><path d="m18 5 3 3" /><path d="m15 8 3 3" />
                </svg>
              }
            />
            <KpiCard
              label="Total Submission"
              value={data.total_submissions}
              sub="Semua waktu"
              color="sky"
              icon={
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" className="h-5 w-5">
                  <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" /><polyline points="14 2 14 8 20 8" />
                </svg>
              }
            />
            <KpiCard
              label="Submission Hari Ini"
              value={data.submissions_today}
              sub={new Date().toLocaleDateString('id-ID', { day: 'numeric', month: 'long', year: 'numeric' })}
              color="violet"
              icon={
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" className="h-5 w-5">
                  <rect x="3" y="4" width="18" height="18" rx="2" /><line x1="16" y1="2" x2="16" y2="6" /><line x1="8" y1="2" x2="8" y2="6" /><line x1="3" y1="10" x2="21" y2="10" />
                </svg>
              }
            />
            <KpiCard
              label="Rata-rata Proses"
              value={fmtDuration(data.avg_processing_seconds)}
              sub="Per dokumen (semua waktu)"
              color="emerald"
              icon={
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" className="h-5 w-5">
                  <circle cx="12" cy="12" r="10" />
                  <polyline points="12 6 12 12 16 14" />
                </svg>
              }
            />
          </div>

          {/* ── Per Skema ── */}
          <div className="glass-surface rounded-2xl p-5">
            <p className="mb-4 font-mono text-[10px] uppercase tracking-[0.18em] text-foreground-subtle">
              Submission per Skema
            </p>
            <SchemaBar items={data.by_schema} />
          </div>

          {/* ── Recent uploads ── */}
          <div className="glass-surface rounded-2xl p-5">
            <p className="mb-4 font-mono text-[10px] uppercase tracking-[0.18em] text-foreground-subtle">
              5 Upload Terbaru
            </p>
            {data.recent.length === 0 ? (
              <p className="text-sm text-foreground-muted">Belum ada submission.</p>
            ) : (
              <div className="divide-y divide-white/40">
                {data.recent.map((r, i) => (
                  <div key={i} className="flex items-center gap-3 py-3 first:pt-0 last:pb-0">
                    <StatusDot status={r.overall_status} />
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-semibold text-foreground">{r.original_filename}</p>
                      <p className="text-xs text-foreground-muted">
                        {r.schema_code} · {REPORT_LABELS[r.report_type] ?? r.report_type}
                      </p>
                    </div>
                    <p className="shrink-0 text-xs text-foreground-muted">{fmtDate(r.completed_at)}</p>
                  </div>
                ))}
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}
