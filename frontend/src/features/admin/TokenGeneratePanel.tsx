import { AdminMenuIcon } from './AdminMenuIcon';

type Props = {
  tokenCount: number;
  onTokenCountChange: (n: number) => void;
  onGenerate: () => void;
  tokenLoading: boolean;
  generatedToken: string;
  bulkTokens: string[];
  copied: boolean;
  onCopy: () => void;
  onExportBulk: () => void;
  tokenError: string;
};

export function TokenGeneratePanel({
  tokenCount,
  onTokenCountChange,
  onGenerate,
  tokenLoading,
  generatedToken,
  bulkTokens,
  copied,
  onCopy,
  onExportBulk,
  tokenError,
}: Props) {
  return (
    <div className="glass-surface rounded-[1.5rem] p-6 sm:p-8">
      <div className="flex items-center gap-2">
        <AdminMenuIcon name="key" className="h-4 w-4 text-brand-600" />
        <h2 className="text-lg font-semibold text-foreground">Buat Token Sekali Pakai</h2>
      </div>
      <p className="mt-1.5 text-sm text-foreground-muted">
        Masukkan jumlah token lalu klik Generate. Token 1 bisa langsung disalin; token banyak bisa diekspor sebagai
        file.
      </p>

      <div className="mt-5 space-y-4">
        <div className="flex flex-wrap items-end gap-3">
          <div className="flex flex-col gap-1">
            <label className="text-xs font-semibold uppercase tracking-wide text-foreground-subtle">
              Jumlah Token
            </label>
            <input
              type="number"
              min={1}
              max={500}
              value={tokenCount}
              onChange={(e) => {
                const v = parseInt(e.target.value, 10);
                if (!isNaN(v)) onTokenCountChange(Math.max(1, Math.min(500, v)));
              }}
              className="glass-input w-28 rounded-2xl px-4 py-2.5 text-center text-sm font-semibold"
            />
          </div>
          <button
            type="button"
            onClick={onGenerate}
            disabled={tokenLoading}
            className="btn-liquid btn-liquid-primary px-6 py-2.5 text-sm font-semibold disabled:opacity-50"
          >
            {tokenLoading ? 'Memproses...' : `Generate ${tokenCount === 1 ? 'Token' : `${tokenCount} Token`}`}
          </button>
        </div>

        {tokenCount === 1 && (
          <div className="glass-surface-subtle flex flex-wrap items-center gap-3 rounded-2xl px-4 py-3">
            <code className="flex-1 break-all font-mono text-sm text-foreground">
              {generatedToken || 'Belum ada token yang dibuat'}
            </code>
            {generatedToken && (
              <button
                type="button"
                onClick={onCopy}
                className="btn-liquid btn-liquid-ghost px-3 py-1.5 text-xs font-semibold"
              >
                {copied ? 'Tersalin!' : 'Copy'}
              </button>
            )}
          </div>
        )}

        {tokenCount > 1 && bulkTokens.length > 0 && (
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <p className="text-sm font-semibold text-foreground">{bulkTokens.length} token berhasil di-generate</p>
              <button
                type="button"
                onClick={onExportBulk}
                className="btn-liquid btn-liquid-primary px-4 py-2 text-xs font-semibold"
              >
                Ekspor (.txt)
              </button>
            </div>
            <div className="glass-surface-subtle max-h-48 overflow-y-auto rounded-2xl px-4 py-3">
              {bulkTokens.map((t) => (
                <code key={t} className="block break-all py-0.5 font-mono text-xs text-foreground-muted">
                  {t}
                </code>
              ))}
            </div>
          </div>
        )}

        {tokenError && (
          <div className="rounded-2xl border border-red-300 bg-red-50/70 p-4 text-sm font-semibold text-red-700">
            {tokenError}
          </div>
        )}
      </div>
    </div>
  );
}
