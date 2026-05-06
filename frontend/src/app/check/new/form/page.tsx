'use client';

import { FormEvent, useMemo, useState } from 'react';
import Link from 'next/link';

type Lomba = 'PKM' | 'Lainnya';
type Laporan = 'Proposal' | 'Laporan Kemajuan' | 'Laporan Akhir' | 'Artikel Ilmiah';

const skemaPkm = ['PKM-KC', 'PKM-K', 'PKM-KI', 'PKM-PI', 'PKM-RE'];
const API_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';

const LAPORAN_TO_CODE: Record<Laporan, string> = {
  'Proposal': 'PROPOSAL',
  'Laporan Kemajuan': 'PROGRESS_REPORT',
  'Laporan Akhir': 'FINAL_REPORT',
  'Artikel Ilmiah': 'SCIENTIFIC_ARTICLE',
};

type ModuleResult = {
  status?: string;
  [key: string]: unknown;
};

type CheckResults = {
  submission_id: string;
  status: string;
  overall_status: string;
  results: {
    structure: ModuleResult;
    physical_sheet: ModuleResult;
    format: ModuleResult;
    page_numbering: ModuleResult;
    budget: ModuleResult;
    reference: ModuleResult;
  };
};

export default function NewCheckFormPage() {
  const [lomba, setLomba] = useState<Lomba>('PKM');
  const [laporan, setLaporan] = useState<Laporan>('Proposal');
  const [skema, setSkema] = useState('PKM-KC');
  const [token, setToken] = useState('');
  const [danaBelmawa, setDanaBelmawa] = useState('');
  const [danaPt, setDanaPt] = useState('');
  const [file, setFile] = useState<File | null>(null);
  const [logs, setLogs] = useState<string[]>([
    'Sistem siap. Silakan isi alur dari atas ke bawah.',
  ]);
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState<CheckResults | null>(null);
  const [errorMsg, setErrorMsg] = useState<string>('');

  const totalDana = useMemo(() => {
    const belmawa = Number(danaBelmawa || 0);
    const pt = Number(danaPt || 0);
    return belmawa + pt;
  }, [danaBelmawa, danaPt]);

  function addLog(message: string) {
    setLogs((prev) => [
      `${new Date().toLocaleTimeString('id-ID', {
        hour: '2-digit',
        minute: '2-digit',
      })} · ${message}`,
      ...prev,
    ]);
  }

  function onLombaChange(nextValue: Lomba) {
    if (nextValue === 'Lainnya') {
      addLog('Jenis lomba selain PKM masih coming soon.');
      return;
    }
    setLomba(nextValue);
  }

  function onLaporanChange(nextValue: Laporan) {
    if (nextValue !== 'Proposal') {
      addLog(`${nextValue} masih coming soon. Saat ini hanya Proposal yang aktif.`);
      return;
    }
    setLaporan(nextValue);
  }

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setErrorMsg('');
    setResult(null);

    if (!token.trim()) {
      addLog('Token wajib diisi sebelum submit.');
      return;
    }
    if (!file) {
      addLog('File laporan belum diunggah.');
      return;
    }
    if (!file.name.toLowerCase().endsWith('.docx')) {
      addLog('File harus berformat .docx');
      setErrorMsg('File harus berformat .docx');
      return;
    }

    setSubmitting(true);
    addLog(`Mengirim ${laporan} - ${skema} ke server...`);

    const fd = new FormData();
    fd.append('token', token.trim());
    fd.append('competition', 'PKM');
    fd.append('report_type', LAPORAN_TO_CODE[laporan]);
    fd.append('schema_code', skema);
    fd.append('funding_belmawa', String(Number(danaBelmawa || 0)));
    fd.append('funding_pt', String(Number(danaPt || 0)));
    fd.append('funding_external', '0');
    fd.append('file', file);

    try {
      const res = await fetch(`${API_URL}/api/check`, {
        method: 'POST',
        body: fd,
      });
      const data = await res.json();

      if (!res.ok) {
        const msg = data?.detail ?? `Error ${res.status}`;
        addLog(`Gagal: ${msg}`);
        setErrorMsg(typeof msg === 'string' ? msg : JSON.stringify(msg));
        return;
      }

      addLog(`Selesai. Status: ${data.overall_status}`);
      setResult(data as CheckResults);
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      addLog(`Network error: ${msg}`);
      setErrorMsg(`Tidak bisa terhubung ke server: ${msg}`);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="relative mx-auto max-w-6xl px-4 pb-20 pt-10 sm:px-6">
      <section className="glass-surface-elevated relative overflow-hidden rounded-[2rem] p-6 sm:p-10">
        <div aria-hidden className="orb orb-brand absolute -right-10 -top-12 h-52 w-52 opacity-60" />
        <p className="font-mono text-xs uppercase tracking-[0.2em] text-foreground-subtle">
          Form Input
        </p>
        <h1 className="mt-3 max-w-4xl text-3xl font-light tracking-tight text-foreground sm:text-5xl">
          Form proses <span className="font-display italic text-gradient-brand">laporan PKM</span>
        </h1>
      </section>

      <section className="mt-6 grid gap-6 lg:grid-cols-[1fr_380px]">
        <form onSubmit={onSubmit} className="glass-surface rounded-[1.75rem] p-6 sm:p-8">
          <div className="space-y-5">
            <FieldLabel index="01" title="Pilih jenis lomba" />
            <div className="grid grid-cols-2 gap-3">
              <button
                type="button"
                onClick={() => onLombaChange('PKM')}
                className={`rounded-2xl border px-4 py-3 text-sm ${
                  lomba === 'PKM'
                    ? 'border-brand-400 bg-brand-100/70 text-brand-700'
                    : 'glass-surface-subtle border-white/50'
                }`}
              >
                PKM (aktif)
              </button>
              <button
                type="button"
                onClick={() => onLombaChange('Lainnya')}
                className="glass-surface-subtle rounded-2xl border border-white/50 px-4 py-3 text-sm text-foreground-muted"
              >
                Lomba lain (coming soon)
              </button>
            </div>

            <FieldLabel index="02" title="Pilih jenis laporan" />
            <div className="grid gap-3 sm:grid-cols-2">
              {(['Proposal', 'Laporan Kemajuan', 'Laporan Akhir', 'Artikel Ilmiah'] as Laporan[]).map(
                (item) => (
                  <button
                    key={item}
                    type="button"
                    onClick={() => onLaporanChange(item)}
                    className={`rounded-2xl border px-4 py-3 text-left text-sm ${
                      laporan === item
                        ? 'border-brand-400 bg-brand-100/70 text-brand-700'
                        : 'glass-surface-subtle border-white/50 text-foreground-muted'
                    }`}
                  >
                    {item}
                    {item !== 'Proposal' ? ' · coming soon' : ' · aktif'}
                  </button>
                ),
              )}
            </div>

            <FieldLabel index="03" title="Pilih skema PKM" />
            <select
              value={skema}
              onChange={(event) => setSkema(event.target.value)}
              className="glass-input w-full rounded-2xl px-4 py-3 text-sm"
            >
              {skemaPkm.map((item) => (
                <option key={item} value={item}>
                  {item}
                </option>
              ))}
            </select>

            <FieldLabel index="04" title="Input token" />
            <input
              value={token}
              onChange={(event) => setToken(event.target.value)}
              placeholder="Contoh: PKM-2026-ABCD12"
              className="glass-input w-full rounded-2xl px-4 py-3 text-sm"
            />

            <FieldLabel index="05" title="Input dana" />
            <div className="grid gap-3 sm:grid-cols-2">
              <input
                type="number"
                min={0}
                value={danaBelmawa}
                onChange={(event) => setDanaBelmawa(event.target.value)}
                placeholder="Dana Belmawa"
                className="glass-input w-full rounded-2xl px-4 py-3 text-sm"
              />
              <input
                type="number"
                min={0}
                value={danaPt}
                onChange={(event) => setDanaPt(event.target.value)}
                placeholder="Dana Perguruan Tinggi"
                className="glass-input w-full rounded-2xl px-4 py-3 text-sm"
              />
            </div>
            <p className="text-xs text-foreground-subtle">
              Total dana: Rp{totalDana.toLocaleString('id-ID')}
            </p>

            <FieldLabel index="06" title="Upload laporan (.docx)" />
            <input
              type="file"
              accept=".docx"
              onChange={(event) => {
                const f = event.target.files?.[0] ?? null;
                setFile(f);
                if (f) addLog(`File dipilih: ${f.name}`);
              }}
              className="glass-input w-full rounded-2xl px-4 py-3 text-sm file:mr-3 file:rounded-xl file:border-0 file:bg-brand-500 file:px-3 file:py-1.5 file:text-xs file:font-medium file:text-white"
            />

            <button
              type="submit"
              disabled={submitting}
              className="btn-liquid btn-liquid-primary w-full px-5 py-3 text-sm disabled:opacity-50"
            >
              {submitting ? 'Memproses... (1-2 menit)' : 'Submit / Proses'}
            </button>

            {errorMsg && (
              <div className="rounded-2xl border border-red-300 bg-red-50/70 p-4 text-sm text-red-700">
                {errorMsg}
              </div>
            )}
          </div>
        </form>

        <aside className="space-y-4 lg:sticky lg:top-6 lg:h-fit">
          <div className="glass-surface rounded-[1.5rem] p-6">
            <h2 className="text-lg font-semibold text-foreground">Ringkasan Input</h2>
            <div className="mt-4 space-y-2 text-sm text-foreground-muted">
              <p>Lomba: {lomba}</p>
              <p>Laporan: {laporan}</p>
              <p>Skema: {skema}</p>
              <p>Token: {token ? 'Terisi' : 'Belum diisi'}</p>
              <p>File: {file?.name || 'Belum dipilih'}</p>
            </div>
          </div>

          <div className="glass-surface rounded-[1.5rem] p-6">
            <h2 className="text-lg font-semibold text-foreground">Log Aktivitas</h2>
            <ul className="mt-3 space-y-1 text-xs text-foreground-muted">
              {logs.map((log, i) => (
                <li key={i}>{log}</li>
              ))}
            </ul>
          </div>

          <Link href="/check/new" className="btn-liquid btn-liquid-ghost inline-flex px-4 py-2 text-sm">
            Kembali ke Beranda Input
          </Link>
        </aside>
      </section>

      {result && <ResultsSection result={result} />}
    </main>
  );
}

