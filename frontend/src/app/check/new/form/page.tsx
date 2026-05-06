'use client';

import { FormEvent, useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import type { CheckResults } from '@/features/check/types';

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

const LAST_RESULT_STORAGE_KEY = 'last_check_result_v1';

export default function NewCheckFormPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const token = searchParams.get('token')?.trim() ?? '';
  const [lomba, setLomba] = useState<Lomba>('PKM');
  const [laporan, setLaporan] = useState<Laporan>('Proposal');
  const [skema, setSkema] = useState('PKM-KC');
  const [danaBelmawa, setDanaBelmawa] = useState('');
  const [danaPt, setDanaPt] = useState('');
  const [file, setFile] = useState<File | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string>('');

  const totalDana = useMemo(() => {
    const belmawa = Number(danaBelmawa || 0);
    const pt = Number(danaPt || 0);
    return belmawa + pt;
  }, [danaBelmawa, danaPt]);

  useEffect(() => {
    if (!token) {
      router.replace('/check/new');
    }
  }, [token, router]);

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

      const resultData = data as CheckResults;
      sessionStorage.setItem(LAST_RESULT_STORAGE_KEY, JSON.stringify(resultData));
      router.push('/check/new/result');
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      setErrorMsg(`Tidak bisa terhubung ke server: ${msg}`);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    !token ? null : (
    <main className="relative mx-auto max-w-6xl px-4 pb-20 pt-10 sm:px-6">
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

    </main>
    )
  );
}

function FieldLabel({ title }: { title: string }) {
  return (
    <div>
      <p className="text-base font-semibold text-foreground">{title}</p>
    </div>
  );
}
