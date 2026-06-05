type IconName = 'clock' | 'shield' | 'pin' | 'download';

const BENEFITS: { icon: IconName; title: string; body: string }[] = [
  {
    icon: 'clock',
    title: 'Cukup HitunganMenit, bukan berjam-jam',
    body: 'Menyisir laporan manual bisa makan waktu seharian. Di sini seluruh temuan muncul sekaligus dalam hitungan menit.',
  },
  {
    icon: 'shield',
    title: 'Konsisten, tidak khilaf',
    body: 'Mata bisa lelah dan satu detail terlewat berujung gugur administrasi. Sistem memeriksa setiap komponen wajib dengan standar yang sama, setiap kali.',
  },
  {
    icon: 'pin',
    title: 'Langsung tahu letaknya',
    body: 'Tak perlu membandingkan dengan panduan halaman demi halaman — setiap temuan menunjuk halaman dan bagian persisnya.',
  },
  {
    icon: 'download',
    title: 'Ringkasan siap dibagikan',
    body: 'Unduh hasil pengecekan sebagai PDF untuk dibawa ke tim atau dosen pembimbing.',
  },
];

function BenefitIcon({ name }: { name: IconName }) {
  const common = {
    viewBox: '0 0 24 24',
    fill: 'none',
    stroke: 'currentColor',
    strokeWidth: 2,
    strokeLinecap: 'round' as const,
    strokeLinejoin: 'round' as const,
    className: 'h-5 w-5',
  };
  switch (name) {
    case 'clock':
      return (
        <svg {...common}>
          <circle cx="12" cy="12" r="9" />
          <polyline points="12 7 12 12 15 14" />
        </svg>
      );
    case 'shield':
      return (
        <svg {...common}>
          <path d="M12 3l7 3v5c0 4.5-3 8-7 9-4-1-7-4.5-7-9V6l7-3z" />
          <polyline points="9 12 11 14 15 10" />
        </svg>
      );
    case 'pin':
      return (
        <svg {...common}>
          <path d="M12 21s-6-5.3-6-10a6 6 0 1 1 12 0c0 4.7-6 10-6 10z" />
          <circle cx="12" cy="11" r="2" />
        </svg>
      );
    case 'download':
      return (
        <svg {...common}>
          <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
          <polyline points="7 10 12 15 17 10" />
          <line x1="12" y1="15" x2="12" y2="3" />
        </svg>
      );
  }
}

export function CheckLandingBenefits() {
  return (
    <section className="relative px-4 py-16 sm:px-6 sm:py-20">
      <div className="mx-auto max-w-5xl">
        <div className="mx-auto max-w-2xl text-center">
          <h2
            data-reveal
            className="font-display text-2xl font-bold leading-tight text-foreground sm:text-3xl"
          >
            Yang manual bikin lelah, yang otomatis bikin tenang.
          </h2>
          <p
            data-reveal
            data-reveal-delay="1"
            className="mx-auto mt-3 max-w-xl text-sm leading-relaxed text-foreground-muted sm:text-base"
          >
            Pekerjaan yang dulu menyita waktu, tenaga, dan fokus penuh — kini diambil alih sistem
            supaya kamu bisa fokus ke isi laporannya.
          </p>
        </div>

        <div className="mt-10 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {BENEFITS.map((item, i) => (
            <div
              key={item.title}
              data-reveal
              data-reveal-delay={`${(i % 4) + 1}` as '1' | '2' | '3' | '4'}
              className="rounded-2xl border border-border bg-surface-elevated p-5"
            >
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-brand-100 text-brand-700">
                <BenefitIcon name={item.icon} />
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
