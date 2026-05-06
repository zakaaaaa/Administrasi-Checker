'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';

const uploadByScheme = [
  { label: 'PKM-KC', percent: 78, count: 41 },
  { label: 'PKM-K', percent: 62, count: 28 },
  { label: 'PKM-RE', percent: 47, count: 19 },
  { label: 'PKM-PI', percent: 35, count: 13 },
];

const uploadTrend = [12, 18, 16, 24, 22, 30, 34];
const userTrend = [22, 27, 19, 25, 31, 29, 37];

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';
const STORAGE_KEY = 'admin_session_v1';

export default function AdminPage() {
  const [adminId, setAdminId] = useState<string>('');
  const [adminUsername, setAdminUsername] = useState<string>('');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [loginError, setLoginError] = useState('');
  const [loginLoading, setLoginLoading] = useState(false);

  const [generatedToken, setGeneratedToken] = useState('');
  const [tokenError, setTokenError] = useState('');
  const [tokenLoading, setTokenLoading] = useState(false);

  // Restore session on mount
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
    setTokenError('');
  }

  async function handleGenerateToken() {
    setTokenError('');
    setGeneratedToken('');
    if (!adminId) {
      setTokenError('Belum login.');
      return;
    }
    setTokenLoading(true);
    try {
      const res = await fetch(`${API_URL}/api/admin/tokens`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ admin_id: adminId }),
      });
      const data = await res.json();
      if (!res.ok) {
        // Session might be invalid (admin deleted)
        if (res.status === 401) {
          handleLogout();
          setTokenError('Session berakhir. Silakan login ulang.');
          return;
        }
        setTokenError(typeof data?.detail === 'string' ? data.detail : 'Gagal generate token');
        return;
      }
      setGeneratedToken(data.token);
    } catch (err) {
      setTokenError(`Tidak bisa terhubung ke server: ${err instanceof Error ? err.message : err}`);
    } finally {
      setTokenLoading(false);
    }
  }

  const isAuthed = Boolean(adminId);

  return (
    <main className="relative mx-auto max-w-6xl px-4 pb-20 pt-10 sm:px-6">
      <section className="glass-surface-elevated relative overflow-hidden rounded-[2rem] p-6 sm:p-10">
        <div aria-hidden className="orb orb-accent absolute -right-12 -top-10 h-48 w-48 opacity-55" />
        <p className="font-mono text-xs uppercase tracking-[0.2em] text-foreground-subtle">
          Admin Flow
        </p>
        <h1 className="mt-3 text-3xl font-light tracking-tight text-foreground sm:text-5xl">
          Auth dan <span className="font-display italic text-gradient-brand">dashboard admin</span>
        </h1>
        <p className="mt-4 max-w-3xl text-sm text-foreground-muted">
          Dashboard ini jadi ruang kontrol utama: pantau upload, perilaku user, kesehatan
          server, lalu generate token untuk user.
        </p>
        {isAuthed && (
          <p className="mt-3 text-xs text-foreground-subtle">
            Login sebagai <strong>{adminUsername}</strong>{' '}
            <button
              type="button"
              onClick={handleLogout}
              className="ml-2 underline hover:text-red-700"
            >
              Logout
            </button>
          </p>
        )}
      </section>

      {!isAuthed ? (
        <section className="mt-6 glass-surface rounded-[1.75rem] p-6 sm:p-8">
          <h2 className="text-xl font-semibold text-foreground">Login Admin</h2>

          <div className="mt-5 grid gap-3">
            <input
              value={username}
              onChange={(event) => setUsername(event.target.value)}
              placeholder="Username admin"
              className="glass-input rounded-2xl px-4 py-3 text-sm"
              onKeyDown={(e) => {
                if (e.key === 'Enter') handleAuth();
              }}
            />
            <input
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              placeholder="Password"
              className="glass-input rounded-2xl px-4 py-3 text-sm"
              onKeyDown={(e) => {
                if (e.key === 'Enter') handleAuth();
              }}
            />
            <button
              type="button"
              onClick={handleAuth}
              disabled={loginLoading}
              className="btn-liquid btn-liquid-primary mt-2 px-5 py-3 text-sm disabled:opacity-50"
            >
              {loginLoading ? 'Memproses...' : 'Login'}
            </button>
            {loginError && (
              <div className="rounded-2xl border border-red-300 bg-red-50/70 p-3 text-sm text-red-700">
                {loginError}
              </div>
            )}
          </div>
        </section>
      ) : (
        <section className="mt-6 space-y-5">
          <div className="grid gap-4 sm:grid-cols-3">
            <KpiCard title="Upload Hari Ini" value="34" unit="berkas" delta={12} />
            <KpiCard title="User Aktif" value="37" unit="user" delta={9} />
            <KpiCard title="CPU Rata-rata" value="31" unit="%" delta={-4} />
          </div>

          <div className="grid gap-5 lg:grid-cols-2">
            <div className="glass-surface rounded-[1.75rem] p-6 sm:p-8">
              <h2 className="text-lg font-semibold text-foreground">Grafik Upload Mingguan</h2>
              <p className="mt-1 text-xs text-foreground-muted">
                Total berkas masuk selama 7 hari terakhir.
              </p>
              <LineChart
                values={uploadTrend}
                labels={['Sen', 'Sel', 'Rab', 'Kam', 'Jum', 'Sab', 'Min']}
                colorClass="text-brand-500"
              />
            </div>

            <div className="glass-surface rounded-[1.75rem] p-6 sm:p-8">
              <h2 className="text-lg font-semibold text-foreground">Grafik User Aktif</h2>
              <p className="mt-1 text-xs text-foreground-muted">
                Pergerakan user aktif harian.
              </p>
              <LineChart
                values={userTrend}
                labels={['Sen', 'Sel', 'Rab', 'Kam', 'Jum', 'Sab', 'Min']}
                colorClass="text-violet-500"
              />
            </div>
          </div>

          <div className="grid gap-5 lg:grid-cols-[1.2fr_0.8fr]">
            <div className="glass-surface rounded-[1.75rem] p-6 sm:p-8">
              <h3 className="text-lg font-semibold text-foreground">Upload per Skema</h3>
              <div className="mt-5 space-y-4">
                {uploadByScheme.map((item) => (
                  <ProgressRow
                    key={item.label}
                    label={item.label}
                    value={item.percent}
                    count={item.count}
                  />
                ))}
              </div>
            </div>

            <div className="glass-surface rounded-[1.75rem] p-6 sm:p-8">
              <h3 className="text-lg font-semibold text-foreground">Monitoring Server</h3>
              <p className="mt-1 text-xs text-foreground-muted">CPU, RAM, dan Disk usage.</p>
              <DonutChart cpu={31} ram={58} disk={44} />
            </div>
          </div>

          <div className="glass-surface rounded-[1.75rem] p-6 sm:p-8">
            <h3 className="text-lg font-semibold text-foreground">Generate Token</h3>
            <p className="mt-2 text-sm text-foreground-muted">
              Klik tombol untuk membuat token sekali pakai bagi pengguna.
            </p>
            <div className="mt-4 flex flex-wrap items-center gap-3">
              <button
                type="button"
                onClick={handleGenerateToken}
                disabled={tokenLoading}
                className="btn-liquid btn-liquid-primary px-5 py-2.5 text-sm disabled:opacity-50"
              >
                {tokenLoading ? 'Memproses...' : 'Generate Token'}
              </button>
              <code className="glass-surface-subtle rounded-xl px-3 py-2 text-xs text-foreground">
                {generatedToken || 'Belum ada token yang dibuat'}
              </code>
              {generatedToken && (
                <button
                  type="button"
                  onClick={() => navigator.clipboard.writeText(generatedToken)}
                  className="btn-liquid btn-liquid-ghost px-3 py-2 text-xs"
                >
                  Copy
                </button>
              )}
            </div>
            {tokenError && (
              <div className="mt-3 rounded-2xl border border-red-300 bg-red-50/70 p-3 text-sm text-red-700">
                {tokenError}
              </div>
            )}
          </div>
        </section>
      )}

      <div className="mt-6">
        <Link href="/" className="btn-liquid btn-liquid-ghost inline-flex px-4 py-2 text-sm">
          Kembali ke Beranda
        </Link>
      </div>
    </main>
  );
}

