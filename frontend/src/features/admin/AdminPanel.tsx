'use client';

import { useState, useSyncExternalStore } from 'react';
import { AdminComingSoonPanel } from './AdminComingSoonPanel';
import { AdminDesktopHeader } from './AdminDesktopHeader';
import { AdminLoginScreen } from './AdminLoginScreen';
import { AdminMobileNav } from './AdminMobileNav';
import { AdminOverviewPanel } from './AdminOverviewPanel';
import { AdminSidebar } from './AdminSidebar';
import { API_URL, MENU_ITEMS, STORAGE_KEY } from './constants';
import { TokenGeneratePanel } from './TokenGeneratePanel';
import { TokenMonitoringPanel } from './TokenMonitoringPanel';
import { UploadHistoryPanel } from './UploadHistoryPanel';
import type { MenuKey } from './types';

type AdminSession = {
  adminId: string;
  username: string;
};

const EMPTY_ADMIN_SESSION: AdminSession = { adminId: '', username: '' };
const ADMIN_SESSION_CHANGE_EVENT = 'admin-session-change';

function subscribeHydration() {
  return () => {};
}

function getClientHydrationSnapshot() {
  return true;
}

function getServerHydrationSnapshot() {
  return false;
}

function subscribeStoredAdminSession(onStoreChange: () => void) {
  if (typeof window === 'undefined') return () => {};

  const handleChange = () => onStoreChange();
  window.addEventListener('storage', handleChange);
  window.addEventListener(ADMIN_SESSION_CHANGE_EVENT, handleChange);

  return () => {
    window.removeEventListener('storage', handleChange);
    window.removeEventListener(ADMIN_SESSION_CHANGE_EVENT, handleChange);
  };
}

function getStoredAdminSessionSnapshot() {
  if (typeof window === 'undefined') return null;
  try {
    return localStorage.getItem(STORAGE_KEY);
  } catch {
    return null;
  }
}

function getServerAdminSessionSnapshot() {
  return null;
}

function parseStoredAdminSession(raw: string | null): AdminSession {
  try {
    if (!raw) return EMPTY_ADMIN_SESSION;
    const parsed = JSON.parse(raw) as { admin_id?: string; username?: string };
    return {
      adminId: parsed.admin_id ?? '',
      username: parsed.username ?? '',
    };
  } catch {
    return EMPTY_ADMIN_SESSION;
  }
}

function emitAdminSessionChange() {
  window.dispatchEvent(new Event(ADMIN_SESSION_CHANGE_EVENT));
}

function storeAdminSession(session: AdminSession) {
  localStorage.setItem(
    STORAGE_KEY,
    JSON.stringify({ admin_id: session.adminId, username: session.username }),
  );
  emitAdminSessionChange();
}

function clearStoredAdminSession() {
  localStorage.removeItem(STORAGE_KEY);
  emitAdminSessionChange();
}

