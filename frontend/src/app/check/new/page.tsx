 'use client';

import { FormEvent, useState } from 'react';
import { useRouter } from 'next/navigation';

export default function NewCheckPage() {
  const [token, setToken] = useState('');
  const router = useRouter();

  function handleContinue(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!token.trim()) return;
    router.push(`/check/new/form?token=${encodeURIComponent(token.trim())}`);
  }

  return (
    <main className="relative mx-auto max-w-6xl px-4 pb-20 pt-10 sm:px-6">
      <section className="glass-surface-elevated relative overflow-hidden rounded-[2rem] p-6 sm:p-10">
        <div
          aria-hidden
          className="orb orb-brand absolute -right-12 -top-16 h-56 w-56 opacity-70"
        />
        <p className="font-mono text-sm uppercase tracking-[0.2em] text-foreground-subtle">
         Beranda Input
        </p>
        <h1 className="mt-3 max-w-4xl text-4xl font-semibold tracking-tight text-foreground sm:text-6xl">
          Siapkan data dulu, lalu masuk ke{' '}
          <span className="font-display text-gradient-brand">form input PKM</span>.
        </h1>
        <p className="mt-4 max-w-3xl text-base leading-relaxed text-foreground-muted">
          Halaman ini menjadi briefing singkat sebelum pengisian. Tujuannya agar user paham
          alur, syarat, dan dokumen yang dibutuhkan sehingga proses lebih cepat.
        </p>
      
      </section>

      <section className="mt-6 grid gap-6 lg:grid-cols-[1fr_360px]">
        <div className="glass-surface rounded-[1.75rem] p-6 sm:p-8">
          <p className="font-mono text-sm uppercase tracking-[0.2em] text-foreground-subtle">
            Alur Pengisian
          </p>
          <div className="mt-4 grid gap-3 sm:grid-cols-2">
            {[
              'Input token',
              'Pilih jenis laporan (Proposal aktif)',
              'Pilih skema PKM',
              'Pilih lomba (PKM aktif)',
              'Input dana (Belmawa + PT)',
              'Upload laporan',
              'Submit / Proses',
            ].map((item) => (
              <div key={item} className="glass-surface-subtle rounded-2xl p-4">
                <p className="text-base font-semibold text-foreground">{item}</p>
              </div>
            ))}
          </div>
        </div>

        <aside className="space-y-4">
          <form onSubmit={handleContinue} className="glass-surface rounded-[1.5rem] p-6">
            <h2 className="text-xl font-semibold text-foreground">Masukkan token dulu</h2>
            <p className="mt-2 text-base text-foreground-muted">
              Token wajib diisi sebelum masuk ke halaman pengecekan.
            </p>
            <input
              value={token}
              onChange={(event) => setToken(event.target.value)}
              placeholder="Contoh: PKM-2026-ABCD12"
              className="glass-input mt-4 w-full rounded-2xl px-4 py-3 text-base font-medium"
            />
            <button
              type="submit"
              disabled={!token.trim()}
              className="btn-liquid btn-liquid-primary mt-4 inline-flex w-full px-4 py-3 text-base font-semibold disabled:opacity-50"
            >
              Lanjut ke Form Pengecekan
            </button>
          </form>

          <div className="glass-surface-subtle rounded-[1.5rem] p-6">
            <h2 className="text-xl font-semibold text-foreground">Syarat Minimum</h2>
            <ul className="mt-3 space-y-2 text-base text-foreground-muted">
              <li>Token aktif dari admin.</li>
              <li>Data dana Belmawa dan Perguruan Tinggi.</li>
              <li>File laporan format `.doc`, `.docx`, atau `.pdf`.</li>
            </ul>
          </div>
        </aside>
      </section>
    </main>
  );
}
