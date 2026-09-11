import type { Metadata } from 'next';
import { PdfReportPage } from '@/features/check/PdfReportPage';

export const metadata: Metadata = { robots: { index: false, follow: false } };

export default function Page() {
  return <PdfReportPage />;
}
