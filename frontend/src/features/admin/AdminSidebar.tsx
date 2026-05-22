import { AdminMenuIcon } from './AdminMenuIcon';
import type { MenuItem, MenuKey } from './types';
import { MENU_ITEMS } from './constants';

function SidebarNavButton({
  item,
  isActive,
  onClick,
}: {
  item: MenuItem;
  isActive: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition ${
        isActive
          ? 'bg-brand-100/70 text-brand-700'
          : 'text-foreground-muted hover:bg-white/50 hover:text-foreground'
      }`}
    >
      <AdminMenuIcon name={item.key} className="h-4 w-4 shrink-0" />
      <span className="flex-1 truncate text-left">{item.label}</span>
      {!item.active && (
        <span className="rounded-full bg-white/60 px-1.5 py-0.5 font-mono text-[9px] uppercase tracking-wider text-foreground-subtle">
          Soon
        </span>
      )}
    </button>
  );
}

type Props = {
  activeMenu: MenuKey;
  onSelectMenu: (key: MenuKey) => void;
  onLogout: () => void;
};

export function AdminSidebar({ activeMenu, onSelectMenu, onLogout }: Props) {
  return (
    <aside className="glass-surface-elevated sticky top-0 hidden h-screen w-64 shrink-0 flex-col border-r border-white/40 lg:flex">
      <div className="flex items-center gap-2.5 border-b border-white/40 px-5 py-5">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src="https://wryvhzvzeuadzbpelbdz.supabase.co/storage/v1/object/public/web/logopkm.png"
          alt="Logo"
          className="h-8 w-auto object-contain"
        />
        <div className="leading-tight">
          <p className="text-sm font-semibold tracking-tight text-foreground">KelasPKM</p>
          <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-foreground-subtle">
            Admin Panel
          </p>
        </div>
      </div>

      <nav className="flex-1 space-y-1 overflow-y-auto px-3 py-4">
        {MENU_ITEMS.map((item) => (
          <SidebarNavButton
            key={item.key}
            item={item}
            isActive={item.key === activeMenu}
            onClick={() => onSelectMenu(item.key)}
          />
        ))}
      </nav>

      <div className="border-t border-white/40 px-3 py-4">
        <button
          type="button"
          onClick={onLogout}
          className="flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium text-red-600 transition hover:bg-red-50"
        >
          <AdminMenuIcon name="logout" />
          <span>Logout</span>
        </button>
      </div>
    </aside>
  );
}
