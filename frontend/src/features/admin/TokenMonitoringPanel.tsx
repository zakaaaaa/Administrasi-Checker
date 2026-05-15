import { AdminMenuIcon } from './AdminMenuIcon';
import type { TokenRecord } from './types';

type Props = {
  tokenList: TokenRecord[];
  tokenListLoading: boolean;
  tokenListError: string;
  filterStatus: 'all' | 'used' | 'unused';
  setFilterStatus: (v: 'all' | 'used' | 'unused') => void;
  filterDateFrom: string;
  setFilterDateFrom: (v: string) => void;
  filterDateTo: string;
  setFilterDateTo: (v: string) => void;
  onRefresh: () => void;
};

export function TokenMonitoringPanel({
  tokenList,
  tokenListLoading,
  tokenListError,
  filterStatus,
  setFilterStatus,
  filterDateFrom,
  setFilterDateFrom,
  filterDateTo,
  setFilterDateTo,
  onRefresh,
}: Props) {
  const filtered = tokenList.filter((t) => {
    if (filterStatus === 'used' && !t.used) return false;
    if (filterStatus === 'unused' && t.used) return false;
    if (filterDateFrom && t.created_at) {
      if (new Date(t.created_at) < new Date(filterDateFrom)) return false;
    }
    if (filterDateTo && t.created_at) {
      const to = new Date(filterDateTo);
      to.setHours(23, 59, 59, 999);
      if (new Date(t.created_at) > to) return false;
    }
    return true;
  });
  const usedCount = tokenList.filter((t) => t.used).length;
  const unusedCount = tokenList.length - usedCount;

  return (
    <div className="glass-surface rounded-[1.5rem] p-6 sm:p-8">
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <AdminMenuIcon name="monitoring" className="h-4 w-4 text-brand-600" />
          <h2 className="text-lg font-semibold text-foreground">Monitoring Token</h2>
        </div>
        <button
          type="button"
          onClick={onRefresh}
          disabled={tokenListLoading}
          className="btn-liquid btn-liquid-ghost px-4 py-1.5 text-xs font-semibold disabled:opacity-50"
        >
          {tokenListLoading ? 'Memuat...' : 'Refresh'}
        </button>
      </div>

      {tokenList.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-2">
          <span className="rounded-full bg-white/50 px-3 py-1 text-xs font-semibold text-foreground-muted">
            Total: {tokenList.length}
          </span>
          <span className="rounded-full bg-green-100/80 px-3 py-1 text-xs font-semibold text-green-700">
            Belum dipakai: {unusedCount}
          </span>
          <span className="rounded-full bg-red-100/80 px-3 py-1 text-xs font-semibold text-red-700">
            Terpakai: {usedCount}
          </span>
        </div>
      )}

      <div className="mt-4 flex flex-wrap items-end gap-3">
        <div className="flex flex-col gap-1">
          <label className="text-[10px] font-semibold uppercase tracking-wide text-foreground-subtle">
            Dari Tanggal
          </label>
          <input
            type="date"
            value={filterDateFrom}
            onChange={(e) => setFilterDateFrom(e.target.value)}
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
            onChange={(e) => setFilterDateTo(e.target.value)}
            className="glass-input rounded-xl px-3 py-2 text-xs font-medium"
          />
        </div>
        <div className="flex flex-col gap-1">
          <label className="text-[10px] font-semibold uppercase tracking-wide text-foreground-subtle">Status</label>
          <div className="flex overflow-hidden rounded-xl border border-white/40 bg-white/30">
            {(['all', 'unused', 'used'] as const).map((s) => (
              <button
                key={s}
                type="button"
                onClick={() => setFilterStatus(s)}
                className={`px-3 py-2 text-xs font-semibold transition ${
                  filterStatus === s ? 'bg-brand-500 text-white' : 'text-foreground-muted hover:bg-white/50'
                }`}
              >
                {s === 'all' ? 'Semua' : s === 'unused' ? 'Belum dipakai' : 'Terpakai'}
              </button>
            ))}
          </div>
        </div>
        {(filterDateFrom || filterDateTo || filterStatus !== 'all') && (
          <button
            type="button"
            onClick={() => {
              setFilterDateFrom('');
              setFilterDateTo('');
              setFilterStatus('all');
            }}
            className="rounded-xl px-3 py-2 text-xs font-semibold text-foreground-muted transition hover:bg-white/40"
          >
            Reset filter
          </button>
        )}
      </div>

      {tokenListError && (
        <div className="mt-4 rounded-2xl border border-red-300 bg-red-50/70 p-3 text-sm font-semibold text-red-700">
          {tokenListError}
        </div>
      )}

      {tokenListLoading && (
        <div className="mt-6 py-8 text-center text-sm text-foreground-muted">Memuat data token...</div>
      )}

      {!tokenListLoading && !tokenListError && tokenList.length === 0 && (
        <div className="mt-6 rounded-2xl border border-dashed border-white/60 bg-white/30 py-8 text-center">
          <p className="text-sm text-foreground-muted">Belum ada token. Generate token untuk melihat daftar.</p>
        </div>
      )}

      {!tokenListLoading && tokenList.length > 0 && filtered.length === 0 && (
        <div className="mt-6 rounded-2xl border border-dashed border-white/60 bg-white/30 py-8 text-center">
          <p className="text-sm text-foreground-muted">Tidak ada token yang cocok dengan filter.</p>
        </div>
      )}

      {!tokenListLoading && filtered.length > 0 && (
        <div className="mt-4 overflow-x-auto rounded-2xl">
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-white/30">
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
              {filtered.map((t) => (
                <tr key={t.token} className="border-b border-white/10 transition hover:bg-white/20">
                  <td className="px-3 py-2.5">
                    <code className="break-all font-mono text-xs text-foreground">{t.token}</code>
                  </td>
                  <td className="whitespace-nowrap px-3 py-2.5 text-xs text-foreground-muted">
                    {t.created_at
                      ? new Date(t.created_at).toLocaleString('id-ID', { dateStyle: 'short', timeStyle: 'short' })
                      : '—'}
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
                    {t.used_at
                      ? new Date(t.used_at).toLocaleString('id-ID', { dateStyle: 'short', timeStyle: 'short' })
                      : '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="mt-2 px-3 text-[11px] text-foreground-subtle">
            Menampilkan {filtered.length} dari {tokenList.length} token
          </p>
        </div>
      )}
    </div>
  );
}
