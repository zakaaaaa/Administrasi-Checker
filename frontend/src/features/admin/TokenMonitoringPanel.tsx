import { useCallback, useEffect, useState } from 'react';
import { AdminMenuIcon } from './AdminMenuIcon';
import { API_URL } from './constants';
import type { TokenRecord } from './types';

type TokenStatus = 'all' | 'used' | 'unused';

type TokenResponse = {
  tokens: TokenRecord[];
  total: number;
  used_count: number;
  unused_count: number;
  page: number;
  page_size: number;
  total_pages: number;
};

type Props = {
  adminId: string;
};

function formatDateTime(value: string | null): string {
  return value
    ? new Date(value).toLocaleString('id-ID', { dateStyle: 'short', timeStyle: 'short' })
    : '-';
}

function SearchIcon() {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2.3"
      strokeLinecap="round"
      strokeLinejoin="round"
      className="h-4 w-4"
    >
      <circle cx="11" cy="11" r="8" />
      <path d="m21 21-4.3-4.3" />
    </svg>
  );
}

function RefreshIcon({ loading }: { loading: boolean }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2.5"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={`h-3.5 w-3.5 ${loading ? 'animate-spin' : ''}`}
    >
      <polyline points="1 4 1 10 7 10" />
      <path d="M3.51 15a9 9 0 1 0 .49-3.51" />
    </svg>
  );
}

