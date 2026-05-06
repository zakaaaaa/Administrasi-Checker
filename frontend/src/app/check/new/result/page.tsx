'use client';

import { useState } from 'react';
import Link from 'next/link';
import jsPDF from 'jspdf';
import autoTable from 'jspdf-autotable';
import { CheckResultsView } from '@/features/check/CheckResultsView';
import type { CheckResults } from '@/features/check/types';

const LAST_RESULT_STORAGE_KEY = 'last_check_result_v1';

export default function CheckResultPage() {
  const [result] = useState<CheckResults | null>(() => {
    if (typeof window === 'undefined') return null;
    const raw = sessionStorage.getItem(LAST_RESULT_STORAGE_KEY);
    if (!raw) return null;
    try {
      return JSON.parse(raw) as CheckResults;
    } catch {
      return null;
    }
  });

  function exportPdf() {
    if (!result) return;

    const doc = new jsPDF({ unit: 'pt', format: 'a4' });
    const marginX = 40;
    let y = 48;

    const overallStatusLabel =
      result.overall_status === 'pass'
        ? 'LULUS'
        : result.overall_status === 'warning'
          ? 'PERLU DIPERHATIKAN'
          : 'BELUM LULUS';

    doc.setFont('helvetica', 'bold');
    doc.setFontSize(16);
    doc.text('Laporan Hasil Pengecekan PKM', marginX, y);
    y += 24;

    doc.setFont('helvetica', 'normal');
    doc.setFontSize(11);
    doc.text(`Submission ID: ${result.submission_id}`, marginX, y);
    y += 16;
    doc.text(`Status Keseluruhan: ${overallStatusLabel}`, marginX, y);
    y += 22;

    const modules = [
      { key: 'structure', label: 'Struktur Dokumen' },
      { key: 'physical_sheet', label: 'Jumlah Lembar Fisik' },
      { key: 'format', label: 'Format Penulisan' },
      { key: 'page_numbering', label: 'Penomoran Halaman' },
      { key: 'budget', label: 'Audit Anggaran' },
      { key: 'reference', label: 'Daftar Pustaka' },
    ] as const;

    modules.forEach(({ key, label }, moduleIndex) => {
      const mod = result.results[key] as { status?: string; messages?: { text: string }[] };
      const status = (mod?.status ?? 'unknown').toUpperCase();
      const messages = Array.isArray(mod?.messages) ? mod.messages : [];

      if (moduleIndex > 0) y += 10;
      doc.setFont('helvetica', 'bold');
      doc.setFontSize(12);
      doc.text(`${label} (${status})`, marginX, y);
      y += 8;

      const rows =
        messages.length > 0
          ? messages.map((m, i) => [String(i + 1), m.text.replace(/^\s*•\s*/, '').trim()])
          : [['1', 'Tidak ada catatan.']];

      autoTable(doc, {
        startY: y + 6,
        margin: { left: marginX, right: marginX },
        head: [['No', 'Catatan']],
        body: rows,
        styles: { fontSize: 10, cellPadding: 5, lineColor: [220, 220, 220], lineWidth: 0.5 },
        headStyles: { fillColor: [245, 245, 245], textColor: [40, 40, 40] },
      });

      y = (doc as jsPDF & { lastAutoTable?: { finalY: number } }).lastAutoTable?.finalY ?? y + 28;
    });

    const safeId = result.submission_id.replace(/[^a-zA-Z0-9-_]/g, '_');
    doc.save(`hasil-pengecekan-${safeId}.pdf`);
  }

  return (
    <main className="relative mx-auto max-w-6xl px-4 pb-20 pt-10 sm:px-6">
      <section className="glass-surface-elevated relative overflow-hidden rounded-[2rem] p-6 sm:p-10 print:hidden">
        <h1 className="max-w-4xl text-4xl font-semibold tracking-tight text-foreground sm:text-6xl">
          Output <span className="font-display text-gradient-brand">hasil pengecekan</span>
        </h1>
        <p className="mt-3 text-base text-foreground-muted">
          Halaman ini khusus untuk melihat hasil dan export PDF.
        </p>
      </section>

      <section className="mt-6 space-y-6">
        <div className="flex flex-wrap gap-3 print:hidden">
          <button
            type="button"
            onClick={exportPdf}
            disabled={!result}
            className="btn-liquid btn-liquid-primary px-5 py-3 text-base font-semibold disabled:opacity-50"
          >
            Export PDF
          </button>
          <Link href="/check/new" className="btn-liquid btn-liquid-ghost px-5 py-3 text-base">
            Kembali ke Beranda Input
          </Link>
        </div>

        {result ? (
          <CheckResultsView result={result} />
        ) : (
          <section className="rounded-2xl border border-amber-300 bg-amber-50 p-4 text-base font-semibold text-amber-800">
            Hasil belum tersedia. Silakan submit dokumen dulu dari halaman form.
          </section>
        )}
      </section>
    </main>
  );
}
