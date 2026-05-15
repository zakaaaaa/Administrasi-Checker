import { AdminMenuIcon } from './AdminMenuIcon';
import type { MenuKey } from './types';
import { MENU_ITEMS } from './constants';

type Props = {
  activeMenu: MenuKey;
  onSelectMenu: (key: MenuKey) => void;
  onLogout: () => void;
};

export function AdminMobileNav({ activeMenu, onSelectMenu, onLogout }: Props) {
  return (
    <div className="glass-surface-elevated sticky top-0 z-20 border-b border-white/40 lg:hidden">
      <div className="flex items-center justify-between px-4 py-3">
        <div className="flex items-center gap-2">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src="https://wryvhzvzeuadzbpelbdz.supabase.co/storage/v1/object/public/web/logopkm.png"
            alt="Logo"
            className="h-7 w-auto object-contain"
          />
          <span className="text-sm font-semibold tracking-tight text-foreground">KelasPKM Admin</span>
        </div>
        <button
          type="button"
          onClick={onLogout}
          className="rounded-full px-3 py-1 text-xs font-semibold text-red-600 hover:bg-red-50"
        >
          Logout
        </button>
      </div>
      <nav className="flex gap-2 overflow-x-auto px-4 pb-3">
        {MENU_ITEMS.map((item) => {
          const isActive = item.key === activeMenu;
          return (
            <button
              key={item.key}
              type="button"
              onClick={() => onSelectMenu(item.key)}
              className={`flex shrink-0 items-center gap-1.5 rounded-full border px-3 py-1.5 text-xs font-semibold transition ${
                isActive
                  ? 'border-brand-400 bg-brand-100/70 text-brand-700'
                  : 'glass-surface-subtle border-white/50 text-foreground-muted'
              }`}
            >
              <AdminMenuIcon name={item.key} className="h-3.5 w-3.5" />
              {item.label}
            </button>
          );
        })}
      </nav>
    </div>
  );
}
