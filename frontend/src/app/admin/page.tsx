'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';
const STORAGE_KEY = 'admin_session_v1';

type MenuKey =
  | 'token'
  | 'monitoring'
  | 'dashboard'
  | 'users'
  | 'uploads'
  | 'server'
  | 'settings';

type MenuItem = {
  key: MenuKey;
  label: string;
  description: string;
  active: boolean;
};

const MENU_ITEMS: MenuItem[] = [
  {
    key: 'token',
    label: 'Generate Token',
    description: 'Buat token sekali pakai untuk user.',
    active: true,
  },
  {
    key: 'monitoring',
    label: 'Monitoring Token',
    description: 'Pantau status pemakaian token.',
    active: true,
  },
  {
    key: 'dashboard',
    label: 'Dashboard',
    description: 'Ringkasan metrik harian.',
    active: false,
  },
  {
    key: 'users',
    label: 'Manajemen User',
    description: 'Daftar dan aktivitas user.',
    active: false,
  },
  {
    key: 'uploads',
    label: 'Riwayat Upload',
    description: 'Log seluruh berkas masuk.',
    active: false,
  },
  {
    key: 'server',
    label: 'Monitoring Server',
    description: 'CPU, RAM, dan Disk usage.',
    active: false,
  },
  {
    key: 'settings',
    label: 'Pengaturan',
    description: 'Konfigurasi sistem.',
    active: false,
  },
];