function FieldLabel({ index, title }: { index: string; title: string }) {
  return (
    <div>
      <p className="font-mono text-[11px] uppercase tracking-[0.2em] text-foreground-subtle">
        Step {index}
      </p>
      <p className="mt-1 text-sm font-medium text-foreground">{title}</p>
    </div>
  );
}
type Message = { level: string; text: string };

function ResultsSection({ result }: { result: CheckResults }) {
  const overallColor =
    result.overall_status === 'pass'
      ? 'text-emerald-700'
      : result.overall_status === 'warning'
      ? 'text-amber-700'
      : 'text-red-700';

  const modules = [
    { key: 'structure', label: 'Struktur Dokumen' },
    { key: 'physical_sheet', label: 'Jumlah Lembar Fisik' },
    { key: 'format', label: 'Format Penulisan' },
    { key: 'page_numbering', label: 'Penomoran Halaman' },
    { key: 'budget', label: 'Audit Anggaran' },
    { key: 'reference', label: 'Daftar Pustaka' },
  ] as const;

  return (
    <section className="mt-8 glass-surface rounded-[1.75rem] p-6 sm:p-8">
      <p className="font-mono text-xs uppercase tracking-[0.2em] text-foreground-subtle">
        Hasil Pengecekan
      </p>
      <div className="mt-2 flex items-baseline gap-3">
        <h2 className="text-2xl font-light tracking-tight text-foreground">
          Status keseluruhan:
        </h2>
        <span className={`text-2xl font-semibold uppercase ${overallColor}`}>
          {result.overall_status === 'pass'
            ? 'Lulus'
            : result.overall_status === 'warning'
            ? 'Perlu Diperhatikan'
            : 'Belum Lulus'}
        </span>
      </div>
      <p className="mt-1 text-xs text-foreground-subtle">
        Submission ID: <code>{result.submission_id}</code>
      </p>

      <div className="mt-6 grid gap-3">
        {modules.map(({ key, label }) => {
          const mod = result.results[key] as { status?: string; messages?: Message[] };
          const status = mod?.status ?? 'unknown';
          const messages = Array.isArray(mod?.messages) ? mod.messages : [];
          return (
            <ModuleCard key={key} label={label} status={status} messages={messages} />
          );
        })}
      </div>
    </section>
  );
}

