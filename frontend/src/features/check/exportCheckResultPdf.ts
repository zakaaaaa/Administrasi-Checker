import jsPDF from 'jspdf';
import autoTable from 'jspdf-autotable';
import type { CheckResults } from './types';

const MODULES = [
  { key: 'structure', label: 'Struktur Dokumen' },
  { key: 'physical_sheet', label: 'Jumlah Lembar Fisik' },
  { key: 'format', label: 'Format Penulisan' },
  { key: 'page_numbering', label: 'Penomoran Halaman' },
  { key: 'budget', label: 'Audit Anggaran' },
  { key: 'reference', label: 'Daftar Pustaka' },
  { key: 'schedule', label: 'Jadwal Kegiatan' },
  { key: 'similarity', label: 'Similaritas' },
] as const;

export function exportCheckResultPdf(result: CheckResults) {
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

  MODULES.forEach(({ key, label }, moduleIndex) => {
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