export default function AdminPage() {
  const [adminId, setAdminId] = useState<string>('');
  const [adminUsername, setAdminUsername] = useState<string>('');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [loginError, setLoginError] = useState('');
  const [loginLoading, setLoginLoading] = useState(false);

  const [activeMenu, setActiveMenu] = useState<MenuKey>('token');
  const [showPassword, setShowPassword] = useState(false);

  const [tokenCount, setTokenCount] = useState(1);
  const [generatedToken, setGeneratedToken] = useState('');
  const [bulkTokens, setBulkTokens] = useState<string[]>([]);
  const [tokenError, setTokenError] = useState('');
  const [tokenLoading, setTokenLoading] = useState(false);
  const [copied, setCopied] = useState(false);

  const [tokenList, setTokenList] = useState<TokenRecord[]>([]);
  const [tokenListLoading, setTokenListLoading] = useState(false);
  const [tokenListError, setTokenListError] = useState('');
  const [filterStatus, setFilterStatus] = useState<'all' | 'used' | 'unused'>('all');
  const [filterDateFrom, setFilterDateFrom] = useState('');
  const [filterDateTo, setFilterDateTo] = useState('');

  useEffect(() => {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (raw) {
        const parsed = JSON.parse(raw) as { admin_id: string; username: string };
        if (parsed.admin_id && parsed.username) {
          setAdminId(parsed.admin_id);
          setAdminUsername(parsed.username);
        }
      }
    } catch {
      // ignore
    }
  }, []);

  useEffect(() => {
    if (activeMenu === 'monitoring' && adminId) {
      fetchTokenList();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeMenu, adminId]);

  async function handleAuth() {
    setLoginError('');
    if (!username || !password) {
      setLoginError('Username dan password wajib diisi.');
      return;
    }
    setLoginLoading(true);
    try {
      const res = await fetch(`${API_URL}/api/admin/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password }),
      });
      const data = await res.json();
      if (!res.ok) {
        setLoginError(typeof data?.detail === 'string' ? data.detail : 'Login gagal');
        return;
      }
      setAdminId(data.admin_id);
      setAdminUsername(data.username);
      localStorage.setItem(
        STORAGE_KEY,
        JSON.stringify({ admin_id: data.admin_id, username: data.username }),
      );
      setPassword('');
    } catch (err) {
      setLoginError(`Tidak bisa terhubung ke server: ${err instanceof Error ? err.message : err}`);
    } finally {
      setLoginLoading(false);
    }
  }

  function handleLogout() {
    localStorage.removeItem(STORAGE_KEY);
    setAdminId('');
    setAdminUsername('');
    setGeneratedToken('');
    setBulkTokens([]);
    setTokenError('');
    setTokenList([]);
    setActiveMenu('token');
  }

  async function handleGenerateToken() {
    setTokenError('');
    setGeneratedToken('');
    setBulkTokens([]);
    setCopied(false);
    if (!adminId) { setTokenError('Belum login.'); return; }
    setTokenLoading(true);
    try {
      if (tokenCount === 1) {
        const res = await fetch(`${API_URL}/api/admin/tokens`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ admin_id: adminId }),
        });
        const data = await res.json();
        if (!res.ok) {
          if (res.status === 401) { handleLogout(); setTokenError('Session berakhir. Silakan login ulang.'); return; }
          setTokenError(typeof data?.detail === 'string' ? data.detail : 'Gagal generate token');
          return;
        }
        setGeneratedToken(data.token);
      } else {
        const res = await fetch(`${API_URL}/api/admin/tokens/bulk`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ admin_id: adminId, count: tokenCount }),
        });
        const data = await res.json();
        if (!res.ok) {
          if (res.status === 401) { handleLogout(); setTokenError('Session berakhir. Silakan login ulang.'); return; }
          setTokenError(typeof data?.detail === 'string' ? data.detail : 'Gagal generate token');
          return;
        }
        setBulkTokens(data.tokens as string[]);
      }
      fetchTokenList();
    } catch (err) {
      setTokenError(`Tidak bisa terhubung ke server: ${err instanceof Error ? err.message : err}`);
    } finally {
      setTokenLoading(false);
    }
  }

  async function handleCopyToken() {
    if (!generatedToken) return;
    try {
      await navigator.clipboard.writeText(generatedToken);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch { /* ignore */ }
  }

  function handleExportTokens() {
    if (!bulkTokens.length) return;
    const content = bulkTokens.join('\n');
    const blob = new Blob([content], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `tokens_${new Date().toISOString().slice(0, 10)}.txt`;
    a.click();
    URL.revokeObjectURL(url);
  }

  async function fetchTokenList() {
    if (!adminId) return;
    setTokenListLoading(true);
    setTokenListError('');
    try {
      const res = await fetch(`${API_URL}/api/admin/tokens?admin_id=${encodeURIComponent(adminId)}`);
      const data = await res.json();
      if (!res.ok) {
        setTokenListError(typeof data?.detail === 'string' ? data.detail : 'Gagal memuat daftar token');
        return;
      }
      setTokenList(data.tokens);
    } catch (err) {
      setTokenListError(`Tidak bisa terhubung ke server: ${err instanceof Error ? err.message : err}`);
    } finally {
      setTokenListLoading(false);
    }
  }

  const isAuthed = Boolean(adminId);

  if (!isAuthed) {
    return (
      <main className="relative flex min-h-[calc(100vh-4rem)] items-center justify-center px-4 py-10 sm:px-6">
        <div aria-hidden className="orb orb-brand pointer-events-none absolute -left-20 top-10 h-72 w-72 opacity-50" />
        <div aria-hidden className="orb orb-accent pointer-events-none absolute -right-16 bottom-10 h-72 w-72 opacity-40" />

        <div className="relative z-10 flex w-full max-w-md flex-col items-center">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src="https://wryvhzvzeuadzbpelbdz.supabase.co/storage/v1/object/public/web/logopkm.png"
            alt="Logo PKM"
            className="mb-6 h-16 w-auto object-contain"
          />

          <section className="glass-surface-elevated w-full rounded-[1.75rem] p-7 sm:p-9">
            <h1 className="text-2xl font-semibold tracking-tight text-foreground sm:text-3xl">
              Masuk ke Akun
            </h1>

            <div className="mt-6 space-y-4">
              <div>
                <label className="text-xs font-semibold uppercase tracking-wide text-foreground-subtle">
                  Username
                </label>
                <div className="relative mt-1.5">
                  <span className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-foreground-subtle">
                    <svg
                      xmlns="http://www.w3.org/2000/svg"
                      width="18"
                      height="18"
                      viewBox="0 0 24 24"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="1.8"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    >
                      <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
                      <circle cx="12" cy="7" r="4" />
                    </svg>
                  </span>
                  <input
                    value={username}
                    onChange={(event) => setUsername(event.target.value)}
                    placeholder="Masukkan username"
                    autoComplete="username"
                    className="glass-input w-full rounded-2xl py-3 pl-11 pr-4 text-sm font-medium"
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') handleAuth();
                    }}
                  />
                </div>
              </div>

              <div>
                <label className="text-xs font-semibold uppercase tracking-wide text-foreground-subtle">
                  Password
                </label>
                <div className="relative mt-1.5">
                  <span className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-foreground-subtle">
                    <svg
                      xmlns="http://www.w3.org/2000/svg"
                      width="18"
                      height="18"
                      viewBox="0 0 24 24"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="1.8"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    >
                      <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
                      <path d="M7 11V7a5 5 0 0 1 10 0v4" />
                    </svg>
                  </span>
                  <input
                    type={showPassword ? 'text' : 'password'}
                    value={password}
                    onChange={(event) => setPassword(event.target.value)}
                    placeholder="Masukkan password"
                    autoComplete="current-password"
                    className="glass-input w-full rounded-2xl py-3 pl-11 pr-11 text-sm font-medium"
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') handleAuth();
                    }}
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword((prev) => !prev)}
                    aria-label={showPassword ? 'Sembunyikan password' : 'Tampilkan password'}
                    className="absolute right-3 top-1/2 -translate-y-1/2 rounded-full p-1.5 text-foreground-subtle hover:text-foreground"
                  >
                    {showPassword ? (
                      <svg
                        xmlns="http://www.w3.org/2000/svg"
                        width="18"
                        height="18"
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="1.8"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                      >
                        <path d="M17.94 17.94A10.94 10.94 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94" />
                        <path d="M9.9 4.24A10.94 10.94 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19" />
                        <path d="M14.12 14.12a3 3 0 1 1-4.24-4.24" />
                        <line x1="1" y1="1" x2="23" y2="23" />
                      </svg>
                    ) : (
                      <svg
                        xmlns="http://www.w3.org/2000/svg"
                        width="18"
                        height="18"
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="1.8"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                      >
                        <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
                        <circle cx="12" cy="12" r="3" />
                      </svg>
                    )}
                  </button>
                </div>
              </div>

              <button
                type="button"
                onClick={handleAuth}
                disabled={loginLoading}
                className="btn-liquid btn-liquid-primary w-full px-5 py-3 text-base font-semibold disabled:opacity-50"
              >
                {loginLoading ? 'Memproses...' : 'Masuk'}
              </button>

              {loginError && (
                <div className="rounded-2xl border border-red-300 bg-red-50/70 p-3 text-sm font-medium text-red-700">
                  {loginError}
                </div>
              )}

              <div className="flex items-center gap-3">
                <div className="h-px flex-1 bg-foreground/10" />
                <span className="text-xs uppercase tracking-wider text-foreground-subtle">Atau</span>
                <div className="h-px flex-1 bg-foreground/10" />
              </div>

              <p className="text-center text-sm text-foreground-muted">
                Bukan admin?{' '}
                <Link href="/" className="font-semibold text-brand-600 hover:text-brand-700">
                  Kembali ke beranda
                </Link>
              </p>
            </div>
          </section>

          <p className="mt-6 text-center text-xs text-foreground-subtle">
            © 2026 KelasPKM. All rights reserved.
          </p>
        </div>
      </main>
    );
  }

  const activeItem = MENU_ITEMS.find((item) => item.key === activeMenu) ?? MENU_ITEMS[0];

  return (
    <div className="relative">
      <div className="relative flex min-h-screen">
        {/* Sidebar */}
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
              <SidebarItem
                key={item.key}
                item={item}
                isActive={item.key === activeMenu}
                onClick={() => setActiveMenu(item.key)}
              />
            ))}
          </nav>

          <div className="space-y-1 border-t border-white/40 px-3 py-4">
            <Link
              href="/"
              className="flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium text-foreground-muted transition hover:bg-white/50 hover:text-foreground"
            >
              <MenuIcon name="home" />
              <span>Beranda</span>
            </Link>
            <button
              type="button"
              onClick={handleLogout}
              className="flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium text-red-600 transition hover:bg-red-50"
            >
              <MenuIcon name="logout" />
              <span>Logout</span>
            </button>
          </div>
        </aside>

        {/* Main column */}
        <div className="flex min-w-0 flex-1 flex-col">
          {/* Mobile top bar */}
          <div className="glass-surface-elevated sticky top-0 z-20 border-b border-white/40 lg:hidden">
            <div className="flex items-center justify-between px-4 py-3">
              <div className="flex items-center gap-2">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src="https://wryvhzvzeuadzbpelbdz.supabase.co/storage/v1/object/public/web/logopkm.png"
                  alt="Logo"
                  className="h-7 w-auto object-contain"
                />
                <span className="text-sm font-semibold tracking-tight text-foreground">
                  KelasPKM Admin
                </span>
              </div>
              <button
                type="button"
                onClick={handleLogout}
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
                    onClick={() => setActiveMenu(item.key)}
                    className={`flex shrink-0 items-center gap-1.5 rounded-full border px-3 py-1.5 text-xs font-semibold transition ${
                      isActive
                        ? 'border-brand-400 bg-brand-100/70 text-brand-700'
                        : 'glass-surface-subtle border-white/50 text-foreground-muted'
                    }`}
                  >
                    <MenuIcon name={item.key} className="h-3.5 w-3.5" />
                    {item.label}
                  </button>
                );
              })}
            </nav>
          </div>

          {/* Desktop top header */}
          <header className="glass-surface-elevated sticky top-0 z-10 hidden border-b border-white/40 px-6 py-4 lg:block">
            <div className="flex items-center justify-between gap-4">
              <div>
                <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-foreground-subtle">
                  {activeItem.active ? 'Aktif' : 'Coming Soon'}
                </p>
                <h1 className="text-xl font-semibold tracking-tight text-foreground">
                  {activeItem.label}
                </h1>
              </div>
              <div className="flex items-center gap-2">
                <span className="glass-surface-subtle rounded-full px-3 py-1.5 text-xs font-mono uppercase tracking-wider text-foreground-subtle">
                  {adminUsername}
                </span>
              </div>
            </div>
          </header>

          {/* Content */}
          <main className="flex-1 px-4 py-6 sm:px-6">
            <div className="mb-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              <KpiCard
                icon="user"
                label="Sesi Admin"
                value={adminUsername}
                hint="Logged in"
              />
              <KpiCard
                icon="key"
                label="Token Di-generate"
                value={
                  bulkTokens.length
                    ? `${bulkTokens.length} token`
                    : generatedToken
                    ? '1 token'
                    : '—'
                }
                hint={
                  bulkTokens.length || generatedToken
                    ? 'Baru di-generate'
                    : 'Belum ada'
                }
              />
              <KpiCard
                icon="pulse"
                label="Status Sistem"
                value="Online"
                hint="Semua layanan aktif"
              />
            </div>

            {activeMenu === 'token' ? (
              <div className="glass-surface rounded-[1.5rem] p-6 sm:p-8">
                  <div className="flex items-center gap-2">
                    <MenuIcon name="key" className="h-4 w-4 text-brand-600" />
                    <h2 className="text-lg font-semibold text-foreground">Buat Token Sekali Pakai</h2>
                  </div>
                  <p className="mt-1.5 text-sm text-foreground-muted">
                    Masukkan jumlah token lalu klik Generate. Token 1 bisa langsung disalin; token banyak bisa diekspor sebagai file.
                  </p>

                  <div className="mt-5 space-y-4">
                    {/* Count input + button */}
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
                            if (!isNaN(v)) setTokenCount(Math.max(1, Math.min(500, v)));
                          }}
                          className="glass-input w-28 rounded-2xl px-4 py-2.5 text-center text-sm font-semibold"
                        />
                      </div>
                      <button
                        type="button"
                        onClick={handleGenerateToken}
                        disabled={tokenLoading}
                        className="btn-liquid btn-liquid-primary px-6 py-2.5 text-sm font-semibold disabled:opacity-50"
                      >
                        {tokenLoading ? 'Memproses...' : `Generate ${tokenCount === 1 ? 'Token' : `${tokenCount} Token`}`}
                      </button>
                    </div>

                    {/* Single token result */}
                    {tokenCount === 1 && (
                      <div className="glass-surface-subtle flex flex-wrap items-center gap-3 rounded-2xl px-4 py-3">
                        <code className="flex-1 break-all font-mono text-sm text-foreground">
                          {generatedToken || 'Belum ada token yang dibuat'}
                        </code>
                        {generatedToken && (
                          <button
                            type="button"
                            onClick={handleCopyToken}
                            className="btn-liquid btn-liquid-ghost px-3 py-1.5 text-xs font-semibold"
                          >
                            {copied ? 'Tersalin!' : 'Copy'}
                          </button>
                        )}
                      </div>
                    )}

                    {/* Bulk token result */}
                    {tokenCount > 1 && bulkTokens.length > 0 && (
                      <div className="space-y-3">
                        <div className="flex items-center justify-between">
                          <p className="text-sm font-semibold text-foreground">
                            {bulkTokens.length} token berhasil di-generate
                          </p>
                          <button
                            type="button"
                            onClick={handleExportTokens}
                            className="btn-liquid btn-liquid-primary px-4 py-2 text-xs font-semibold"
                          >
                            Ekspor (.txt)
                          </button>
                        </div>
                        <div className="glass-surface-subtle max-h-48 overflow-y-auto rounded-2xl px-4 py-3">
                          {bulkTokens.map((t) => (
                            <code key={t} className="block break-all font-mono text-xs text-foreground-muted py-0.5">
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
            ) : activeMenu === 'monitoring' ? (
              <MonitoringPage
                tokenList={tokenList}
                tokenListLoading={tokenListLoading}
                tokenListError={tokenListError}
                filterStatus={filterStatus}
                setFilterStatus={setFilterStatus}
                filterDateFrom={filterDateFrom}
                setFilterDateFrom={setFilterDateFrom}
                filterDateTo={filterDateTo}
                setFilterDateTo={setFilterDateTo}
                onRefresh={fetchTokenList}
              />
            ) : (
              <div className="glass-surface rounded-[1.5rem] p-6 sm:p-8">
                <div className="rounded-2xl border border-dashed border-white/60 bg-white/40 p-10 text-center">
                  <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-2xl bg-brand-100/80 text-brand-600">
                    <MenuIcon name={activeMenu} className="h-5 w-5" />
                  </div>
                  <p className="mt-4 font-mono text-[10px] uppercase tracking-[0.2em] text-foreground-subtle">
                    Coming Soon
                  </p>
                  <h3 className="mt-1 text-xl font-semibold text-foreground">
                    {activeItem.label} belum tersedia
                  </h3>
                  <p className="mt-2 max-w-md mx-auto text-sm text-foreground-muted">
                    Fitur ini sedang dalam pengembangan. Untuk sementara, hanya
                    Generate Token yang dapat digunakan.
                  </p>
                  <button
                    type="button"
                    onClick={() => setActiveMenu('token')}
                    className="btn-liquid btn-liquid-primary mt-5 px-5 py-2.5 text-sm font-semibold"
                  >
                    Buka Generate Token
                  </button>
                </div>
              </div>
            )}
          </main>
        </div>
      </div>
    </div>
  );
}

type TokenRecord = { token: string; created_at: string | null; used: boolean; used_at: string | null };

function MonitoringPage({
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
}: {
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
}) {
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
          <MenuIcon name="monitoring" className="h-4 w-4 text-brand-600" />
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
          <label className="text-[10px] font-semibold uppercase tracking-wide text-foreground-subtle">
            Status
          </label>
          <div className="flex overflow-hidden rounded-xl border border-white/40 bg-white/30">
            {(['all', 'unused', 'used'] as const).map((s) => (
              <button
                key={s}
                type="button"
                onClick={() => setFilterStatus(s)}
                className={`px-3 py-2 text-xs font-semibold transition ${
                  filterStatus === s
                    ? 'bg-brand-500 text-white'
                    : 'text-foreground-muted hover:bg-white/50'
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
            onClick={() => { setFilterDateFrom(''); setFilterDateTo(''); setFilterStatus('all'); }}
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
                <th className="px-3 py-2.5 text-xs font-semibold uppercase tracking-wide text-foreground-subtle">Token</th>
                <th className="px-3 py-2.5 text-xs font-semibold uppercase tracking-wide text-foreground-subtle">Dibuat</th>
                <th className="px-3 py-2.5 text-xs font-semibold uppercase tracking-wide text-foreground-subtle">Status</th>
                <th className="px-3 py-2.5 text-xs font-semibold uppercase tracking-wide text-foreground-subtle">Dipakai Pada</th>
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

function SidebarItem({
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
      <MenuIcon name={item.key} className="h-4 w-4 shrink-0" />
      <span className="flex-1 truncate text-left">{item.label}</span>
      {!item.active && (
        <span className="rounded-full bg-white/60 px-1.5 py-0.5 font-mono text-[9px] uppercase tracking-wider text-foreground-subtle">
          Soon
        </span>
      )}
    </button>
  );
}

function KpiCard({
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
          <MenuIcon name={icon} className="h-4 w-4" />
        </div>
        <div className="min-w-0 flex-1">
          <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-foreground-subtle">
            {label}
          </p>
          <p className="truncate text-base font-semibold text-foreground">{value}</p>
          <p className="text-[11px] text-foreground-muted">{hint}</p>
        </div>
      </div>
    </div>
  );
}

type IconName = MenuKey | 'home' | 'logout' | 'user' | 'key' | 'pulse';

function MenuIcon({ name, className }: { name: IconName; className?: string }) {
  const cls = className ?? 'h-4 w-4';
  const common = {
    xmlns: 'http://www.w3.org/2000/svg',
    viewBox: '0 0 24 24',
    fill: 'none',
    stroke: 'currentColor',
    strokeWidth: 1.8,
    strokeLinecap: 'round' as const,
    strokeLinejoin: 'round' as const,
    className: cls,
  };
  switch (name) {
    case 'monitoring':
      return (
        <svg {...common}>
          <path d="M2 12h4l3-9 4 18 3-9h4" />
        </svg>
      );
    case 'token':
    case 'key':
      return (
        <svg {...common}>
          <circle cx="8" cy="15" r="4" />
          <path d="m10.85 12.15 7.4-7.4" />
          <path d="m18 5 3 3" />
          <path d="m15 8 3 3" />
        </svg>
      );
    case 'dashboard':
      return (
        <svg {...common}>
          <rect x="3" y="3" width="7" height="7" rx="1.5" />
          <rect x="14" y="3" width="7" height="7" rx="1.5" />
          <rect x="3" y="14" width="7" height="7" rx="1.5" />
          <rect x="14" y="14" width="7" height="7" rx="1.5" />
        </svg>
      );
    case 'users':
      return (
        <svg {...common}>
          <path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2" />
          <circle cx="9" cy="7" r="4" />
          <path d="M22 21v-2a4 4 0 0 0-3-3.87" />
          <path d="M16 3.13a4 4 0 0 1 0 7.75" />
        </svg>
      );
    case 'uploads':
      return (
        <svg {...common}>
          <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
          <polyline points="17 8 12 3 7 8" />
          <line x1="12" y1="3" x2="12" y2="15" />
        </svg>
      );
    case 'server':
      return (
        <svg {...common}>
          <rect x="2" y="3" width="20" height="8" rx="2" />
          <rect x="2" y="13" width="20" height="8" rx="2" />
          <line x1="6" y1="7" x2="6.01" y2="7" />
          <line x1="6" y1="17" x2="6.01" y2="17" />
        </svg>
      );
    case 'settings':
      return (
        <svg {...common}>
          <circle cx="12" cy="12" r="3" />
          <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.6a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" />
        </svg>
      );
    case 'home':
      return (
        <svg {...common}>
          <path d="M3 9.5 12 3l9 6.5V21a1 1 0 0 1-1 1h-5v-7h-6v7H4a1 1 0 0 1-1-1z" />
        </svg>
      );
    case 'logout':
      return (
        <svg {...common}>
          <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
          <polyline points="16 17 21 12 16 7" />
          <line x1="21" y1="12" x2="9" y2="12" />
        </svg>
      );
    case 'user':
      return (
        <svg {...common}>
          <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
          <circle cx="12" cy="7" r="4" />
        </svg>
      );
    case 'pulse':
      return (
        <svg {...common}>
          <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
        </svg>
      );
    default:
      return null;
  }
}
