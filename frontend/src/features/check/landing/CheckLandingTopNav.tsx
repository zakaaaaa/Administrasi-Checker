'use client';

const LOGO_URL =
  'https://wryvhzvzeuadzbpelbdz.supabase.co/storage/v1/object/public/web/logopkm.png';

type Props = {
  onStart: () => void;
};

export function CheckLandingTopNav({ onStart }: Props) {
  return (
    <header className="sticky top-0 z-30 border-b border-border bg-surface-elevated">
      <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-3 sm:px-6">
        <a href="#top" className="flex items-center gap-2.5">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={LOGO_URL} alt="PKM Checker" className="h-8 w-auto object-contain" />
        </a>

        <nav className="hidden items-center gap-7 md:flex">
          <a
            href="#preview"
            className="text-sm text-foreground-muted transition hover:text-foreground"
          >
            Hasil
          </a>
          <a
            href="#cakupan"
            className="text-sm text-foreground-muted transition hover:text-foreground"
          >
            Cakupan
          </a>
          <a
            href="#flow-section"
            className="text-sm text-foreground-muted transition hover:text-foreground"
          >
            Alur
          </a>
        </nav>

        <button
          type="button"
          onClick={onStart}
          className="btn-liquid btn-liquid-primary rounded-xl px-4 py-2 text-sm font-semibold text-white"
        >
          Mulai Pengecekan
        </button>
      </div>
    </header>
  );
}
