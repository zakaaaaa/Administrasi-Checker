import type { Metadata, Viewport } from 'next';
import { Plus_Jakarta_Sans, Poppins } from 'next/font/google';
import { RootShellOrbs } from '@/components/layout/RootShellOrbs';
import '@/styles/globals.css';

// ----------------------------------------------------------------------------
// Fonts: pasangan display + body yang khas, bukan generic
// ----------------------------------------------------------------------------
const jakarta = Plus_Jakarta_Sans({
  subsets: ['latin'],
  variable: '--font-jakarta',
  display: 'swap',
  weight: ['300', '400', '500', '600', '700', '800'],
});

const poppins = Poppins({
  subsets: ['latin'],
  variable: '--font-poppins',
  display: 'swap',
  weight: ['400', '500', '600', '700', '800'],
});

// ----------------------------------------------------------------------------
// Metadata
// ----------------------------------------------------------------------------
export const metadata: Metadata = {
  title: {
    default: 'PKM Checker — Pengecekan Otomatis Laporan PKM',
    template: '%s · PKM Checker',
  },
  description:
    'Sistem otomatis pengecekan administrasi laporan PKM: struktur, format, RAB, daftar pustaka, dan biodata. Lulus tahap administrasi sebelum di-submit.',
  keywords: ['PKM', 'laporan', 'pengecekan', 'mahasiswa', 'kemahasiswaan'],
  authors: [{ name: 'Tim Kemahasiswaan' }],
};

export const viewport: Viewport = {
  width: 'device-width',
  initialScale: 1,
  maximumScale: 5,
  themeColor: '#f3fafe',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html
      lang="id"
      data-scroll-behavior="smooth"
      className={`${jakarta.variable} ${poppins.variable}`}
    >
      <body className="canvas-glass min-h-screen overflow-x-hidden font-sans text-base font-medium text-foreground antialiased">
        <RootShellOrbs />

        {children}
      </body>
    </html>
  );
}