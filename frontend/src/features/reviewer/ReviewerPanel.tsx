'use client';

import { useEffect, useState } from 'react';
import { AdminLoginScreen } from '@/features/admin/AdminLoginScreen';
import { ReviewerCheckForm } from './ReviewerCheckForm';
import { API_URL, STORAGE_KEY } from '@/features/admin/constants';

export function ReviewerPanel() {
  const [adminId, setAdminId] = useState('');
  const [adminUsername, setAdminUsername] = useState('');

  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [loginError, setLoginError] = useState('');
  const [loginLoading, setLoginLoading] = useState(false);

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

  async function handleLogin() {
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
      localStorage.setItem(STORAGE_KEY, JSON.stringify({ admin_id: data.admin_id, username: data.username }));
      setPassword('');
    } catch (err) {
      setLoginError(`Tidak bisa terhubung ke server: ${err instanceof Error ? err.message : String(err)}`);
    } finally {
      setLoginLoading(false);
    }
  }

  function handleLogout() {
    localStorage.removeItem(STORAGE_KEY);
    setAdminId('');
    setAdminUsername('');
  }

  if (!adminId) {
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
        onLogin={handleLogin}
      />
    );
  }

  return <ReviewerCheckForm adminId={adminId} adminUsername={adminUsername} onLogout={handleLogout} />;
}
