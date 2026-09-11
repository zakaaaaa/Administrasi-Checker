'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { AdminMenuIcon } from './AdminMenuIcon';
import { API_URL } from './constants';

// ─── Types ────────────────────────────────────────────────────────────────────

type ServerStats = {
  collected_at: string;
  system: { hostname: string; cpu_cores_logical: number };
  cpu: { percent: number; per_core: number[]; load_avg: [number, number, number] };
  memory: { total: number; available: number; used: number; percent: number };
  disks: {
    device: string;
    mountpoint: string;
    fstype: string;
    total: number;
    used: number;
    free: number;
    percent: number;
  }[];
  network: {
    sent_total: number;
    recv_total: number;
    sent_per_sec: number | null;
    recv_per_sec: number | null;
  };
  disk_io: {
    read_total: number;
    write_total: number;
    read_per_sec: number | null;
    write_per_sec: number | null;
  };
  services: {
    name: string;
    label: string;
    active_state: string;
    sub_state: string;
    main_pid: number | null;
    memory_bytes: number | null;
    uptime_seconds: number | null;
  }[];
};

type Sample = { t: number; cpu: number; mem: number; net: number | null };

const POLL_MS = 5000;
const HISTORY_SIZE = 60; // 60 × 5 dtk = 5 menit terakhir

// ─── Helpers ──────────────────────────────────────────────────────────────────

function fmtNum(n: number, digits = 1) {
  return n.toLocaleString('id-ID', { maximumFractionDigits: digits });
}

function fmtBytes(bytes: number | null | undefined, digits = 1): string {
  if (bytes === null || bytes === undefined) return '—';
  const units = ['B', 'KB', 'MB', 'GB', 'TB'];
  let v = bytes;
  let i = 0;
  while (v >= 1024 && i < units.length - 1) {
    v /= 1024;
    i += 1;
  }
  return `${fmtNum(v, i === 0 ? 0 : digits)} ${units[i]}`;
}

function fmtRate(bytesPerSec: number | null | undefined): string {
  return bytesPerSec === null || bytesPerSec === undefined ? '—' : `${fmtBytes(bytesPerSec)}/s`;
}

