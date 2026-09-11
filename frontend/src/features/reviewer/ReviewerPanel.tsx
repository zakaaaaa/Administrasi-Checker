'use client';

import { useEffect, useState } from 'react';
import { AdminLoginScreen } from '@/features/admin/AdminLoginScreen';
import { ReviewerCheckForm } from './ReviewerCheckForm';
import { API_URL, STORAGE_KEY as ADMIN_STORAGE_KEY } from '@/features/admin/constants';

// Akses: reviewer hanya panel reviewer; admin boleh panel reviewer juga.
// Sesi reviewer disimpan terpisah supaya tidak ikut "masuk" ke /admin,
// sedangkan admin memakai sesi admin yang sama dengan /admin — login di
// salah satu panel berlaku di keduanya.
const REVIEWER_STORAGE_KEY = 'reviewer_session_v1';

type ReviewerSession = {
  reviewerId: string;
  displayName: string;
  role: 'reviewer' | 'admin';
};

function readStoredSession(): ReviewerSession | null {
  try {
    const reviewerRaw = localStorage.getItem(REVIEWER_STORAGE_KEY);
    if (reviewerRaw) {
      const parsed = JSON.parse(reviewerRaw) as { reviewer_id?: string; username?: string; full_name?: string };
      if (parsed.reviewer_id && parsed.username) {
        return {
          reviewerId: parsed.reviewer_id,
          displayName: parsed.full_name || parsed.username,
          role: 'reviewer',
        };
      }
    }
    const adminRaw = localStorage.getItem(ADMIN_STORAGE_KEY);
    if (adminRaw) {
      const parsed = JSON.parse(adminRaw) as { admin_id?: string; username?: string };
      if (parsed.admin_id && parsed.username) {
        return { reviewerId: parsed.admin_id, displayName: parsed.username, role: 'admin' };
      }
    }
  } catch {
    // ignore
  }
  return null;
}

export function ReviewerPanel() {
  const [session, setSession] = useState<ReviewerSession | null>(null);

  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [loginError, setLoginError] = useState('');
  const [loginLoading, setLoginLoading] = useState(false);

  useEffect(() => {
    const stored = readStoredSession();
    if (stored) setSession(stored);
  }, []);

  async function handleLogin() {
    setLoginError('');
    if (!username || !password) {
      setLoginError('Username dan password wajib diisi.');
      return;
    }
    setLoginLoading(true);
    try {
      const res = await fetch(`${API_URL}/api/reviewer/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password }),
      });
      const data = await res.json();
      if (!res.ok) {
        setLoginError(typeof data?.detail === 'string' ? data.detail : 'Login gagal');
        return;
      }
      const isAdmin = data.role === 'admin';
      try {
        if (isAdmin) {
          // Sesi reviewer lama didahulukan saat memuat ulang — buang.
          localStorage.removeItem(REVIEWER_STORAGE_KEY);
          localStorage.setItem(
            ADMIN_STORAGE_KEY,
            JSON.stringify({ admin_id: data.reviewer_id, username: data.username }),
          );
        } else {
          localStorage.setItem(
            REVIEWER_STORAGE_KEY,
            JSON.stringify({ reviewer_id: data.reviewer_id, username: data.username, full_name: data.full_name }),
          );
        }
      } catch {
        // sesi tetap berlaku sampai tab ditutup
      }
      setSession({
        reviewerId: data.reviewer_id,
        displayName: isAdmin ? data.username : data.full_name || data.username,
        role: isAdmin ? 'admin' : 'reviewer',
      });
      setPassword('');
    } catch (err) {
      setLoginError(`Tidak bisa terhubung ke server: ${err instanceof Error ? err.message : String(err)}`);
    } finally {
      setLoginLoading(false);
    }
  }

  function handleLogout() {
    try {
      // Keluar dari sesi yang sedang dipakai saja. Untuk admin, ini juga
      // mengeluarkan dari /admin (sesinya memang satu).
      localStorage.removeItem(session?.role === 'admin' ? ADMIN_STORAGE_KEY : REVIEWER_STORAGE_KEY);
    } catch {
      // ignore
    }
    setSession(null);
  }

  if (!session) {
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
        footerPrompt="Bukan reviewer?"
      />
    );
  }

  return (
    <ReviewerCheckForm
      reviewerId={session.reviewerId}
      displayName={session.displayName}
      isAdmin={session.role === 'admin'}
      onLogout={handleLogout}
    />
  );
}
