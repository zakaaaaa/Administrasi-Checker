import type { MenuItem } from './types';

type Props = {
  activeItem: MenuItem;
  adminUsername: string;
};

export function AdminDesktopHeader({ activeItem, adminUsername }: Props) {
  return (
    <header className="glass-surface-elevated sticky top-0 z-10 hidden border-b border-white/40 px-6 py-4 lg:block">
      <div className="flex items-center justify-between gap-4">
        <div>
          <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-foreground-subtle">
            {activeItem.active ? 'Aktif' : 'Coming Soon'}
          </p>
          <h1 className="text-xl font-semibold tracking-tight text-foreground">{activeItem.label}</h1>
        </div>
        <div className="flex items-center gap-2">
          <span className="glass-surface-subtle rounded-full px-3 py-1.5 text-xs font-mono uppercase tracking-wider text-foreground-subtle">
            {adminUsername}
          </span>
        </div>
      </div>
    </header>
  );
}
