import Link from 'next/link';

export default function NewCheckPage() {
  return (
    <main className="relative mx-auto max-w-6xl px-4 pb-20 pt-10 sm:px-6">
      <section className="glass-surface-elevated relative overflow-hidden rounded-[2rem] p-6 sm:p-10">
        <div
          aria-hidden
          className="orb orb-brand absolute -right-12 -top-16 h-56 w-56 opacity-70"
        />
        <p className="font-mono text-xs uppercase tracking-[0.2em] text-foreground-subtle">
         Beranda Input
        </p>
        <h1 className="mt-3 max-w-4xl text-3xl font-light tracking-tight text-foreground sm:text-5xl">
          Siapkan data dulu, lalu masuk ke{' '}
          <span className="font-display italic text-gradient-brand">form input PKM</span>.
        </h1>
        <p className="mt-4 max-w-3xl text-sm leading-relaxed text-foreground-muted">
          Halaman ini menjadi briefing singkat sebelum pengisian. Tujuannya agar user paham
          alur, syarat, dan dokumen yang dibutuhkan sehingga proses lebih cepat.
        </p>
      
      </section>

      <section className="mt-6 grid gap-6 lg:grid-cols-[1fr_360px]">
        <div className="glass-surface rounded-[1.75rem] p-6 sm:p-8">
          <p className="font-mono text-xs uppercase tracking-[0.2em] text-foreground-subtle">
            Alur Pengisian
          </p>
          <div className="mt-4 grid gap-3 sm:grid-cols-2">
            {[
              'Pilih lomba (PKM aktif)',
              'Pilih jenis laporan (Proposal aktif)',
              'Pilih skema PKM',
              'Input token',
              'Input dana (Belmawa + PT)',
              'Upload laporan',
              'Submit / Proses',
            ].map((item, index) => (
              <div key={item} className="glass-surface-subtle rounded-2xl p-4">
                <p className="font-mono text-[11px] uppercase tracking-[0.2em] text-foreground-subtle">
                  Step {(index + 1).toString().padStart(2, '0')}
                </p>
                <p className="mt-1 text-sm text-foreground">{item}</p>
              </div>
            ))}
          </div>
        </div>

        <aside className="space-y-4">
          <div className="glass-surface-subtle rounded-[1.5rem] p-6">
            <h2 className="text-lg font-semibold text-foreground">Syarat Minimum</h2>
            <ul className="mt-3 space-y-2 text-sm text-foreground-muted">
              <li>Token aktif dari admin.</li>
              <li>Data dana Belmawa dan Perguruan Tinggi.</li>
              <li>File laporan format `.doc`, `.docx`, atau `.pdf`.</li>
            </ul>
          </div>
       
          <Link
            href="/check/new/form"
            className="btn-liquid btn-liquid-primary inline-flex w-full px-4 py-2.5 text-sm"
          >
            Mulai Input Sekarang
          </Link>
        </aside>
      </section>
    </main>
  );
}