export function TokenMonitoringPanel({ adminId }: Props) {
  const [tokenList, setTokenList] = useState<TokenRecord[]>([]);
  const [tokenListLoading, setTokenListLoading] = useState(false);
  const [tokenListError, setTokenListError] = useState('');
  const [searchToken, setSearchToken] = useState('');
  const [debouncedSearchToken, setDebouncedSearchToken] = useState('');
  const [filterStatus, setFilterStatus] = useState<TokenStatus>('all');
  const [filterDateFrom, setFilterDateFrom] = useState('');
  const [filterDateTo, setFilterDateTo] = useState('');
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const [total, setTotal] = useState(0);
  const [usedCount, setUsedCount] = useState(0);
  const [unusedCount, setUnusedCount] = useState(0);
  const [totalPages, setTotalPages] = useState(1);

  const fetchTokenList = useCallback(async () => {
    if (!adminId) return;
    setTokenListLoading(true);
    setTokenListError('');
    try {
      const params = new URLSearchParams({
        admin_id: adminId,
        page: String(page),
        page_size: String(pageSize),
        status: filterStatus,
      });
      if (debouncedSearchToken.trim()) params.set('q', debouncedSearchToken.trim());
      if (filterDateFrom) params.set('date_from', filterDateFrom);
      if (filterDateTo) params.set('date_to', filterDateTo);

      const res = await fetch(`${API_URL}/api/admin/tokens?${params.toString()}`);
      const data = await res.json() as Partial<TokenResponse> & { detail?: unknown };
      if (!res.ok) {
        setTokenListError(typeof data?.detail === 'string' ? data.detail : 'Gagal memuat daftar token');
        return;
      }

      const nextTotal = typeof data.total === 'number' ? data.total : 0;
      const nextTotalPages = typeof data.total_pages === 'number' ? Math.max(1, data.total_pages) : 1;
      setTokenList(Array.isArray(data.tokens) ? data.tokens : []);
      setTotal(nextTotal);
      setUsedCount(typeof data.used_count === 'number' ? data.used_count : 0);
      setUnusedCount(typeof data.unused_count === 'number' ? data.unused_count : 0);
      setTotalPages(nextTotalPages);
      if (nextTotal > 0 && page > nextTotalPages) {
        setPage(nextTotalPages);
      }
    } catch (err) {
      setTokenListError(
        `Tidak bisa terhubung ke server: ${err instanceof Error ? err.message : String(err)}`,
      );
    } finally {
      setTokenListLoading(false);
    }
  }, [adminId, debouncedSearchToken, filterDateFrom, filterDateTo, filterStatus, page, pageSize]);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void fetchTokenList();
    }, 0);
    return () => window.clearTimeout(timer);
  }, [fetchTokenList]);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      setDebouncedSearchToken(searchToken.trim());
      setPage(1);
    }, 350);
    return () => window.clearTimeout(timer);
  }, [searchToken]);

  function resetFilters() {
    setSearchToken('');
    setFilterDateFrom('');
    setFilterDateTo('');
    setFilterStatus('all');
    setPage(1);
  }

  const startRecord = total === 0 ? 0 : (page - 1) * pageSize + 1;
  const endRecord = total === 0 ? 0 : Math.min(total, startRecord + tokenList.length - 1);
  const canPrev = page > 1 && !tokenListLoading;
  const canNext = page < totalPages && !tokenListLoading;
  const hasActiveFilter =
    Boolean(searchToken || filterDateFrom || filterDateTo || filterStatus !== 'all');

  return (
    <div className="glass-surface rounded-[1.5rem] p-6 sm:p-8">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <div className="flex items-center gap-2">
          <AdminMenuIcon name="monitoring" className="h-4 w-4 text-brand-600" />
          <h2 className="text-lg font-semibold text-foreground">Monitoring Token</h2>
        </div>
        <button
          type="button"
          onClick={fetchTokenList}
          disabled={tokenListLoading}
          className="inline-flex h-10 items-center justify-center gap-1.5 rounded-xl border border-border px-3 text-xs font-medium text-foreground-muted transition hover:border-brand-200 hover:text-foreground disabled:opacity-50"
        >
          <RefreshIcon loading={tokenListLoading} />
          Refresh
        </button>
      </div>

      <div className="mt-3 flex flex-wrap gap-2">
        <span className="rounded-full bg-white/50 px-3 py-1 text-xs font-semibold text-foreground-muted">
          Total: {total}
        </span>
        <span className="rounded-full bg-green-100/80 px-3 py-1 text-xs font-semibold text-green-700">
          Belum dipakai: {unusedCount}
        </span>
        <span className="rounded-full bg-red-100/80 px-3 py-1 text-xs font-semibold text-red-700">
          Terpakai: {usedCount}
        </span>
      </div>

      <div className="mt-4 grid gap-3 lg:grid-cols-[minmax(240px,1fr)_auto] lg:items-end">
        <div className="flex flex-col gap-1">
          <label
            htmlFor="token-search"
            className="text-[10px] font-semibold uppercase tracking-wide text-foreground-subtle"
          >
            Cari Token
          </label>
          <div className="relative">
            <span className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-foreground-subtle">
              <SearchIcon />
            </span>
            <input
              id="token-search"
              type="search"
              value={searchToken}
              onChange={(e) => setSearchToken(e.target.value)}
              placeholder="Cari token, contoh PKM-2026-ABC123"
              className="glass-input w-full rounded-xl py-2 pl-9 pr-9 text-xs font-medium placeholder:text-foreground-subtle"
            />
            {searchToken && (
              <button
                type="button"
                onClick={() => setSearchToken('')}
                aria-label="Hapus pencarian token"
                className="absolute right-2 top-1/2 flex h-6 w-6 -translate-y-1/2 items-center justify-center rounded-lg text-foreground-subtle transition hover:bg-white/50 hover:text-foreground"
              >
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2.4"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  className="h-3.5 w-3.5"
                >
                  <path d="M18 6 6 18" />
                  <path d="m6 6 12 12" />
                </svg>
              </button>
            )}
          </div>
        </div>

        <div className="flex flex-wrap items-end gap-3">
          <div className="flex flex-col gap-1">
            <label className="text-[10px] font-semibold uppercase tracking-wide text-foreground-subtle">
              Dari Tanggal
            </label>
            <input
              type="date"
              value={filterDateFrom}
              onChange={(e) => {
                setFilterDateFrom(e.target.value);
                setPage(1);
              }}
              className="glass-input rounded-xl px-3 py-2 text-xs font-medium"
            />
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-[10px] font-semibold uppercase tracking-wide text-foreground-subtle">
              Sampai Tanggal
            </label>
            <input
              type="date"
              value={filterDateTo}
              onChange={(e) => {
                setFilterDateTo(e.target.value);
                setPage(1);
              }}
              className="glass-input rounded-xl px-3 py-2 text-xs font-medium"
            />
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-[10px] font-semibold uppercase tracking-wide text-foreground-subtle">
              Status
            </label>
            <div className="flex overflow-hidden rounded-xl border border-border bg-surface">
              {(['all', 'unused', 'used'] as const).map((s) => (
                <button
                  key={s}
                  type="button"
                  onClick={() => {
                    setFilterStatus(s);
                    setPage(1);
                  }}
                  className={`px-3 py-2 text-xs font-semibold transition ${
                    filterStatus === s ? 'bg-brand-500 text-white' : 'text-foreground-muted hover:bg-white/50'
                  }`}
                >
                  {s === 'all' ? 'Semua' : s === 'unused' ? 'Belum dipakai' : 'Terpakai'}
                </button>
              ))}
            </div>
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-[10px] font-semibold uppercase tracking-wide text-foreground-subtle">
              Per Halaman
            </label>
            <select
              value={pageSize}
              onChange={(e) => {
                setPageSize(Number(e.target.value));
                setPage(1);
              }}
              className="glass-input rounded-xl px-3 py-2 text-xs font-medium"
            >
              <option value={10}>10</option>
              <option value={20}>20</option>
              <option value={50}>50</option>
            </select>
          </div>
          {hasActiveFilter && (
            <button
              type="button"
              onClick={resetFilters}
              className="rounded-xl px-3 py-2 text-xs font-semibold text-foreground-muted transition hover:bg-white/40"
            >
              Reset filter
            </button>
          )}
        </div>
      </div>

      {tokenListError && (
        <div className="mt-4 rounded-2xl border border-red-300 bg-red-50/70 p-3 text-sm font-semibold text-red-700">
          {tokenListError}
        </div>
      )}

      {tokenListLoading && tokenList.length === 0 && (
        <div className="mt-6 py-8 text-center text-sm text-foreground-muted">Memuat data token...</div>
      )}

      {!tokenListLoading && !tokenListError && tokenList.length === 0 && !hasActiveFilter && (
        <div className="mt-6 rounded-2xl border border-dashed border-border bg-surface py-8 text-center">
          <p className="text-sm text-foreground-muted">Belum ada token. Generate token untuk melihat daftar.</p>
        </div>
      )}

      {!tokenListLoading && !tokenListError && tokenList.length === 0 && hasActiveFilter && (
        <div className="mt-6 rounded-2xl border border-dashed border-border bg-surface py-8 text-center">
          <p className="text-sm text-foreground-muted">
            Tidak ada token yang cocok dengan pencarian atau filter.
          </p>
        </div>
      )}

      {tokenList.length > 0 && (
        <div className="mt-4 overflow-hidden rounded-2xl">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-border">
                  <th className="px-3 py-2.5 text-xs font-semibold uppercase tracking-wide text-foreground-subtle">
                    Token
                  </th>
                  <th className="px-3 py-2.5 text-xs font-semibold uppercase tracking-wide text-foreground-subtle">
                    Dibuat
                  </th>
                  <th className="px-3 py-2.5 text-xs font-semibold uppercase tracking-wide text-foreground-subtle">
                    Status
                  </th>
                  <th className="px-3 py-2.5 text-xs font-semibold uppercase tracking-wide text-foreground-subtle">
                    Dipakai Pada
                  </th>
                </tr>
              </thead>
              <tbody>
                {tokenList.map((t) => (
                  <tr key={t.token} className="border-b border-border transition hover:bg-surface">
                    <td className="px-3 py-2.5">
                      <code className="break-all font-mono text-xs text-foreground">{t.token}</code>
                    </td>
                    <td className="whitespace-nowrap px-3 py-2.5 text-xs text-foreground-muted">
                      {formatDateTime(t.created_at)}
                    </td>
                    <td className="whitespace-nowrap px-3 py-2.5">
                      {t.used ? (
                        <span className="inline-flex items-center rounded-full bg-red-100/80 px-2.5 py-0.5 text-xs font-semibold text-red-700">
                          Terpakai
                        </span>
                      ) : (
                        <span className="inline-flex items-center rounded-full bg-green-100/80 px-2.5 py-0.5 text-xs font-semibold text-green-700">
                          Belum dipakai
                        </span>
                      )}
                    </td>
                    <td className="whitespace-nowrap px-3 py-2.5 text-xs text-foreground-muted">
                      {formatDateTime(t.used_at)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="flex flex-col gap-3 border-t border-border px-3 py-3 sm:flex-row sm:items-center sm:justify-between">
            <p className="text-xs font-medium text-foreground-muted">
              Menampilkan {startRecord}-{endRecord} dari {total} token
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