function ModuleCard({
  label,
  status,
  messages,
}: {
  label: string;
  status: string;
  messages: Message[];
}) {
  const statusBadge =
    status === 'pass'
      ? { text: 'Lulus', cls: 'text-emerald-700 bg-emerald-50/70 border-emerald-200' }
      : status === 'warning'
      ? { text: 'Perhatian', cls: 'text-amber-700 bg-amber-50/70 border-amber-200' }
      : status === 'fail'
      ? { text: 'Belum Lulus', cls: 'text-red-700 bg-red-50/70 border-red-200' }
      : status === 'error'
      ? { text: 'Error', cls: 'text-red-700 bg-red-50/70 border-red-200' }
      : { text: status, cls: 'text-gray-700 bg-gray-50/70 border-gray-200' };

  // Group messages by level
  const fails = messages.filter((m) => m.level === 'fail' || m.level === 'error');
  const warnings = messages.filter((m) => m.level === 'warning');
  const passes = messages.filter((m) => m.level === 'pass' || m.level === 'info');

  // Default: open if not pass
  const defaultOpen = status !== 'pass';

  return (
    <details
      open={defaultOpen}
      className="glass-surface-subtle rounded-2xl border border-white/50"
    >
      <summary className="flex cursor-pointer items-center justify-between p-4 text-sm">
        <div className="flex items-center gap-3">
          <span className="font-medium text-foreground">{label}</span>
          {messages.length > 0 && (
            <span className="text-xs text-foreground-subtle">
              ({messages.length} catatan)
            </span>
          )}
        </div>
        <span
          className={`rounded-full border px-3 py-1 text-xs font-semibold ${statusBadge.cls}`}
        >
          {statusBadge.text}
        </span>
      </summary>

      <div className="border-t border-white/40 px-4 py-4">
        {messages.length === 0 ? (
          <p className="text-sm text-foreground-muted">Tidak ada catatan.</p>
        ) : (
          <div className="space-y-4">
            {fails.length > 0 && (
              <MessageTable
                title="Harus Diperbaiki"
                items={fails}
                rowCls="text-red-800"
                titleCls="text-red-700"
              />
            )}
            {warnings.length > 0 && (
              <MessageTable
                title="Perlu Diperhatikan"
                items={warnings}
                rowCls="text-amber-800"
                titleCls="text-amber-700"
              />
            )}
            {passes.length > 0 && (
              <MessageTable
                title="Sudah Sesuai"
                items={passes}
                rowCls="text-emerald-800"
                titleCls="text-emerald-700"
              />
            )}
          </div>
        )}
      </div>
    </details>
  );
}

