'use client';

import { FormEvent, useMemo, useState } from 'react';
import Link from 'next/link';
import { useSearchParams } from 'next/navigation';

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
  const searchParams = useSearchParams();
  const token = searchParams.get('token')?.trim() ?? '';
  const [lomba, setLomba] = useState<Lomba>('PKM');
  const [laporan, setLaporan] = useState<Laporan>('Proposal');
  const [skema, setSkema] = useState('PKM-KC');
  const [danaBelmawa, setDanaBelmawa] = useState('');
  const [danaPt, setDanaPt] = useState('');
  const [file, setFile] = useState<File | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState<CheckResults | null>(null);
  const [errorMsg, setErrorMsg] = useState<string>('');

  const totalDana = useMemo(() => {
    const belmawa = Number(danaBelmawa || 0);
    const pt = Number(danaPt || 0);
    return belmawa + pt;
  }, [danaBelmawa, danaPt]);

  function onLombaChange(nextValue: Lomba) {
    if (nextValue === 'Lainnya') {
      setErrorMsg('Jenis lomba selain PKM masih coming soon.');
      return;
    }
    setErrorMsg('');
    setLomba(nextValue);
  }

  function onLaporanChange(nextValue: Laporan) {
    setErrorMsg('');
    setLaporan(nextValue);
  }

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setErrorMsg('');
    setResult(null);

    if (!token) {
      setErrorMsg('Token wajib diisi dari halaman awal.');
      return;
    }
    if (!file) {
      setErrorMsg('File laporan belum diunggah.');
      return;
    }
    if (!file.name.toLowerCase().endsWith('.docx')) {
      setErrorMsg('File harus berformat .docx');
      return;
    }

    setSubmitting(true);

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
        setErrorMsg(typeof msg === 'string' ? msg : JSON.stringify(msg));
        return;
      }

      setResult(data as CheckResults);
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      setErrorMsg(`Tidak bisa terhubung ke server: ${msg}`);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="relative mx-auto max-w-6xl px-4 pb-20 pt-10 sm:px-6">
      {!token && (
        <section className="mb-6 rounded-2xl border border-amber-300 bg-amber-50 p-4 text-base font-semibold text-amber-800">
          Token belum tersedia. Silakan kembali ke halaman awal untuk mengisi token dulu.
        </section>
      )}
      <section className="glass-surface-elevated relative overflow-hidden rounded-[2rem] p-6 sm:p-10">
        <div aria-hidden className="orb orb-brand absolute -right-10 -top-12 h-52 w-52 opacity-60" />
        
        <h1 className="mt-3 max-w-4xl text-4xl font-semibold tracking-tight text-foreground sm:text-6xl">
          Form proses <span className="font-display text-gradient-brand">laporan PKM</span>
        </h1>
      </section>

      <section className="mt-6 grid gap-6 lg:grid-cols-[1fr_380px]">
        <form onSubmit={onSubmit} className="glass-surface rounded-[1.75rem] p-6 sm:p-8">
          <div className="space-y-5">
            <FieldLabel title="Pilih jenis lomba" />
            <div className="grid grid-cols-2 gap-3">
              <button
                type="button"
                onClick={() => onLombaChange('PKM')}
                className={`rounded-2xl border px-4 py-3 text-base font-semibold ${
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
                className="glass-surface-subtle rounded-2xl border border-white/50 px-4 py-3 text-base font-semibold text-foreground-muted"
              >
                Lomba lain (coming soon)
              </button>
            </div>

            <FieldLabel title="Pilih jenis laporan" />
            <select
              value={laporan}
              onChange={(event) => onLaporanChange(event.target.value as Laporan)}
              className="glass-input w-full rounded-2xl px-4 py-3 text-base font-medium"
            >
              {(['Proposal', 'Laporan Kemajuan', 'Laporan Akhir', 'Artikel Ilmiah'] as Laporan[]).map(
                (item) => (
                  <option key={item} value={item}>
                    {item}
                  </option>
                ),
              )}
            </select>

            <FieldLabel title="Pilih skema PKM" />
            <select
              value={skema}
              onChange={(event) => setSkema(event.target.value)}
              className="glass-input w-full rounded-2xl px-4 py-3 text-base font-medium"
            >
              {skemaPkm.map((item) => (
                <option key={item} value={item}>
                  {item}
                </option>
              ))}
            </select>

            <FieldLabel title="Input dana" />
            <div className="grid gap-3 sm:grid-cols-2">
              <input
                type="number"
                min={0}
                value={danaBelmawa}
                onChange={(event) => setDanaBelmawa(event.target.value)}
                placeholder="Dana Belmawa"
                className="glass-input w-full rounded-2xl px-4 py-3 text-base font-medium"
              />
              <input
                type="number"
                min={0}
                value={danaPt}
                onChange={(event) => setDanaPt(event.target.value)}
                placeholder="Dana Perguruan Tinggi"
                className="glass-input w-full rounded-2xl px-4 py-3 text-base font-medium"
              />
            </div>
            <p className="text-sm font-semibold text-foreground-subtle">
              Total dana: Rp{totalDana.toLocaleString('id-ID')}
            </p>

            <FieldLabel title="Upload laporan (.docx)" />
            <input
              type="file"
              accept=".docx"
              onChange={(event) => {
                const f = event.target.files?.[0] ?? null;
                setFile(f);
              }}
              className="glass-input w-full rounded-2xl px-4 py-3 text-base font-medium file:mr-3 file:rounded-xl file:border-0 file:bg-brand-500 file:px-3 file:py-1.5 file:text-sm file:font-semibold file:text-white"
            />

            <button
              type="submit"
              disabled={submitting || !token}
              className="btn-liquid btn-liquid-primary w-full px-5 py-3 text-base font-semibold disabled:opacity-50"
            >
              {submitting ? 'Memproses... (1-2 menit)' : 'Submit / Proses'}
            </button>

            {errorMsg && (
              <div className="rounded-2xl border border-red-300 bg-red-50/70 p-4 text-base font-semibold text-red-700">
                {errorMsg}
              </div>
            )}
          </div>
        </form>

        <aside className="space-y-4 lg:sticky lg:top-6 lg:h-fit">
          <div className="glass-surface rounded-[1.5rem] p-6">
            <h2 className="text-xl font-semibold text-foreground">Ringkasan Input</h2>
            <div className="mt-4 space-y-2 text-base text-foreground-muted">
              <p>Lomba: {lomba}</p>
              <p>Laporan: {laporan}</p>
              <p>Skema: {skema}</p>
              <p>Token: {token || 'Belum diisi dari halaman awal'}</p>
              <p>File: {file?.name || 'Belum dipilih'}</p>
            </div>
          </div>

          <Link href="/check/new" className="btn-liquid btn-liquid-ghost inline-flex px-4 py-2 text-base">
            Kembali ke Beranda Input
          </Link>
        </aside>
      </section>

      {result && <ResultsSection result={result} />}
    </main>
  );
}

function FieldLabel({ title }: { title: string }) {
  return (
    <div>
      <p className="text-base font-semibold text-foreground">{title}</p>
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
