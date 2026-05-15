import { AdminMenuIcon } from './AdminMenuIcon';
import type { IconName } from './types';

function AdminKpiCard({
  icon,
  label,
  value,
  hint,
}: {
  icon: IconName;
  label: string;
  value: string;
  hint: string;
}) {
  return (
    <div className="glass-surface rounded-2xl p-4">
      <div className="flex items-center gap-3">
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-brand-100/70 text-brand-600">
          <AdminMenuIcon name={icon} className="h-4 w-4" />
        </div>
        <div className="min-w-0 flex-1">
          <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-foreground-subtle">{label}</p>
          <p className="truncate text-base font-semibold text-foreground">{value}</p>
          <p className="text-[11px] text-foreground-muted">{hint}</p>
        </div>
      </div>
    </div>
  );
}

type Props = {
  adminUsername: string;
  bulkTokensLength: number;
  hasGeneratedSingle: boolean;
};

export function AdminKpiGrid({ adminUsername, bulkTokensLength, hasGeneratedSingle }: Props) {
  const tokenValue =
    bulkTokensLength > 0
      ? `${bulkTokensLength} token`
      : hasGeneratedSingle
        ? '1 token'
        : '—';
  const tokenHint =
    bulkTokensLength > 0 || hasGeneratedSingle ? 'Baru di-generate' : 'Belum ada';

  return (
    <div className="mb-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
      <AdminKpiCard icon="user" label="Sesi Admin" value={adminUsername} hint="Logged in" />
      <AdminKpiCard icon="key" label="Token Di-generate" value={tokenValue} hint={tokenHint} />
      <AdminKpiCard icon="pulse" label="Status Sistem" value="Online" hint="Semua layanan aktif" />
    </div>
  );
}
