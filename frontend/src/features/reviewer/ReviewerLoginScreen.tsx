'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { supabase } from '@/lib/supabaseClient';

export function ReviewerLoginScreen() {
  const router = useRouter();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  async function handleLogin() {
    setError('');
    if (!email.trim() || !password) {
      setError('Email dan password wajib diisi.');
      return;
    }
    setLoading(true);
    const { error: err } = await supabase.auth.signInWithPassword({
      email: email.trim(),
      password,
    });
    setLoading(false);
    if (err) {
      setError(err.message || 'Gagal masuk. Periksa email/password.');
      return;
    }
    router.replace('/reviewer/check');
  }

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
          <p className="font-mono text-xs uppercase tracking-[0.2em] text-foreground-subtle">
            Reviewer · Tanpa Token
          </p>
          <h1 className="mt-2 text-2xl font-semibold tracking-tight text-foreground sm:text-3xl">
            Login Reviewer
          </h1>
          <p className="mt-2 text-sm text-foreground-muted">
            Gunakan akun reviewer yang telah dibuatkan oleh admin.
          </p>

          <div className="mt-6 space-y-4">
            <div>
              <label className="text-xs font-semibold uppercase tracking-wide text-foreground-subtle">
                Email
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
                    <path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z" />
                    <polyline points="22,6 12,13 2,6" />
                  </svg>
                </span>
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="reviewer@kampus.ac.id"
                  autoComplete="email"
                  className="glass-input w-full rounded-2xl py-3 pl-11 pr-4 text-sm font-medium"
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') handleLogin();
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
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Masukkan password"
                  autoComplete="current-password"
                  className="glass-input w-full rounded-2xl py-3 pl-11 pr-11 text-sm font-medium"
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') handleLogin();
                  }}
                />
                <button
                  type="button"
                  onClick={() => setShowPassword((s) => !s)}
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
              onClick={handleLogin}
              disabled={loading}
              className="btn-liquid btn-liquid-primary w-full px-5 py-3 text-base font-semibold disabled:opacity-50"
            >
              {loading ? 'Memproses…' : 'Masuk sebagai Reviewer'}
            </button>

            {error && (
              <div className="rounded-2xl border border-red-300 bg-red-50/70 p-3 text-sm font-medium text-red-700">
                {error}
              </div>
            )}

            <div className="flex items-center gap-3">
              <div className="h-px flex-1 bg-foreground/10" />
              <span className="text-xs uppercase tracking-wider text-foreground-subtle">Atau</span>
              <div className="h-px flex-1 bg-foreground/10" />
            </div>

            <p className="text-center text-sm text-foreground-muted">
              Bukan reviewer?{' '}
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