function KpiCard({
  title,
  value,
  unit,
  delta,
}: {
  title: string;
  value: string;
  unit: string;
  delta: number;
}) {
  return (
    <article className="glass-surface-subtle rounded-2xl p-5">
      <p className="font-mono text-[11px] uppercase tracking-[0.2em] text-foreground-subtle">
        {title}
      </p>
      <div className="mt-2 flex items-end gap-1.5">
        <p className="text-3xl font-semibold tracking-tight text-foreground">{value}</p>
        <span className="pb-1 text-xs text-foreground-muted">{unit}</span>
      </div>
      <p className={`mt-1 text-xs ${delta >= 0 ? 'text-emerald-700' : 'text-amber-700'}`}>
        {delta >= 0 ? '+' : ''}
        {delta}% vs kemarin
      </p>
    </article>
  );
}

function ProgressRow({ label, value, count }: { label: string; value: number; count: number }) {
  return (
    <div>
      <div className="mb-1.5 flex items-center justify-between text-xs text-foreground-muted">
        <span>{label}</span>
        <span>
          {count} berkas ({value}%)
        </span>
      </div>
      <div className="h-2 rounded-full bg-white/60">
        <div
          className="h-full rounded-full bg-gradient-to-r from-brand-400 to-brand-600"
          style={{ width: `${value}%` }}
        />
      </div>
    </div>
  );
}

