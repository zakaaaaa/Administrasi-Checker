import { SKEMA_OPTIONS } from '../form/checkFormConstants';

type Faq = { q: string; a: string; showSchemes?: boolean };

const FAQS: Faq[] = [
  {
    q: 'Skema PKM apa saja yang didukung?',
    a: 'PKM Checker mendukung seluruh skema PKM. Aturan pemeriksaan menyesuaikan otomatis dengan skema yang kamu pilih:',
    showSchemes: true,
  },
  {
    q: 'File apa yang bisa diunggah?',
    a: 'Dokumen Word berformat .docx. Sistem membaca struktur, format, dan lampiran langsung dari dokumen tersebut.',
  },
  {
    q: 'Berapa lama prosesnya?',
    a: 'Umumnya beberapa menit, tergantung panjang dokumen dan kebutuhan pembacaan gambar (OCR) pada lampiran seperti biodata dan tanda tangan.',
  },
  {
    q: 'Dari mana saya mendapatkan token?',
    a: 'Token diterbitkan oleh admin kelaspkm. Token inilah yang membuka sesi input pengecekan.',
  },
  {
    q: 'Apakah dokumen saya aman?',
    a: 'Dokumen hanya diproses untuk keperluan pengecekan dan terhubung ke riwayat unggahan pada token-mu.',
  },
];

export function CheckLandingFaq() {
  return (
    <section className="relative px-4 py-16 sm:px-6 sm:py-20">
      <div className="mx-auto max-w-3xl">
        <h2
          data-reveal
          className="text-center font-display text-2xl font-bold leading-tight text-foreground sm:text-3xl"
        >
          Pertanyaan yang sering muncul
        </h2>

        <div className="mt-8 space-y-3">
          {FAQS.map((f, i) => (
            <details
              key={i}
              data-reveal
              className="group rounded-2xl border border-border bg-surface-elevated p-5 transition hover:border-brand-300"
            >
              <summary className="flex cursor-pointer list-none items-center justify-between gap-4 text-base font-semibold text-foreground [&::-webkit-details-marker]:hidden">
                {f.q}
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2.5"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  className="h-4 w-4 shrink-0 text-brand-500 transition-transform duration-200 group-open:rotate-180"
                >
                  <polyline points="6 9 12 15 18 9" />
                </svg>
              </summary>
              <p className="mt-3 text-sm leading-relaxed text-foreground-muted">{f.a}</p>

              {f.showSchemes && (
                <div className="mt-4 flex flex-wrap gap-2">
                  {SKEMA_OPTIONS.map((s) => (
                    <span
                      key={s.value}
                      className="inline-flex items-center gap-1.5 rounded-lg border border-border bg-surface-sunken px-2.5 py-1 text-xs"
                    >
                      <span className="font-semibold text-foreground">{s.label}</span>
                      <span className="text-foreground-subtle">{s.desc}</span>
                    </span>
                  ))}
                </div>
              )}
            </details>
          ))}
        </div>
      </div>
    </section>
  );
}
