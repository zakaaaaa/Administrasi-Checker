import { AdminMenuIcon } from './AdminMenuIcon';
import type { MenuItem, MenuKey } from './types';

type Props = {
  activeItem: MenuItem;
  activeMenu: MenuKey;
  onGoToToken: () => void;
};

export function AdminComingSoonPanel({ activeItem, activeMenu, onGoToToken }: Props) {
  return (
    <div className="glass-surface rounded-[1.5rem] p-6 sm:p-8">
      <div className="rounded-2xl border border-dashed border-white/60 bg-white/40 p-10 text-center">
        <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-2xl bg-brand-100/80 text-brand-600">
          <AdminMenuIcon name={activeMenu} className="h-5 w-5" />
        </div>
        <p className="mt-4 font-mono text-[10px] uppercase tracking-[0.2em] text-foreground-subtle">Coming Soon</p>
        <h3 className="mt-1 text-xl font-semibold text-foreground">{activeItem.label} belum tersedia</h3>
        <p className="mx-auto mt-2 max-w-md text-sm text-foreground-muted">
          Fitur ini sedang dalam pengembangan. Untuk sementara, hanya Generate Token yang dapat digunakan.
        </p>
        <button
          type="button"
          onClick={onGoToToken}
          className="btn-liquid btn-liquid-primary mt-5 px-5 py-2.5 text-sm font-semibold"
        >
          Buka Generate Token
        </button>
      </div>
    </div>
  );
}
