import type { CheckResults } from './types';

type ReportMeta = { schemaLabel?: string; reportLabel?: string };

/** Download the server-rendered PDF; the report remains selectable text. */
export async function exportCheckResultPdf(
  result: CheckResults,
  sourceFileName?: string,
  meta: ReportMeta = {},
): Promise<void> {
  // Send only fields used by the shared report, omitting raw analysis artifacts.
  const reportResult = {
    submission_id: result.submission_id,
    status: result.status,
    overall_status: result.overall_status,
    results: Object.fromEntries(Object.entries(result.results).map(([key, mod]) => [key, mod && {
      status: mod.status, messages: mod.messages, message: mod.message,
      ...(key === 'structure' ? { schema: mod.schema } : {}),
    }])),
  };
  const response = await fetch('/export/pdf', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ result: reportResult, sourceFileName, ...meta }),
    signal: AbortSignal.timeout(60000),
  });
  if (!response.ok || !response.headers.get('content-type')?.includes('application/pdf')) {
    throw new Error('PDF gagal dibuat.');
  }
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  const rawName = (sourceFileName ?? result.submission_id).replace(/\.[^.]+$/, '');
  const safeName = rawName.replace(/[^a-zA-Z0-9-_]+/g, '_').replace(/^_+|_+$/g, '') || 'dokumen';
  link.href = url;
  link.download = `hasil-pengecekan-${safeName}.pdf`;
  document.body.append(link);
  try {
    link.click();
  } finally {
    link.remove();
    // Allow the browser to start consuming the download before releasing it.
    setTimeout(() => URL.revokeObjectURL(url), 60000);
  }
}
