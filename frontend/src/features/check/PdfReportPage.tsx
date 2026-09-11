'use client';

import { useEffect, useSyncExternalStore } from 'react';
import { CheckResultReport, type CheckResultReportProps } from './CheckResultReport';
import { PDF_PRINT_STYLES } from './pdfPrintStyles';

declare global {
  interface Window {
    __CHECK_PDF_REPORT__?: Omit<CheckResultReportProps, 'exportMode'>;
  }
}

const subscribe = () => () => {};
const getSnapshot = () => window.__CHECK_PDF_REPORT__ ?? null;
const getServerSnapshot = () => null;

/** Used only by the local PDF renderer. No report data is stored in the URL. */
export function PdfReportPage() {
  const report = useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot);
  useEffect(() => {
    if (!report) return;
    let active = true;
    document.getElementById('print-report')?.getBoundingClientRect();
    void document.fonts.ready.then(() => {
      if (active) document.documentElement.dataset.pdfReady = 'true';
    });
    return () => { active = false; delete document.documentElement.dataset.pdfReady; };
  }, [report]);

  if (!report) return null;
  return (
    <>
      <style>{PDF_PRINT_STYLES}</style>
      <div id="print-report"><CheckResultReport {...report} exportMode /></div>
    </>
  );
}
