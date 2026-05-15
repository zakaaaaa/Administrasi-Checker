const FLOW_STEPS = [
  'Input token',
  'Pilih jenis laporan (Proposal aktif)',
  'Pilih skema PKM',
  'Pilih lomba (PKM aktif)',
  'Input dana (Belmawa + PT)',
  'Upload laporan',
  'Submit / Proses',
];

export function CheckLandingFlowSection() {
  return (
    <div data-reveal className="check-landing-glass-card rounded-[1.75rem] p-6 sm:p-8">
      <div className="flex items-center gap-2">
        <span className="h-1.5 w-8 rounded-full bg-brand-500" />
        <p className="font-mono text-sm uppercase tracking-[0.2em] text-foreground-subtle">
          Alur Pengisian
        </p>
      </div>
      <div className="mt-5 grid gap-3 sm:grid-cols-2">
        {FLOW_STEPS.map((item, idx) => (
          <div
            key={item}
            className="group flex items-center gap-3 rounded-2xl border border-white/60 bg-white/50 p-4 backdrop-blur-md transition hover:border-orange-200 hover:bg-white/80"
          >
            <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-brand-100 text-sm font-bold text-brand-600 transition group-hover:bg-brand-500 group-hover:text-white">
              {idx + 1}
            </div>
            <p className="text-base font-semibold text-foreground">{item}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
