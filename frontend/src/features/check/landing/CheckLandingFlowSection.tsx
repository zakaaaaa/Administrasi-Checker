const FLOW_STEPS = [
  {
    title: 'Akses',
    body: 'Masukkan token dari admin, lalu pilih jenis laporan dan skema PKM yang sesuai.',
    accent: 'Token aktif',
  },
  {
    title: 'Dokumen',
    body: 'Unggah file laporan agar sistem membaca format, struktur, dan lampiran.',
    accent: 'Upload file',
  },
  {
    title: 'Hasil',
    body: 'Lihat temuan, rapikan dokumen, lalu unduh ringkasan hasil pengecekan.',
    accent: 'Review temuan',
  },
];

export function CheckLandingFlowSection() {
  return (
    <section id="flow-section" className="relative px-4 py-16 sm:px-6 sm:py-20">
      <div className="mx-auto max-w-5xl">
        <div className="mx-auto max-w-2xl text-center">
          <h2
            data-reveal
            data-reveal-delay="1"
            className="mt-3 font-display text-2xl font-bold leading-tight text-foreground sm:text-3xl"
          >
            Tiga langkah sampai hasil cek siap dibaca.
          </h2>
        </div>

        <div className="mt-10 grid gap-4 lg:grid-cols-3">
          {FLOW_STEPS.map((item, idx) => (
            <div
              key={item.title}
              data-reveal
              data-reveal-delay={`${idx + 1}` as '1' | '2' | '3'}
              className="group relative min-h-[180px] overflow-hidden rounded-2xl border border-border bg-surface-elevated p-5 transition hover:-translate-y-0.5 hover:border-brand-300"
            >
              <div
                aria-hidden
                className="absolute right-4 top-3 text-5xl font-bold leading-none text-brand-100 transition group-hover:text-brand-200"
              >
                0{idx + 1}
              </div>
              <div className="relative z-10">
                <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-brand-100 text-sm font-bold text-brand-700 transition group-hover:bg-brand-500 group-hover:text-white">
                  0{idx + 1}
                </div>
                <p className="mt-5 text-xs font-semibold uppercase tracking-[0.16em] text-brand-700">
                  {item.accent}
                </p>
                <h3 className="mt-2 text-lg font-semibold text-foreground">{item.title}</h3>
                <p className="mt-2 text-sm leading-relaxed text-foreground-muted">{item.body}</p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
