'use client';

import { FormEvent, useMemo, useState } from 'react';
import Link from 'next/link';

type Lomba = 'PKM' | 'Lainnya';
type Laporan = 'Proposal' | 'Laporan Kemajuan' | 'Laporan Akhir' | 'Artikel Ilmiah';

const skemaPkm = ['PKM-KC', 'PKM-K', 'PKM-KI', 'PKM-PI', 'PKM-RE'];

export default function NewCheckFormPage() {
  const [lomba, setLomba] = useState<Lomba>('PKM');
  const [laporan, setLaporan] = useState<Laporan>('Proposal');
  const [skema, setSkema] = useState('PKM-KC');
  const [token, setToken] = useState('');
  const [danaBelmawa, setDanaBelmawa] = useState('');
  const [danaPt, setDanaPt] = useState('');
  const [fileName, setFileName] = useState('');
  const [logs, setLogs] = useState<string[]>([
    'Sistem siap. Silakan isi alur dari atas ke bawah.',
  ]);

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

  function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!token.trim()) {
      addLog('Token wajib diisi sebelum submit.');
      return;
    }
    if (!fileName) {
      addLog('File laporan belum diunggah.');
      return;
    }
    addLog(
      `Proses dimulai: ${laporan} - ${skema}. Total dana Rp${totalDana.toLocaleString('id-ID')}.`,
    );
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

            <FieldLabel index="06" title="Upload laporan" />
            <input
              type="file"
              accept=".doc,.docx,.pdf"
              onChange={(event) => {
                const file = event.target.files?.[0];
                setFileName(file?.name ?? '');
                if (file?.name) addLog(`File dipilih: ${file.name}`);
              }}
              className="glass-input w-full rounded-2xl px-4 py-3 text-sm file:mr-3 file:rounded-xl file:border-0 file:bg-brand-500 file:px-3 file:py-1.5 file:text-xs file:font-medium file:text-white"
            />

            <button
              type="submit"
              className="btn-liquid btn-liquid-primary w-full px-5 py-3 text-sm"
            >
              Submit / Proses
            </button>
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
              <p>File: {fileName || 'Belum dipilih'}</p>
            </div>
          </div>
          
          <Link href="/check/new" className="btn-liquid btn-liquid-ghost inline-flex px-4 py-2 text-sm">
            Kembali ke Beranda Input
          </Link>
        </aside>
      </section>
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
