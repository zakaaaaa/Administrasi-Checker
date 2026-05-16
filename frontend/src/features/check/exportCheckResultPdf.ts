import jsPDF from 'jspdf';
import autoTable from 'jspdf-autotable';
import type { CheckResults, ModuleKey } from './types';

const MODULE_LABELS: Record<ModuleKey, string> = {
  structure: 'Struktur Dokumen',
  physical_sheet: 'Jumlah Lembar Fisik',
  format: 'Format Penulisan',
  page_numbering: 'Penomoran Halaman',
  budget: 'Audit Anggaran',
  reference: 'Daftar Pustaka',
  ai_content: 'Konten Artikel Ilmiah',
  ai_format: 'Format Khusus PKM-AI',
};

const MODULE_ORDER: ModuleKey[] = [
  'structure',
  'physical_sheet',
  'format',
  'ai_format',
  'page_numbering',
  'ai_content',
  'budget',
  'reference',
];

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

  const modules = MODULE_ORDER.filter((key) => result.results[key] !== undefined).map(
    (key) => ({ key, label: MODULE_LABELS[key] }),
  );

  modules.forEach(({ key, label }, moduleIndex) => {
    const mod = result.results[key] as
      | { status?: string; messages?: { text: string }[] }
      | undefined;
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