function LineChart({
  values,
  labels,
  colorClass,
}: {
  values: number[];
  labels: string[];
  colorClass: string;
}) {
  const max = Math.max(...values);
  const min = Math.min(...values);
  const range = Math.max(max - min, 1);
  const points = values
    .map((value, index) => {
      const x = (index / (values.length - 1)) * 100;
      const y = 100 - ((value - min) / range) * 100;
      return `${x},${y}`;
    })
    .join(' ');

  return (
    <div className="mt-4">
      <div className="glass-surface-subtle rounded-2xl p-3">
        <svg viewBox="0 0 100 100" className={`h-44 w-full ${colorClass}`}>
          <polyline
            fill="none"
            stroke="currentColor"
            strokeWidth="2.8"
            points={points}
            strokeLinecap="round"
            strokeLinejoin="round"
          />
          {values.map((value, index) => {
            const x = (index / (values.length - 1)) * 100;
            const y = 100 - ((value - min) / range) * 100;
            return <circle key={`${value}-${index}`} cx={x} cy={y} r="1.8" fill="currentColor" />;
          })}
        </svg>
      </div>
      <div className="mt-2 grid grid-cols-7 gap-1 text-center text-[10px] uppercase text-foreground-subtle">
        {labels.map((label) => (
          <span key={label}>{label}</span>
        ))}
      </div>
    </div>
  );
}

function DonutChart({ cpu, ram, disk }: { cpu: number; ram: number; disk: number }) {
  const circle = 2 * Math.PI * 42;

  return (
    <div className="mt-4">
      <div className="glass-surface-subtle flex items-center justify-center rounded-2xl p-4">
        <svg viewBox="0 0 100 100" className="h-44 w-44">
          <circle cx="50" cy="50" r="42" stroke="rgba(255,255,255,.5)" strokeWidth="8" fill="none" />
          <circle
            cx="50"
            cy="50"
            r="42"
            stroke="hsl(var(--brand-500))"
            strokeWidth="8"
            fill="none"
            strokeDasharray={`${(cpu / 100) * circle} ${circle}`}
            transform="rotate(-90 50 50)"
            strokeLinecap="round"
          />
        </svg>
      </div>
      <div className="mt-3 space-y-2 text-xs text-foreground-muted">
        <p>CPU: {cpu}%</p>
        <p>RAM: {ram}%</p>
        <p>Disk: {disk}%</p>
      </div>
    </div>
  );
}
