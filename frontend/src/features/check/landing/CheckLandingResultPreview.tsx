type PreviewRow = {
  level: 'fail' | 'warn';
  page: string;
  text: string;
  mod: string;
};

const PREVIEW_ROWS: PreviewRow[] = [
  {
    level: 'fail',
    page: 'Hal. 11',
    text: 'Margin tidak sesuai aturan PKM (kiri, kanan)',
    mod: 'Format Penulisan',
  },
  {
    level: 'fail',
    page: 'Hal. 4',
    text: 'Lampiran biodata dosen pembimbing belum ditemukan',
    mod: 'Lampiran',
  },
  {
    level: 'warn',
    page: 'Hal. 12',
    text: 'Ukuran huruf tidak 12 pt',
    mod: 'Format Penulisan',
  },
  {
    level: 'warn',
    page: '—',
    text: 'Urutan daftar pustaka belum alfabetis',
    mod: 'Daftar Pustaka',
  },
];

function PreviewRowItem({ row }: { row: PreviewRow }) {
  const isFail = row.level === 'fail';
  const rowCls = isFail ? 'border-red-100 bg-red-50/60' : 'border-amber-100 bg-amber-50/60';
  const dotCls = isFail ? 'bg-red-400' : 'bg-amber-400';
  const textCls = isFail ? 'text-red-900' : 'text-amber-900';
  const tagCls = isFail ? 'bg-red-100 text-red-700' : 'bg-amber-100 text-amber-700';
  const pageCls = isFail ? 'text-red-400' : 'text-amber-400';

  return (
    <div className={`flex items-start gap-3 rounded-xl border px-3.5 py-2.5 ${rowCls}`}>
      <span className={`mt-1.5 h-2 w-2 shrink-0 rounded-full ${dotCls}`} />
      <span className={`mt-0.5 w-14 shrink-0 font-mono text-xs font-medium ${pageCls}`}>
        {row.page}
      </span>
      <p className={`flex-1 text-sm font-medium leading-snug ${textCls}`}>{row.text}</p>
      <span className={`hidden shrink-0 rounded px-2 py-0.5 font-mono text-[10px] font-semibold sm:inline ${tagCls}`}>
        {row.mod}
      </span>
    </div>
  );
}

export function CheckLandingResultPreview() {
  return (
    <section id="preview" className="relative px-4 py-16 sm:px-6 sm:py-20">
      <div className="mx-auto max-w-5xl">
        <div className="mx-auto max-w-2xl text-center">
          <h2
            data-reveal
            data-reveal-delay="1"
            className="mt-3 font-display text-2xl font-bold leading-tight text-foreground sm:text-3xl"
          >
            Temuan yang jelas, langsung bisa ditindaklanjuti.
          </h2>
          <p
            data-reveal
            data-reveal-delay="2"
            className="mx-auto mt-3 max-w-xl text-sm leading-relaxed text-foreground-muted sm:text-base"
          >
            Setiap masalah dikelompokkan per bagian laporan dan ditandai lokasinya, lengkap dengan
            tingkat prioritas — mana yang wajib diperbaiki, mana yang sekadar perlu diperhatikan.
          </p>
        </div>

        <div
          data-reveal
          data-reveal-delay="3"
          className="check-landing-glass-card mx-auto mt-10 max-w-3xl overflow-hidden rounded-2xl"
        >
          {/* Window chrome */}
          <div className="flex items-center gap-3 border-b border-border bg-surface-sunken px-4 py-3">
            <div className="flex gap-1.5">
              <span className="h-3 w-3 rounded-full bg-red-300" />
              <span className="h-3 w-3 rounded-full bg-amber-300" />
              <span className="h-3 w-3 rounded-full bg-emerald-300" />
            </div>
            <span className="font-mono text-xs text-foreground-muted">Proposal-PKM-KC.docx</span>
            <span className="ml-auto inline-flex items-center gap-1.5 rounded-full bg-emerald-100 px-2.5 py-0.5 text-[11px] font-semibold text-emerald-700">
              <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" />
              Selesai dicek
            </span>
          </div>

          {/* Body */}
          <div className="space-y-4 p-5 sm:p-6">
            <div className="flex flex-wrap gap-2.5">
              <span className="rounded-lg border border-red-200 bg-red-50 px-3 py-1.5 text-sm font-semibold text-red-700">
                2 harus diperbaiki
              </span>
              <span className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-1.5 text-sm font-semibold text-amber-700">
                2 perlu diperhatikan
              </span>
            </div>

            <div className="space-y-2">
              {PREVIEW_ROWS.map((row, i) => (
                <PreviewRowItem key={i} row={row} />
              ))}
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
