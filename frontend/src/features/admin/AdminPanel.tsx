'use client';

import { useCallback, useEffect, useState } from 'react';
import { AdminComingSoonPanel } from './AdminComingSoonPanel';
import { AdminDesktopHeader } from './AdminDesktopHeader';
import { AdminKpiGrid } from './AdminKpiGrid';
import { AdminLoginScreen } from './AdminLoginScreen';
import { AdminMobileNav } from './AdminMobileNav';
import { AdminSidebar } from './AdminSidebar';
import { API_URL, MENU_ITEMS, STORAGE_KEY } from './constants';
import { TokenGeneratePanel } from './TokenGeneratePanel';
import { TokenMonitoringPanel } from './TokenMonitoringPanel';
import type { MenuKey, TokenRecord } from './types';

export function AdminPanel() {
  const [adminId, setAdminId] = useState('');
  const [adminUsername, setAdminUsername] = useState('');
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

  const fetchTokenList = useCallback(async () => {
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
      setTokenListError(
        `Tidak bisa terhubung ke server: ${err instanceof Error ? err.message : String(err)}`,
      );
    } finally {
      setTokenListLoading(false);
    }
  }, [adminId]);

  useEffect(() => {
    if (activeMenu === 'monitoring' && adminId) {
      void fetchTokenList();
    }
  }, [activeMenu, adminId, fetchTokenList]);

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
      void fetchTokenList();
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
            <AdminKpiGrid
              adminUsername={adminUsername}
              bulkTokensLength={bulkTokens.length}
              hasGeneratedSingle={Boolean(generatedToken)}
            />

            {activeMenu === 'token' ? (
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
              <TokenMonitoringPanel
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