function MessageTable({
  title,
  items,
  rowCls,
  titleCls,
}: {
  title: string;
  items: Message[];
  rowCls: string;
  titleCls: string;
}) {
  return (
    <div>
      <p className={`mb-2 text-xs font-semibold uppercase tracking-wider ${titleCls}`}>
        {title} ({items.length})
      </p>
      <div className="overflow-hidden rounded-xl border border-white/40 bg-white/30">
        <table className="w-full text-sm">
          <thead className="bg-white/40 text-xs uppercase tracking-wider text-foreground-subtle">
            <tr>
              <th className="w-12 px-3 py-2 text-left">#</th>
              <th className="px-3 py-2 text-left">Catatan</th>
            </tr>
          </thead>
          <tbody>
            {items.map((m, i) => {
              const { lokasi, masalah } = parseMessage(m.text);
              return (
                <tr key={i} className="border-t border-white/30 align-top">
                  <td className={`px-3 py-2 text-xs ${rowCls}`}>{i + 1}</td>
                  <td className={`px-3 py-2 leading-relaxed ${rowCls}`}>
                    {lokasi && (
                      <span className="mr-2 inline-block rounded bg-white/50 px-2 py-0.5 text-[11px] font-medium">
                        {lokasi}
                      </span>
                    )}
                    {masalah}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

/**
 * Parse message text dari engine. Engine kadang format:
 *   "[Section #2] Margin left tidak sesuai..."
 *   "[Entry #5] Mengandung 'et al.'..."
 *   "  • [Section #0] Ukuran kertas..."
 * Kita ekstrak prefix [..] sebagai lokasi.
 */
function parseMessage(text: string): { lokasi: string; masalah: string } {
  const cleaned = text.replace(/^\s*•\s*/, '').trim();
  const m = cleaned.match(/^\[([^\]]+)\]\s*(.+)$/);
  if (m) {
    return { lokasi: m[1], masalah: m[2] };
  }
  return { lokasi: '', masalah: cleaned };
}
