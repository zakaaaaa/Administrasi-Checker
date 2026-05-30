const FLOW_STEPS = [
  {
    title: 'Akses',
    body: 'Masukkan token, lalu pilih jenis laporan dan skema PKM yang sesuai.',
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
    <div data-reveal className="check-landing-glass-card rounded-[1.75rem] p-5 sm:p-8">
      <div className="mx-auto max-w-3xl text-center">
        <div className="flex items-center justify-center gap-2">
          <span className="h-1.5 w-8 rounded-full bg-brand-500" />
          <p className="font-mono text-sm uppercase tracking-[0.2em] text-foreground-subtle">
            Alur Pengisian
          </p>
          <span className="h-1.5 w-8 rounded-full bg-brand-500" />
        </div>
        <h2 className="mt-4 font-display text-2xl font-bold leading-tight text-foreground sm:text-3xl">
          Tiga langkah sampai hasil cek siap dibaca.
        </h2>
        <p className="mx-auto mt-3 max-w-2xl text-sm leading-relaxed text-foreground-muted sm:text-base">
          Mulai dari akses token, unggah dokumen, lalu baca rangkuman temuan yang perlu dirapikan.
        </p>
      </div>

      <div className="mt-8 grid gap-4 lg:grid-cols-3">
        {FLOW_STEPS.map((item, idx) => (
          <div
            key={item.title}
            className="group relative min-h-[190px] overflow-hidden rounded-2xl border border-white/60 bg-white/55 p-5 backdrop-blur-md transition hover:-translate-y-0.5 hover:border-brand-200 hover:bg-white/80"
          >
            <div
              aria-hidden
              className="absolute right-4 top-4 text-5xl font-bold leading-none text-brand-100/70 transition group-hover:text-brand-100"
            >
              0{idx + 1}
            </div>
            <div className="relative z-10">
              <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-brand-100 text-sm font-bold text-brand-700 transition group-hover:bg-brand-500 group-hover:text-white">
                0{idx + 1}
              </div>
              <p className="mt-5 text-xs font-semibold uppercase tracking-[0.16em] text-brand-700">
                {item.accent}
              </p>
              <h3 className="mt-2 text-xl font-bold text-foreground">{item.title}</h3>
              <p className="mt-2 text-sm leading-relaxed text-foreground-muted">{item.body}</p>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