function fmtUptime(seconds: number | null | undefined): string {
  if (seconds === null || seconds === undefined) return '—';
  const d = Math.floor(seconds / 86400);
  const h = Math.floor((seconds % 86400) / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  if (d > 0) return `${d} hari ${h} jam`;
  if (h > 0) return `${h} jam ${m} mnt`;
  if (m > 0) return `${m} mnt`;
  return `${seconds} dtk`;
}

function fmtTime(ms: number) {
  return new Date(ms).toLocaleTimeString('id-ID', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
}

type Severity = {
  label: string;
  bar: string;
  track: string;
  badge: string;
  dot: string;
};

function severity(percent: number): Severity {
  if (percent >= 90) {
    return {
      label: 'Kritis',
      bar: 'bg-red-500',
      track: 'bg-red-100',
      badge: 'bg-red-50 text-red-700 ring-red-200',
      dot: 'bg-red-500',
    };
  }
  if (percent >= 70) {
    return {
      label: 'Tinggi',
      bar: 'bg-amber-500',
      track: 'bg-amber-100',
      badge: 'bg-amber-50 text-amber-700 ring-amber-200',
      dot: 'bg-amber-500',
    };
  }
  return {
    label: 'Normal',
    bar: 'bg-brand-500',
    track: 'bg-brand-100',
    badge: 'bg-emerald-50 text-emerald-700 ring-emerald-200',
    dot: 'bg-emerald-500',
  };
}

const SERVICE_STATES: Record<string, { label: string; dot: string; text: string }> = {
  active:       { label: 'Berjalan',  dot: 'bg-emerald-500', text: 'text-emerald-700' },
  activating:   { label: 'Memulai',   dot: 'bg-amber-500',   text: 'text-amber-700' },
  reloading:    { label: 'Reload',    dot: 'bg-amber-500',   text: 'text-amber-700' },
  deactivating: { label: 'Berhenti…', dot: 'bg-amber-500',   text: 'text-amber-700' },
  inactive:     { label: 'Mati',      dot: 'bg-red-500',     text: 'text-red-700' },
  failed:       { label: 'Gagal',     dot: 'bg-red-500',     text: 'text-red-700' },
};

// ─── Sub-components ───────────────────────────────────────────────────────────

function SeverityBadge({ percent }: { percent: number }) {
  const s = severity(percent);
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-[11px] font-semibold ring-1 ${s.badge}`}>
      <span className={`h-1.5 w-1.5 rounded-full ${s.dot}`} />
      {s.label}
    </span>
  );
}

function Meter({ percent, className = 'h-2' }: { percent: number; className?: string }) {
  const s = severity(percent);
  const width = Math.min(100, Math.max(0, percent));
  return (
    <div className={`overflow-hidden rounded-full ${s.track} ${className}`}>
      <div
        className={`h-full rounded-full ${s.bar} transition-[width] duration-500`}
        style={{ width: `${width}%` }}
      />
    </div>
  );
}

/**
 * Riwayat satu metrik. Titik terbaru di kanan; slot tetap HISTORY_SIZE supaya
 * skala waktu konsisten saat riwayat masih pendek. Hover → garis + tooltip.
 */
function Sparkline({
  samples,
  pick,
  format,
  fixedMax,
}: {
  samples: Sample[];
  pick: (s: Sample) => number | null;
  format: (v: number) => string;
  fixedMax?: number;
}) {
  const [hoverIdx, setHoverIdx] = useState<number | null>(null);
  const W = 100;
  const H = 40;
  const step = W / (HISTORY_SIZE - 1);
  const n = samples.length;
  const values = samples.map(pick);
  const observedMax = Math.max(0, ...values.filter((v): v is number => v !== null));
  const max = fixedMax ?? (observedMax > 0 ? observedMax * 1.2 : 1);

  const xAt = (i: number) => W - (n - 1 - i) * step;
  const yAt = (v: number) => H - 1 - (Math.min(v, max) / max) * (H - 4);

  let line = '';
  let area = '';
  let segStartX: number | null = null;
  let prevX = 0;
  values.forEach((v, i) => {
    if (v === null) {
      if (segStartX !== null) area += `L${prevX},${H} L${segStartX},${H} Z `;
      segStartX = null;
      return;
    }
    const x = xAt(i);
    const y = yAt(v);
    if (segStartX === null) {
      line += `M${x},${y} `;
      area += `M${x},${y} `;
      segStartX = x;
    } else {
      line += `L${x},${y} `;
      area += `L${x},${y} `;
    }
    prevX = x;
  });
  if (segStartX !== null) area += `L${prevX},${H} L${segStartX},${H} Z`;

  function handleMove(e: React.MouseEvent<HTMLDivElement>) {
    if (!n) return;
    const rect = e.currentTarget.getBoundingClientRect();
    const fx = ((e.clientX - rect.left) / rect.width) * W;
    const idx = n - 1 - Math.round((W - fx) / step);
    setHoverIdx(idx >= 0 && idx < n && values[idx] !== null ? idx : null);
  }

  const hv = hoverIdx !== null ? values[hoverIdx] : null;
  const hx = hoverIdx !== null ? xAt(hoverIdx) : 0;

  return (
    <div
      className="relative h-10 w-full cursor-crosshair"
      onMouseMove={handleMove}
      onMouseLeave={() => setHoverIdx(null)}
    >
      <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" className="h-full w-full overflow-visible">
        <line x1="0" y1={H - 0.5} x2={W} y2={H - 0.5} stroke="hsl(var(--border))" strokeWidth="1" vectorEffect="non-scaling-stroke" />
        {area && <path d={area} fill="hsl(var(--brand-100))" fillOpacity="0.7" />}
        {line && (
          <path
            d={line}
            fill="none"
            stroke="hsl(var(--brand-500))"
            strokeWidth="2"
            strokeLinejoin="round"
            strokeLinecap="round"
            vectorEffect="non-scaling-stroke"
          />
        )}
        {hv !== null && (
          <line x1={hx} y1="0" x2={hx} y2={H} stroke="hsl(var(--foreground-subtle))" strokeWidth="1" strokeDasharray="2 2" vectorEffect="non-scaling-stroke" />
        )}
      </svg>
      {hv !== null && hoverIdx !== null && (
        <>
          <span
            className="pointer-events-none absolute h-2.5 w-2.5 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-white bg-brand-600"
            style={{ left: `${hx}%`, top: `${(yAt(hv) / H) * 100}%` }}
          />
          <div
            className="pointer-events-none absolute bottom-full z-10 mb-1.5 -translate-x-1/2 whitespace-nowrap rounded-lg bg-slate-900 px-2 py-1 text-[11px] font-medium text-white shadow-lg"
            style={{ left: `${Math.min(85, Math.max(15, hx))}%` }}
          >
            <span className="tabular-nums">{format(hv)}</span>
            <span className="ml-1.5 text-white/60">{fmtTime(samples[hoverIdx].t)}</span>
          </div>
        </>
      )}
    </div>
  );
}

function MetricTile({
  label,
  value,
  sub,
  badgePercent,
  children,
}: {
  label: string;
  value: string;
  sub: string;
  badgePercent?: number;
  children: React.ReactNode;
}) {
  return (
    <div className="glass-surface flex flex-col gap-3 rounded-2xl p-5">
      <div className="flex items-start justify-between gap-2">
        <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-foreground-subtle">{label}</p>
        {badgePercent !== undefined && <SeverityBadge percent={badgePercent} />}
      </div>
      <div>
        <p className="text-2xl font-semibold tracking-tight text-foreground">{value}</p>
        <p className="mt-0.5 text-xs text-foreground-muted">{sub}</p>
      </div>
      <div className="mt-auto">{children}</div>
    </div>
  );
}

function SectionCard({ title, right, children }: { title: string; right?: React.ReactNode; children: React.ReactNode }) {
  return (
    <div className="glass-surface rounded-2xl p-5">
      <div className="mb-4 flex items-center justify-between gap-2">
        <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-foreground-subtle">{title}</p>
        {right}
      </div>
      {children}
    </div>
  );
}

// ─── Main ─────────────────────────────────────────────────────────────────────

export function ServerMonitoringPanel({ adminId }: { adminId: string }) {
  const [stats, setStats] = useState<ServerStats | null>(null);
  const [history, setHistory] = useState<Sample[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [paused, setPaused] = useState(false);
  const inFlight = useRef(false);

  const fetchStats = useCallback(async () => {
    if (!adminId || inFlight.current) return;
    inFlight.current = true;
    setLoading(true);
    try {
      const res = await fetch(
        `${API_URL}/api/admin/server-stats?admin_id=${encodeURIComponent(adminId)}`,
        { cache: 'no-store' },
      );
      const json = await res.json();
      if (!res.ok) {
        setError(typeof json?.detail === 'string' ? json.detail : 'Gagal memuat metrik server');
        return;
      }
      const data = json as ServerStats;
      const { sent_per_sec, recv_per_sec } = data.network;
      setError('');
      setStats(data);
      setHistory((prev) =>
        [
          ...prev,
          {
            t: Date.parse(data.collected_at),
            cpu: data.cpu.percent,
            mem: data.memory.percent,
            net: sent_per_sec === null || recv_per_sec === null ? null : sent_per_sec + recv_per_sec,
          },
        ].slice(-HISTORY_SIZE),
      );
    } catch (err) {
      setError(`Tidak bisa terhubung ke server: ${err instanceof Error ? err.message : String(err)}`);
    } finally {
      inFlight.current = false;
      setLoading(false);
    }
  }, [adminId]);

  // Polling berantai (bukan setInterval) supaya request tidak menumpuk;
  // dilewati saat tab browser tidak terlihat.
  useEffect(() => {
    if (paused) return;
    let cancelled = false;
    let timer: number | undefined;
    async function tick() {
      if (!document.hidden) await fetchStats();
      if (!cancelled) timer = window.setTimeout(tick, POLL_MS);
    }
    timer = window.setTimeout(tick, 0);
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [fetchStats, paused]);

  const rootDisk = stats?.disks.find((d) => d.mountpoint === '/') ?? stats?.disks[0];
  const live = !paused && !error;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-foreground-subtle">Admin</p>
          <div className="mt-0.5 flex flex-wrap items-center gap-2">
            <AdminMenuIcon name="server" className="h-4 w-4 text-brand-600" />
            <h2 className="text-lg font-semibold text-foreground">Monitoring Server</h2>
            {stats && (
              <span className="rounded-lg bg-surface-sunken px-2 py-0.5 font-mono text-xs text-foreground-muted">
                {stats.system.hostname}
              </span>
            )}
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <span className="inline-flex items-center gap-1.5 text-xs text-foreground-muted">
            <span className="relative flex h-2 w-2">
              {live && <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-75" />}
              <span className={`relative inline-flex h-2 w-2 rounded-full ${live ? 'bg-emerald-500' : 'bg-gray-400'}`} />
            </span>
            {paused ? 'Dijeda' : error ? 'Terputus' : `Live · tiap ${POLL_MS / 1000} dtk`}
            {stats && <span className="text-foreground-subtle">· {fmtTime(Date.parse(stats.collected_at))}</span>}
          </span>
          <button
            type="button"
            onClick={() => setPaused((p) => !p)}
            className="inline-flex items-center gap-1.5 rounded-xl border border-black/10 px-3 py-2 text-xs font-medium text-foreground-muted transition hover:border-brand-200 hover:text-foreground"
          >
            {paused ? (
              <svg viewBox="0 0 24 24" fill="currentColor" className="h-3.5 w-3.5"><path d="M8 5v14l11-7z" /></svg>
            ) : (
              <svg viewBox="0 0 24 24" fill="currentColor" className="h-3.5 w-3.5"><rect x="6" y="5" width="4" height="14" rx="1" /><rect x="14" y="5" width="4" height="14" rx="1" /></svg>
            )}
            {paused ? 'Lanjutkan' : 'Jeda'}
          </button>
          <button
            type="button"
            onClick={() => void fetchStats()}
            disabled={loading}
            className="inline-flex items-center gap-1.5 rounded-xl border border-black/10 px-3 py-2 text-xs font-medium text-foreground-muted transition hover:border-brand-200 hover:text-foreground disabled:opacity-50"
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" className={`h-3.5 w-3.5 ${loading ? 'animate-spin' : ''}`}>
              <polyline points="1 4 1 10 7 10" />
              <path d="M3.51 15a9 9 0 1 0 .49-3.51" />
            </svg>
            Refresh
          </button>
        </div>
      </div>

      {error && (
        <div className="rounded-2xl border border-red-200 bg-red-50/80 p-3.5 text-sm font-medium text-red-700">
          {error}
        </div>
      )}

      {!stats ? (
        !error && (
          <div className="flex items-center justify-center py-20">
            <svg className="h-6 w-6 animate-spin text-brand-500" viewBox="0 0 24 24" fill="none">
              <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" opacity="0.25" />
              <path d="M12 2a10 10 0 0 1 10 10" stroke="currentColor" strokeWidth="3" strokeLinecap="round" />
            </svg>
          </div>
        )
      ) : (
        <>
          {/* ── KPI tiles ── */}
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <MetricTile
              label="CPU"
              value={`${fmtNum(stats.cpu.percent)}%`}
              sub={`${stats.system.cpu_cores_logical} core · load ${fmtNum(stats.cpu.load_avg[0], 2)}`}
              badgePercent={stats.cpu.percent}
            >
              <Sparkline samples={history} pick={(s) => s.cpu} format={(v) => `${fmtNum(v)}%`} fixedMax={100} />
            </MetricTile>
            <MetricTile
              label="Memori (RAM)"
              value={`${fmtNum(stats.memory.percent)}%`}
              sub={`${fmtBytes(stats.memory.used)} / ${fmtBytes(stats.memory.total)}`}
              badgePercent={stats.memory.percent}
            >
              <Sparkline samples={history} pick={(s) => s.mem} format={(v) => `${fmtNum(v)}%`} fixedMax={100} />
            </MetricTile>
            {rootDisk && (
              <MetricTile
                label={`Disk (${rootDisk.mountpoint})`}
                value={`${fmtNum(rootDisk.percent)}%`}
                sub={`${fmtBytes(rootDisk.used)} / ${fmtBytes(rootDisk.total)} · sisa ${fmtBytes(rootDisk.free)}`}
                badgePercent={rootDisk.percent}
              >
                <div className="space-y-2">
                  <Meter percent={rootDisk.percent} />
                  <p className="text-xs text-foreground-muted">
                    I/O baca <span className="font-medium text-foreground tabular-nums">{fmtRate(stats.disk_io.read_per_sec)}</span>
                    {' · '}tulis <span className="font-medium text-foreground tabular-nums">{fmtRate(stats.disk_io.write_per_sec)}</span>
                  </p>
                </div>
              </MetricTile>
            )}
            <MetricTile
              label="Jaringan"
              value={`↓ ${fmtRate(stats.network.recv_per_sec)}`}
              sub={`↑ ${fmtRate(stats.network.sent_per_sec)} · total ↓ ${fmtBytes(stats.network.recv_total)} ↑ ${fmtBytes(stats.network.sent_total)}`}
            >
              <Sparkline samples={history} pick={(s) => s.net} format={(v) => `${fmtRate(v)} (↓+↑)`} />
            </MetricTile>
          </div>

          <div className="grid gap-3 lg:grid-cols-2">
            {/* ── Per core ── */}
            <SectionCard
              title="Pemakaian per Core"
              right={
                <span className="text-xs text-foreground-muted">
                  Load avg <span className="font-medium text-foreground tabular-nums">
                    {stats.cpu.load_avg.map((v) => fmtNum(v, 2)).join(' · ')}
                  </span>
                </span>
              }
            >
              <div className="space-y-2.5">
                {stats.cpu.per_core.map((v, i) => (
                  <div key={i} className="flex items-center gap-3">
                    <span className="w-14 shrink-0 font-mono text-xs text-foreground-muted">Core {i + 1}</span>
                    <Meter percent={v} className="h-2 flex-1" />
                    <span className="w-12 shrink-0 text-right font-mono text-xs text-foreground tabular-nums">{fmtNum(v)}%</span>
                  </div>
                ))}
                <p className="pt-1 text-[11px] text-foreground-subtle">
                  Load average 1/5/15 menit. Di atas {stats.system.cpu_cores_logical} (jumlah core) berarti antrean proses mulai menumpuk.
                </p>
              </div>
            </SectionCard>

            {/* ── Disks ── */}
            <SectionCard title="Partisi Disk">
              <div className="space-y-4">
                {stats.disks.map((d) => (
                  <div key={d.device}>
                    <div className="mb-1.5 flex items-baseline justify-between gap-2">
                      <p className="min-w-0 truncate text-sm font-semibold text-foreground">
                        {d.mountpoint}
                        <span className="ml-2 font-mono text-[11px] font-normal text-foreground-subtle">{d.device} · {d.fstype}</span>
                      </p>
                      <span className="shrink-0 font-mono text-xs text-foreground tabular-nums">{fmtNum(d.percent)}%</span>
                    </div>
                    <Meter percent={d.percent} />
                    <p className="mt-1 text-xs text-foreground-muted">
                      {fmtBytes(d.used)} terpakai dari {fmtBytes(d.total)} · sisa {fmtBytes(d.free)}
                    </p>
                  </div>
                ))}
              </div>
            </SectionCard>
          </div>

          {/* ── Services ── */}
          <SectionCard title="Status Service">
            <div className="grid gap-3 md:grid-cols-3">
              {stats.services.map((svc) => {
                const st = SERVICE_STATES[svc.active_state] ?? { label: svc.active_state, dot: 'bg-gray-400', text: 'text-foreground-muted' };
                return (
                  <div key={svc.name} className="rounded-xl border border-border bg-surface p-4">
                    <div className="flex items-center justify-between gap-2">
                      <p className="text-sm font-semibold text-foreground">{svc.label}</p>
                      <span className={`inline-flex items-center gap-1.5 text-xs font-semibold ${st.text}`}>
                        <span className={`h-2 w-2 rounded-full ${st.dot}`} />
                        {st.label}
                      </span>
                    </div>
                    <p className="mt-0.5 font-mono text-[11px] text-foreground-subtle">{svc.name}.service</p>
                    <div className="mt-3 grid grid-cols-3 gap-2 text-xs">
                      <div>
                        <p className="text-foreground-subtle">Uptime</p>
                        <p className="font-medium text-foreground">{fmtUptime(svc.uptime_seconds)}</p>
                      </div>
                      <div>
                        <p className="text-foreground-subtle">RAM</p>
                        <p className="font-medium text-foreground tabular-nums">{fmtBytes(svc.memory_bytes)}</p>
                      </div>
                      <div>
                        <p className="text-foreground-subtle">PID</p>
                        <p className="font-medium text-foreground tabular-nums">{svc.main_pid ?? '—'}</p>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </SectionCard>
        </>
      )}
    </div>
  );
}
