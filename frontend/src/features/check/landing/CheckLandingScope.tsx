const CHECK_SCOPES = [
  {
    title: 'Struktur laporan',
    body: 'Urutan bagian, kelengkapan bab, dan komponen wajib sesuai panduan.',
  },
  {
    title: 'Format & penomoran',
    body: 'Margin, ukuran huruf, penomoran halaman, dan tata letak naskah.',
  },
  {
    title: 'Anggaran (RAB)',
    body: 'Kesesuaian sumber dana Belmawa, perguruan tinggi, dan rekap biaya.',
  },
  {
    title: 'Daftar pustaka',
    body: 'Urutan alfabetis, kelengkapan sitasi, dan catatan yang perlu dirapikan.',
  },
  {
    title: 'Lampiran & biodata',
    body: 'Biodata, surat pendukung, tanda tangan, dan tanggal pada lampiran.',
  },
  {
    title: 'Luaran',
    body: 'Kelengkapan luaran wajib sesuai skema PKM yang dipilih.',
  },
  {
    title: 'Jadwal kegiatan',
    body: 'Format tabel jadwal, header kolom, dan rentang bulan kegiatan.',
  },
  {
    title: 'Similaritas',
    body: 'Indikasi kemiripan teks dan catatan sitasi yang perlu ditinjau.',
  },
];

function CheckMark() {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2.4"
      strokeLinecap="round"
      strokeLinejoin="round"
      className="h-4 w-4"
    >
      <polyline points="20 6 9 17 4 12" />
    </svg>
  );
}

export function CheckLandingScope() {
  return (
    <section id="cakupan" className="relative px-4 py-16 sm:px-6 sm:py-20">
      <div className="mx-auto max-w-5xl">
        <div className="mx-auto max-w-2xl text-center">
          <h2
            data-reveal
            data-reveal-delay="1"
            className="mt-3 font-display text-2xl font-bold leading-tight text-foreground sm:text-3xl"
          >
            Fokus pada hal yang paling sering membuat laporan direvisi.
          </h2>
        </div>

        <div className="mt-10 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {CHECK_SCOPES.map((item, i) => (
            <div
              key={item.title}
              data-reveal
              data-reveal-delay={`${(i % 4) + 1}` as '1' | '2' | '3' | '4'}
              className="rounded-2xl border border-border bg-surface-elevated p-5 transition hover:border-brand-300"
            >
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-brand-100 text-brand-700">
                <CheckMark />
              </div>
              <h3 className="mt-4 text-base font-semibold text-foreground">{item.title}</h3>
              <p className="mt-1.5 text-sm leading-relaxed text-foreground-muted">{item.body}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
