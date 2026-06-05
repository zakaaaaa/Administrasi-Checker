const LOGO_URL =
  'https://wryvhzvzeuadzbpelbdz.supabase.co/storage/v1/object/public/web/logopkm.png';

const WA_NUMBER_DISPLAY = '+62 896-5754-2643';
const WA_LINK = 'https://wa.me/6289657542643';
const IG_HANDLE = '@kelaspkm';
const IG_LINK = 'https://www.instagram.com/kelaspkm';

const NAV_LINKS = [
  { href: '#preview', label: 'Hasil' },
  { href: '#cakupan', label: 'Cakupan' },
  { href: '#flow-section', label: 'Alur' },
  { href: '#mulai', label: 'Mulai Pengecekan' },
];

function WhatsAppIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" className="h-4 w-4">
      <path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.71.306 1.263.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413z" />
    </svg>
  );
}

function InstagramIcon() {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      className="h-4 w-4"
    >
      <rect x="2" y="2" width="20" height="20" rx="5" ry="5" />
      <path d="M16 11.37A4 4 0 1 1 12.63 8 4 4 0 0 1 16 11.37z" />
      <line x1="17.5" y1="6.5" x2="17.51" y2="6.5" />
    </svg>
  );
}

export function CheckLandingFooter() {
  const year = new Date().getFullYear();
  return (
    <footer className="border-t border-border bg-surface-elevated">
      <div className="mx-auto max-w-6xl px-4 py-12 sm:px-6">
        <div className="grid gap-10 md:grid-cols-[1.5fr_1fr_1.2fr]">
          {/* Brand */}
          <div>
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={LOGO_URL} alt="Kelas PKM" className="h-8 w-auto object-contain" />
            <p className="mt-4 max-w-xs text-sm leading-relaxed text-foreground-muted">
              Pengecekan administrasi laporan PKM otomatis — lulus tahap administrasi sebelum
              dokumen di-submit.
            </p>
          </div>

          {/* Navigasi */}
          <div>
            <p className="text-xs font-semibold uppercase tracking-widest text-foreground-subtle">
              Navigasi
            </p>
            <ul className="mt-4 space-y-2.5 text-sm">
              {NAV_LINKS.map((link) => (
                <li key={link.href}>
                  <a
                    href={link.href}
                    className="text-foreground-muted transition hover:text-foreground"
                  >
                    {link.label}
                  </a>
                </li>
              ))}
            </ul>
          </div>

          {/* Kontak */}
          <div>
            <p className="text-xs font-semibold uppercase tracking-widest text-foreground-subtle">
              Hubungi kami
            </p>
            <ul className="mt-4 space-y-3 text-sm">
              <li>
                <a
                  href={WA_LINK}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="group inline-flex items-center gap-3 text-foreground-muted transition hover:text-foreground"
                >
                  <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl border border-border bg-surface-sunken text-brand-700 transition group-hover:border-brand-300">
                    <WhatsAppIcon />
                  </span>
                  {WA_NUMBER_DISPLAY}
                </a>
              </li>
              <li>
                <a
                  href={IG_LINK}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="group inline-flex items-center gap-3 text-foreground-muted transition hover:text-foreground"
                >
                  <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl border border-border bg-surface-sunken text-brand-700 transition group-hover:border-brand-300">
                    <InstagramIcon />
                  </span>
                  {IG_HANDLE}
                </a>
              </li>
            </ul>
          </div>
        </div>

        {/* Bottom bar */}
        <div className="mt-10 flex flex-col items-center justify-between gap-3 border-t border-border pt-6 sm:flex-row">
          <p className="text-xs text-foreground-subtle">
            © {year} Kelas PKM. Semua hak dilindungi.
          </p>
          <p className="text-xs text-foreground-subtle">
            PKM Checker — pengecekan administrasi laporan PKM
          </p>
        </div>
      </div>
    </footer>
  );
}