export function AdminPanel() {
  const sessionReady = useSyncExternalStore(
    subscribeHydration,
    getClientHydrationSnapshot,
    getServerHydrationSnapshot,
  );
  const storedSessionRaw = useSyncExternalStore(
    subscribeStoredAdminSession,
    getStoredAdminSessionSnapshot,
    getServerAdminSessionSnapshot,
  );
  const storedSession = sessionReady ? parseStoredAdminSession(storedSessionRaw) : EMPTY_ADMIN_SESSION;
  const adminId = storedSession.adminId;
  const adminUsername = storedSession.username;

  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [loginError, setLoginError] = useState('');
  const [loginLoading, setLoginLoading] = useState(false);

  const [activeMenu, setActiveMenu] = useState<MenuKey>('dashboard');
  const [showPassword, setShowPassword] = useState(false);

  const [tokenCount, setTokenCount] = useState(1);
  const [generatedToken, setGeneratedToken] = useState('');
  const [bulkTokens, setBulkTokens] = useState<string[]>([]);
  const [tokenError, setTokenError] = useState('');
  const [tokenLoading, setTokenLoading] = useState(false);
  const [copied, setCopied] = useState(false);

  function handleLogout() {
    clearStoredAdminSession();
    setGeneratedToken('');
    setBulkTokens([]);
    setTokenError('');
    setActiveMenu('dashboard');
  }

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
      storeAdminSession({
        adminId: data.admin_id,
        username: data.username,
      });
      setPassword('');
    } catch (err) {
      setLoginError(`Tidak bisa terhubung ke server: ${err instanceof Error ? err.message : String(err)}`);
    } finally {
      setLoginLoading(false);
    }
  }

  async function handleGenerateToken() {
    setTokenError('');
    setGeneratedToken('');
    setBulkTokens([]);
    setCopied(false);
    if (!adminId) {
      setTokenError('Belum login.');
      return;
    }
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
          if (res.status === 401) {
            handleLogout();
            setTokenError('Session berakhir. Silakan login ulang.');
            return;
          }
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
          if (res.status === 401) {
            handleLogout();
            setTokenError('Session berakhir. Silakan login ulang.');
            return;
          }
          setTokenError(typeof data?.detail === 'string' ? data.detail : 'Gagal generate token');
          return;
        }
        setBulkTokens(data.tokens as string[]);
      }
    } catch (err) {
      setTokenError(`Tidak bisa terhubung ke server: ${err instanceof Error ? err.message : String(err)}`);
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
    } catch {
      /* ignore */
    }
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

  const isAuthed = Boolean(adminId);

  if (!sessionReady) {
    return (
      <main className="relative flex min-h-[calc(100vh-4rem)] items-center justify-center px-4 py-10 sm:px-6">
        <div className="text-sm font-medium text-slate-600">Memuat sesi admin...</div>
      </main>
    );
  }

  if (!isAuthed) {
    return (
      <AdminLoginScreen
        username={username}
        password={password}
        showPassword={showPassword}
        loginError={loginError}
        loginLoading={loginLoading}
        onUsernameChange={setUsername}
        onPasswordChange={setPassword}
        onTogglePassword={() => setShowPassword((p) => !p)}
        onLogin={handleAuth}
      />
    );
  }

  const activeItem = MENU_ITEMS.find((item) => item.key === activeMenu) ?? MENU_ITEMS[0];

  return (
    <div className="relative">
      <div className="relative flex min-h-screen">
        <AdminSidebar activeMenu={activeMenu} onSelectMenu={setActiveMenu} onLogout={handleLogout} />

        <div className="flex min-w-0 flex-1 flex-col">
          <AdminMobileNav activeMenu={activeMenu} onSelectMenu={setActiveMenu} onLogout={handleLogout} />
          <AdminDesktopHeader activeItem={activeItem} adminUsername={adminUsername} />

          <main className="flex-1 px-4 py-6 sm:px-6">
            {activeMenu === 'dashboard' ? (
              <AdminOverviewPanel adminId={adminId} />
            ) : activeMenu === 'token' ? (
              <TokenGeneratePanel
                tokenCount={tokenCount}
                onTokenCountChange={setTokenCount}
                onGenerate={handleGenerateToken}
                tokenLoading={tokenLoading}
                generatedToken={generatedToken}
                bulkTokens={bulkTokens}
                copied={copied}
                onCopy={handleCopyToken}
                onExportBulk={handleExportTokens}
                tokenError={tokenError}
              />
            ) : activeMenu === 'monitoring' ? (
              <TokenMonitoringPanel adminId={adminId} />
            ) : activeMenu === 'uploads' ? (
              <UploadHistoryPanel adminId={adminId} />
            ) : (
              <AdminComingSoonPanel
                activeItem={activeItem}
                activeMenu={activeMenu}
                onGoToToken={() => setActiveMenu('token')}
              />
            )}
          </main>
        </div>
      </div>
    </div>
  );
}
